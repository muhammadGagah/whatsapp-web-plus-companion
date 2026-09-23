import json
import subprocess
import threading
import unittest
from unittest.mock import patch

from _path import installPackagePath

installPackagePath()

from globalPlugins.whatsappWebPlusCompanion.models import Channel, LoaderError
from globalPlugins.whatsappWebPlusCompanion.packages import (
	PackageInfo,
	PowerShellCommand,
	findPackage,
	findRunningPackageProcesses,
	forceClosePackageProcesses,
	resolvePackage,
	runPowerShell,
	runPowerShellCancellable,
)
from globalPlugins.whatsappWebPlusCompanion.policy import CHANNELS
from globalPlugins.whatsappWebPlusCompanion.processes import (
	Listener,
	collectProcessTopology,
	validateListener,
)


class PackageProcessTests(unittest.TestCase):
	@patch("globalPlugins.whatsappWebPlusCompanion.packages.subprocess.Popen")
	def test_cancellable_power_shell_kills_child_when_diagnosis_stops(self, popen) -> None:
		class Process:
			returncode = None

			def __init__(self) -> None:
				self.killed = False

			def kill(self) -> None:
				self.killed = True

			def communicate(self, timeout=None):
				return "", ""

		process = Process()
		popen.return_value = process
		cancel = threading.Event()
		cancel.set()

		with self.assertRaisesRegex(LoaderError, "operation.cancelled"):
			runPowerShellCancellable("Get-AppxPackage", cancel)

		self.assertFalse(process.killed)
		popen.assert_not_called()  # Cancellation is now checked before creating a process.

	@patch("globalPlugins.whatsappWebPlusCompanion.packages.subprocess.run")
	def test_power_shell_does_not_inherit_nvda_stdin(self, run) -> None:
		run.return_value = subprocess.CompletedProcess([], 0, "[]", "")

		self.assertEqual(runPowerShell("Write-Output '[]'"), "[]")
		run.assert_called_once_with(
			[
				"powershell.exe",
				"-NoProfile",
				"-NonInteractive",
				"-Command",
				"Write-Output '[]'",
			],
			stdin=subprocess.DEVNULL,
			capture_output=True,
			check=False,
			encoding="utf-8",
			errors="strict",
			timeout=10,
			creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
		)

	@patch("globalPlugins.whatsappWebPlusCompanion.packages.subprocess.run")
	def test_sync_timeout_has_safe_stage_details(self, run):
		run.side_effect = subprocess.TimeoutExpired("private command", 30)
		with self.assertRaises(LoaderError) as raised:
			runPowerShell(PowerShellCommand("private command", "package.lookup", 30))
		self.assertEqual(raised.exception.code, "powershell.failed")
		self.assertIn("stage=package.lookup", raised.exception.safeDetail)
		self.assertIn("budget=30.00s", raised.exception.safeDetail)
		self.assertNotIn("private command", raised.exception.safeDetail)

	def test_package_query_is_scoped_but_family_still_verified(self):
		for policy in CHANNELS.values():
			commands = []

			def runner(command):
				commands.append(command)
				return json.dumps([{"PackageFamilyName": "wrong", "PackageFullName": "wrong"}])

			self.assertIsNone(findPackage(policy, runner))
			self.assertIn("-Name '" + policy.packageFamily.rsplit("_", 1)[0] + "'", commands[0])
			self.assertEqual(commands[0].timeout, 30)

	@patch("globalPlugins.whatsappWebPlusCompanion.packages.subprocess.Popen")
	def test_slow_lookup_completes_after_old_ten_second_limit(self, popen):
		clock = [0.0]
		process = popen.return_value
		process.returncode = 0

		def communicate(timeout):
			if clock[0] == 0:
				clock[0] = 12
				raise subprocess.TimeoutExpired("lookup", timeout)
			return "[]", ""

		process.communicate.side_effect = communicate
		with patch(
			"globalPlugins.whatsappWebPlusCompanion.packages.time.monotonic",
			side_effect=lambda: clock[0],
		):
			self.assertEqual(
				runPowerShellCancellable(
					PowerShellCommand("lookup", "package.lookup", 30),
					threading.Event(),
				),
				"[]",
			)
		process.kill.assert_not_called()

	@patch("globalPlugins.whatsappWebPlusCompanion.packages.subprocess.Popen")
	def test_outer_deadline_caps_longer_query_and_kills_process(self, popen):
		with patch(
			"globalPlugins.whatsappWebPlusCompanion.packages.time.monotonic",
			side_effect=[0, 0, 5, 5],
		):
			with self.assertRaises(LoaderError) as raised:
				runPowerShellCancellable(
					PowerShellCommand("lookup", "package.lookup", 30),
					threading.Event(),
					deadline=5,
				)
		self.assertIn("timeout;stage=package.lookup;elapsed=5.00s;budget=5.00s", raised.exception.safeDetail)
		popen.return_value.kill.assert_called_once()

	@patch("globalPlugins.whatsappWebPlusCompanion.packages.subprocess.Popen")
	def test_cancel_during_query_kills_process(self, popen):
		cancel = threading.Event()

		def communicate(timeout):
			cancel.set()
			raise subprocess.TimeoutExpired("lookup", timeout)

		popen.return_value.communicate.side_effect = communicate
		with self.assertRaisesRegex(LoaderError, "operation.cancelled"):
			runPowerShellCancellable(PowerShellCommand("lookup", "package.lookup", 30), cancel)
		popen.return_value.kill.assert_called_once()

	def test_exact_package_and_process_path_resolution(self) -> None:
		packageRows = [
			{
				"PackageFullName": "5319275A.WhatsAppDesktop_1.0_x64__cv1g1gvanyjgm",
				"PackageFamilyName": "5319275A.WhatsAppDesktop_cv1g1gvanyjgm",
				"InstallLocation": "C:\\Program Files\\WindowsApps\\WA",
			},
		]
		package = resolvePackage(CHANNELS[Channel.STABLE], lambda _: json.dumps(packageRows))
		processRows = [
			{"ProcessId": 10, "ExecutablePath": "C:\\Program Files\\WindowsApps\\WA\\WhatsApp.exe"},
			{"ProcessId": 99, "ExecutablePath": "C:\\Other\\WhatsApp.exe"},
		]
		self.assertEqual(findRunningPackageProcesses(package, lambda _: json.dumps(processRows)), (10,))

	def test_missing_package_is_optional_for_force_close_discovery(self) -> None:
		self.assertIsNone(findPackage(CHANNELS[Channel.BETA], lambda _: "[]"))

	def test_force_close_returns_verified_counts(self) -> None:
		package = PackageInfo(
			"5319275A.WhatsAppDesktop_1.0_x64__cv1g1gvanyjgm",
			"5319275A.WhatsAppDesktop_cv1g1gvanyjgm",
			"C:\\Program Files\\WindowsApps\\WA",
		)
		scripts: list[str] = []

		def runner(script: str) -> str:
			scripts.append(script)
			return json.dumps({"Found": 2, "Remaining": 0})

		result = forceClosePackageProcesses(package, runner)
		self.assertEqual((result.foundCount, result.closedCount, result.remainingCount), (2, 2, 0))
		self.assertIn("Invoke-CimMethod", scripts[0])
		self.assertIn("OrdinalIgnoreCase", scripts[0])

	def test_topology_queries_are_separate_and_keep_ownership_validation(self):
		commands = []

		def runner(command):
			commands.append(command)
			if command.stage == "listener.ports":
				return json.dumps(
					{"Listeners": [{"LocalAddress": "127.0.0.1", "LocalPort": 49223, "OwningProcess": 20}]},
				)
			return json.dumps({"Processes": [{"ProcessId": 20, "ParentProcessId": 10}]})

		listeners, parents = collectProcessTopology(49223, runner)
		self.assertEqual([c.stage for c in commands], ["listener.ports", "listener.processes"])
		self.assertEqual([c.timeout for c in commands], [30, 30])
		self.assertNotIn("Get-CimInstance", commands[0])
		self.assertNotIn("Get-NetTCPConnection", commands[1])
		self.assertEqual(validateListener(49223, listeners, parents, {10}), 20)
		with self.assertRaisesRegex(LoaderError, "listener.ancestry"):
			validateListener(49223, listeners, parents, {99})

	def test_topology_timeout_preserves_precise_stage(self):
		for failingStage in ("listener.ports", "listener.processes"):

			def runner(command):
				if command.stage == failingStage:
					raise LoaderError("powershell.failed", "timeout;stage=" + command.stage)
				return json.dumps({"Listeners": []})

			with self.assertRaises(LoaderError) as raised:
				collectProcessTopology(49223, runner)
			self.assertEqual(raised.exception.safeDetail, "timeout;stage=" + failingStage)

	def test_slow_topology_checks_fit_listener_budget_and_keep_outer_deadline(self):
		from globalPlugins.whatsappWebPlusCompanion import launcher

		for outerEnd in (90.0, 40.0):
			clock = [0.0]
			deadlines = []

			def run(command, cancelEvent, *, deadline):
				deadlines.append(deadline)
				self.assertGreaterEqual(deadline - clock[0], 12)
				clock[0] += 12
				if command.stage == "listener.ports":
					return json.dumps(
						{
							"Listeners": [
								{"LocalAddress": "127.0.0.1", "LocalPort": 49223, "OwningProcess": 20},
							],
						},
					)
				return json.dumps({"Processes": [{"ProcessId": 20, "ParentProcessId": 10}]})

			cancel = threading.Event()
			io = launcher._OperationIO(cancel, lambda closer: None, outerEnd)
			with (
				patch.object(launcher.time, "monotonic", side_effect=lambda: clock[0]),
				patch.object(launcher, "runPowerShellCancellable", side_effect=run),
			):
				self.assertEqual(launcher._waitForValidatedListener(49223, {10}, cancel, io=io), 20)
			self.assertEqual(deadlines, [min(60, outerEnd)] * 2)

	def test_listener_requires_literal_loopback_and_package_ancestry(self) -> None:
		self.assertEqual(
			validateListener(49223, [Listener("127.0.0.1", 49223, 30)], {30: 20, 20: 10}, {10}),
			30,
		)
		for listeners, parents in (
			([Listener("0.0.0.0", 49223, 30)], {30: 10}),
			([Listener("127.0.0.1", 49223, 30)], {30: 99}),
		):
			with self.assertRaises(LoaderError):
				validateListener(49223, listeners, parents, {10})
