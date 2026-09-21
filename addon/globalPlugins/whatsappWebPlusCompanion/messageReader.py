"""Validated message snapshots rendered by NVDA's built-in browseable window."""

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
		if kind in ("text", "link"):
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
		"version": 1,
		"status": value["status"],
		**{key: value[key] for key in _LABELS},
		"runs": normalized,
	}


def renderReader(reader: dict, language: str = "") -> str:
	def text(value):
		return html.escape(value).replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br>")

	lang = language if _LANGUAGE.fullmatch(language) else "en"
	parts = [f'<main lang="{html.escape(lang, quote=True)}" dir="auto"><h1>{text(reader["heading"])}</h1>']
	if reader["status"] == "error":
		return "".join(parts) + f"<p>{text(reader['message'])}</p></main>"
	parts.append('<article dir="auto">')
	lists = []
	for run in reader["runs"]:
		kind = run["type"]
		if kind == "text":
			parts.append(text(run["text"]))
		elif kind == "link":
			parts.append(
				f'<a href="{html.escape(run["href"], quote=True)}">{text(run["text"] or run["href"])}</a>'
			)
		elif kind == "break":
			parts.append("<br>")
		elif kind == "listStart":
			tag = "ol" if run["ordered"] else "ul"
			lists.append(tag)
			parts.append(f"<{tag}>")
		elif kind == "listEnd":
			parts.append(f"</{lists.pop()}>")
		elif kind == "listItemStart":
			parts.append("<li>")
		elif kind == "listItemEnd":
			parts.append("</li>")
	timestamp = (
		f"{reader['sentAtLabel']} {reader['sentAt']}" if reader["sentAt"] else reader["timeUnavailable"]
	)
	parts.append(f"</article><p>{text(timestamp)}</p></main>")
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


def showReader(reader: dict, language: str = "") -> None:
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
