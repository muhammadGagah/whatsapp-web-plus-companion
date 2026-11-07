import json
import os
import pathlib
import socket
import sys
import threading
import unittest
from unittest.mock import patch

from _path import installPackagePath

installPackagePath()

from globalPlugins.whatsappWebPlusCompanion import launcher, nativeProbes  # noqa: E402
from globalPlugins.whatsappWebPlusCompanion.models import Channel, LoaderError  # noqa: E402
from globalPlugins.whatsappWebPlusCompanion.packages import (  # noqa: E402
	PackageInfo,
	findRunningPackageProcesses,
)
from globalPlugins.whatsappWebPlusCompanion.processes import (  # noqa: E402
	Listener,
	captureEndpointIdentity,
	collectProcessTopology,
	validateListener,
)


def _refusingRunner(command):
	raise AssertionError(f"PowerShell must not run: {getattr(command, 'stage', command)}")


def _ownPackage() -> PackageInfo:
	rows = nativeProbes.processRows(details=True)
	path = next(row["ExecutablePath"] for row in rows if row["ProcessId"] == os.getpid())
	return PackageInfo("Test_1.0_x64__x", "Test_x", str(pathlib.PureWindowsPath(path).parent))


@unittest.skipUnless(sys.platform == "win32", "Win32 snapshots")
class NativeProbeTests(unittest.TestCase):
	def setUp(self):
		self.server = socket.socket()
		self.server.bind(("127.0.0.1", 0))
		self.server.listen(1)
		self.port = self.server.getsockname()[1]

	def tearDown(self):
		self.server.close()

	def test_listener_rows_match_power_shell_shape(self):
		rows = nativeProbes.tcpRows("listen", self.port)
		self.assertEqual(
			[(row["LocalAddress"], row["LocalPort"], row["OwningProcess"]) for row in rows],
			[("127.0.0.1", self.port, os.getpid())],
		)

	def test_ipv6_listener_is_reported_so_exposure_is_still_rejected(self):
		try:
			server6 = socket.socket(socket.AF_INET6)
			server6.bind(("::1", self.port))
		except OSError:
			self.skipTest("IPv6 loopback unavailable or port taken")
		with server6:
			server6.listen(1)
			rows = nativeProbes.tcpRows("listen", self.port)
			self.assertIn("::1", {row["LocalAddress"] for row in rows})
			listeners, parents = collectProcessTopology(self.port, _refusingRunner, native=True)
			with self.assertRaisesRegex(LoaderError, "listener.exposure"):
				validateListener(self.port, listeners, parents, {os.getppid()})

	def test_established_rows_are_filtered_by_both_ports(self):
		client = socket.create_connection(("127.0.0.1", self.port))
		accepted, _ = self.server.accept()
		with client, accepted:
			rows = nativeProbes.tcpRows("established", self.port, client.getsockname()[1])
			self.assertEqual(len(rows), 1)
			self.assertEqual(rows[0]["RemotePort"], client.getsockname()[1])
			self.assertEqual(rows[0]["OwningProcess"], os.getpid())
			self.assertEqual(nativeProbes.tcpRows("established", self.port, 1), [])

	def test_process_rows_include_parent_path_and_creation_time(self):
		rows = {row["ProcessId"]: row for row in nativeProbes.processRows(details=True)}
		own = rows[os.getpid()]
		self.assertEqual(own["ParentProcessId"], os.getppid())
		self.assertTrue(own["ExecutablePath"].lower().endswith(".exe"))
		self.assertGreater(own["Created"], 0)
		self.assertEqual(own["Created"] % 10, 0)

	def test_native_topology_validates_ancestry_without_power_shell(self):
		listeners, parents = collectProcessTopology(self.port, _refusingRunner, native=True)
		self.assertEqual(validateListener(self.port, listeners, parents, {os.getppid()}), os.getpid())

	def test_native_topology_falls_back_to_power_shell(self):
		stages = []

		def runner(command):
			stages.append(command.stage)
			if command.stage == "listener.ports":
				return json.dumps({"Listeners": []})
			return json.dumps({"Processes": []})

		with patch.object(nativeProbes, "tcpRows", side_effect=nativeProbes.NativeProbeUnavailable("x")):
			self.assertEqual(collectProcessTopology(self.port, runner, native=True), ([], {}))
		self.assertEqual(stages, ["listener.ports", "listener.processes"])

	def test_native_endpoint_identity_and_package_processes(self):
		package = _ownPackage()
		self.assertIn(os.getpid(), findRunningPackageProcesses(package, _refusingRunner, native=True))
		client = socket.create_connection(("127.0.0.1", self.port))
		accepted, _ = self.server.accept()
		with client, accepted:
			first = captureEndpointIdentity(self.port, package, _refusingRunner, native=True)
			second = captureEndpointIdentity(
				self.port,
				package,
				_refusingRunner,
				clientPort=client.getsockname()[1],
				native=True,
			)
		self.assertEqual(first.pid, os.getpid())
		self.assertEqual(first, second)

	def test_package_processes_fall_back_to_power_shell(self):
		package = PackageInfo("P", "F", "C:\\Program Files\\WindowsApps\\WA")
		rows = [{"ProcessId": 10, "ExecutablePath": "C:\\Program Files\\WindowsApps\\WA\\WhatsApp.exe"}]
		with patch.object(nativeProbes, "processRows", side_effect=nativeProbes.NativeProbeUnavailable("x")):
			self.assertEqual(
				findRunningPackageProcesses(package, lambda _: json.dumps(rows), native=True), (10,)
			)


class _Cancel:
	def is_set(self):
		return False

	def wait(self, timeout=None):
		return False


class LaunchDiagnosticsTests(unittest.TestCase):
	def _io(self, seconds=30.0):
		return launcher._OperationIO(
			threading.Event(), lambda closer: None, launcher.time.monotonic() + seconds
		)

	def test_listener_timeout_reports_the_validation_failure_not_only_the_probe(self):
		with (
			patch.object(
				launcher,
				"collectProcessTopology",
				side_effect=[
					([Listener("::1", 49223, 20)], {20: 10}),
					LoaderError(
						"powershell.failed", "timeout;stage=listener.ports;elapsed=1.63s;budget=1.61s"
					),
				],
			),
		):
			with self.assertRaises(LoaderError) as raised:
				launcher._waitForValidatedListener(49223, {10}, _Cancel(), io=self._io())
		self.assertEqual(raised.exception.code, "listener.timeout")
		detail = raised.exception.safeDetail
		self.assertTrue(detail.startswith("last=listener.exposure;"), detail)
		self.assertIn("cause=powershell.failed[timeout;stage=listener.ports", detail)
		self.assertIn("attempts=2", detail)

	def test_non_timeout_probe_failure_is_still_raised_unchanged(self):
		with patch.object(
			launcher, "collectProcessTopology", side_effect=LoaderError("powershell.failed", "exit=1")
		):
			with self.assertRaises(LoaderError) as raised:
				launcher._waitForValidatedListener(49223, {10}, _Cancel(), io=self._io())
		self.assertEqual(
			(raised.exception.code, raised.exception.safeDetail), ("powershell.failed", "exit=1")
		)

	def test_ancestry_failure_refreshes_package_processes_and_drops_stale_pids(self):
		package = PackageInfo("P", "F", "C:\\WA")
		topology = ([Listener("127.0.0.1", 49223, 20)], {20: 30, 10: 0})
		with (
			patch.object(launcher, "collectProcessTopology", return_value=topology),
			patch.object(launcher, "findRunningPackageProcesses", return_value=(30,)) as refresh,
			patch.object(launcher, "validateListener", wraps=validateListener) as validate,
		):
			pid = launcher._waitForValidatedListener(49223, {10}, _Cancel(), io=self._io(), package=package)
		self.assertEqual(pid, 20)
		self.assertEqual(refresh.call_count, 1)
		self.assertEqual([call.args[3] for call in validate.call_args_list], [{10}, {30}])

	def test_empty_refresh_keeps_previous_package_processes(self):
		package = PackageInfo("P", "F", "C:\\WA")
		with (
			patch.object(
				launcher,
				"collectProcessTopology",
				side_effect=[
					([Listener("127.0.0.1", 49223, 20)], {20: 30}),
					([Listener("127.0.0.1", 49223, 20)], {20: 10}),
				],
			),
			patch.object(launcher, "findRunningPackageProcesses", return_value=()),
		):
			pid = launcher._waitForValidatedListener(49223, {10}, _Cancel(), io=self._io(), package=package)
		self.assertEqual(pid, 20)

	def test_package_process_timeout_keeps_probe_cause(self):
		with patch.object(
			launcher,
			"findRunningPackageProcesses",
			side_effect=LoaderError("powershell.failed", "timeout;stage=package.processes"),
		):
			with self.assertRaises(LoaderError) as raised:
				launcher._waitForPackageProcesses(PackageInfo("P", "F", "C:\\WA"), _Cancel(), io=self._io())
		self.assertEqual(raised.exception.code, "package.processTimeout")
		self.assertIn("cause=powershell.failed[timeout;stage=package.processes]", raised.exception.safeDetail)

	def test_failed_launch_detail_lists_completed_steps(self):
		def failing(channel, cancelEvent, setState, registerCloser, reportObserver, gate, *rest, **options):
			gate("package")
			gate("notRunning")
			raise LoaderError("listener.timeout", "last=listener.exposure")

		seen = []
		with patch.object(launcher, "_launchOperation", side_effect=failing):
			with self.assertRaises(LoaderError) as raised:
				launcher.launchOperation(
					Channel.STABLE, threading.Event(), lambda state: None, gateObserver=seen.append
				)
		self.assertEqual(seen, ["package", "notRunning"])
		detail = raised.exception.safeDetail
		self.assertTrue(detail.startswith("last=listener.exposure;gates=package@"), detail)
		self.assertIn(",notRunning@", detail)
		self.assertIn(";failedAt=", detail)

	def test_cancelled_launch_detail_is_unchanged(self):
		with patch.object(launcher, "_launchOperation", side_effect=LoaderError("operation.cancelled")):
			with self.assertRaises(LoaderError) as raised:
				launcher.launchOperation(Channel.STABLE, threading.Event(), lambda state: None)
		self.assertEqual(raised.exception.safeDetail, "")


if __name__ == "__main__":
	unittest.main()
