import copy
import sys
import time
import types
import unittest
from unittest.mock import MagicMock, patch

from _path import installPackagePath

installPackagePath()
from globalPlugins.whatsappWebPlusCompanion import cdp, launcher, messageReader, security
from globalPlugins.whatsappWebPlusCompanion.models import OperationResult


def payload(text="Complete reply", **updates):
	value = {
		"version": 1,
		"status": "ready",
		"title": "Message - WhatsApp Companion",
		"heading": "Message",
		"sentAt": "12:34",
		"sentAtLabel": "Sent:",
		"timeUnavailable": "Sent time unavailable.",
		"message": "",
		"runs": [{"type": "text", "text": text}],
	}
	value.update(updates)
	return value


def envelope(reader):
	return {
		"contractVersion": 2,
		"sessionToken": "s",
		"generation": 1,
		"context": "c",
		"latestSequence": 1,
		"entries": [
			{
				"sequence": 1,
				"generation": 1,
				"sessionToken": "s",
				"context": "c",
				"source": "message-reader",
				"privacy": False,
				"language": "id",
				"text": "",
				"reader": reader,
				"readerExpiresAt": int(time.time() * 1000) + 10000,
			},
		],
	}


class ReaderPayloadTests(unittest.TestCase):
	def test_list_containers_require_list_items(self):
		for child in [
			{"type": "text", "text": "outside item"},
			{"type": "link", "text": "link", "href": "https://example.com"},
			{"type": "break"},
			{"type": "listStart", "ordered": False},
		]:
			with self.subTest(child=child):
				runs = [{"type": "listStart", "ordered": False}, child]
				if child["type"] == "listStart":
					runs.append({"type": "listEnd"})
				runs.append({"type": "listEnd"})
				self.assertIsNone(messageReader.validateReader(payload(runs=runs)))
		runs = [
			{"type": "listStart", "ordered": False},
			{"type": "listItemStart"},
			{"type": "listStart", "ordered": True},
			{"type": "listItemStart"},
			{"type": "text", "text": "nested item"},
			{"type": "listItemEnd"},
			{"type": "listEnd"},
			{"type": "listItemEnd"},
			{"type": "listEnd"},
		]
		self.assertIsNotNone(messageReader.validateReader(payload(runs=runs)))

	def test_shortcut_headings_use_native_formatted_reader(self):
		value = payload(
			kind="shortcuts",
			runs=[
				{"type": "heading", "level": 1, "text": "Shortcut list"},
				{"type": "heading", "level": 2, "text": "Navigation <safe>"},
				{"type": "text", "text": "Alt+1: Chat list"},
			],
		)
		reader = messageReader.validateReader(value)
		self.assertIsNotNone(reader)
		self.assertIn("<h2>Navigation &lt;safe&gt;</h2>", messageReader.renderReader(reader))
		with patch.object(messageReader, "showFormattedReader") as show:
			messageReader.showReader(reader, "id")
			show.assert_called_once_with(reader, "id")
		value["runs"][0]["level"] = 99
		self.assertIsNone(messageReader.validateReader(value))
		value["runs"][0]["level"] = 1
		value.pop("kind")
		self.assertIsNone(messageReader.validateReader(value))

	def test_expired_reader_is_not_replayed_after_reconnect(self):
		value = envelope(payload())
		value["entries"][0]["readerExpiresAt"] = int(time.time() * 1000) - 1
		session = MagicMock()
		session.request.return_value = {"result": {"value": value}}
		self.assertEqual(cdp.readCompanionAnnouncements(session).entries, ())

	def test_long_message_survives_bridge_parser_and_renderer(self):
		text = "Full text " * 1000
		session = MagicMock()
		session.request.return_value = {"result": {"value": envelope(payload(text))}}
		batch = cdp.readCompanionAnnouncements(session)
		self.assertEqual(len(batch.entries), 1)
		self.assertEqual(batch.entries[0].reader["runs"][0]["text"], text)
		self.assertIn(text, messageReader.renderReader(batch.entries[0].reader, "id"))

	def test_html_is_escaped_and_structure_preserved(self):
		reader = payload("<script>alert('x')</script>\nNext line")
		reader["runs"] += [
			{"type": "listStart", "ordered": False},
			{"type": "listItemStart"},
			{"type": "link", "text": "<Documentation>", "href": 'https://example.com/?q="&a=1'},
			{"type": "listItemEnd"},
			{"type": "listEnd"},
		]
		validated = messageReader.validateReader(reader)
		self.assertIsNotNone(validated)
		rendered = messageReader.renderReader(validated, "id")
		self.assertNotIn("<script>", rendered)
		self.assertIn("&lt;script&gt;", rendered)
		self.assertIn("</div><div>Next line</div>", rendered)
		self.assertIn('<ul><li><div><a href="https://example.com/?q=&quot;&amp;a=1">', rendered)
		self.assertIn("&lt;Documentation&gt;</a></div></li></ul>", rendered)
		self.assertIn('lang="id"', rendered)
		self.assertNotIn("Sent: 12:34", rendered)
		self.assertNotIn("<h1>", rendered)

	def test_formatted_lines_preserve_only_authored_blank_lines(self):
		for body, expected in (
			("First\nSecond", "<div>First</div><div>Second</div>"),
			("First\n\nSecond", "<div>First</div><div><br></div><div>Second</div>"),
			("\nFirst\n", "<div><br></div><div>First</div><div><br></div>"),
		):
			with self.subTest(body=body):
				html = messageReader.renderReader(payload(body))
				self.assertEqual(
					html,
					'<main lang="en" dir="auto"><article dir="auto">' + expected + "</article></main>",
				)

	def test_formatted_inline_links_and_break_runs_do_not_add_blank_lines(self):
		reader = payload(
			runs=[
				{"type": "text", "text": "Read "},
				{"type": "link", "text": "guide", "href": "https://example.com"},
				{"type": "text", "text": " now"},
				{"type": "break"},
				{"type": "text", "text": "Next"},
			],
		)
		html = messageReader.renderReader(reader)
		self.assertIn('<div>Read <a href="https://example.com">guide</a> now</div><div>Next</div>', html)
		self.assertNotIn("<br>", html)
		self.assertNotIn(reader["heading"], html)
		self.assertNotIn(reader["sentAt"], html)

	def test_formatted_multiline_link_keeps_single_keyboard_stop(self):
		reader = payload(runs=[{"type": "link", "text": "First\nSecond", "href": "https://example.com"}])
		html = messageReader.renderReader(reader)
		self.assertEqual(html.count("<a "), 1)
		self.assertIn("First<br>Second</a>", html)

	def test_invalid_or_oversized_payload_is_rejected(self):
		invalid = [
			None,
			{},
			payload("x" * 140000),
			payload(version=True),
			payload(title="x" * 513),
			payload(runs=[{"type": "link", "text": "unsafe", "href": "javascript:alert(1)"}]),
			payload(runs=[{"type": "listItemStart"}]),
			payload(runs=[{"type": "listEnd"}]),
			payload(runs=[{"type": "img", "src": "file:///x"}]),
			payload(runs=[]),
		]
		for value in invalid:
			with self.subTest(value=str(value)[:80]):
				self.assertIsNone(messageReader.validateReader(value))

	def test_error_payload_is_a_single_message(self):
		reader = messageReader.validateReader(
			payload(status="error", runs=[], message="Cannot load complete message"),
		)
		self.assertIsNotNone(reader)
		self.assertIn("Cannot load complete message", messageReader.renderReader(reader))

	def test_foreground_is_verified_without_process_or_network_work(self):
		fakeApi = types.SimpleNamespace(getForegroundObject=lambda: types.SimpleNamespace(processID=42))
		with patch.dict(sys.modules, {"api": fakeApi}):
			self.assertTrue(messageReader.isReaderForeground((42, 43)))
			self.assertFalse(messageReader.isReaderForeground((43,)))
			self.assertFalse(messageReader.isReaderForeground(()))

	def test_native_window_uses_supported_buttons_without_retry(self):
		calls = []

		def modern(message, title=None, isHtml=False, closeButton=False, copyButton=False):
			calls.append((message, title, isHtml, closeButton, copyButton))

		with patch.dict(sys.modules, {"ui": types.SimpleNamespace(browseableMessage=modern)}):
			messageReader.showFormattedReader(payload())
		self.assertEqual(len(calls), 1)
		self.assertEqual(calls[0][2:], (True, True, True))

		def legacy(message, title=None, isHtml=False):
			calls.append((message, title, isHtml))

		with patch.dict(sys.modules, {"ui": types.SimpleNamespace(browseableMessage=legacy)}):
			messageReader.showFormattedReader(payload())
		self.assertEqual(len(calls), 2)

	def test_forward_reader_uses_distinct_ui_result(self):
		session = MagicMock()
		session.readerProcessIds = (42,)
		session.request.return_value = {"result": {"value": envelope(payload())}}
		reports = []

		def report(value):
			reports.append(value)
			return True

		launcher._forwardCompanionAnnouncements(session, launcher._AnnouncementState(), report)
		self.assertEqual([item.messageKey for item in reports], ["companion.invalidate", "companion.reader"])
		self.assertEqual(reports[-1].values["readerProcessIds"], (42,))


class PlainReaderTests(unittest.TestCase):
	def test_authored_lines_and_literal_characters_are_preserved(self):
		body = "# literal heading\r\nWords  with spaces\n\nBackslash: \\ end\n" + "long " * 200
		self.assertEqual(messageReader.readerPlainText(payload(body)), body.replace("\r\n", "\n"))
		self.assertEqual(
			messageReader.readerPlainText(payload(status="error", runs=[], message="Error")),
			"Error",
		)

	def test_links_and_nested_lists_are_readable_without_markdown_links(self):
		reader = payload(
			runs=[
				{"type": "link", "text": "https://example.com", "href": "https://example.com"},
				{"type": "break"},
				{"type": "link", "text": "Guide", "href": "https://example.com/guide"},
				{"type": "listStart", "ordered": True},
				{"type": "listItemStart"},
				{"type": "text", "text": "First"},
				{"type": "listStart", "ordered": False},
				{"type": "listItemStart"},
				{"type": "text", "text": "Nested"},
				{"type": "listItemEnd"},
				{"type": "listEnd"},
				{"type": "listItemEnd"},
				{"type": "listItemStart"},
				{"type": "text", "text": "Second"},
				{"type": "listItemEnd"},
				{"type": "listEnd"},
			],
		)
		self.assertEqual(
			messageReader.readerPlainText(reader),
			"https://example.com\nGuide (https://example.com/guide)\n1. First\n  - Nested\n2. Second\n",
		)

	def test_native_plain_reader_copy_focus_and_formatted_action(self):
		buttons = []
		dialog = MagicMock()
		textControl = MagicMock()

		def makeButton(*args, **kwargs):
			button = MagicMock()
			button.Bind.side_effect = lambda event, handler: setattr(button, "activate", handler)
			buttons.append(button)
			return button

		wx = types.SimpleNamespace(
			Dialog=MagicMock(return_value=dialog),
			TextCtrl=MagicMock(return_value=textControl),
			StaticText=MagicMock(),
			BoxSizer=MagicMock(),
			Button=makeButton,
			DEFAULT_DIALOG_STYLE=1,
			RESIZE_BORDER=2,
			VERTICAL=4,
			HORIZONTAL=8,
			ALL=16,
			TE_MULTILINE=32,
			TE_READONLY=64,
			TE_DONTWRAP=128,
			EXPAND=256,
			LEFT=512,
			RIGHT=1024,
			ID_CANCEL=2,
			EVT_BUTTON="button",
			EVT_CLOSE="close",
		)
		api = types.SimpleNamespace(copyToClip=MagicMock(return_value=True))
		ui = types.SimpleNamespace(message=MagicMock())
		gui = types.SimpleNamespace(mainFrame=MagicMock())
		package = sys.modules["globalPlugins.whatsappWebPlusCompanion"]
		reader = payload("First\nSecond\n\nThird  line\\")
		with (
			patch.dict(sys.modules, {"wx": wx, "api": api, "ui": ui, "gui": gui}),
			patch.object(package, "_", lambda value: value, create=True),
			patch.object(messageReader, "showFormattedReader") as formatted,
		):
			messageReader.showReader(reader, "id")
			self.assertEqual(wx.TextCtrl.call_args.kwargs["value"], reader["runs"][0]["text"])
			self.assertEqual(wx.TextCtrl.call_args.kwargs["style"], 32 | 64 | 128)
			textControl.SetInsertionPoint.assert_called_once_with(0)
			textControl.SetFocus.assert_called_once_with()
			dialog.SetEscapeId.assert_called_once_with(wx.ID_CANCEL)
			buttons[0].activate(None)
			api.copyToClip.assert_called_once_with(reader["runs"][0]["text"])
			ui.message.assert_called_with("Message copied.")
			api.copyToClip.return_value = False
			buttons[0].activate(None)
			ui.message.assert_called_with("Could not copy the message.")
			buttons[1].activate(None)
			formatted.assert_called_once_with(reader, "id")
			buttons[2].activate(None)
			dialog.Destroy.assert_called_once_with()


class ReaderDeliveryTests(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		from test_plugin_ui_flow import _installFakeEnvironment

		_installFakeEnvironment()

	def setUp(self):
		self.module = sys.modules["globalPlugins.whatsappWebPlusCompanion"]
		self.plugin = self.module.GlobalPlugin()
		self.plugin._announcementGuard = security.AnnouncementGuard(lambda: True)
		self.plugin._brailleMessages = MagicMock()
		self.plugin._companionSession = "s"
		self.plugin._companionGeneration = 1
		self.plugin._companionContext = "c"
		self.result = OperationResult(
			True,
			"companion.reader",
			"companion.reader",
			{
				"session": "s",
				"generation": 1,
				"context": "c",
				"sequence": 1,
				"reader": payload(),
				"source": "message-reader",
				"language": "en",
				"privacy": False,
				"readerProcessIds": (42,),
				"readerExpiresAt": int(time.time() * 1000) + 10000,
				"securityEpoch": self.plugin._announcementGuard.snapshot()[1],
			},
		)

	def tearDown(self):
		self.plugin.terminate()

	def test_dialog_opens_once_and_does_not_announce_body(self):
		with (
			patch.object(self.module, "isReaderForeground", return_value=True),
			patch.object(self.module, "showReader") as show,
			patch.object(self.module.speech, "speak") as speak,
		):
			for _ in range(2):
				self.assertTrue(self.plugin._reportIfCurrent(self.plugin._generation, self.result))
			show.assert_called_once()
			speak.assert_not_called()
		self.plugin._brailleMessages.clearPending.assert_called_once_with(silent=True)
		self.plugin._brailleMessages.enqueue.assert_not_called()

	def test_foreground_change_claims_and_discards_request(self):
		with (
			patch.object(self.module, "isReaderForeground", return_value=False),
			patch.object(self.module, "showReader") as show,
		):
			self.plugin._reportIfCurrent(self.plugin._generation, self.result)
			show.assert_not_called()
		self.assertEqual(self.plugin._companionLastSequence, 1)

	def test_lock_or_stale_context_never_opens_reader(self):
		with (
			patch.object(self.module, "isReaderForeground", return_value=True),
			patch.object(self.module, "showReader") as show,
		):
			stale = copy.deepcopy(self.result)
			stale.values["context"] = "other"
			self.plugin._reportIfCurrent(self.plugin._generation, stale)
			self.plugin._announcementGuard.setBlocked("lock", True)
			self.plugin._reportIfCurrent(self.plugin._generation, self.result)
			self.plugin._announcementGuard.setBlocked("lock", False)
			self.plugin._reportIfCurrent(self.plugin._generation, self.result)
			show.assert_not_called()

	def test_failed_gui_call_is_not_retried(self):
		with (
			patch.object(self.module, "isReaderForeground", return_value=True),
			patch.object(self.module, "showReader", side_effect=RuntimeError("no viewer")) as show,
		):
			self.plugin._reportIfCurrent(self.plugin._generation, self.result)
			self.plugin._reportIfCurrent(self.plugin._generation, self.result)
			show.assert_called_once()


if __name__ == "__main__":
	unittest.main()
