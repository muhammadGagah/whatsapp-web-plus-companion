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

		def Destroy(self) -> None:
			pass

	class FakeMenu:
		def __init__(self) -> None:
			self.entries: list = []

		def Append(self, itemId, label: str, helpText: str) -> FakeMenuItem:
			item = FakeMenuItem(label)
			self.entries.append(item)
			return item

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
		"speech": types.SimpleNamespace(speak=lambda commands: None),
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
		self.plugin = pluginModule.GlobalPlugin()

	def test_diagnosis_usable_reports_not_needed_without_uac(self) -> None:
		from globalPlugins.whatsappWebPlusCompanion.registryRepair import RegistryPermissionStatus

		with mock.patch.object(
			self.module,
			"diagnoseRegistryPermissions",
			return_value=RegistryPermissionStatus.USABLE,
		):
			self.plugin._startRegistryDiagnosis()
			for _ in range(100):
				if (
					"The required WebView2 policy permissions are already available. No changes were made."
					in self.uiMessages
				):
					break
				time.sleep(0.001)

		self.assertIn("Checking WebView2 policy permissions.", self.uiMessages)
		self.assertIn(
			"The required WebView2 policy permissions are already available. No changes were made.",
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

		self.assertIn("Checking WebView2 policy permissions.", self.uiMessages)
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
		self.assertIn("Active calls and file transfers will be interrupted", dialog.message)
		self.assertIn("review a separate confirmation", dialog.message)
		self.assertEqual(dialog.noLabel, "&Keep WhatsApp open")
		self.assertEqual(dialog.yesLabel, "&Force close WhatsApp and continue")
		self.assertTrue(dialog.defaultNo)
		self.assertTrue(dialog.fallbackNo)
		self.assertNotIn("Close WhatsApp before diagnosing WebView2 policy permissions.", self.uiMessages)

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

	def test_standalone_force_close_dialog_has_clear_copy_and_safe_default(self) -> None:
		self.plugin._reviewForceClose()

		dialog = self.plugin._dialog
		self.assertIsNotNone(dialog)
		self.assertEqual(dialog.title, "Force close WhatsApp applications?")
		self.assertIn("Active calls and file transfers will be interrupted", dialog.message)
		self.assertIn("Text you have not sent may be lost", dialog.message)
		self.assertEqual(dialog.noLabel, "&Keep WhatsApp open")
		self.assertEqual(dialog.yesLabel, "&Force close")
		self.assertTrue(dialog.defaultNo)
		self.assertTrue(dialog.fallbackNo)

		with mock.patch.object(self.plugin.controller, "forceClose", return_value=True) as forceClose:
			dialog.callback(None)
		forceClose.assert_called_once_with()
		self.assertIn(
			"Closing all running WhatsApp Stable and Beta apps from Microsoft Store.",
			self.uiMessages,
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
			"WhatsApp Stable is still loading with WhatsApp Companion. Please wait.",
			self.uiMessages,
		)
		self.uiMessages.clear()
		self.plugin.script_reportLastResult(None)
		self.assertEqual(
			self.uiMessages,
			["WhatsApp Stable is still loading with WhatsApp Companion. Please wait."],
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
				if (
					"The required WebView2 policy permissions are already available. No changes were made."
					in self.uiMessages
				):
					break
				time.sleep(0.001)
		self.assertIn("Checking WebView2 policy permissions.", self.uiMessages)

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
				if (
					"The required WebView2 policy permissions are already available. No changes were made."
					in self.uiMessages
				):
					break
				time.sleep(0.001)
		self.assertIsNone(self.plugin._dialog)
		self.assertIn("Checking WebView2 policy permissions.", self.uiMessages)
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
		self.assertTrue(any("computer-wide WebView2 policy setting" in text for text in self.uiMessages))

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
			"The required WebView2 policy permissions are already available. No changes were made.",
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
			["The WhatsApp Web Plus userscript is up to date at version 2.6.75."],
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
				"updated from version 2.6.74 to 2.6.75" in message
				and "next time WhatsApp is launched through the Companion" in message
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
				"refreshed at version 2.6.75" in message
				and "official script differed" in message
				and "next time WhatsApp is launched through the Companion" in message
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
					"The WhatsApp Web Plus userscript is up to date at version 2.6.74.",
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
			"The WhatsApp Web Plus userscript is up to date at version 2.6.75.",
		)

	def test_restricted_update_context_is_saved_as_last_result(self) -> None:
		with mock.patch.object(self.module.globalVars.appArgs, "secure", True):
			self.plugin._startUpdateCheck()
		self.assertTrue(
			any("cannot be updated in this NVDA context" in message for message in self.uiMessages),
		)
		self.assertEqual(self.plugin.lastResult.code, "update.context")


if __name__ == "__main__":
	unittest.main()
