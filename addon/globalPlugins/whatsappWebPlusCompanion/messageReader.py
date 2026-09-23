"""Validated message and shortcut snapshots for native NVDA readers."""

import html
import inspect
import json
import re
from urllib.parse import urlsplit

MAX_READER_UNITS = 131072
_LANGUAGE = re.compile(r"^[a-z]{2,3}(?:-[a-z0-9]{2,8})*$", re.I)
_PROTOCOLS = {"http", "https", "mailto", "tel"}
_LABELS = ("title", "heading", "sentAt", "sentAtLabel", "timeUnavailable", "message")


def validateReader(value: object) -> dict | None:
	if not isinstance(value, dict) or type(value.get("version")) is not int or value["version"] != 1:
		return None
	if value.get("status") not in ("ready", "error"):
		return None
	if any(not isinstance(value.get(key), str) or len(value[key]) > 512 for key in _LABELS):
		return None
	if not value["title"] or not value["heading"]:
		return None
	if value.get("kind", "message") not in ("message", "shortcuts"):
		return None
	runs = value.get("runs")
	if not isinstance(runs, list) or len(runs) > 4096:
		return None
	if value["status"] == "error" and (runs or not value["message"]):
		return None
	if value["status"] == "ready" and (not runs or value["message"]):
		return None
	try:
		encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
		if len(encoded.encode("utf-16-le")) // 2 > MAX_READER_UNITS:
			return None
	except (TypeError, ValueError, UnicodeError, RecursionError):
		return None
	stack = []
	normalized = []
	for run in runs:
		if not isinstance(run, dict):
			return None
		kind = run.get("type")
		if stack and stack[-1] == "list" and kind not in ("listItemStart", "listEnd"):
			return None
		if kind == "heading":
			if (
				value.get("kind") != "shortcuts"
				or stack
				or type(run.get("level")) is not int
				or run["level"] not in (1, 2)
			):
				return None
			if not isinstance(run.get("text"), str) or not run["text"] or len(run["text"]) > 512:
				return None
			item = {"type": kind, "text": run["text"], "level": run["level"]}
		elif kind in ("text", "link"):
			if not isinstance(run.get("text"), str):
				return None
			item = {"type": kind, "text": run["text"]}
			if kind == "link":
				href = run.get("href")
				if not isinstance(href, str) or not href or len(href) > 8192:
					return None
				try:
					if urlsplit(href).scheme.lower() not in _PROTOCOLS or any(ord(c) < 32 for c in href):
						return None
				except ValueError:
					return None
				item["href"] = href
		elif kind == "listStart":
			if type(run.get("ordered")) is not bool or len(stack) >= 32:
				return None
			stack.append("list")
			item = {"type": kind, "ordered": run["ordered"]}
		elif kind == "listItemStart":
			if not stack or stack[-1] != "list" or len(stack) >= 32:
				return None
			stack.append("item")
			item = {"type": kind}
		elif kind in ("listEnd", "listItemEnd"):
			if not stack or stack.pop() != ("list" if kind == "listEnd" else "item"):
				return None
			item = {"type": kind}
		elif kind == "break":
			item = {"type": kind}
		else:
			return None
		normalized.append(item)
	if stack:
		return None
	return {
		**({"kind": "shortcuts"} if value.get("kind") == "shortcuts" else {}),
		"version": 1,
		"status": value["status"],
		**{key: value[key] for key in _LABELS},
		"runs": normalized,
	}


def renderReader(reader: dict, language: str = "") -> str:
	"""Render message content or a shortcut reference as escaped HTML.

	Keep authored lines in compact blocks rather than BR-delimited inline text.
	Empty authored lines still need a BR to occupy a line in the HTML viewer.
	"""

	def text(value):
		return html.escape(value).replace("\r\n", "\n").replace("\r", "\n")

	lang = language if _LANGUAGE.fullmatch(language) else "en"
	parts = [f'<main lang="{html.escape(lang, quote=True)}" dir="auto"><article dir="auto">']
	line: list[str] = []
	pendingLine = False

	def flushLine(force=False):
		nonlocal pendingLine
		if line or force:
			parts.append("<div>" + ("".join(line) if line else "<br>") + "</div>")
		line.clear()
		pendingLine = False

	def appendText(value):
		nonlocal pendingLine
		segments = text(value).split("\n")
		for index, segment in enumerate(segments):
			if index:
				flushLine(force=True)
				pendingLine = True
			if segment:
				line.append(segment)
				pendingLine = False

	lists = []
	runs = reader["runs"] if reader["status"] == "ready" else [{"type": "text", "text": reader["message"]}]
	for run in runs:
		kind = run["type"]
		if kind == "heading":
			flushLine()
			level = run["level"]
			parts.append(f"<h{level}>{text(run['text'])}</h{level}>")
		elif kind == "text":
			appendText(run["text"])
		elif kind == "link":
			# A multiline link remains one keyboard stop, rather than being split
			# into separate anchors at each authored line.
			label = text(run["text"] or run["href"]).replace("\n", "<br>")
			line.append(f'<a href="{html.escape(run["href"], quote=True)}">{label}</a>')
			pendingLine = False
		elif kind == "break":
			flushLine(force=True)
			pendingLine = True
		elif kind == "listStart":
			flushLine()
			tag = "ol" if run["ordered"] else "ul"
			lists.append(tag)
			parts.append(f"<{tag}>")
		elif kind == "listEnd":
			flushLine()
			parts.append(f"</{lists.pop()}>")
		elif kind == "listItemStart":
			flushLine()
			parts.append("<li>")
		elif kind == "listItemEnd":
			flushLine(force=pendingLine)
			parts.append("</li>")
	flushLine(force=pendingLine)
	parts.append("</article></main>")
	return "".join(parts)


def isReaderForeground(processIds: object) -> bool:
	if not isinstance(processIds, (tuple, list)) or not processIds:
		return False
	try:
		import api

		pid = api.getForegroundObject().processID
		return type(pid) is int and pid > 0 and pid in processIds
	except (ImportError, AttributeError, RuntimeError, OSError):
		return False


def readerPlainText(reader: dict) -> str:
	"""Serialize authored lines independently of browser width or rich clipboard formats."""
	if reader["status"] == "error":
		return reader["message"]
	parts: list[str] = []
	lists: list[dict] = []

	def append(value: str) -> None:
		if value:
			parts.append(value.replace("\r\n", "\n").replace("\r", "\n"))

	def boundary() -> None:
		if parts and not parts[-1].endswith("\n"):
			parts.append("\n")

	for run in reader["runs"]:
		kind = run["type"]
		if kind == "heading":
			boundary()
			append(run["text"])
			boundary()
		elif kind == "text":
			append(run["text"])
		elif kind == "link":
			label = run["text"] or run["href"]
			append(label)
			if label != run["href"]:
				append(f" ({run['href']})")
		elif kind == "break":
			parts.append("\n")
		elif kind == "listStart":
			boundary()
			lists.append({"ordered": run["ordered"], "next": 1})
		elif kind == "listItemStart":
			boundary()
			item = lists[-1]
			marker = f"{item['next']}. " if item["ordered"] else "- "
			append("  " * (len(lists) - 1) + marker)
			item["next"] += 1
		elif kind == "listItemEnd":
			boundary()
		elif kind == "listEnd":
			lists.pop()
	return "".join(parts)


def showFormattedReader(reader: dict, language: str = "") -> None:
	import ui

	options = {"isHtml": True}
	# Older supported NVDA releases have fewer keyword parameters. Inspect once
	# before opening; retrying after a TypeError could open a duplicate window.
	try:
		parameters = inspect.signature(ui.browseableMessage).parameters
		for name in ("closeButton", "copyButton"):
			if name in parameters:
				options[name] = True
	except (TypeError, ValueError):
		pass
	ui.browseableMessage(renderReader(reader, language), title=reader["title"], **options)


def showReader(reader: dict, language: str = "") -> None:
	"""Use native text navigation for authored lines; keep HTML available on request."""
	if reader.get("kind") == "shortcuts":
		showFormattedReader(reader, language)
		return

	import api
	import gui
	import ui
	import wx

	from . import _

	body = readerPlainText(reader)
	dialog = wx.Dialog(gui.mainFrame, title=reader["title"], style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
	layout = wx.BoxSizer(wx.VERTICAL)
	# A preceding static label gives the native edit control its accessible name.
	layout.Add(wx.StaticText(dialog, label=reader["heading"]), 0, wx.ALL, 10)
	textControl = wx.TextCtrl(
		dialog,
		value=body,
		style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_DONTWRAP,
	)
	layout.Add(textControl, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
	if reader["status"] == "ready":
		timestamp = (
			f"{reader['sentAtLabel']} {reader['sentAt']}" if reader["sentAt"] else reader["timeUnavailable"]
		)
		layout.Add(wx.StaticText(dialog, label=timestamp), 0, wx.ALL, 10)
	buttons = wx.BoxSizer(wx.HORIZONTAL)
	# Translators: Copies only the message body, without the reader heading or sent time.
	copyButton = wx.Button(dialog, label=_("&Copy message"))
	# Translators: Opens the formatted message with clickable links and structured lists.
	formattedButton = wx.Button(dialog, label=_("&Formatted view"))
	# Translators: Closes the message reader window.
	closeButton = wx.Button(dialog, wx.ID_CANCEL, label=_("C&lose"))
	for button in (copyButton, formattedButton, closeButton):
		buttons.Add(button, 0, wx.RIGHT, 8)
	layout.Add(buttons, 0, wx.ALL, 10)
	dialog.SetSizer(layout)
	dialog.SetSize(dialog.FromDIP((760, 520)))
	dialog.SetMinSize(dialog.FromDIP((360, 260)))

	def copyMessage(event) -> None:
		try:
			copied = api.copyToClip(body)
		except Exception:
			copied = False
		# Translators: Short result of copying the message body from the reader.
		ui.message(_("Message copied.") if copied else _("Could not copy the message."))

	def close(event) -> None:
		dialog.Destroy()

	copyButton.Bind(wx.EVT_BUTTON, copyMessage)
	formattedButton.Bind(wx.EVT_BUTTON, lambda event: showFormattedReader(reader, language))
	closeButton.Bind(wx.EVT_BUTTON, close)
	dialog.Bind(wx.EVT_CLOSE, close)
	dialog.SetEscapeId(wx.ID_CANCEL)
	gui.mainFrame.prePopup()
	try:
		dialog.Show()
		textControl.SetInsertionPoint(0)
		textControl.SetFocus()
	finally:
		gui.mainFrame.postPopup()
