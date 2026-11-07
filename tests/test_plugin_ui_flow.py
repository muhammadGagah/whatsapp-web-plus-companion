import builtins
import importlib
import sys
import threading
import time
import types
import unittest
from unittest import mock

from _path import installPackagePath

installPackagePath()

_environmentPatcher = None
_environmentInstalled = False
_uiMessages: list[str] = []


class _FakeNativeDialog:
	instances: list["_FakeNativeDialog"] = []

	def __init__(self, parent, message, caption, style) -> None:
		self.parent = parent
		self.message = message
		self.caption = caption
		self.style = style
		self.destroyed = False
		self.labels = None
		self.instances.append(self)

	def SetOKCancelLabels(self, okLabel, cancelLabel) -> None:
		self.labels = (okLabel, cancelLabel)

	def Destroy(self) -> None:
		self.destroyed = True


class _FakeMessageDialog:
	def __init__(self, parent, message, title="", buttons=None) -> None:
		self.parent = parent
		self.message = message
		self.title = title
		self.shown = False
		self.raised = False
		self.focused = False
		self.closed = False
		self.destroyed = False
		self.callback = None
		self.defaultNo = False
		self.fallbackNo = False
		self.noLabel = ""
		self.yesLabel = ""

	def addNoButton(self, *, label, defaultFocus=False, fallbackAction=False):
		self.defaultNo = defaultFocus
		self.fallbackNo = fallbackAction
		self.noLabel = label
		return self

	def addYesButton(self, *, label, callback=None):
		self.callback = callback
		self.yesLabel = label
		return self

	def Bind(self, eventType, handler) -> None:
		self.destroyHandler = handler

	def Show(self) -> None:
		self.shown = True

	def Raise(self) -> None:
		self.raised = True

	def SetFocus(self) -> None:
		self.focused = True

	def Close(self) -> None:
		self.closed = True

	def IsDestroyed(self) -> bool:
		return False


def _installFakeEnvironment() -> None:
	global _environmentInstalled
	if _environmentInstalled:
		return
	_environmentInstalled = True
	builtins._ = lambda text: text

	class FakeMenuItem:
		_nextId = 1

		def __init__(self, label: str) -> None:
			self.Id = self._nextId
			FakeMenuItem._nextId += 1
			self.label = label

		def Enable(self, enabled) -> None:
			self.enabled = enabled

		def Check(self, checked) -> None:
			self.checked = checked

		def Destroy(self) -> None:
			pass

	class FakeMenu:
		def __init__(self) -> None:
			self.entries: list = []

		def Append(self, itemId, label: str, helpText: str) -> FakeMenuItem:
			item = FakeMenuItem(label)
			self.entries.append(item)
			return item

		def AppendCheckItem(self, itemId, label: str, helpText: str) -> FakeMenuItem:
			return self.Append(itemId, label, helpText)

		def AppendSeparator(self) -> None:
			self.entries.append(None)

		def Remove(self, itemId: int) -> None:
			pass

		def Destroy(self) -> None:
			pass

	class FakeToolsMenu(FakeMenu):
		def AppendSubMenu(self, menu, label: str, helpText: str) -> FakeMenuItem:
			item = FakeMenuItem(label)
			self.entries.append(item)
			return item

	class FakeOwner:
		def __init__(self) -> None:
			self.toolsMenu = FakeToolsMenu()

		def Bind(self, *args, **kwargs) -> None:
			pass

		def Unbind(self, *args, **kwargs) -> None:
			pass

	fakeWx = types.SimpleNamespace(
		Menu=FakeMenu,
		MenuItem=FakeMenuItem,
		ID_ANY=-1,
		EVT_MENU=object(),
		EVT_UPDATE_UI=object(),
		EVT_MENU_OPEN=object(),
		EVT_MENU_CLOSE=object(),
		EVT_WINDOW_DESTROY=object(),
		CallAfter=lambda function, *args, **kwargs: function(*args, **kwargs),
		CallLater=lambda delay, function, *args, **kwargs: function(*args, **kwargs),
		CommandEvent=object,
		MessageDialog=_FakeNativeDialog,
		Window=object,
		WindowDestroyEvent=object,
		MessageBoxCaptionStr="Message",
		OK=8,
		CANCEL=32,
		CANCEL_DEFAULT=64,
		OK_DEFAULT=128,
		ICON_QUESTION=4,
		CENTER=16,
		ID_OK=5100,
	)
	fakeGuiMessage = types.SimpleNamespace(
		displayDialogAsModal=lambda dialog: 0,
		MessageDialog=_FakeMessageDialog,
		Payload=object,
	)
	fakeGui = types.SimpleNamespace(
		mainFrame=types.SimpleNamespace(sysTrayIcon=FakeOwner(), Handle=12345),
		message=fakeGuiMessage,
	)
	fakeGlobalPluginHandler = types.SimpleNamespace(
		GlobalPlugin=type(
			"GlobalPlugin",
			(),
			{"__init__": lambda self: None, "terminate": lambda self: None},
		),
	)
	fakeLogHandler = types.SimpleNamespace(
		log=types.SimpleNamespace(
			exception=lambda *a, **k: None,
			warning=lambda *a, **k: None,
			info=lambda *a, **k: None,
		),
	)
	fakeModules = {
		"wx": fakeWx,
		"gui": fakeGui,
		"gui.message": fakeGuiMessage,
		"addonHandler": types.SimpleNamespace(initTranslation=lambda: None),
		"braille": types.SimpleNamespace(handler=types.SimpleNamespace(message=lambda text: None)),
		"config": types.SimpleNamespace(conf={"braille": {"messageTimeout": 4, "showMessages": 1}}),
		"globalVars": types.SimpleNamespace(appArgs=types.SimpleNamespace(secure=False)),
		"globalPluginHandler": fakeGlobalPluginHandler,
		"logHandler": fakeLogHandler,
		"NVDAState": types.SimpleNamespace(shouldWriteToDisk=lambda: True),
		"speech": types.SimpleNamespace(
			speak=lambda commands: None,
			speech=types.SimpleNamespace(speak=lambda commands: None),
		),
		"speech.commands": types.SimpleNamespace(LangChangeCommand=lambda language: object()),
		"scriptHandler": types.SimpleNamespace(script=lambda **kwargs: lambda function: function),
		"ui": types.SimpleNamespace(message=lambda text: _uiMessages.append(text)),
	}
	global _environmentPatcher
	_environmentPatcher = mock.patch.dict(sys.modules, fakeModules)
	_environmentPatcher.start()
	sys.modules.pop("globalPlugins.whatsappWebPlusCompanion", None)
	importlib.import_module("globalPlugins.whatsappWebPlusCompanion")


class PluginUiFlowTests(unittest.TestCase):
	@classmethod
	def setUpClass(cls) -> None:
		_installFakeEnvironment()

	def setUp(self) -> None:
		import wx

		self.uiMessages = _uiMessages
		self.wx = wx
		_FakeNativeDialog.instances.clear()
		_uiMessages.clear()
		pluginModule = sys.modules["globalPlugins.whatsappWebPlusCompanion"]
		self.module = pluginModule
		# Unit tests never touch the real per-user registry journal.
		pluginModule.recoverPendingRegistryStateAtStartup = lambda: None
		self.plugin = pluginModule.GlobalPlugin()

	def test_recovery_progress_speaks_without_replacing_last_result(self) -> None:
		from globalPlugins.whatsappWebPlusCompanion.models import OperationResult

		previous = OperationResult(True, "attached", "active", {})
		self.plugin.lastResult = previous
		progress = OperationResult(True, "cdp.recovering", "cdp.recovering", {})
		with mock.patch.object(self.module.commandFeedback, "message") as feedback:
			self.assertTrue(self.plugin._reportIfCurrent(self.plugin._generation, progress))
			feedback.assert_called_once_with("Reconnecting WhatsApp Companion. Please wait.")
			self.assertIs(self.plugin.lastResult, previous)
			feedback.reset_mock()
			self.assertFalse(self.plugin._reportIfCurrent(self.plugin._generation - 1, progress))
			feedback.assert_not_called()

	def test_recovery_success_and_failure_are_spoken_and_saved(self) -> None:
		from globalPlugins.whatsappWebPlusCompanion.models import OperationResult

		for result, expected in (
			(
				OperationResult(True, "cdp.restored", "cdp.restored", {}),
				"WhatsApp Companion is connected again.",
			),
			(
				OperationResult(False, "cdp.timeout", "cdp.timeout", {}),
				"Couldn't reconnect WhatsApp Companion. Close WhatsApp, then launch it again.",
			),
		):
			self.plugin.lastResult = OperationResult(True, "attached", "active", {})
			with mock.patch.object(self.module.commandFeedback, "message") as feedback:
				self.assertFalse(self.plugin._reportIfCurrent(self.plugin._generation - 1, result))
				feedback.assert_not_called()
				self.assertTrue(self.plugin._reportIfCurrent(self.plugin._generation, result))
				feedback.assert_called_once_with(expected)
				self.assertIs(self.plugin.lastResult, result)

	def test_lock_and_secure_desktop_request_recording_stop(self) -> None:
		with (
			mock.patch.object(self.plugin, "_recording") as recorder,
			mock.patch.object(self.plugin, "_suspendCompanionOutput"),
		):
			self.plugin._onSessionLockChanged(False)
			recorder.stop.assert_not_called()
			self.plugin._onSessionLockChanged(True)
			recorder.stop.assert_called_once_with()
			recorder.stop.reset_mock()
			self.plugin._onSecureDesktopChanged(True)
			recorder.stop.assert_called_once_with()

	def test_stop_cancels_probe_and_queued_recording_start(self) -> None:
		for afterProbe in (False, True):
			with (
				self.subTest(afterProbe=afterProbe),
				mock.patch.object(self.plugin, "_recordingAllowed", return_value=True),
				mock.patch.object(self.plugin, "_recording") as recorder,
				mock.patch.object(self.plugin, "_callAvailability") as availability,
				mock.patch.object(self.plugin, "_announce"),
				mock.patch("wx.CallAfter") as dispatch,
			):
				recorder.active = False
				completed = mock.Mock()
				self.plugin._startRecording("beta", "mic", "folder", completed)
				checked = availability.request.call_args.kwargs["callback"]
				if afterProbe:
					checked({"beta": object()})
					completed.assert_called_once_with(True)
					recorder.start.assert_not_called()
				self.plugin._stopRecording()
				if afterProbe:
					dispatch.call_args.args[0](*dispatch.call_args.args[1:])
				else:
					checked({"beta": object()})
					completed.assert_called_once_with(False)
				recorder.start.assert_not_called()
				self.assertFalse(self.plugin._recordingSetupPending)

	def test_delayed_recording_result_does_not_cross_security_epoch(self):
		from globalPlugins.whatsappWebPlusCompanion.security import AnnouncementGuard

		self.plugin._announcementGuard = AnnouncementGuard(lambda: True)
		with (
			mock.patch.object(self.module.wx, "CallLater") as timer,
			mock.patch.object(self.module.commandFeedback, "message") as say,
		):
			self.plugin._announce("private recording path", protected=True)
			self.plugin._announcementGuard.setBlocked("lock", True)
			self.plugin._announcementGuard.setBlocked("lock", False)
			timer.call_args.args[1]()
			say.assert_not_called()

	def test_terminal_recording_result_blocked_during_speech_delay_is_held(self):
		from globalPlugins.whatsappWebPlusCompanion.security import AnnouncementGuard

		self.plugin._announcementGuard = AnnouncementGuard(lambda: True)
		with (
			mock.patch.object(self.plugin, "_recordingAllowed", return_value=True),
			mock.patch.object(self.module.wx, "CallLater") as timer,
			mock.patch.object(self.module.commandFeedback, "message") as say,
		):
			self.plugin._recordingReport("saved", "private.wav")
			speak = timer.call_args.args[1]
			self.plugin._announcementGuard.setBlocked("lock", True)
			speak()
			say.assert_not_called()
			self.assertEqual(self.plugin._heldRecordingReport, ("saved", "private.wav"))
			# Progress messages are not terminal outcomes and are simply dropped.
			self.plugin._heldRecordingReport = None
			self.plugin._announcementGuard.setBlocked("lock", False)
			self.plugin._recording.cancel.clear()
			self.plugin._recordingReport("started", "private.wav")
			speak = timer.call_args.args[1]
			self.plugin._announcementGuard.setBlocked("lock", True)
			speak()
			self.assertIsNone(self.plugin._heldRecordingReport)

	def test_recording_setup_speech_is_suppressed_after_lock(self):
		from globalPlugins.whatsappWebPlusCompanion.security import AnnouncementGuard

		for source in ("lock", "secure-desktop"):
			self.plugin._announcementGuard = AnnouncementGuard(lambda: True)
			with (
				self.subTest(source=source),
				mock.patch.object(self.module.wx, "CallLater") as timer,
				mock.patch.object(self.module.commandFeedback, "message") as say,
			):
				self.plugin._announceRecording("Starting call recording. Please wait.")
				self.plugin._announcementGuard.setBlocked(source, True)
				timer.call_args.args[1]()
				self.plugin._announcementGuard.setBlocked(source, False)
				timer.call_args.args[1]()
				say.assert_not_called()

	def test_recording_worker_report_cannot_cross_security_transition(self):
		from globalPlugins.whatsappWebPlusCompanion.security import AnnouncementGuard

		self.plugin._announcementGuard = AnnouncementGuard(lambda: True)
		with (
			mock.patch.object(self.module.wx, "CallAfter") as dispatch,
			mock.patch.object(self.module.wx, "CallLater") as later,
			mock.patch.object(self.plugin, "_recordingReport") as report,
		):
			self.plugin._queueRecordingReport("started", "private.wav")
			callback, *args = dispatch.call_args.args
			self.plugin._announcementGuard.setBlocked("lock", True)
			self.plugin._announcementGuard.setBlocked("lock", False)
			callback(*args)
			report.assert_not_called()
			later.assert_not_called()
			# A terminal outcome is not spoken through the stale path, but it is not lost either.
			self.plugin._queueRecordingReport("saved", "private.wav")
			callback, *args = dispatch.call_args.args
			self.plugin._announcementGuard.setBlocked("lock", True)
			self.plugin._announcementGuard.setBlocked("lock", False)
			callback(*args)
			report.assert_not_called()
			later.call_args.args[1](*later.call_args.args[2:])
			report.assert_called_once_with("saved", "private.wav")
			report.reset_mock()
			self.plugin._queueRecordingReport("saved", "current.wav")
			callback, *args = dispatch.call_args.args
			callback(*args)
			report.assert_called_once_with("saved", "current.wav")

	def lockedRecordingPlugin(self):
		from globalPlugins.whatsappWebPlusCompanion.security import AnnouncementGuard

		self.plugin._announcementGuard = AnnouncementGuard(lambda: True)
		patches = (
			mock.patch.object(self.plugin, "_recording"),
			mock.patch.object(self.plugin, "_suspendCompanionOutput"),
			mock.patch.object(self.plugin, "_cancelCallRecovery"),
			mock.patch.object(self.plugin, "_announce"),
		)
		recorder, _suspend, _cancel, announce = (patch.start() for patch in patches)
		for patch in patches:
			self.addCleanup(patch.stop)
		recorder.active = False
		recorder.cancel.is_set.return_value = False
		return recorder, announce

	def test_recording_stopped_by_lock_is_reported_after_unlock(self):
		for locked, unlocked in (
			(
				lambda: self.plugin._onSessionLockChanged(True),
				lambda: self.plugin._onSessionLockChanged(False),
			),
			(
				lambda: self.plugin._onSecureDesktopChanged(True),
				lambda: self.plugin._onSecureDesktopChanged(False),
			),
		):
			with self.subTest(locked=locked):
				recorder, announce = self.lockedRecordingPlugin()
				locked()
				recorder.stop.assert_called_once_with()
				# The worker reports while Windows is still locked: nothing is spoken, not even the path.
				self.plugin._queueRecordingReport("started", "late.wav")
				self.plugin._queueRecordingReport("cancelled", "")
				self.plugin._queueRecordingReport("saved", "private.wav")
				announce.assert_not_called()
				unlocked()
				announce.assert_called_once_with(
					"Recording saved: private.wav",
					protected=True,
					onBlocked=mock.ANY,
				)
				self.assertIsNone(self.plugin._heldRecordingReport)
				unlocked()
				announce.assert_called_once()

	def test_held_recording_report_waits_for_every_security_block(self):
		recorder, announce = self.lockedRecordingPlugin()
		self.plugin._onSessionLockChanged(True)
		self.plugin._onSecureDesktopChanged(True)
		self.plugin._queueRecordingReport("failed", "partial.wav")
		self.plugin._onSessionLockChanged(False)
		announce.assert_not_called()
		self.plugin._onSecureDesktopChanged(False)
		announce.assert_called_once()
		self.assertIn("partial.wav", announce.call_args.args[0])

	def test_held_recording_report_is_given_before_the_next_recording_command(self):
		recorder, announce = self.lockedRecordingPlugin()
		with mock.patch.object(self.module.wx, "CallLater"):
			self.plugin._onSessionLockChanged(True)
			self.plugin._queueRecordingReport("cancelled", "")
			self.plugin._announcementGuard.setBlocked("lock", False)
			announce.assert_not_called()
			self.plugin._stopRecording()
		self.assertEqual(
			[call.args[0] for call in announce.call_args_list],
			["Recording cancelled.", "No call recording is running."],
		)

	def test_terminate_discards_held_recording_report(self):
		recorder, announce = self.lockedRecordingPlugin()
		with mock.patch.object(self.module.wx, "CallLater"):
			self.plugin._onSessionLockChanged(True)
			self.plugin._queueRecordingReport("saved", "private.wav")
		self.plugin.terminate()
		self.assertIsNone(self.plugin._heldRecordingReport)
		self.plugin._deliverHeldRecordingReport(3)
		announce.assert_not_called()

	def test_unavailable_after_stop_is_reported_as_cancelled_without_invalidating(self):
		with (
			mock.patch.object(self.plugin, "_recordingAllowed", return_value=True),
			mock.patch.object(self.plugin, "_callAvailability") as availability,
			mock.patch.object(self.plugin, "_announce") as announce,
		):
			self.plugin._recording.stop()
			self.plugin._recordingReport("unavailable", "")
			announce.assert_called_once_with("Recording cancelled.", protected=True, onBlocked=mock.ANY)
			availability.invalidate.assert_not_called()

	def test_automatic_stops_are_announced_with_saved_path(self):
		for state, expected in (
			("call-ended", "The call ended. Recording saved: call.wav"),
			("limit", "Recording reached the 4-hour limit. Saved: call.wav"),
		):
			with (
				self.subTest(state=state),
				mock.patch.object(self.plugin, "_recordingAllowed", return_value=True),
				mock.patch.object(self.plugin, "_announce") as announce,
			):
				self.plugin._recordingReport(state, "call.wav")
				announce.assert_called_once_with(expected, protected=True, onBlocked=mock.ANY)

	def test_lock_before_queued_start_clears_preparation_state(self):
		allowed = [True, True]
		with (
			mock.patch.object(
				self.plugin,
				"_recordingAllowed",
				side_effect=lambda: allowed.pop(0) if allowed else False,
			),
			mock.patch.object(self.plugin, "_recording") as recorder,
			mock.patch.object(self.plugin, "_callAvailability") as availability,
			mock.patch.object(self.plugin, "_announce"),
			mock.patch.object(self.module.wx, "CallAfter") as dispatch,
		):
			recorder.active = False
			completed = mock.Mock()
			self.plugin._startRecording("beta", "mic", "folder", completed)
			availability.request.call_args.kwargs["callback"]({"beta": object()})
			completed.assert_called_once_with(True)
			self.assertTrue(self.plugin._recordingSetupPending)
			dispatch.call_args.args[0](*dispatch.call_args.args[1:])
			recorder.start.assert_not_called()
			self.assertFalse(self.plugin._recordingSetupPending)

	def test_recording_waits_until_nvda_is_no_longer_in_the_foreground(self):
		import os

		foreground = [(11, os.getpid()), (11, os.getpid()), (22, 999)]
		with (
			mock.patch.object(self.plugin, "_recordingAllowed", return_value=True),
			mock.patch.object(self.plugin, "_recording") as recorder,
			mock.patch.object(self.plugin, "_announce"),
			mock.patch.object(self.module, "foregroundWindow", side_effect=lambda: foreground.pop(0)),
			mock.patch.object(self.module.wx, "CallLater") as later,
		):
			self.plugin._recordingSetupPending = True
			token = self.plugin._recordingSetupToken
			self.plugin._beginRecordingWhenForegroundSettles("beta", "mic", "folder", token, 3)
			for _attempt in range(2):
				recorder.start.assert_not_called()
				self.assertTrue(self.plugin._recordingSetupPending)
				later.call_args.args[1](*later.call_args.args[2:])
			recorder.start.assert_called_once_with("beta", "mic", "folder", foreground=22)
			self.assertFalse(self.plugin._recordingSetupPending)

	def test_stop_before_capture_says_preparation_is_cancelled(self):
		with (
			mock.patch.object(self.plugin, "_recordingAllowed", return_value=True),
			mock.patch.object(self.plugin, "_recording") as recorder,
			mock.patch.object(self.plugin, "_announce") as announce,
		):
			recorder.active = True
			recorder.captureStarted = False
			self.plugin._stopRecording()
			recorder.stop.assert_called_once_with()
			self.assertEqual(announce.call_args.args[0], "Cancelling the recording.")
			recorder.captureStarted = True
			self.plugin._stopRecording()
			self.assertEqual(announce.call_args.args[0], "Stopping recording and saving the file.")

	def test_focus_change_report_explains_why_recording_did_not_start(self):
		with (
			mock.patch.object(self.plugin, "_recordingAllowed", return_value=True),
			mock.patch.object(self.plugin, "_announce") as announce,
		):
			self.plugin._recording.cancel.clear()
			self.plugin._recordingReport("focus-changed", "")
			self.assertIn("you left the call window", announce.call_args.args[0])

	def test_failed_call_check_is_not_reported_as_no_call(self):
		expected = "Couldn't check for a WhatsApp call. Try again."
		with (
			mock.patch.object(self.plugin, "_recordingAllowed", return_value=True),
			mock.patch.object(self.plugin, "_recording") as recorder,
			mock.patch.object(self.plugin, "_callAvailability") as availability,
			mock.patch.object(self.plugin, "_announce") as announce,
		):
			recorder.active = False
			completed = mock.Mock()
			self.plugin._startRecording("beta", "mic", "folder", completed)
			availability.request.call_args.kwargs["callback"](None)
			completed.assert_called_once_with(False)
			self.assertEqual(announce.call_args.args[0], expected)
			self.assertFalse(self.plugin._recordingSetupPending)
			announce.reset_mock()
			self.plugin._recordingSetupPending = True
			self.plugin._recordingCallReady(None, self.plugin._recordingSetupToken)
			self.assertEqual(announce.call_args.args[0], expected)
			self.assertFalse(self.plugin._recordingSetupPending)
			announce.reset_mock()
			self.plugin._recordingSetupPending = True
			self.plugin._showRecordingDialog(
				[{"id": "a", "name": "Mic"}],
				self.plugin._recordingSetupToken,
				None,
			)
			self.assertEqual(announce.call_args.args[0], expected)

	def test_menu_state_uses_cached_evidence_and_unknown_stays_enabled(self):
		from globalPlugins.whatsappWebPlusCompanion.models import Channel

		with (
			mock.patch.object(self.plugin, "_recordingAllowed", return_value=True),
			mock.patch.object(self.module, "recordingSupported", return_value=True),
			mock.patch.object(self.plugin._callAvailability, "request") as request,
		):
			self.assertTrue(self.plugin._recordingMenuEnabled())
			self.plugin._callAvailability._finish(self.plugin._callAvailability._generation, {})
			self.assertFalse(self.plugin._recordingMenuEnabled())
			self.assertFalse(self.plugin._recordingCallAvailable(Channel.BETA))
			# Enabled-state predicates never start a probe themselves; the open menu's refresh does.
			request.reset_mock()
			self.plugin._recordingMenuEnabled()
			request.assert_not_called()
			self.plugin._requestCallAvailability()
			request.assert_called_once_with()

	def test_recording_start_is_blocked_by_security(self) -> None:
		with (
			mock.patch.object(self.plugin, "_recordingAllowed", return_value=False),
			mock.patch.object(self.plugin, "_recording") as recorder,
		):
			self.plugin._startRecording(None, "microphone", "folder")
			recorder.start.assert_not_called()

	def test_cancelled_recording_cannot_announce_late_start(self) -> None:
		self.plugin._recording.stop()
		with (
			mock.patch.object(self.plugin, "_recordingAllowed", return_value=True),
			mock.patch.object(self.plugin, "_announce") as announce,
		):
			self.plugin._recordingReport("started", "record.wav")
			announce.assert_not_called()

	def test_closed_after_recovery_progress_announces_outcome_only_when_needed(self) -> None:
		from globalPlugins.whatsappWebPlusCompanion.models import OperationResult

		for recoveryReported in (False, True):
			result = OperationResult(
				True,
				"package.closed",
				"package.closed",
				{"recoveryReported": recoveryReported},
			)
			with mock.patch.object(self.module.commandFeedback, "message") as feedback:
				self.plugin._reportIfCurrent(self.plugin._generation, result)
				self.assertEqual(feedback.call_count, int(recoveryReported))
				self.assertIs(self.plugin.lastResult, result)

	def test_process_probe_failures_never_offer_permission_repair(self) -> None:
		from globalPlugins.whatsappWebPlusCompanion.models import LoaderError

		def diagnosis(*args, **kwargs):
			kwargs["whatsappRunning"]()
			raise AssertionError("Diagnosis must stop on unknown process state")

		self.plugin._registryDiagnosisPending = True
		with (
			mock.patch.object(self.module, "findPackage", side_effect=LoaderError("powershell.failed")),
			mock.patch.object(self.module, "diagnoseRegistryPermissions", side_effect=diagnosis),
			mock.patch.object(self.plugin, "_confirmRegistryRepair") as repair,
			mock.patch.object(self.plugin, "_finishRegistryDiagnosis") as finished,
		):
			self.plugin._runRegistryDiagnosis(self.plugin._generation, threading.Event())
			repair.assert_not_called()
			finished.assert_not_called()
		self.assertFalse(self.plugin._registryDiagnosisPending)
		self.assertEqual(self.plugin.lastResult.code, "registry.repair.processUnknown")
		self.assertTrue(
			any("Couldn't tell whether WhatsApp is open" in text for text in self.uiMessages),
		)

	def test_process_probe_distinguishes_unknown_absent_and_running(self) -> None:
		from globalPlugins.whatsappWebPlusCompanion.models import LoaderError

		with mock.patch.object(self.module, "findPackage", return_value=None):
			self.assertFalse(self.plugin._whatsappRunning())
		with (
			mock.patch.object(self.module, "findPackage", return_value=object()),
			mock.patch.object(
				self.module,
				"findRunningPackageProcesses",
				side_effect=RuntimeError("unknown"),
			),
		):
			with self.assertRaises(LoaderError) as error:
				self.plugin._whatsappRunning()
			self.assertEqual(error.exception.code, "registry.repair.processUnknown")
		with (
			mock.patch.object(
				self.module,
				"findPackage",
				side_effect=[LoaderError("powershell.failed"), object()],
			),
			mock.patch.object(self.module, "findRunningPackageProcesses", return_value=[object()]),
		):
			self.assertTrue(self.plugin._whatsappRunning())

	def test_delayed_command_feedback_uses_helper_and_disposed_callback_is_silent(self) -> None:
		callbacks = []
		with (
			mock.patch.object(
				self.wx,
				"CallLater",
				side_effect=lambda delay, callback: callbacks.append(callback),
			),
			mock.patch.object(self.module.commandFeedback, "message") as feedback,
		):
			self.plugin._announce("requested result")
			feedback.assert_not_called()
			callbacks.pop()()
			feedback.assert_called_once_with("requested result")
			self.plugin._announce("stale result")
			self.plugin._disposed = True
			callbacks.pop()()
			feedback.assert_called_once()

	def test_diagnosis_usable_reports_not_needed_without_uac(self) -> None:
		from globalPlugins.whatsappWebPlusCompanion.registryRepair import RegistryPermissionStatus

		with mock.patch.object(
			self.module,
			"diagnoseRegistryPermissions",
			return_value=RegistryPermissionStatus.USABLE,
		):
			self.plugin._startRegistryDiagnosis()
			for _ in range(100):
				if "WebView2 permissions are fine. Nothing needs fixing." in self.uiMessages:
					break
				time.sleep(0.001)

		self.assertIn("Checking WebView2 permissions.", self.uiMessages)
		self.assertIn(
			"WebView2 permissions are fine. Nothing needs fixing.",
			self.uiMessages,
		)
		self.assertEqual(self.plugin.lastResult.code, "registry.repair.notNeeded")
		self.assertEqual(_FakeNativeDialog.instances, [])

	def test_terminate_cancels_and_reaps_registry_diagnosis_worker_cooperatively(self) -> None:
		started = threading.Event()

		def waitForCancellation(*_args, **kwargs):
			started.set()
			cancelled = kwargs["isCancelled"]
			for _ in range(1000):
				if cancelled():
					raise self.module.LoaderError("operation.cancelled")
				time.sleep(0.001)
			raise AssertionError("diagnosis was not cancelled")

		with mock.patch.object(
			self.module,
			"diagnoseRegistryPermissions",
			side_effect=waitForCancellation,
		):
			self.plugin._startRegistryDiagnosis()
			self.assertTrue(started.wait(1))
			worker = self.plugin._registryDiagnosisWorker
			self.assertIsNotNone(worker)
			self.plugin.terminate()
			worker.join(1)

		self.assertFalse(worker.is_alive())
		self.assertTrue(self.plugin._registryDiagnosisCancel.is_set())

	def test_announcements_use_current_speech_history_hook_once(self) -> None:
		for language in ("", "id-ID"):
			with (
				self.subTest(language=language),
				mock.patch.object(self.plugin, "_allowCompanionOutput", return_value=True),
				mock.patch.object(self.module.speech, "speak") as packageSpeak,
				mock.patch.object(self.module.speech.speech, "speak") as historyHook,
				mock.patch.object(
					self.module,
					"LangChangeCommand",
					side_effect=lambda lang: ("language", lang),
				),
				mock.patch.object(self.plugin, "_brailleMessages") as brailleQueue,
			):
				self.plugin._speakAndQueueBraille("Sticker description", language, "status")
				expected = ["Sticker description"]
				if language:
					expected = [("language", "id_ID"), "Sticker description", ("language", None)]
				historyHook.assert_called_once_with(expected)
				packageSpeak.assert_not_called()
				brailleQueue.enqueue.assert_called_once_with("Sticker description", "status")

	def test_renderer_session_change_clears_all_pending_braille(self) -> None:
		from globalPlugins.whatsappWebPlusCompanion.models import OperationResult

		queue = mock.Mock()
		self.plugin._brailleMessages = queue
		self.plugin._companionSession = "old-session"
		self.plugin._companionLastSequence = 7
		result = OperationResult(
			True,
			"companion.invalidate",
			"companion.invalidate",
			{
				"session": "new-session",
				"generation": 1,
				"context": "new-session:1",
				"source": "message-log",
			},
		)

		self.assertTrue(self.plugin._applyCompanionInvalidation(result))
		queue.clearPending.assert_called_once_with()
		queue.discardPending.assert_not_called()
		self.assertEqual(self.plugin._companionLastSequence, 0)

	def test_missing_registry_key_offers_setup_confirmation(self) -> None:
		from globalPlugins.whatsappWebPlusCompanion.registryRepair import RegistryPermissionStatus

		self.plugin._finishRegistryDiagnosis(0, RegistryPermissionStatus.MISSING_KEY)
		self.assertEqual(self.plugin.lastResult.code, "registry.repair.confirmationRequired")
		self.assertIsNotNone(self.plugin._dialog)
		self.assertTrue(self.plugin._dialog.shown)
		self.assertTrue(self.plugin._dialog.defaultNo)

	def test_diagnosis_repairable_shows_confirmation_dialog(self) -> None:
		from globalPlugins.whatsappWebPlusCompanion.registryRepair import RegistryPermissionStatus

		with mock.patch.object(
			self.module,
			"diagnoseRegistryPermissions",
			return_value=RegistryPermissionStatus.REPAIRABLE_ACCESS_DENIED,
		):
			self.plugin._startRegistryDiagnosis()
			for _ in range(100):
				if self.plugin._dialog is not None:
					break
				time.sleep(0.001)

		self.assertIn("Checking WebView2 permissions.", self.uiMessages)
		self.assertIsNotNone(self.plugin._dialog)
		self.assertEqual(
			self.plugin.lastResult.code,
			"registry.repair.confirmationRequired",
		)
		self.assertTrue(self.plugin._dialog.shown)
		self.assertTrue(self.plugin._dialog.defaultNo)

	def test_running_whatsapp_offers_force_close_then_resumes_diagnosis(self) -> None:
		from globalPlugins.whatsappWebPlusCompanion.models import OperationResult
		from globalPlugins.whatsappWebPlusCompanion.registryRepair import RegistryPermissionStatus

		self.plugin._finishRegistryDiagnosis(0, RegistryPermissionStatus.WHATSAPP_RUNNING)

		dialog = self.plugin._dialog
		self.assertIsNotNone(dialog)
		self.assertEqual(dialog.title, "Close WhatsApp to continue diagnosis?")
		self.assertIn("Calls and file transfers will stop", dialog.message)
		self.assertIn("you'll be asked again", dialog.message)
		self.assertEqual(dialog.noLabel, "&Keep WhatsApp open")
		self.assertEqual(dialog.yesLabel, "&Force close WhatsApp and continue")
		self.assertTrue(dialog.defaultNo)
		self.assertTrue(dialog.fallbackNo)
		self.assertNotIn("Close WhatsApp before checking WebView2 permissions.", self.uiMessages)

		completion = None

		def startForceClose(onComplete=None):
			nonlocal completion
			completion = onComplete
			return True

		with mock.patch.object(self.plugin.controller, "forceClose", side_effect=startForceClose):
			dialog.callback(None)
		self.assertIsNotNone(completion)
		self.plugin._onDialogDestroyed(
			types.SimpleNamespace(GetEventObject=lambda: dialog, Skip=lambda: None),
		)

		with mock.patch.object(self.plugin, "_startRegistryDiagnosis") as startDiagnosis:
			completion(OperationResult(True, "processes.closed", "processes.closed", {}))
			startDiagnosis.assert_called_once_with()

	def test_running_whatsapp_does_not_resume_after_incomplete_force_close(self) -> None:
		from globalPlugins.whatsappWebPlusCompanion.models import OperationResult

		with mock.patch.object(self.plugin, "_startRegistryDiagnosis") as startDiagnosis:
			self.plugin._resumeRegistryDiagnosisAfterForceClose(
				self.plugin._generation,
				OperationResult(False, "processes.partial", "processes.partial", {}),
			)
			startDiagnosis.assert_not_called()

	def test_force_close_dialog_suggests_the_only_connected_whatsapp(self) -> None:
		Channel = self.module.Channel
		for active, expected in (
			((), None),
			((Channel.BETA,), Channel.BETA),
			((Channel.STABLE, Channel.BETA), None),
		):
			created = []

			def create(default):
				created.append(default)
				return _FakeMessageDialog(None, "Force close")

			with (
				self.subTest(active=active),
				mock.patch.object(self.plugin.controller, "activeChannels", return_value=active),
				mock.patch.object(self.plugin, "_createForceCloseDialog", side_effect=create),
			):
				self.plugin._dialog = None
				self.plugin._reviewForceClose()
			self.assertEqual(created, [expected])
			self.assertTrue(self.plugin._dialog.shown)

	def test_force_close_choice_closes_one_channel_or_all(self) -> None:
		Channel = self.module.Channel
		cases = (
			(None, mock.call(), "Closing WhatsApp Stable and Beta."),
			((Channel.STABLE, Channel.BETA), mock.call(), None),
			(
				(Channel.BETA,),
				mock.call(channels=(Channel.BETA,)),
				"Closing WhatsApp Beta.",
			),
		)
		for channels, expectedCall, message in cases:
			self.uiMessages.clear()
			with (
				self.subTest(channels=channels),
				mock.patch.object(self.plugin.controller, "forceClose", return_value=True) as forceClose,
			):
				self.plugin._startForceClose(channels)
			self.assertEqual(forceClose.call_args_list, [expectedCall])
			if message:
				self.assertEqual(self.uiMessages, [message])

	def test_single_channel_force_close_results_name_the_channel(self) -> None:
		from globalPlugins.whatsappWebPlusCompanion.models import OperationResult

		closed = OperationResult(
			True,
			"processes.closed",
			"processes.closed.one",
			{"channel": "beta", "closedCount": 3},
		)
		none = OperationResult(True, "processes.none", "processes.none.one", {"channel": "stable"})
		self.assertEqual(
			self.plugin._messageForResult(closed),
			"WhatsApp Beta was closed (3 processes).",
		)
		self.assertEqual(
			self.plugin._messageForResult(none),
			"WhatsApp Stable wasn't running.",
		)

	def test_resumed_diagnosis_waits_for_an_existing_dialog_to_close(self) -> None:
		generation = self.plugin._generation
		existingDialog = _FakeMessageDialog(None, "Other result")
		self.plugin._dialog = existingDialog
		self.plugin._registryDiagnosisResumeGeneration = generation

		with mock.patch.object(self.plugin, "_startRegistryDiagnosis") as startDiagnosis:
			self.plugin._continueRegistryDiagnosisAfterForceClose(generation)
			startDiagnosis.assert_not_called()
			self.assertTrue(existingDialog.raised)

			self.plugin._onDialogDestroyed(
				types.SimpleNamespace(GetEventObject=lambda: existingDialog, Skip=lambda: None),
			)
			startDiagnosis.assert_called_once_with()

	def test_pending_resume_blocks_competing_operations(self) -> None:
		generation = self.plugin._generation
		self.plugin._registryDiagnosisResumeGeneration = generation

		with (
			mock.patch.object(self.plugin.controller, "start") as startLaunch,
			mock.patch.object(self.plugin.controller, "forceClose") as forceClose,
			mock.patch.object(self.module.threading.Thread, "start") as startThread,
		):
			self.plugin._launch(self.module.Channel.STABLE)
			self.plugin._startRegistryDiagnosis()
			self.plugin._reviewForceClose()

			startLaunch.assert_not_called()
			forceClose.assert_not_called()
			startThread.assert_not_called()

		with mock.patch.object(self.plugin, "_startRegistryDiagnosis") as startDiagnosis:
			self.plugin._continueRegistryDiagnosisAfterForceClose(generation)
			self.assertIsNone(self.plugin._registryDiagnosisResumeGeneration)
			startDiagnosis.assert_called_once_with()

	def test_launch_progress_replaces_stale_last_result_while_whatsapp_is_loading(self) -> None:
		from globalPlugins.whatsappWebPlusCompanion.models import OperationResult

		self.plugin.lastResult = OperationResult(False, "internal.error", "internal.error", {})
		with mock.patch.object(self.plugin.controller, "start", return_value=True):
			self.plugin._launch(self.module.Channel.STABLE)

		self.assertEqual(self.plugin.lastResult.code, "operation.loading")
		self.assertIn(
			"Opening WhatsApp Stable with WhatsApp Companion. Please wait.",
			self.uiMessages,
		)
		self.uiMessages.clear()
		self.plugin.script_reportLastResult(None)
		self.assertEqual(
			self.uiMessages,
			["Opening WhatsApp Stable with WhatsApp Companion. Please wait."],
		)

	def test_dead_stale_dialog_is_cleared_and_diagnosis_proceeds(self) -> None:
		self.plugin._dialog = types.SimpleNamespace(
			IsDestroyed=lambda: True,
			Raise=lambda: None,
			SetFocus=lambda: None,
		)
		self.assertFalse(self.plugin._focusExistingDialog())
		self.assertIsNone(self.plugin._dialog)

		from globalPlugins.whatsappWebPlusCompanion.registryRepair import RegistryPermissionStatus

		with mock.patch.object(
			self.module,
			"diagnoseRegistryPermissions",
			return_value=RegistryPermissionStatus.USABLE,
		):
			self.plugin._startRegistryDiagnosis()
			for _ in range(100):
				if "WebView2 permissions are fine. Nothing needs fixing." in self.uiMessages:
					break
				time.sleep(0.001)
		self.assertIn("Checking WebView2 permissions.", self.uiMessages)

	def test_py_dead_object_error_recovers_singleton(self) -> None:
		class DeadDialog:
			def IsDestroyed(self) -> bool:
				return False

			def Raise(self) -> None:
				raise RuntimeError("wrapped C/C++ object of type MessageDialog has been deleted")

			def SetFocus(self) -> None:
				pass

		dialog = DeadDialog()
		self.plugin._dialog = dialog
		self.assertFalse(self.plugin._focusExistingDialog())
		self.assertIsNone(self.plugin._dialog)

	def test_deleted_message_dialog_heals_and_diagnosis_proceeds(self) -> None:
		class DeletedDialog:
			def IsDestroyed(self) -> bool:
				return False

			def Raise(self) -> None:
				raise RuntimeError("wrapped C/C++ object of type MessageDialog has been deleted")

			def SetFocus(self) -> None:
				pass

		self.plugin._dialog = DeletedDialog()

		from globalPlugins.whatsappWebPlusCompanion.registryRepair import RegistryPermissionStatus

		with mock.patch.object(
			self.module,
			"diagnoseRegistryPermissions",
			return_value=RegistryPermissionStatus.USABLE,
		):
			self.plugin._startRegistryDiagnosis()
			for _ in range(100):
				if "WebView2 permissions are fine. Nothing needs fixing." in self.uiMessages:
					break
				time.sleep(0.001)
		self.assertIsNone(self.plugin._dialog)
		self.assertIn("Checking WebView2 permissions.", self.uiMessages)
		self.assertEqual(self.plugin.lastResult.code, "registry.repair.notNeeded")

	def test_diagnosis_loader_error_reports_exact_code(self) -> None:
		from globalPlugins.whatsappWebPlusCompanion.models import LoaderError

		def failDiagnosis(*args, **kwargs):
			raise LoaderError(
				"registry.machine.readAccessDenied",
				"stage=machine.read;winerror=5",
			)

		with mock.patch.object(self.module, "diagnoseRegistryPermissions", side_effect=failDiagnosis):
			self.plugin._startRegistryDiagnosis()
			for _ in range(100):
				if self.plugin.lastResult is not None:
					break
				time.sleep(0.001)
		self.assertEqual(self.plugin.lastResult.code, "registry.machine.readAccessDenied")
		self.assertTrue(any("computer-wide WebView2 setting" in text for text in self.uiMessages))

	def test_repair_identity_capture_failure_reports_exact_code(self) -> None:
		from globalPlugins.whatsappWebPlusCompanion.models import LoaderError

		def failCapture():
			raise LoaderError("registry.repair.context", "stage=identity.open")

		with mock.patch.object(self.module, "captureRequestIdentity", side_effect=failCapture):
			self.plugin._startRegistryRepair(None)
		self.assertEqual(self.plugin.lastResult.code, "registry.repair.context")
		self.assertFalse(self.plugin.controller.repairing)

	def test_menu_announcements_are_deferred_past_focus_announcement(self) -> None:
		from globalPlugins.whatsappWebPlusCompanion.models import OperationResult

		scheduled: list[tuple[int, object]] = []

		def recordCallLater(delay, function, *args, **kwargs):
			scheduled.append((delay, function))

		with mock.patch.object(self.wx, "CallLater", side_effect=recordCallLater):
			self.plugin._announce("Deferred hello")
			self.plugin._report(
				OperationResult(
					True,
					"registry.repair.notNeeded",
					"registry.repair.notNeeded",
					{},
				),
				defer=True,
			)

		self.assertEqual(len(scheduled), 2)
		for delay, _function in scheduled:
			self.assertGreater(delay, 0)
		self.assertNotIn("Deferred hello", self.uiMessages)
		for _delay, function in scheduled:
			function()
		self.assertIn("Deferred hello", self.uiMessages)
		self.assertIn(
			"WebView2 permissions are fine. Nothing needs fixing.",
			self.uiMessages,
		)

	def test_fast_update_completion_suppresses_stale_progress(self) -> None:
		from globalPlugins.whatsappWebPlusCompanion.updater import UpdateCheckResult, UpdateStatus

		scheduled: list[object] = []

		def recordCallLater(delay, function, *args, **kwargs):
			scheduled.append(lambda: function(*args, **kwargs))

		with (
			mock.patch.object(self.wx, "CallLater", side_effect=recordCallLater),
			mock.patch.object(self.module.threading.Thread, "start"),
		):
			self.plugin._startUpdateCheck()
			worker = self.plugin._updateWorker
			self.assertIsNotNone(worker)
			self.plugin._finishUpdateCheck(
				self.plugin._generation,
				self.plugin._updateOperationToken,
				UpdateCheckResult(UpdateStatus.CURRENT, "2.6.75", "2.6.75"),
				worker,
			)

		self.assertEqual(self.uiMessages, [])
		for callback in scheduled:
			callback()
		self.assertEqual(
			self.uiMessages,
			["WhatsApp Web Plus is up to date (2.6.75)."],
		)

	def test_updated_bundle_result_explains_next_launch(self) -> None:
		from globalPlugins.whatsappWebPlusCompanion.updater import UpdateCheckResult, UpdateStatus

		with mock.patch.object(self.module.threading.Thread, "start"):
			self.plugin._startUpdateCheck()
		worker = self.plugin._updateWorker
		self.assertIsNotNone(worker)
		self.plugin._finishUpdateCheck(
			self.plugin._generation,
			self.plugin._updateOperationToken,
			UpdateCheckResult(UpdateStatus.UPDATED, "2.6.74", "2.6.75"),
			worker,
		)
		self.assertTrue(
			any(
				"updated from 2.6.74 to 2.6.75" in message and "next time you launch WhatsApp" in message
				for message in self.uiMessages
			),
		)
		self.assertEqual(self.plugin.lastResult.code, "update.updated")

	def test_same_version_content_refresh_is_reported_clearly(self) -> None:
		from globalPlugins.whatsappWebPlusCompanion.updater import UpdateCheckResult, UpdateStatus

		with mock.patch.object(self.module.threading.Thread, "start"):
			self.plugin._startUpdateCheck()
		worker = self.plugin._updateWorker
		self.assertIsNotNone(worker)
		self.plugin._finishUpdateCheck(
			self.plugin._generation,
			self.plugin._updateOperationToken,
			UpdateCheckResult(UpdateStatus.UPDATED, "2.6.75", "2.6.75", contentChanged=True),
			worker,
		)
		self.assertTrue(
			any(
				"2.6.75 was replaced with the official copy" in message
				and "next time you launch WhatsApp" in message
				for message in self.uiMessages
			),
		)
		self.assertEqual(self.plugin.lastResult.code, "update.refreshed")

	def test_second_update_waits_until_the_first_terminal_status_is_delivered(self) -> None:
		from globalPlugins.whatsappWebPlusCompanion.updater import UpdateCheckResult, UpdateStatus

		scheduled: list[object] = []

		def recordCallLater(delay, function, *args, **kwargs):
			scheduled.append(lambda: function(*args, **kwargs))

		with (
			mock.patch.object(self.wx, "CallLater", side_effect=recordCallLater),
			mock.patch.object(self.module.threading.Thread, "start"),
		):
			self.plugin._startUpdateCheck()
			firstToken = self.plugin._updateOperationToken
			firstWorker = self.plugin._updateWorker
			self.plugin._finishUpdateCheck(
				self.plugin._generation,
				firstToken,
				UpdateCheckResult(UpdateStatus.CURRENT, "2.6.74", "2.6.74"),
				firstWorker,
			)
			self.plugin._startUpdateCheck()
			self.assertEqual(self.plugin._updateOperationToken, firstToken)
			self.assertTrue(self.plugin._updateTerminalPending)

			for callback in list(scheduled):
				callback()
			self.assertEqual(
				self.uiMessages,
				[
					"WhatsApp Web Plus is up to date (2.6.74).",
				],
			)
			self.assertFalse(self.plugin._updateTerminalPending)
			self.plugin._startUpdateCheck()
			secondToken = self.plugin._updateOperationToken
			secondWorker = self.plugin._updateWorker
			self.plugin._finishUpdateCheck(
				self.plugin._generation,
				secondToken,
				UpdateCheckResult(UpdateStatus.CURRENT, "2.6.75", "2.6.75"),
				secondWorker,
			)
			scheduled[-1]()

		self.assertEqual(
			self.uiMessages[-1],
			"WhatsApp Web Plus is up to date (2.6.75).",
		)

	def test_restricted_update_context_is_saved_as_last_result(self) -> None:
		with mock.patch.object(self.module.globalVars.appArgs, "secure", True):
			self.plugin._startUpdateCheck()
		self.assertTrue(
			any("can't be updated from this NVDA session" in message for message in self.uiMessages),
		)
		self.assertEqual(self.plugin.lastResult.code, "update.context")

	def test_signed_update_failures_are_owned_once_and_preserve_safe_diagnostics(self) -> None:
		from globalPlugins.whatsappWebPlusCompanion.updater import UpdateCheckResult, UpdateStatus

		for errorCode in (
			"signatureInvalid",
			"keyUnknown",
			"replay",
			"downgrade",
			"assetMismatch",
			"verifierUnavailable",
		):
			with self.subTest(errorCode=errorCode):
				self.uiMessages.clear()
				_FakeNativeDialog.instances.clear()
				# Unit tests never touch the real per-user registry journal.
				self.module.recoverPendingRegistryStateAtStartup = lambda: None
				plugin = self.module.GlobalPlugin()
				with (
					mock.patch.object(self.module.threading.Thread, "start"),
					mock.patch.object(plugin, "_deliverCompanionAnnouncement") as companionDelivery,
					mock.patch.object(plugin, "_speakAndQueueBraille") as browserDelivery,
				):
					plugin._startUpdateCheck()
					worker = plugin._updateWorker
					self.assertIsNotNone(worker)
					plugin._finishUpdateCheck(
						plugin._generation,
						plugin._updateOperationToken,
						UpdateCheckResult(UpdateStatus.ERROR, "2.6.76", errorCode=errorCode),
						worker,
					)
					companionDelivery.assert_not_called()
					browserDelivery.assert_not_called()

				self.assertEqual(len(self.uiMessages), 2)
				self.assertEqual(
					self.uiMessages[0],
					"Checking for WhatsApp Web Plus updates.",
				)
				self.assertIn("Your current version was kept.", self.uiMessages[1])
				if errorCode == "keyUnknown":
					self.assertIn("Update WhatsApp Companion, then try again", self.uiMessages[1])
				self.assertEqual(plugin.lastResult.code, f"update.{errorCode}")
				self.assertEqual(plugin.lastResult.values["errorCode"], errorCode)
				self.assertEqual(_FakeNativeDialog.instances, [])

				self.uiMessages.clear()
				plugin.script_reportLastResult(None)
				self.assertEqual(len(self.uiMessages), 1)
				self.assertIn(f"Technical error code: {errorCode}.", self.uiMessages[0])
				plugin.terminate()

	def test_termination_suppresses_delayed_signed_update_result(self) -> None:
		from globalPlugins.whatsappWebPlusCompanion.updater import UpdateCheckResult, UpdateStatus

		scheduled: list[object] = []

		def recordCallLater(delay, function, *args, **kwargs):
			scheduled.append(lambda: function(*args, **kwargs))

		with (
			mock.patch.object(self.wx, "CallLater", side_effect=recordCallLater),
			mock.patch.object(self.module.threading.Thread, "start"),
		):
			self.plugin._startUpdateCheck()
			worker = self.plugin._updateWorker
			self.plugin._finishUpdateCheck(
				self.plugin._generation,
				self.plugin._updateOperationToken,
				UpdateCheckResult(UpdateStatus.ERROR, "2.6.76", errorCode="signatureInvalid"),
				worker,
			)
			self.assertIsNotNone(self.plugin.lastResult)
			self.plugin.terminate()
			for callback in scheduled:
				callback()

		self.assertEqual(self.uiMessages, [])


_STABLE_EXE = (
	r"C:\Program Files\WindowsApps\5319275A.WhatsAppDesktop_2.2642.101.0_x64__cv1g1gvanyjgm\WhatsApp.Root.exe"
)
_BETA_EXE = (
	r"C:\Program Files\WindowsApps\5319275A.51895FA4EA97F_2.2643.3.0_x64__cv1g1gvanyjgm\WhatsApp.Root.exe"
)


class TwoChannelPluginTests(unittest.TestCase):
	@classmethod
	def setUpClass(cls) -> None:
		_installFakeEnvironment()

	def setUp(self) -> None:
		pluginModule = sys.modules["globalPlugins.whatsappWebPlusCompanion"]
		self.module = pluginModule
		pluginModule.recoverPendingRegistryStateAtStartup = lambda: None
		self.plugin = pluginModule.GlobalPlugin()
		self.plugin._brailleMessages = mock.Mock()
		from globalPlugins.whatsappWebPlusCompanion.security import AnnouncementGuard

		self.plugin._announcementGuard = AnnouncementGuard(lambda: True)

	def tearDown(self) -> None:
		self.plugin.controller.stop()

	def _result(self, key, channel, **values):
		from globalPlugins.whatsappWebPlusCompanion.models import OperationResult

		return OperationResult(True, key, key, {"channel": channel, **values})

	def _connect(self, channel, session):
		invalidate = self._result(
			"companion.invalidate",
			channel,
			session=session,
			generation=1,
			context=f"{session}:1",
			source="status",
		)
		self.assertTrue(self.plugin._applyCompanionInvalidation(invalidate))

	def _announcement(self, channel, session, sequence, text):
		return self._result(
			"companion.announcement",
			channel,
			session=session,
			generation=1,
			context=f"{session}:1",
			sequence=sequence,
			source="status",
			privacy=False,
			text=text,
		)

	def test_stable_and_beta_keep_their_own_announcement_order(self) -> None:
		self._connect("stable", "s")
		self._connect("beta", "b")
		with (
			mock.patch.object(self.plugin, "_speakAndQueueBraille") as speak,
			mock.patch.object(self.plugin, "_foregroundChannel", return_value=None),
		):
			self.assertTrue(
				self.plugin._deliverCompanionAnnouncement(self._announcement("stable", "s", 1, "One"))
			)
			self.assertTrue(
				self.plugin._deliverCompanionAnnouncement(self._announcement("beta", "b", 1, "Two"))
			)
			self.assertFalse(
				self.plugin._deliverCompanionAnnouncement(self._announcement("beta", "b", 1, "Again"))
			)
			# A reconnect of Beta does not reset Stable.
			self._connect("beta", "b2")
			self.assertTrue(
				self.plugin._deliverCompanionAnnouncement(self._announcement("beta", "b2", 1, "Three"))
			)
			self.assertFalse(
				self.plugin._deliverCompanionAnnouncement(self._announcement("stable", "s", 1, "Old"))
			)
		self.assertEqual([call.args[0] for call in speak.call_args_list], ["One", "Two", "Three"])

	def test_whatsapp_in_the_background_is_quiet_while_the_other_one_is_in_front(self) -> None:
		from globalPlugins.whatsappWebPlusCompanion.models import Channel

		self._connect("stable", "s")
		self._connect("beta", "b")
		with (
			mock.patch.object(self.plugin, "_speakAndQueueBraille") as speak,
			mock.patch.object(self.plugin, "_foregroundChannel", return_value=Channel.STABLE),
		):
			self.assertTrue(
				self.plugin._deliverCompanionAnnouncement(self._announcement("beta", "b", 1, "Beta"))
			)
			self.assertTrue(
				self.plugin._deliverCompanionAnnouncement(self._announcement("stable", "s", 1, "Stable"))
			)
		self.assertEqual([call.args[0] for call in speak.call_args_list], ["Stable"])
		# The skipped Beta message is consumed, not replayed when Beta comes to the front.
		self.assertEqual(self.plugin._delivery("beta").lastSequence, 1)

	def test_closing_one_channel_keeps_the_other_channel_session(self) -> None:
		self._connect("stable", "s")
		self._connect("beta", "b")
		with mock.patch.object(self.module.commandFeedback, "message"):
			self.plugin._reportIfCurrent(self.plugin._generation, self._result("package.closed", "beta"))
		self.assertEqual(self.plugin._delivery("stable").session, "s")
		self.assertEqual(self.plugin._delivery("beta").session, "")

	def test_launching_a_channel_that_already_runs_names_that_channel(self) -> None:
		from globalPlugins.whatsappWebPlusCompanion.models import Channel

		with (
			mock.patch.object(self.plugin.controller, "channelActive", return_value=True),
			mock.patch.object(self.plugin.controller, "start") as start,
			mock.patch.object(self.plugin, "_announce") as announce,
		):
			self.plugin._launch(Channel.BETA)
		start.assert_not_called()
		announce.assert_called_once_with("WhatsApp Beta is already running with WhatsApp Companion.")

	def test_launch_report_is_tagged_with_its_channel(self) -> None:
		from globalPlugins.whatsappWebPlusCompanion.models import Channel, OperationResult

		with (
			mock.patch.object(self.plugin.controller, "channelForToken", return_value=Channel.BETA),
			mock.patch.object(self.plugin, "_queueReport", return_value=True) as queue,
		):
			self.plugin._queueLaunchReport(OperationResult(True, "cdp.restored", "cdp.restored", {}), 7)
		self.assertEqual(queue.call_args.args[0].values, {"channel": "beta"})


class AutoConnectPluginTests(unittest.TestCase):
	@classmethod
	def setUpClass(cls) -> None:
		_installFakeEnvironment()

	def setUp(self) -> None:
		pluginModule = sys.modules["globalPlugins.whatsappWebPlusCompanion"]
		self.module = pluginModule
		pluginModule.recoverPendingRegistryStateAtStartup = lambda: None
		self.plugin = pluginModule.GlobalPlugin()
		self.patches = [
			mock.patch.object(pluginModule.settings, "autoConnect", return_value=True),
			mock.patch.object(self.plugin, "_recordingAllowed", return_value=True),
			mock.patch.object(pluginModule.nativeProbes, "processAgeSeconds", return_value=3.0),
			mock.patch.object(self.plugin, "_announce"),
		]
		for item in self.patches:
			item.start()

	def tearDown(self) -> None:
		for item in self.patches:
			item.stop()
		self.plugin.controller.stop()

	@staticmethod
	def _window(pid=4321, path=_STABLE_EXE, name="whatsapp_root"):
		return types.SimpleNamespace(
			processID=pid, appModule=types.SimpleNamespace(appName=name, appPath=path)
		)

	def _foreground(self, window):
		nextHandler = mock.Mock()
		self.plugin.event_foreground(window, nextHandler)
		nextHandler.assert_called_once_with()

	def test_whatsapp_opened_by_the_user_is_reopened_once_for_its_channel(self) -> None:
		from globalPlugins.whatsappWebPlusCompanion.models import Channel

		with mock.patch.object(self.plugin.controller, "start", return_value=True) as start:
			self._foreground(self._window(path=_BETA_EXE))
			self._foreground(self._window(path=_BETA_EXE))
		start.assert_called_once_with(Channel.BETA, replaceRecent=True)
		self.assertEqual(self.plugin.selectedChannel, Channel.BETA)
		self.plugin._announce.assert_called_once_with(
			"Reopening WhatsApp Beta with WhatsApp Companion. Please wait.",
		)

	def test_nothing_is_reopened_when_it_should_not_be(self) -> None:
		from globalPlugins.whatsappWebPlusCompanion.models import Channel

		cases = {
			"setting off": lambda: mock.patch.object(self.module.settings, "autoConnect", return_value=False),
			"opened long ago": lambda: mock.patch.object(
				self.module.nativeProbes,
				"processAgeSeconds",
				return_value=120.0,
			),
			"age unknown": lambda: mock.patch.object(
				self.module.nativeProbes, "processAgeSeconds", return_value=None
			),
			"already connected": lambda: mock.patch.object(
				self.plugin.controller,
				"channelActive",
				return_value=True,
			),
			"force closing": lambda: mock.patch.object(
				type(self.plugin.controller),
				"forceClosing",
				new_callable=mock.PropertyMock,
				return_value=True,
			),
		}
		for pid, (name, makePatch) in enumerate(cases.items(), start=100):
			with self.subTest(name), makePatch(), mock.patch.object(self.plugin.controller, "start") as start:
				self._foreground(self._window(pid=pid))
				start.assert_not_called()
		for name, window in (
			("other app", self._window(pid=200, path=r"C:\Windows\notepad.exe", name="notepad")),
			("unknown WhatsApp build", self._window(pid=201, path=r"C:\Tools\WhatsApp.exe")),
		):
			with self.subTest(name), mock.patch.object(self.plugin.controller, "start") as start:
				self._foreground(window)
				start.assert_not_called()
		self.plugin._autoConnectBlocked.add(Channel.STABLE)
		with mock.patch.object(self.plugin.controller, "start") as start:
			self._foreground(self._window(pid=300))
			start.assert_not_called()

	def test_failed_automatic_connection_stays_quiet_when_whatsapp_was_open_before(self) -> None:
		from globalPlugins.whatsappWebPlusCompanion.models import Channel, OperationResult

		self.plugin._autoConnectTokens[9] = Channel.STABLE
		with mock.patch.object(self.plugin, "_queueReport") as queue:
			self.assertTrue(
				self.plugin._queueLaunchReport(
					OperationResult(False, "autoConnect.tooLate", "autoConnect.tooLate", {}),
					9,
				),
			)
		queue.assert_not_called()
		self.assertIn(Channel.STABLE, self.plugin._autoConnectBlocked)
		# A manual launch lifts the block again.
		with mock.patch.object(self.plugin.controller, "start", return_value=True):
			self.plugin._launch(Channel.STABLE)
		self.assertNotIn(Channel.STABLE, self.plugin._autoConnectBlocked)

	def test_other_automatic_failures_are_still_reported(self) -> None:
		from globalPlugins.whatsappWebPlusCompanion.models import Channel, OperationResult

		self.plugin._autoConnectTokens[9] = Channel.BETA
		failure = OperationResult(False, "autoConnect.closeFailed", "autoConnect.closeFailed", {})
		with mock.patch.object(self.plugin, "_queueReport", return_value=True) as queue:
			self.plugin._queueLaunchReport(failure, 9)
		queue.assert_called_once()
		self.assertIn(Channel.BETA, self.plugin._autoConnectBlocked)

	def test_toggle_saves_the_setting_and_says_the_new_state(self) -> None:
		with (
			mock.patch.object(self.module.settings, "autoConnect", return_value=False),
			mock.patch.object(self.module.settings, "setAutoConnect", return_value=True) as save,
		):
			self.plugin._toggleAutoConnect()
		save.assert_called_once_with(True)
		self.assertTrue(self.plugin._announce.call_args.args[0].startswith("Automatic connection on."))


if __name__ == "__main__":
	unittest.main()
