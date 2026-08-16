import json
import pathlib
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from .models import LoaderError
from .policy import ChannelPolicy

PowerShellRunner = Callable[[str], str]


class CancellationEvent(Protocol):
	def is_set(self) -> bool: ...


@dataclass(frozen=True, slots=True)
class PackageInfo:
	fullName: str
	familyName: str
	installLocation: str


@dataclass(frozen=True, slots=True)
class PackageProcessCloseResult:
	foundCount: int
	remainingCount: int

	@property
	def closedCount(self) -> int:
		return max(0, self.foundCount - self.remainingCount)


def runPowerShell(script: str) -> str:
	completed = subprocess.run(
		["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
		stdin=subprocess.DEVNULL,
		capture_output=True,
		check=False,
		encoding="utf-8",
		errors="strict",
		timeout=10,
		creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
	)
	if completed.returncode:
		raise LoaderError("powershell.failed", f"exit={completed.returncode}")
	return completed.stdout


def runPowerShellCancellable(script: str, cancelEvent: CancellationEvent) -> str:
	process = subprocess.Popen(
		["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
		stdin=subprocess.DEVNULL,
		stdout=subprocess.PIPE,
		stderr=subprocess.PIPE,
		text=True,
		encoding="utf-8",
		errors="strict",
		creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
	)
	deadline = time.monotonic() + 10
	while True:
		if cancelEvent.is_set():
			process.kill()
			_ = process.communicate()
			raise LoaderError("operation.cancelled")
		remaining = deadline - time.monotonic()
		if remaining <= 0:
			process.kill()
			_ = process.communicate()
			raise LoaderError("powershell.failed", "timeout")
		try:
			stdout, _stderr = process.communicate(timeout=min(0.1, remaining))
		except subprocess.TimeoutExpired:
			continue
		if process.returncode:
			raise LoaderError("powershell.failed", f"exit={process.returncode}")
		return stdout


def _rows(rawText: str) -> list[object]:
	try:
		raw = json.loads(rawText or "[]")
	except (TypeError, ValueError) as error:
		raise LoaderError("powershell.json", type(error).__name__) from error
	return raw if isinstance(raw, list) else [raw]


def findPackage(policy: ChannelPolicy, runner: PowerShellRunner = runPowerShell) -> PackageInfo | None:
	script = (
		"Get-AppxPackage | Select-Object PackageFullName,PackageFamilyName,InstallLocation "
		"| ConvertTo-Json -Compress"
	)
	matches = [
		row
		for row in _rows(runner(script))
		if isinstance(row, dict) and row.get("PackageFamilyName") == policy.packageFamily
	]
	if not matches:
		return None
	if len(matches) != 1:
		raise LoaderError("package.ambiguous", f"channel={policy.id};count={len(matches)}")
	row = matches[0]
	installLocation = str(row.get("InstallLocation", ""))
	fullName = str(row.get("PackageFullName", ""))
	if not installLocation or not fullName:
		raise LoaderError("package.incomplete", f"channel={policy.id}")
	return PackageInfo(fullName, str(row["PackageFamilyName"]), installLocation)


def resolvePackage(policy: ChannelPolicy, runner: PowerShellRunner = runPowerShell) -> PackageInfo:
	package = findPackage(policy, runner)
	if package is None:
		raise LoaderError("package.ambiguous", f"channel={policy.id};count=0")
	return package


def findRunningPackageProcesses(
	package: PackageInfo,
	runner: PowerShellRunner = runPowerShell,
) -> tuple[int, ...]:
	script = (
		"Get-CimInstance Win32_Process | Select-Object ProcessId,ExecutablePath | ConvertTo-Json -Compress"
	)
	root = pathlib.PureWindowsPath(package.installLocation)
	pids: set[int] = set()
	for row in _rows(runner(script)):
		if not isinstance(row, dict) or not row.get("ExecutablePath"):
			continue
		path = pathlib.PureWindowsPath(str(row["ExecutablePath"]))
		try:
			path.relative_to(root)
		except ValueError:
			continue
		pid = int(row.get("ProcessId") or 0)
		if pid > 0:
			pids.add(pid)
	return tuple(sorted(pids))


def forceClosePackageProcesses(
	package: PackageInfo,
	runner: PowerShellRunner = runPowerShell,
) -> PackageProcessCloseResult:
	root = package.installLocation.rstrip("\\/").replace("'", "''")
	script = (
		f"$root = [IO.Path]::GetFullPath('{root}').TrimEnd('\\') + '\\'; "
		"$matches = @(Get-CimInstance Win32_Process | Where-Object { "
		"$path = $_.ExecutablePath; if (-not $path) { return $false }; "
		"try { $fullPath = [IO.Path]::GetFullPath($path) } catch { return $false }; "
		"$fullPath.StartsWith($root, [StringComparison]::OrdinalIgnoreCase) }); "
		"$found = $matches.Count; foreach ($process in $matches) { "
		"try { $null = Invoke-CimMethod -InputObject $process -MethodName Terminate -ErrorAction Stop } "
		"catch {} }; $deadline = [DateTime]::UtcNow.AddSeconds(2); do { "
		"$remaining = @(Get-CimInstance Win32_Process | Where-Object { "
		"$path = $_.ExecutablePath; if (-not $path) { return $false }; "
		"try { $fullPath = [IO.Path]::GetFullPath($path) } catch { return $false }; "
		"$fullPath.StartsWith($root, [StringComparison]::OrdinalIgnoreCase) }); "
		"if ($remaining.Count -eq 0) { break }; Start-Sleep -Milliseconds 100 "
		"} while ([DateTime]::UtcNow -lt $deadline); "
		"@{Found=[int]$found;Remaining=[int]$remaining.Count} | ConvertTo-Json -Compress"
	)
	rows = _rows(runner(script))
	if len(rows) != 1 or not isinstance(rows[0], dict):
		raise LoaderError("processes.closeResult", f"family={package.familyName}")
	foundCount = int(rows[0].get("Found") or 0)
	remainingCount = int(rows[0].get("Remaining") or 0)
	if foundCount < 0 or remainingCount < 0 or remainingCount > foundCount:
		raise LoaderError("processes.closeResult", f"family={package.familyName}")
	return PackageProcessCloseResult(foundCount, remainingCount)
