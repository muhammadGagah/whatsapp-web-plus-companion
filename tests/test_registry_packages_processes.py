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
	findPackage,
	findRunningPackageProcesses,
	forceClosePackageProcesses,
	resolvePackage,
	runPowerShell,
	runPowerShellCancellable,
)
from globalPlugins.whatsappWebPlusCompanion.policy import CHANNELS
from globalPlugins.whatsappWebPlusCompanion.processes import Listener, validateListener


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

		self.assertTrue(process.killed)

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
