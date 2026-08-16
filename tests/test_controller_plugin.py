import ast
import pathlib
import threading
import time
import unittest
from unittest.mock import patch

from _path import installPackagePath

installPackagePath()

from globalPlugins.whatsappWebPlusCompanion.controller import Controller
from globalPlugins.whatsappWebPlusCompanion.models import (
	Channel,
	LoaderError,
	OperationResult,
	OperationState,
)


class ControllerPluginTests(unittest.TestCase):
	@patch("globalPlugins.whatsappWebPlusCompanion.controller.log.warning")
	def test_loader_error_logs_safe_detail_and_still_notifies(self, warning) -> None:
		notifications: list[OperationResult] = []

		def operation(channel, cancel, state, registerCloser, report):
			raise LoaderError("endpoint.timeout", "socketTimeout")

		controller = Controller(operation, notifications.append)
		self.assertTrue(controller.start(Channel.BETA))
		for _ in range(100):
			if notifications:
				break
			time.sleep(0.001)
		warning.assert_called_once_with(
			"WhatsApp Companion launch failed: code=%s detail=%s",
			"endpoint.timeout",
			"socketTimeout",
		)
		self.assertEqual([result.code for result in notifications], ["endpoint.timeout"])

	def test_controller_serializes_and_reports_attached_while_worker_remains_alive(self) -> None:
		gate = threading.Event()
		notifications: list[OperationResult] = []

		def operation(channel, cancel, state, registerCloser, report):
			state(OperationState.ATTACHED)
			gate.wait(1)
			return OperationResult(True, "done", "active", {})

		controller = Controller(operation, notifications.append)
		self.assertTrue(controller.start(Channel.BETA))
		self.assertFalse(controller.start(Channel.STABLE))
		for _ in range(100):
			if notifications:
				break
			time.sleep(0.001)
		self.assertTrue(notifications[0].ok)
		self.assertIsNotNone(controller.worker)
		self.assertTrue(controller.worker.daemon)
		gate.set()

	def test_stop_invokes_registered_interrupts_without_waiting_for_worker(self) -> None:
		closed: list[bool] = []
		releaseWorker = threading.Event()
		submissionStarted = threading.Event()

		def operation(channel, cancel, state, registerCloser, report):
			registerCloser(lambda: closed.append(True))

			def blockedSubmission():
				submissionStarted.set()
				releaseWorker.wait(2)

			cancel.submitUnlessSet(blockedSubmission)
			return OperationResult(False, "cancelled", "operation.cancelled", {})

		controller = Controller(operation, lambda result: None)
		controller.start(Channel.BETA)
		self.assertTrue(submissionStarted.wait(1.0))
		started = time.monotonic()
		controller.stop()
		self.assertLess(time.monotonic() - started, 0.1)
		self.assertEqual(closed, [True])
		releaseWorker.set()

	def test_normal_package_close_is_reported_as_success_and_returns_to_idle(self) -> None:
		notifications: list[OperationResult] = []

		def operation(channel, cancel, state, registerCloser, report):
			state(OperationState.ATTACHED)
			return OperationResult(
				True,
				"package.closed",
				"package.closed",
				{"channel": channel.value},
			)

		controller = Controller(operation, notifications.append)
		self.assertTrue(controller.start(Channel.STABLE))
		for _ in range(100):
			with controller.lock:
				if controller.worker is None:
					break
			time.sleep(0.001)
		self.assertEqual([result.messageKey for result in notifications], ["active", "package.closed"])
		self.assertTrue(notifications[-1].ok)
		self.assertEqual(controller.state, OperationState.IDLE)

	def test_companion_announcement_is_forwarded_without_ending_operation(self) -> None:
		notifications: list[OperationResult] = []

		def operation(channel, cancel, state, registerCloser, report):
			report(
				OperationResult(
					True,
					"companion.announcement",
					"companion.announcement",
					{"text": "Unread message not found"},
				),
			)
			return OperationResult(True, "package.closed", "package.closed", {"channel": channel.value})

		controller = Controller(operation, notifications.append)
		self.assertTrue(controller.start(Channel.BETA))
		for _ in range(100):
			with controller.lock:
				if controller.worker is None:
					break
			time.sleep(0.001)
		self.assertEqual(
			[result.messageKey for result in notifications],
			["companion.announcement", "package.closed"],
		)

	def test_force_close_cancels_launch_suppresses_stale_result_and_remains_reusable(self) -> None:
		closerCalled = threading.Event()
		notifications: list[OperationResult] = []
		operationOrder: list[str] = []

		def operation(channel, cancel, state, registerCloser, report):
			registerCloser(closerCalled.set)
			cancel.wait(1)
			operationOrder.append("launch-finished")
			return OperationResult(True, "package.closed", "package.closed", {"channel": channel.value})

		def forceCloseOperation():
			operationOrder.append("force-close-started")
			return OperationResult(
				True,
				"processes.closed",
				"processes.closed",
				{"closedCount": 2},
			)

		controller = Controller(operation, notifications.append, forceCloseOperation)
		self.assertTrue(controller.start(Channel.BETA))
		for _ in range(100):
			with controller.lock:
				if controller.closers:
					break
			time.sleep(0.001)
		self.assertTrue(controller.forceClose())
		self.assertFalse(controller.start(Channel.STABLE))
		self.assertTrue(closerCalled.wait(1))
		for _ in range(100):
			with controller.lock:
				if controller.worker is None and controller.forceCloseWorker is None and notifications:
					break
			time.sleep(0.001)
		self.assertEqual(operationOrder, ["launch-finished", "force-close-started"])
		self.assertEqual([result.messageKey for result in notifications], ["processes.closed"])
		self.assertTrue(controller.start(Channel.STABLE))
		controller.stop()

	def test_force_close_rejects_a_second_request_while_pending(self) -> None:
		gate = threading.Event()

		def operation(channel, cancel, state, registerCloser, report):
			return OperationResult(True, "done", "package.closed", {"channel": channel.value})

		def forceCloseOperation():
			gate.wait(1)
			return OperationResult(True, "processes.none", "processes.none", {})

		controller = Controller(operation, lambda result: None, forceCloseOperation)
		self.assertTrue(controller.forceClose())
		self.assertTrue(controller.forceClosing)
		self.assertFalse(controller.forceClose())
		gate.set()
		controller.stop()

	def test_force_close_completion_runs_after_controller_is_idle(self) -> None:
		notifications: list[OperationResult] = []
		completionState: list[tuple[str, bool]] = []
		controller: Controller

		def forceCloseOperation():
			return OperationResult(True, "processes.closed", "processes.closed", {"closedCount": 1})

		def onComplete(result: OperationResult) -> None:
			completionState.append((result.messageKey, controller.forceClosing))

		controller = Controller(
			lambda channel, cancel, state, registerCloser, report: OperationResult(
				True,
				"done",
				"package.closed",
				{"channel": channel.value},
			),
			notifications.append,
			forceCloseOperation,
		)
		self.assertTrue(controller.forceClose(onComplete))
		for _ in range(100):
			if completionState:
				break
			time.sleep(0.001)

		self.assertEqual([result.messageKey for result in notifications], ["processes.closed"])
		self.assertEqual(completionState, [("processes.closed", False)])
		controller.stop()

	def test_force_close_is_rejected_while_registry_repair_is_active(self) -> None:
		repairStarted = threading.Event()
		releaseRepair = threading.Event()

		def repairOperation() -> OperationResult:
			repairStarted.set()
			releaseRepair.wait(1)
			return OperationResult(True, "registry.repair.succeeded", "registry.repair.succeeded", {})

		controller = Controller(
			lambda channel, cancel, state, registerCloser, report: OperationResult(
				True,
				"done",
				"package.closed",
				{"channel": channel.value},
			),
			lambda result: None,
			lambda: OperationResult(True, "processes.none", "processes.none", {}),
		)
		self.assertTrue(controller.startRegistryRepair(repairOperation))
		self.assertTrue(repairStarted.wait(1))
		self.assertFalse(controller.forceClose())
		releaseRepair.set()
		controller.stop()

	def test_force_close_suppresses_late_launch_state_and_announcements(self) -> None:
		launchPaused = threading.Event()
		releaseLaunch = threading.Event()
		notifications: list[OperationResult] = []

		def operation(channel, cancel, state, registerCloser, report):
			launchPaused.set()
			releaseLaunch.wait(1)
			state(OperationState.ATTACHED)
			report(
				OperationResult(
					True,
					"companion.announcement",
					"companion.announcement",
					{"text": "stale"},
				),
			)
			return OperationResult(True, "package.closed", "package.closed", {"channel": channel.value})

		def forceCloseOperation():
			return OperationResult(True, "processes.closed", "processes.closed", {"closedCount": 1})

		controller = Controller(operation, notifications.append, forceCloseOperation)
		self.assertTrue(controller.start(Channel.STABLE))
		self.assertTrue(launchPaused.wait(1))
		self.assertTrue(controller.forceClose())
		releaseLaunch.set()
		for _ in range(100):
			with controller.lock:
				if controller.forceCloseWorker is None and notifications:
					break
			time.sleep(0.001)
		self.assertEqual([result.messageKey for result in notifications], ["processes.closed"])
		controller.stop()

	def test_force_close_invalidates_notification_queued_for_gui_delivery(self) -> None:
		deliveryQueued = threading.Event()
		releaseDelivery = threading.Event()
		notifications: list[OperationResult] = []
		controller: Controller

		def operation(channel, cancel, state, registerCloser, report):
			report(OperationResult(True, "companion.announcement", "companion.announcement", {}))
			return OperationResult(False, "operation.cancelled", "operation.cancelled", {})

		def launchNotify(result, token):
			deliveryQueued.set()
			releaseDelivery.wait(1)
			if not controller.launchTokenIsActive(token):
				return False
			notifications.append(result)
			return True

		def forceCloseOperation():
			return OperationResult(True, "processes.closed", "processes.closed", {"closedCount": 1})

		controller = Controller(
			operation,
			notifications.append,
			forceCloseOperation,
			launchNotify,
		)
		self.assertTrue(controller.start(Channel.STABLE))
		self.assertTrue(deliveryQueued.wait(1))
		self.assertTrue(controller.forceClose())
		releaseDelivery.set()
		for _ in range(100):
			with controller.lock:
				if controller.forceCloseWorker is None and notifications:
					break
			time.sleep(0.001)
		self.assertEqual([result.messageKey for result in notifications], ["processes.closed"])
		controller.stop()

	def test_force_close_invalidates_terminal_result_after_worker_reference_clears(self) -> None:
		deliveryQueued = threading.Event()
		releaseDelivery = threading.Event()
		deliveryFinished = threading.Event()
		notifications: list[OperationResult] = []
		controller: Controller

		def operation(channel, cancel, state, registerCloser, report):
			return OperationResult(False, "endpoint.timeout", "endpoint.timeout", {})

		def launchNotify(result, token):
			deliveryQueued.set()
			releaseDelivery.wait(1)
			try:
				if not controller.launchTokenIsActive(token):
					return False
				notifications.append(result)
				return True
			finally:
				deliveryFinished.set()

		def forceCloseOperation():
			return OperationResult(True, "processes.closed", "processes.closed", {"closedCount": 1})

		controller = Controller(
			operation,
			notifications.append,
			forceCloseOperation,
			launchNotify,
		)
		self.assertTrue(controller.start(Channel.STABLE))
		self.assertTrue(deliveryQueued.wait(1))
		with controller.lock:
			self.assertIsNone(controller.worker)
		self.assertTrue(controller.forceClose())
		for _ in range(100):
			with controller.lock:
				if controller.forceCloseWorker is None and notifications:
					break
			time.sleep(0.001)
		releaseDelivery.set()
		self.assertTrue(deliveryFinished.wait(1))
		self.assertEqual([result.messageKey for result in notifications], ["processes.closed"])
		controller.stop()

	def test_stop_cancels_force_close_queued_behind_launch(self) -> None:
		launchPaused = threading.Event()
		releaseLaunch = threading.Event()
		cleanupCalled = threading.Event()

		def operation(channel, cancel, state, registerCloser, report):
			launchPaused.set()
			releaseLaunch.wait(1)
			return OperationResult(False, "operation.cancelled", "operation.cancelled", {})

		def forceCloseOperation():
			cleanupCalled.set()
			return OperationResult(True, "processes.none", "processes.none", {})

		controller = Controller(operation, lambda result: None, forceCloseOperation)
		self.assertTrue(controller.start(Channel.STABLE))
		self.assertTrue(launchPaused.wait(1))
		self.assertTrue(controller.forceClose())
		controller.stop()
		releaseLaunch.set()
		for _ in range(100):
			with controller.lock:
				if controller.forceCloseWorker is None:
					break
			time.sleep(0.001)
		self.assertFalse(cleanupCalled.is_set())

	def test_commands_are_on_demand_and_have_no_default_gesture(self) -> None:
		path = pathlib.Path(__file__).parents[1] / "addon/globalPlugins/whatsappWebPlusCompanion/__init__.py"
		source = path.read_text(encoding="utf-8")
		tree = ast.parse(source)
		decorators = [
			ast.unparse(node.decorator_list[0])
			for node in ast.walk(tree)
			if isinstance(node, ast.FunctionDef) and node.name.startswith("script_")
		]
		commandNames = {
			node.name
			for node in ast.walk(tree)
			if isinstance(node, ast.FunctionDef) and node.name.startswith("script_")
		}
		self.assertEqual(
			commandNames,
			{
				"script_launchStable",
				"script_launchBeta",
				"script_launchSelected",
				"script_forceCloseWhatsApp",
				"script_reportLastResult",
				"script_checkForScriptUpdates",
				"script_diagnoseAndRepairPermissions",
			},
		)
		self.assertTrue(all("speakOnDemand=True" in item for item in decorators))
		self.assertTrue(all("gesture=" not in item for item in decorators))
		self.assertIn('if result.messageKey == "package.closed":', source)
		self.assertIn('if result.messageKey != "operation.busy":', source)
		self.assertIn('if result.messageKey == "companion.announcement":', source)
		self.assertIn('if result.messageKey == "companion.invalidate":', source)
		self.assertIn("LangChangeCommand(language.replace", source)
		self.assertIn("BrailleMessageQueue(", source)
		self.assertIn("self._brailleMessages.enqueue(text, source)", source)
		self.assertIn("completed.wait(_DELIVERY_TIMEOUT)", source)
		self.assertIn("self._updateCancel.set()", source)
		self.assertIn("if self._disposed:", source)
		self.assertIn("worker is not self._updateWorker", source)
		self.assertIn("except RuntimeError:", source)

	def test_confirmation_dialogs_have_singleton_and_safe_fallback_guards(self) -> None:
		path = pathlib.Path(__file__).parents[1] / "addon/globalPlugins/whatsappWebPlusCompanion/__init__.py"
		source = path.read_text(encoding="utf-8")
		self.assertIn("if self._focusExistingDialog():", source)
		self.assertIn("wx.EVT_WINDOW_DESTROY", source)
		self.assertIn("self._dialog.Close()", source)
		self.assertIn("fallbackAction=True", source)
		self.assertIn('label=_("&Keep WhatsApp open")', source)
		self.assertIn('_("Force close WhatsApp applications?")', source)
		self.assertIn('label=_("&Force close")', source)
		self.assertIn("defaultFocus=True", source)
		self.assertIn("not self.controller.launchTokenIsActive(launchToken)", source)
		self.assertIn(
			"if self._updateCheckPending or self._updateTerminalPending:",
			source,
		)
		self.assertIn("self._updateTerminalPending = True", source)
		self.assertNotIn("script_openScriptUpdate", source)
		self.assertNotIn("os.startfile", source)

	def test_repair_serializes_with_launch_and_delivers_once(self) -> None:
		notifications: list[OperationResult] = []
		release = threading.Event()

		def operation(channel, cancel, state, registerCloser, report):
			return OperationResult(False, "internal.error", "internal.error", {})

		def run():
			release.wait(1)
			return OperationResult(True, "registry.repair.repaired", "registry.repair.repaired", {})

		controller = Controller(operation, notifications.append)
		self.assertTrue(controller.startRegistryRepair(run))
		self.assertFalse(controller.startRegistryRepair(run))
		self.assertFalse(controller.start(Channel.STABLE))
		release.set()
		for _ in range(100):
			with controller.lock:
				if controller.repairWorker is None:
					break
			time.sleep(0.001)
		self.assertEqual([result.messageKey for result in notifications], ["registry.repair.repaired"])
		self.assertTrue(controller.start(Channel.STABLE))
		controller.stop()

	def test_repair_rejected_while_launch_active(self) -> None:
		paused = threading.Event()
		release = threading.Event()
		notifications: list[OperationResult] = []

		def operation(channel, cancel, state, registerCloser, report):
			paused.set()
			release.wait(1)
			return OperationResult(False, "operation.cancelled", "operation.cancelled", {})

		controller = Controller(operation, notifications.append)
		self.assertTrue(controller.start(Channel.STABLE))
		self.assertTrue(paused.wait(1))
		self.assertFalse(controller.startRegistryRepair(lambda: OperationResult(True, "a", "a", {})))
		release.set()
		for _ in range(100):
			with controller.lock:
				if controller.worker is None:
					break
			time.sleep(0.001)
		controller.stop()

	def test_repair_maps_loader_error_values_and_remains_reusable(self) -> None:
		notifications: list[OperationResult] = []
		attempts = 0

		def run():
			nonlocal attempts
			attempts += 1
			if attempts == 1:
				raise LoaderError("registry.repair.managedDeny", "stage=helper.exit", {"conflict": True})
			return OperationResult(True, "registry.repair.repaired", "registry.repair.repaired", {})

		controller = Controller(lambda *a: None, notifications.append)
		self.assertTrue(controller.startRegistryRepair(run))
		for _ in range(100):
			with controller.lock:
				if controller.repairWorker is None:
					break
			time.sleep(0.001)
		self.assertTrue(controller.startRegistryRepair(run))
		for _ in range(100):
			with controller.lock:
				if controller.repairWorker is None:
					break
			time.sleep(0.001)
		self.assertEqual(
			[result.code for result in notifications],
			["registry.repair.managedDeny", "registry.repair.repaired"],
		)
		self.assertEqual(notifications[0].values, {"conflict": True})
		controller.stop()
