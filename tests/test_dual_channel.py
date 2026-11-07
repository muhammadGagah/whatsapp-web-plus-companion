import threading
import time
import unittest
from unittest.mock import patch

from _path import installPackagePath

installPackagePath()

from globalPlugins.whatsappWebPlusCompanion import launcher, nativeProbes, packages  # noqa: E402
from globalPlugins.whatsappWebPlusCompanion.controller import Controller  # noqa: E402
from globalPlugins.whatsappWebPlusCompanion.models import (  # noqa: E402
	Channel,
	LoaderError,
	OperationResult,
	OperationState,
)
from globalPlugins.whatsappWebPlusCompanion.packages import PackageInfo  # noqa: E402
from globalPlugins.whatsappWebPlusCompanion.policy import channelForExecutable  # noqa: E402

_STABLE_DIR = r"C:\Program Files\WindowsApps\5319275A.WhatsAppDesktop_2.2642.101.0_x64__cv1g1gvanyjgm"
_BETA_DIR = r"C:\Program Files\WindowsApps\5319275A.51895FA4EA97F_2.2643.3.0_x64__cv1g1gvanyjgm"


def _waitFor(predicate, timeout=2.0):
	end = time.monotonic() + timeout
	while time.monotonic() < end:
		if predicate():
			return True
		time.sleep(0.005)
	return predicate()


class TwoChannelControllerTests(unittest.TestCase):
	def test_stable_and_beta_run_at_the_same_time_and_report_their_own_channel(self):
		release = threading.Event()
		notifications: list[OperationResult] = []

		def operation(channel, cancel, state, registerCloser, report):
			state(OperationState.ATTACHED)
			release.wait(2)
			return OperationResult(True, "package.closed", "package.closed", {"channel": channel.value})

		controller = Controller(operation, notifications.append)
		self.assertTrue(controller.start(Channel.STABLE))
		self.assertTrue(controller.start(Channel.BETA))
		self.assertFalse(controller.start(Channel.STABLE))
		self.assertFalse(controller.start(Channel.BETA))
		self.assertTrue(_waitFor(lambda: len(notifications) == 2))
		self.assertEqual(
			sorted(result.values["channel"] for result in notifications if result.messageKey == "active"),
			["beta", "stable"],
		)
		self.assertEqual(controller.activeChannels(), (Channel.STABLE, Channel.BETA))
		self.assertEqual(controller.channelState(Channel.BETA), OperationState.ATTACHED)
		release.set()
		self.assertTrue(_waitFor(lambda: not controller.launching()))
		self.assertEqual(controller.channelState(Channel.STABLE), OperationState.IDLE)
		self.assertTrue(controller.start(Channel.STABLE))
		controller.stop()

	def test_tokens_map_to_their_channel_and_closing_one_channel_keeps_the_other(self):
		gates = {Channel.STABLE: threading.Event(), Channel.BETA: threading.Event()}
		tokens: dict[Channel, int] = {}

		def operation(channel, cancel, state, registerCloser, report):
			state(OperationState.ATTACHED)
			gates[channel].wait(2)
			return OperationResult(True, "package.closed", "package.closed", {"channel": channel.value})

		controller = Controller(operation, lambda result: None)
		controller.start(Channel.STABLE)
		tokens[Channel.STABLE] = controller.operationToken
		controller.start(Channel.BETA)
		tokens[Channel.BETA] = controller.operationToken
		for channel, token in tokens.items():
			self.assertEqual(controller.channelForToken(token), channel)
		gates[Channel.STABLE].set()
		self.assertTrue(_waitFor(lambda: not controller.channelActive(Channel.STABLE)))
		self.assertTrue(controller.channelActive(Channel.BETA))
		self.assertTrue(controller.launchTokenIsActive(tokens[Channel.BETA]))
		gates[Channel.BETA].set()
		controller.stop()

	def test_force_close_cancels_both_channels_and_closes_their_connections(self):
		closed: list[str] = []
		notifications: list[OperationResult] = []

		def operation(channel, cancel, state, registerCloser, report):
			registerCloser(lambda: closed.append(channel.value))
			cancel.wait(2)
			return OperationResult(True, "package.closed", "package.closed", {"channel": channel.value})

		controller = Controller(
			operation,
			notifications.append,
			lambda: OperationResult(True, "processes.closed", "processes.closed", {"closedCount": 2}),
		)
		controller.start(Channel.STABLE)
		controller.start(Channel.BETA)
		self.assertTrue(_waitFor(lambda: len(controller.closers) == 2))
		self.assertTrue(controller.forceClose())
		self.assertTrue(_waitFor(lambda: not controller.forceClosing and notifications))
		self.assertEqual(sorted(closed), ["beta", "stable"])
		# The closed sessions do not report afterwards; only the force-close result is spoken.
		self.assertEqual([result.messageKey for result in notifications], ["processes.closed"])
		self.assertFalse(controller.launching())

	def test_force_close_of_one_channel_keeps_the_other_connected(self):
		closed: list[str] = []
		notifications: list[OperationResult] = []
		calls = []

		def operation(channel, cancel, state, registerCloser, report):
			registerCloser(lambda: closed.append(channel.value))
			state(OperationState.ATTACHED)
			cancel.wait(2)
			return OperationResult(True, "package.closed", "package.closed", {"channel": channel.value})

		def forceCloseOperation(**options):
			calls.append(options)
			return OperationResult(True, "processes.closed", "processes.closed.one", {"channel": "beta"})

		controller = Controller(operation, notifications.append, forceCloseOperation)
		controller.start(Channel.STABLE)
		stableToken = controller.operationToken
		controller.start(Channel.BETA)
		self.assertTrue(_waitFor(lambda: len(controller.closers) == 2))
		self.assertTrue(controller.forceClose(channels=(Channel.BETA,)))
		self.assertTrue(
			_waitFor(lambda: not controller.forceClosing and not controller.channelActive(Channel.BETA)),
		)
		self.assertEqual(calls, [{"channels": (Channel.BETA,)}])
		self.assertEqual(closed, ["beta"])
		self.assertTrue(controller.channelActive(Channel.STABLE))
		self.assertTrue(controller.launchTokenIsActive(stableToken))
		self.assertEqual(controller.channelState(Channel.STABLE), OperationState.ATTACHED)
		self.assertNotIn("package.closed", [result.messageKey for result in notifications])
		controller.stop()

	def test_stop_cancels_every_channel(self):
		events = []

		def operation(channel, cancel, state, registerCloser, report):
			events.append(cancel)
			cancel.wait(2)
			return OperationResult(False, "operation.cancelled", "operation.cancelled", {})

		controller = Controller(operation, lambda result: None)
		controller.start(Channel.STABLE)
		controller.start(Channel.BETA)
		self.assertTrue(_waitFor(lambda: len(events) == 2))
		controller.stop()
		self.assertTrue(all(event.is_set() for event in events))

	def test_replace_recent_reaches_the_launch_operation(self):
		seen = []

		def operation(channel, cancel, state, registerCloser, report, **options):
			seen.append(options)
			return OperationResult(False, "operation.cancelled", "operation.cancelled", {})

		controller = Controller(operation, lambda result: None)
		controller.start(Channel.BETA, replaceRecent=True)
		self.assertTrue(_waitFor(lambda: not controller.launching()))
		controller.start(Channel.BETA)
		self.assertTrue(_waitFor(lambda: len(seen) == 2))
		self.assertEqual(seen, [{"replaceRecentInstance": True}, {}])


class ForceCloseChoiceTests(unittest.TestCase):
	def test_choices_are_stable_beta_then_all_and_default_to_all(self):
		import sys
		import types

		fakeWx = types.SimpleNamespace(Dialog=object)
		with patch.dict(
			sys.modules,
			{"wx": fakeWx, "addonHandler": types.SimpleNamespace(initTranslation=lambda: None)},
		):
			import builtins

			builtins._ = getattr(builtins, "_", lambda text: text)
			sys.modules.pop("globalPlugins.whatsappWebPlusCompanion.forceCloseDialog", None)
			from globalPlugins.whatsappWebPlusCompanion import forceCloseDialog
		self.assertEqual(forceCloseDialog.CHOICES, ((Channel.STABLE,), (Channel.BETA,), None))
		self.assertEqual(forceCloseDialog.choiceIndex(Channel.STABLE), 0)
		self.assertEqual(forceCloseDialog.choiceIndex(Channel.BETA), 1)
		self.assertEqual(forceCloseDialog.choiceIndex(None), 2)


class ChannelLookupTests(unittest.TestCase):
	def test_executable_path_identifies_the_store_package(self):
		self.assertEqual(channelForExecutable(_STABLE_DIR + r"\WhatsApp.Root.exe"), Channel.STABLE)
		self.assertEqual(channelForExecutable(_BETA_DIR.lower() + r"\WhatsApp.exe"), Channel.BETA)
		for path in (
			None,
			"",
			r"C:\Program Files\WindowsApps\5319275A.WhatsAppDesktop_2.0_x64__otherpublisher\WhatsApp.exe",
			r"C:\Tools\WhatsApp.exe",
			_STABLE_DIR,
		):
			self.assertIsNone(channelForExecutable(path))


class RecentInstanceTests(unittest.TestCase):
	def setUp(self):
		self.package = PackageInfo("Full", "5319275A.WhatsAppDesktop_cv1g1gvanyjgm", _STABLE_DIR)
		self.now = int((time.time() + 11644473600) * 10_000_000)

	def _rows(self, *ages):
		rows = [{"ProcessId": 1, "ExecutablePath": r"C:\Windows\explorer.exe", "Created": 1}]
		for index, age in enumerate(ages):
			rows.append(
				{
					"ProcessId": 100 + index,
					"ExecutablePath": _STABLE_DIR + r"\WhatsApp.Root.exe",
					"Created": self.now - int(age * 10_000_000),
				},
			)
		return rows

	def test_only_a_whatsapp_started_moments_ago_counts_as_recent(self):
		for ages, expected in (((2, 5), True), ((2, 600), False), ((), False)):
			with (
				self.subTest(ages=ages),
				patch.object(nativeProbes, "processRows", return_value=self._rows(*ages)),
			):
				self.assertIs(packages.packageProcessesStartedWithin(self.package, 30), expected)

	def test_unreadable_process_times_never_count_as_recent(self):
		rows = self._rows(2)
		rows[-1]["Created"] = 0
		with patch.object(nativeProbes, "processRows", return_value=rows):
			self.assertFalse(packages.packageProcessesStartedWithin(self.package, 30))
		with patch.object(nativeProbes, "processRows", side_effect=nativeProbes.NativeProbeUnavailable("x")):
			self.assertFalse(packages.packageProcessesStartedWithin(self.package, 30))

	def _io(self, seconds=30.0, cancel=None):
		return launcher._OperationIO(
			cancel or threading.Event(),
			lambda closer: None,
			time.monotonic() + seconds,
		)

	def test_old_instance_is_left_open(self):
		with (
			patch.object(launcher, "packageProcessesStartedWithin", return_value=False),
			patch.object(launcher, "forceClosePackageProcesses") as close,
		):
			with self.assertRaises(LoaderError) as raised:
				launcher._closeRecentInstance(self.package, threading.Event(), io=self._io())
		self.assertEqual(raised.exception.code, "autoConnect.tooLate")
		close.assert_not_called()

	def test_recent_instance_is_closed_and_waited_for(self):
		with (
			patch.object(launcher, "packageProcessesStartedWithin", return_value=True),
			patch.object(launcher, "forceClosePackageProcesses") as close,
			patch.object(launcher, "findRunningPackageProcesses", side_effect=[(5,), ()]) as running,
		):
			launcher._closeRecentInstance(self.package, threading.Event(), io=self._io())
		close.assert_called_once()
		self.assertEqual(running.call_count, 2)

	def test_instance_that_will_not_close_ends_with_close_failed(self):
		with (
			patch.object(launcher, "packageProcessesStartedWithin", return_value=True),
			patch.object(launcher, "forceClosePackageProcesses"),
			patch.object(launcher, "findRunningPackageProcesses", return_value=(5,)),
			patch.object(launcher, "_AUTO_CONNECT_CLOSE_DEADLINE", 0.3),
		):
			with self.assertRaises(LoaderError) as raised:
				launcher._closeRecentInstance(self.package, threading.Event(), io=self._io())
		self.assertEqual(raised.exception.code, "autoConnect.closeFailed")

	def test_running_whatsapp_is_replaced_only_for_automatic_connection(self):
		def launch(replace):
			with (
				patch.object(launcher, "checkPreflight"),
				patch.object(launcher, "buildSecurityProbe"),
				patch.object(launcher, "resolvePackage", return_value=self.package),
				patch.object(launcher, "findRunningPackageProcesses", return_value=(5,)),
				patch.object(
					launcher,
					"_closeRecentInstance",
					side_effect=LoaderError("autoConnect.tooLate"),
				) as closeRecent,
			):
				with self.assertRaises(LoaderError) as raised:
					launcher.launchOperation(
						Channel.STABLE,
						threading.Event(),
						lambda state: None,
						replaceRecentInstance=replace,
					)
			return raised.exception.code, closeRecent.call_count

		self.assertEqual(launch(False), ("package.running", 0))
		self.assertEqual(launch(True), ("autoConnect.tooLate", 1))


class RegistryTurnTests(unittest.TestCase):
	def _io(self, seconds=5.0, cancel=None):
		return launcher._OperationIO(
			cancel or threading.Event(),
			lambda closer: None,
			time.monotonic() + seconds,
		)

	def test_second_channel_waits_until_the_first_has_restored_the_registry(self):
		launcher._REGISTRY_PHASE.acquire()
		acquired = threading.Event()

		def second():
			launcher._acquireRegistryPhase(self._io())
			acquired.set()
			launcher._REGISTRY_PHASE.release()

		thread = threading.Thread(target=second)
		thread.start()
		self.assertFalse(acquired.wait(0.3))
		launcher._REGISTRY_PHASE.release()
		self.assertTrue(acquired.wait(2))
		thread.join(2)

	def test_waiting_for_the_registry_can_be_cancelled(self):
		launcher._REGISTRY_PHASE.acquire()
		try:
			cancel = threading.Event()
			cancel.set()
			with self.assertRaises(LoaderError) as raised:
				launcher._acquireRegistryPhase(self._io(cancel=cancel))
			self.assertEqual(raised.exception.code, "operation.cancelled")
			with self.assertRaises(LoaderError) as raised:
				launcher._acquireRegistryPhase(self._io(seconds=0.2))
			self.assertEqual(raised.exception.code, "operation.timeout")
		finally:
			launcher._REGISTRY_PHASE.release()

	def test_failed_registry_lease_releases_the_turn(self):
		with (
			patch.object(launcher, "checkPreflight"),
			patch.object(launcher, "buildSecurityProbe"),
			patch.object(launcher, "resolvePackage"),
			patch.object(launcher, "findRunningPackageProcesses", return_value=()),
			patch.object(launcher, "reserveLoopbackPort", return_value=50000),
			patch.object(launcher, "_recoverPendingRegistryState"),
			patch.object(launcher, "RegistryJournal"),
			patch.object(launcher, "RegistryLease") as lease,
		):
			lease.return_value.acquire.side_effect = LoaderError("registry.user.setAccessDenied")
			with self.assertRaises(LoaderError):
				launcher.launchOperation(Channel.BETA, threading.Event(), lambda state: None)
		self.assertTrue(launcher._REGISTRY_PHASE.acquire(blocking=False))
		launcher._REGISTRY_PHASE.release()


if __name__ == "__main__":
	unittest.main()
