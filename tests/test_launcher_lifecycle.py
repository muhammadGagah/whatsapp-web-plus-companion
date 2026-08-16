import unittest
from unittest.mock import ANY, MagicMock, patch

from _path import installPackagePath

installPackagePath()

from globalPlugins.whatsappWebPlusCompanion import launcher
from globalPlugins.whatsappWebPlusCompanion.cdp import (
	CompanionAnnouncement,
	CompanionAnnouncementBatch,
	Target,
)
from globalPlugins.whatsappWebPlusCompanion.models import (
	Channel,
	LoaderError,
	OperationResult,
	OperationState,
)
from globalPlugins.whatsappWebPlusCompanion.processes import Listener


class _CancelEvent:
	def is_set(self) -> bool:
		return False

	def wait(self, timeout: float) -> bool:
		return False


class _CancelAfterPolls(_CancelEvent):
	def __init__(self, polls: int) -> None:
		self.polls = polls
		self.waits: list[float] = []

	def wait(self, timeout: float) -> bool:
		self.waits.append(timeout)
		return len(self.waits) > self.polls


class LauncherLifecycleTests(unittest.TestCase):
	def test_announcement_cursor_advances_only_after_delivery_and_retries_failure(self) -> None:
		entry = CompanionAnnouncement(4, 2, "session", "chat", "status", "id", True, "Halo")
		batch = CompanionAnnouncementBatch(
			"session",
			2,
			"chat",
			4,
			False,
			"startup",
			"",
			False,
			(entry,),
		)
		state = launcher._AnnouncementState()
		reports: list[OperationResult] = []
		outcomes = iter([True, False])

		def report(result: OperationResult) -> bool:
			reports.append(result)
			return next(outcomes)

		with patch.object(launcher, "readCompanionAnnouncements", return_value=batch) as read:
			launcher._forwardCompanionAnnouncements(MagicMock(), state, report)

		self.assertEqual(
			[result.messageKey for result in reports],
			["companion.invalidate", "companion.announcement"],
		)
		self.assertEqual(state.lastAcknowledgedSequence, 0)
		read.assert_called_once_with(ANY, 0, 0)

		reports.clear()
		with patch.object(launcher, "readCompanionAnnouncements", return_value=batch) as read:
			launcher._forwardCompanionAnnouncements(
				MagicMock(),
				state,
				lambda result: reports.append(result) or True,
			)

		self.assertEqual([result.messageKey for result in reports], ["companion.announcement"])
		self.assertEqual(state.lastAcknowledgedSequence, 4)
		read.assert_called_once_with(ANY, 0, 2)

	def test_invalidation_and_overflow_are_reported_before_current_entries(self) -> None:
		entry = CompanionAnnouncement(9, 5, "session", "chat-b", "message-log", "en", False, "New")
		batch = CompanionAnnouncementBatch(
			"session",
			5,
			"chat-b",
			9,
			True,
			"chat-context-changed",
			"message-log",
			True,
			(entry,),
		)
		state = launcher._AnnouncementState("session", 4, "chat-a", 7)
		reports: list[OperationResult] = []
		with patch.object(launcher, "readCompanionAnnouncements", return_value=batch):
			launcher._forwardCompanionAnnouncements(
				MagicMock(),
				state,
				lambda result: reports.append(result) or True,
			)

		self.assertEqual(
			[result.messageKey for result in reports],
			["companion.invalidate", "companion.overflow", "companion.announcement"],
		)
		self.assertEqual(reports[-1].values["language"], "en")
		self.assertEqual(reports[-1].values["source"], "message-log")
		self.assertEqual(state.lastAcknowledgedSequence, 9)

	def test_replacement_renderer_is_reread_from_zero_before_delivery(self) -> None:
		filtered = CompanionAnnouncementBatch(
			"new-session",
			1,
			"new-session:1",
			2,
			False,
			"startup",
			"",
			False,
			(),
		)
		entry = CompanionAnnouncement(
			2,
			1,
			"new-session",
			"new-session:1",
			"status",
			"en",
			False,
			"Renderer ready",
		)
		fresh = CompanionAnnouncementBatch(
			"new-session",
			1,
			"new-session:1",
			2,
			False,
			"startup",
			"",
			False,
			(entry,),
		)
		state = launcher._AnnouncementState("old-session", 4, "old-session:4", 99)
		reports: list[OperationResult] = []

		with patch.object(
			launcher,
			"readCompanionAnnouncements",
			side_effect=[filtered, fresh],
		) as read:
			launcher._forwardCompanionAnnouncements(
				MagicMock(),
				state,
				lambda result: reports.append(result) or True,
			)

		self.assertEqual(read.call_args_list[0].args[1:], (99, 4))
		self.assertEqual(read.call_args_list[1].args[1:], (0, 0))
		self.assertEqual(
			[result.messageKey for result in reports],
			["companion.invalidate", "companion.announcement"],
		)
		self.assertEqual(state.lastAcknowledgedSequence, 2)

	def test_successful_empty_scoped_invalidation_acknowledges_removed_tail(self) -> None:
		batch = CompanionAnnouncementBatch(
			"session",
			3,
			"session:3",
			6,
			True,
			"message-log-reset",
			"message-log",
			False,
			(),
		)
		state = launcher._AnnouncementState("session", 2, "session:2", 5)
		reports: list[OperationResult] = []

		with patch.object(launcher, "readCompanionAnnouncements", return_value=batch):
			launcher._forwardCompanionAnnouncements(
				MagicMock(),
				state,
				lambda result: reports.append(result) or True,
			)

		self.assertEqual([result.messageKey for result in reports], ["companion.invalidate"])
		self.assertEqual(state.lastAcknowledgedSequence, 6)

	def test_listener_validation_retries_transient_topology(self) -> None:
		with (
			patch.object(
				launcher,
				"collectProcessTopology",
				side_effect=[([], {}), ([Listener("127.0.0.1", 12345, 20)], {20: 10})],
			),
			patch.object(
				launcher,
				"validateListener",
				side_effect=[LoaderError("listener.ancestry"), 20],
			) as validate,
		):
			listenerPid = launcher._waitForValidatedListener(12345, {10}, _CancelEvent())

		self.assertEqual(listenerPid, 20)
		self.assertEqual(validate.call_count, 2)

	def test_initial_attachment_retries_transient_renderer_context(self) -> None:
		initial = Target("initial", "https://web.whatsapp.com/", "ws://127.0.0.1:12345/devtools/page/initial")
		replacement = Target(
			"replacement",
			"https://web.whatsapp.com/",
			"ws://127.0.0.1:12345/devtools/page/replacement",
		)
		session = MagicMock()
		with (
			patch.object(launcher, "_discoverTarget", return_value=replacement),
			patch.object(
				launcher,
				"_connectAndInstall",
				side_effect=[LoaderError("cdp.context"), (session, {"state": "ready"}, lambda: None)],
			) as connect,
		):
			target, connectedSession, health, unregister = launcher._waitForInitialAttachment(
				12345,
				initial,
				"source",
				"1.0",
				"a" * 64,
				_CancelEvent(),
			)

		self.assertEqual(target, replacement)
		self.assertIs(connectedSession, session)
		self.assertEqual(health["state"], "ready")
		self.assertIsNotNone(unregister)
		self.assertEqual(connect.call_count, 2)

	def test_connect_registers_interrupt_before_waiting_for_page_readiness(self) -> None:
		webSocket = MagicMock()
		session = MagicMock()
		registered: list[object] = []
		unregister = MagicMock()

		def register(closer):
			registered.append(closer)
			return unregister

		def install(*_args, **kwargs):
			self.assertEqual(registered, [session.interrupt])
			self.assertEqual(kwargs["healthDeadline"], launcher.BUNDLE_HEALTH_DEADLINE)
			raise LoaderError("operation.cancelled")

		with (
			patch.object(launcher.WebSocket, "connect", return_value=webSocket),
			patch.object(launcher, "CdpSession", return_value=session),
			patch.object(launcher, "installAndVerify", side_effect=install),
			self.assertRaisesRegex(LoaderError, "operation.cancelled"),
		):
			launcher._connectAndInstall(
				Target("page", "https://web.whatsapp.com/", "ws://127.0.0.1/devtools/page/page"),
				"source",
				"1.0",
				"a" * 64,
				_CancelEvent(),
				register,
			)

		unregister.assert_called_once_with()
		session.close.assert_called_once_with()

	def test_updated_bundle_health_failures_are_quarantined_and_report_fallback(self) -> None:
		bundle = MagicMock(isUpdate=True, sha256="a" * 64)
		for code in ("bundle.failed", "bundle.healthMismatch", "bundle.healthTimeout"):
			with (
				self.subTest(code=code),
				patch.object(launcher, "quarantineUpdatedBundle", return_value=True) as quarantine,
				self.assertRaisesRegex(LoaderError, "bundle.updateQuarantined") as raised,
			):
				launcher._raiseBundleInstallError(bundle, LoaderError(code))
			self.assertEqual(raised.exception.safeDetail, code)
			quarantine.assert_called_once_with("a" * 64)

	def test_packaged_bundle_failure_is_not_quarantined(self) -> None:
		bundle = MagicMock(isUpdate=False, sha256="b" * 64)
		with (
			patch.object(launcher, "quarantineUpdatedBundle") as quarantine,
			self.assertRaisesRegex(LoaderError, "bundle.healthTimeout"),
		):
			launcher._raiseBundleInstallError(bundle, LoaderError("bundle.healthTimeout"))
		quarantine.assert_not_called()

	def test_announcement_bridge_is_read_before_health_check_without_process_inventory(self) -> None:
		lease = MagicMock(owned=False)
		lease.acquire.side_effect = lambda: setattr(lease, "owned", True)
		lease.restore.side_effect = lambda: setattr(lease, "owned", False)
		target = Target("initial", "https://web.whatsapp.com/", "ws://127.0.0.1/initial")
		session = MagicMock()
		order: list[str] = []

		def forward(*_args) -> None:
			order.append("announcement")

		cancelEvent = _CancelAfterPolls(1)

		with (
			patch.object(launcher, "buildSecurityProbe", return_value=MagicMock()),
			patch.object(launcher, "checkPreflight"),
			patch.object(launcher, "_recoverPendingRegistryState"),
			patch.object(launcher, "resolvePackage", return_value=MagicMock()),
			patch.object(launcher, "findRunningPackageProcesses", side_effect=[(), (41,)]) as processes,
			patch.object(launcher, "_TARGET_HEALTH_INTERVAL", 0.0),
			patch.object(launcher, "reserveLoopbackPort", return_value=12345),
			patch.object(launcher, "RegistryLease", return_value=lease),
			patch.object(launcher, "activateAumid"),
			patch.object(launcher, "waitForEndpoint"),
			patch.object(launcher, "_waitForValidatedListener"),
			patch.object(launcher, "_waitForTarget", return_value=target),
			patch.object(
				launcher,
				"selectEmbeddedBundle",
				return_value=MagicMock(source="source", version="1.0", sha256="hash", isUpdate=False),
			),
			patch.object(
				launcher,
				"_waitForInitialAttachment",
				return_value=(target, session, {"state": "ready"}, lambda: None),
			),
			patch.object(launcher, "_forwardCompanionAnnouncements", side_effect=forward),
			patch.object(
				launcher,
				"_discoverTarget",
				side_effect=lambda _port: order.append("target") or target,
			),
			self.assertRaisesRegex(LoaderError, "operation.cancelled"),
		):
			launcher.launchOperation(Channel.STABLE, cancelEvent, lambda _state: None)

		self.assertEqual(order, ["announcement", "target"])
		self.assertEqual(processes.call_count, 2)
		self.assertEqual(cancelEvent.waits, [launcher._ANNOUNCEMENT_POLL_INTERVAL] * 2)

	def test_normal_package_exit_finishes_without_reconnect(self) -> None:
		lease = MagicMock()
		lease.owned = False

		def acquire() -> None:
			lease.owned = True

		def restore() -> None:
			lease.owned = False

		lease.acquire.side_effect = acquire
		lease.restore.side_effect = restore
		session = MagicMock()
		states: list[OperationState] = []

		with (
			patch.object(launcher, "buildSecurityProbe", return_value=MagicMock()),
			patch.object(launcher, "checkPreflight"),
			patch.object(launcher, "_recoverPendingRegistryState"),
			patch.object(launcher, "resolvePackage", return_value=MagicMock()),
			patch.object(launcher, "findRunningPackageProcesses", side_effect=[(), (41,), ()]),
			patch.object(launcher, "reserveLoopbackPort", return_value=12345),
			patch.object(launcher, "RegistryLease", return_value=lease),
			patch.object(launcher, "activateAumid"),
			patch.object(launcher, "waitForEndpoint"),
			patch.object(launcher, "_waitForValidatedListener"),
			patch.object(launcher, "_waitForTarget", return_value=MagicMock()),
			patch.object(
				launcher,
				"selectEmbeddedBundle",
				return_value=MagicMock(source="source", version="1.0", sha256="hash", isUpdate=False),
			),
			patch.object(
				launcher,
				"_waitForInitialAttachment",
				return_value=(MagicMock(), session, {"readyStateAtInstall": "complete"}, lambda: None),
			),
			patch.object(
				launcher,
				"_forwardCompanionAnnouncements",
				side_effect=LoaderError("cdp.closed"),
			),
			patch.object(launcher, "reconnect") as reconnect,
		):
			result = launcher.launchOperation(Channel.STABLE, _CancelEvent(), states.append)

		self.assertTrue(result.ok)
		self.assertEqual(result.messageKey, "package.closed")
		self.assertNotIn(OperationState.RECONNECTING, states)
		reconnect.assert_not_called()
		session.close.assert_called_once()

	def test_reconnect_keeps_the_discovered_target_paired_with_its_session(self) -> None:
		lease = MagicMock()
		lease.owned = False
		lease.acquire.side_effect = lambda: setattr(lease, "owned", True)
		lease.restore.side_effect = lambda: setattr(lease, "owned", False)
		initial = Target("initial", "https://web.whatsapp.com/", "ws://127.0.0.1/initial")
		replacement = Target("replacement", "https://web.whatsapp.com/", "ws://127.0.0.1/replacement")
		initialSession = MagicMock()
		replacementSession = MagicMock()
		initialUnregister = MagicMock()
		replacementUnregister = MagicMock()

		def reconnectOnce(_discover, connect, _cancelEvent):
			return connect(replacement)

		with (
			patch.object(launcher, "buildSecurityProbe", return_value=MagicMock()),
			patch.object(launcher, "checkPreflight"),
			patch.object(launcher, "_recoverPendingRegistryState"),
			patch.object(launcher, "resolvePackage", return_value=MagicMock()),
			patch.object(
				launcher,
				"findRunningPackageProcesses",
				side_effect=[(), (41,), (41,), ()],
			),
			patch.object(launcher, "_TARGET_HEALTH_INTERVAL", 0.0),
			patch.object(launcher, "reserveLoopbackPort", return_value=12345),
			patch.object(launcher, "RegistryLease", return_value=lease),
			patch.object(launcher, "activateAumid"),
			patch.object(launcher, "waitForEndpoint"),
			patch.object(launcher, "_waitForValidatedListener"),
			patch.object(launcher, "_waitForTarget", return_value=initial),
			patch.object(
				launcher,
				"selectEmbeddedBundle",
				return_value=MagicMock(source="source", version="1.0", sha256="hash", isUpdate=False),
			),
			patch.object(
				launcher,
				"_waitForInitialAttachment",
				return_value=(initial, initialSession, {"state": "ready"}, initialUnregister),
			),
			patch.object(launcher, "_discoverTarget", return_value=replacement) as discover,
			patch.object(
				launcher,
				"_connectAndInstall",
				return_value=(replacementSession, {"state": "ready"}, replacementUnregister),
			),
			patch.object(
				launcher,
				"_forwardCompanionAnnouncements",
				side_effect=[None, LoaderError("cdp.closed")],
			),
			patch.object(launcher, "reconnect", side_effect=reconnectOnce),
		):
			result = launcher.launchOperation(Channel.STABLE, _CancelEvent(), lambda _state: None)

		self.assertEqual(result.messageKey, "package.closed")
		discover.assert_called_once_with(12345)
		initialSession.close.assert_called_once_with()
		initialUnregister.assert_called_once_with()
		replacementSession.close.assert_called_once_with()
		replacementUnregister.assert_called_once_with()


if __name__ == "__main__":
	unittest.main()
