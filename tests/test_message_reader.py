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
			}
		],
	}


class ReaderPayloadTests(unittest.TestCase):
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
		self.assertIn("<br>Next line", rendered)
		self.assertIn('<ul><li><a href="https://example.com/?q=&quot;&amp;a=1">', rendered)
		self.assertIn("&lt;Documentation&gt;</a></li></ul>", rendered)
		self.assertIn('lang="id"', rendered)
		self.assertIn("Sent: 12:34", rendered)

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
			payload(status="error", runs=[], message="Cannot load complete message")
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
			messageReader.showReader(payload())
		self.assertEqual(len(calls), 1)
		self.assertEqual(calls[0][2:], (True, True, True))

		def legacy(message, title=None, isHtml=False):
			calls.append((message, title, isHtml))

		with patch.dict(sys.modules, {"ui": types.SimpleNamespace(browseableMessage=legacy)}):
			messageReader.showReader(payload())
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
