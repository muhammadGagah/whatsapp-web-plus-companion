"""D02: fail-closed session gates, GUI generations and braille backlog invalidation.
NVDA/Windows APIs are simulated here; see COMPATIBILITY_MATRIX.md for real gates.
"""

import sys
import threading
import time
import types
import unittest
from unittest.mock import MagicMock, patch

from _path import installPackagePath

installPackagePath()
from globalPlugins.whatsappWebPlusCompanion import security, launcher
from globalPlugins.whatsappWebPlusCompanion.announcements import BrailleMessageQueue
from globalPlugins.whatsappWebPlusCompanion.cdp import CompanionAnnouncement, CompanionAnnouncementBatch
from globalPlugins.whatsappWebPlusCompanion.models import OperationResult


class GuardTests(unittest.TestCase):
	def test_lock_unlock_between_polls_invalidates_generation(self):
		guard = security.AnnouncementGuard(lambda: True)
		epoch = guard.snapshot()[1]
		guard.setBlocked("lock", True)
		guard.setBlocked("lock", False)
		self.assertFalse(guard.permits(epoch))
		self.assertTrue(guard.permits())

	def test_multiple_blockers_are_independent_and_idempotent(self):
		guard = security.AnnouncementGuard(lambda: True)
		guard.setBlocked("lock", True)
		guard.setBlocked("secure", True)
		epoch = guard.snapshot()[1]
		guard.setBlocked("secure", True)
		self.assertEqual(epoch, guard.snapshot()[1])
		guard.setBlocked("lock", False)
		self.assertFalse(guard.permits())
		guard.setBlocked("secure", False)
		self.assertTrue(guard.permits())

	def test_failed_or_unknown_probe_denies_output(self):
		for value in (False, None, 1, "unlocked"):
			with self.subTest(value=value):
				self.assertFalse(security.AnnouncementGuard(lambda: value).permits())

		def broken():
			raise OSError("unavailable")

		self.assertFalse(security.AnnouncementGuard(broken).permits())

	def test_windows_and_nvda_predicates_must_all_allow_output(self):
		args = types.SimpleNamespace(secure=False)
		tracking = types.SimpleNamespace(
			_getSessionLockedValue=lambda: 1, isLockScreenModeActive=lambda: False
		)
		state = types.SimpleNamespace(shouldWriteToDisk=lambda: True)
		utils = types.SimpleNamespace(isRunningOnSecureDesktop=lambda: False)
		modules = {
			"globalVars": types.SimpleNamespace(appArgs=args),
			"NVDAState": state,
			"utils.security": utils,
			"winAPI": types.SimpleNamespace(sessionTracking=tracking),
		}
		with (
			patch.dict(sys.modules, modules),
			patch.object(security, "_inputDesktopName", return_value="Default") as desktop,
		):
			self.assertTrue(security.announcementOutputAllowed())
			for value in (0, 0xFFFFFFFF, None):
				tracking._getSessionLockedValue = lambda: value
				self.assertFalse(security.announcementOutputAllowed())
			tracking._getSessionLockedValue = lambda: 1
			for value in (None, "Winlogon", "Other"):
				desktop.return_value = value
				self.assertFalse(security.announcementOutputAllowed())
			desktop.return_value = "Default"
			args.secure = True
			self.assertFalse(security.announcementOutputAllowed())
			args.secure = False
			state.shouldWriteToDisk = lambda: False
			self.assertFalse(security.announcementOutputAllowed())

	def test_braille_timer_discards_private_backlog_and_does_not_replay(self):
		allowed = [True]
		shown, timers = [], []

		def schedule(delay, callback):
			timer = types.SimpleNamespace(Stop=lambda: None, run=callback)
			timers.append(timer)
			return timer

		queue = BrailleMessageQueue(shown.append, schedule, outputAllowed=lambda: allowed[0])
		queue.enqueue("first")
		queue.enqueue("private pending")
		allowed[0] = False
		timers[-1].run()
		self.assertEqual(shown, ["first"])
		self.assertFalse(queue._pending)
		self.assertFalse(queue._current)
		allowed[0] = True
		queue.enqueue("new safe message")
		self.assertEqual(shown, ["first", "new safe message"])

	def test_native_braille_mode_drops_old_aggregate(self):
		allowed = [True]
		shown = []
		queue = BrailleMessageQueue(
			shown.append, lambda *a: None, dwellMilliseconds=None, outputAllowed=lambda: allowed[0]
		)
		queue.enqueue("private")
		allowed[0] = False
		queue.enqueue("blocked")
		allowed[0] = True
		queue.enqueue("new")
		self.assertEqual(shown, ["private", "new"])

	def test_worker_does_not_fetch_private_batch_when_locked(self):
		state = launcher._AnnouncementState()
		with patch.object(launcher, "readCompanionAnnouncements") as read:
			launcher._forwardCompanionAnnouncements(
				MagicMock(), state, MagicMock(), security.AnnouncementGuard(lambda: False)
			)
		read.assert_not_called()
		self.assertTrue(state.suppressed)

	def test_unlock_drops_backlog_even_if_renderer_and_sequence_reset(self):
		guard = security.AnnouncementGuard(lambda: True)
		state = launcher._AnnouncementState("old", 4, "old-chat", 200, guard.snapshot()[1])
		guard.setBlocked("lock", True)
		guard.setBlocked("lock", False)
		entry = CompanionAnnouncement(2, 1, "new", "new-chat", "status", "en", False, "private during lock")
		batch = CompanionAnnouncementBatch("new", 1, "new-chat", 2, False, "startup", "", False, (entry,))
		reports = []
		with patch.object(launcher, "readCompanionAnnouncements", return_value=batch):
			launcher._forwardCompanionAnnouncements(
				MagicMock(), state, lambda r: reports.append(r) or True, guard
			)
		self.assertEqual([r.code for r in reports], ["companion.invalidate"])
		self.assertEqual(state.lastAcknowledgedSequence, 2)
		self.assertEqual(state.sessionToken, "new")
		nextEntry = CompanionAnnouncement(3, 1, "new", "new-chat", "status", "en", False, "new safe")
		batch = CompanionAnnouncementBatch("new", 1, "new-chat", 3, False, "", "", False, (nextEntry,))
		with patch.object(launcher, "readCompanionAnnouncements", return_value=batch):
			launcher._forwardCompanionAnnouncements(
				MagicMock(), state, lambda r: reports.append(r) or True, guard
			)
		self.assertEqual(reports[-1].values["text"], "new safe")
		self.assertIn("securityEpoch", reports[-1].values)

	def test_lock_during_cdp_batch_read_does_not_dispatch(self):
		guard = security.AnnouncementGuard(lambda: True)
		state = launcher._AnnouncementState()

		def read(*args):
			guard.setBlocked("lock", True)
			return MagicMock()

		observer = MagicMock()
		with patch.object(launcher, "readCompanionAnnouncements", side_effect=read):
			launcher._forwardCompanionAnnouncements(MagicMock(), state, observer, guard)
		observer.assert_not_called()
		self.assertTrue(state.suppressed)


class PluginOutputTests(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		from test_plugin_ui_flow import _installFakeEnvironment

		_installFakeEnvironment()

	def setUp(self):
		self.module = sys.modules["globalPlugins.whatsappWebPlusCompanion"]
		self.plugin = self.module.GlobalPlugin()
		# Test-only injection: no Windows APIs are replaced in production.
		self.plugin._announcementGuard = security.AnnouncementGuard(lambda: True)
		self.plugin._brailleMessages = MagicMock()
		self.plugin._companionSession = "s"
		self.plugin._companionGeneration = 1
		self.plugin._companionContext = "c"
		self.result = OperationResult(
			True,
			"companion.announcement",
			"companion.announcement",
			{
				"session": "s",
				"generation": 1,
				"context": "c",
				"sequence": 1,
				"source": "status",
				"language": "en",
				"privacy": False,
				"text": "private",
				"securityEpoch": self.plugin._announcementGuard.snapshot()[1],
			},
		)

	def tearDown(self):
		self.plugin.terminate()

	def test_last_moment_guard_blocks_speech_and_braille(self):
		self.plugin._announcementGuard.setBlocked("lock", True)
		with patch.object(self.module.speech, "speak") as speak:
			self.assertTrue(self.plugin._deliverCompanionAnnouncement(self.result))
			speak.assert_not_called()
		self.plugin._brailleMessages.enqueue.assert_not_called()

	def test_old_epoch_after_unlock_is_consumed_without_cancelling_fresh_output(self):
		self.plugin._announcementGuard.setBlocked("lock", True)
		self.plugin._announcementGuard.setBlocked("lock", False)
		with (
			patch.object(self.module.speech, "speak") as speak,
			patch.object(self.plugin, "_suspendCompanionOutput") as suspend,
		):
			self.assertTrue(self.plugin._deliverCompanionAnnouncement(self.result))
			speak.assert_not_called()
			suspend.assert_not_called()

	def test_queued_gui_callback_cannot_replay_after_short_lock(self):
		callbacks, outcome = [], []
		with (
			patch.object(self.module.wx, "CallAfter", side_effect=lambda fn: callbacks.append(fn)),
			patch.object(self.module.speech, "speak") as speak,
		):
			worker = threading.Thread(target=lambda: outcome.append(self.plugin._queueReport(self.result)))
			worker.start()
			for _ in range(100):
				if callbacks:
					break
				time.sleep(0.001)
			self.assertTrue(callbacks)
			self.plugin._announcementGuard.setBlocked("lock", True)
			self.plugin._announcementGuard.setBlocked("lock", False)
			callbacks.pop()()
			worker.join(1)
			self.assertFalse(worker.is_alive())
			self.assertEqual(outcome, [True])
			speak.assert_not_called()

	def test_pending_gui_callback_expires_and_cannot_run_later(self):
		callbacks, outcome = [], []
		with (
			patch.object(self.module, "_DELIVERY_TIMEOUT", 0.05),
			patch.object(self.module.wx, "CallAfter", side_effect=lambda fn: callbacks.append(fn)),
			patch.object(self.module.speech, "speak") as speak,
		):
			worker = threading.Thread(target=lambda: outcome.append(self.plugin._queueReport(self.result)))
			worker.start()
			worker.join(0.5)
			self.assertFalse(worker.is_alive())
			self.assertEqual(outcome, [False])
			callbacks.pop()()
			speak.assert_not_called()

	def test_started_stalled_gui_callback_does_not_block_worker_or_retry(self):
		entered, release, outcome, callbacks = threading.Event(), threading.Event(), [], []

		def stalled(*args):
			entered.set()
			release.wait(2)
			return True

		with (
			patch.object(self.module, "_DELIVERY_TIMEOUT", 0.05),
			patch.object(self.module.wx, "CallAfter", side_effect=lambda fn: callbacks.append(fn)),
			patch.object(self.plugin, "_reportIfCurrent", side_effect=stalled),
		):
			worker = threading.Thread(target=lambda: outcome.append(self.plugin._queueReport(self.result)))
			worker.start()
			for _ in range(100):
				if callbacks:
					break
				time.sleep(0.001)
			gui = threading.Thread(target=callbacks.pop())
			gui.start()
			self.assertTrue(entered.wait(0.5))
			worker.join(0.5)
			try:
				self.assertFalse(worker.is_alive())
				self.assertEqual(outcome, [True])  # At most once after callback started.
			finally:
				release.set()
				gui.join(0.5)

	def test_lock_erases_only_companion_braille_and_cancels_its_speech(self):
		buffer = MagicMock(rawText="private")
		handler = types.SimpleNamespace(messageBuffer=buffer, buffer=buffer, update=MagicMock())
		self.plugin._lastCompanionBraille = "private"
		self.plugin._companionOutputActive = True
		with (
			patch.object(self.module.braille, "handler", handler),
			patch.object(self.module.speech, "cancelSpeech", create=True) as cancel,
		):
			self.plugin._onSessionLockChanged(True)
			buffer.clear.assert_called_once()
			handler.update.assert_called_once()
			cancel.assert_called_once()
		self.plugin._brailleMessages.clearPending.assert_called_with(silent=True)

	def test_secure_transition_does_not_erase_new_secure_screen_braille(self):
		buffer = MagicMock(rawText="Windows security")
		self.plugin._lastCompanionBraille = "private"
		with (
			patch.object(self.module.braille, "handler", types.SimpleNamespace(messageBuffer=buffer)),
			patch.object(self.module.speech, "cancelSpeech", create=True) as cancel,
		):
			self.plugin._onSecureDesktopChanged(True)
			buffer.clear.assert_not_called()
			cancel.assert_not_called()

	def test_security_hooks_are_registered_and_unregistered(self):
		lock, secure = MagicMock(), MagicMock()
		with patch.dict(
			sys.modules,
			{
				"utils.security": types.SimpleNamespace(post_sessionLockStateChanged=lock),
				"winAPI.secureDesktop": types.SimpleNamespace(post_secureDesktopStateChange=secure),
			},
		):
			self.plugin._subscribeAnnouncementSecurity()
		lock.register.assert_called_once_with(self.plugin._onSessionLockChanged)
		secure.register.assert_called_once_with(self.plugin._onSecureDesktopChanged)
		self.plugin.terminate()
		lock.unregister.assert_called_once()
		secure.unregister.assert_called_once()
