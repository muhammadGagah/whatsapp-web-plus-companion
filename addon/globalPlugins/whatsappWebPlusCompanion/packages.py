import json
import pathlib
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from . import nativeProbes
from .models import LoaderError
from .policy import ChannelPolicy

PowerShellRunner = Callable[[str], str]


class PowerShellCommand(str):
	"""Carry diagnostic context through runners that accept a script string."""

	def __new__(cls, script: str, stage: str, timeout: float = 10):
		command = super().__new__(cls, script)
		command.stage = stage
		command.timeout = timeout
		return command


def _failureDetail(script: str, reason: str, started: float, budget: float) -> str:
	stage = getattr(script, "stage", "powershell")
	return f"{reason};stage={stage};elapsed={time.monotonic() - started:.2f}s;budget={budget:.2f}s"


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


# Windows PowerShell writes piped output in the OEM code page. Any process path with a non-ASCII
# character (for example an accented account name) would otherwise fail UTF-8 decoding.
_UTF8_OUTPUT = "[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false);"


def _command(script: str) -> list[str]:
	return ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", _UTF8_OUTPUT + str(script)]


def runPowerShell(script: str) -> str:
	started = time.monotonic()
	budget = getattr(script, "timeout", 10)
	try:
		completed = subprocess.run(
			_command(script),
			stdin=subprocess.DEVNULL,
			capture_output=True,
			check=False,
			encoding="utf-8",
			errors="strict",
			timeout=budget,
			creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
		)
	except subprocess.TimeoutExpired as error:
		raise LoaderError("powershell.failed", _failureDetail(script, "timeout", started, budget)) from error
	except UnicodeDecodeError as error:
		raise LoaderError("powershell.failed", _failureDetail(script, "decode", started, budget)) from error
	if completed.returncode:
		raise LoaderError(
			"powershell.failed",
			_failureDetail(script, f"exit={completed.returncode}", started, budget),
		)
	if completed.stdout is None:
		# On Windows a decode failure ends the reader thread and leaves no output, without raising.
		raise LoaderError("powershell.failed", _failureDetail(script, "decode", started, budget))
	return completed.stdout


def runPowerShellCancellable(
	script: str,
	cancelEvent: CancellationEvent,
	*,
	deadline: float | None = None,
) -> str:
	if cancelEvent.is_set():
		raise LoaderError("operation.cancelled")
	started = time.monotonic()
	end = started + getattr(script, "timeout", 10)
	if deadline is not None:
		end = min(end, deadline)
	budget = max(0.0, end - started)
	if time.monotonic() >= end:
		raise LoaderError("powershell.failed", _failureDetail(script, "timeout", started, budget))
	process = subprocess.Popen(
		_command(script),
		stdin=subprocess.DEVNULL,
		stdout=subprocess.PIPE,
		stderr=subprocess.PIPE,
		text=True,
		encoding="utf-8",
		errors="strict",
		creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
	)
	while True:
		if cancelEvent.is_set():
			_stopPowerShell(process)
			raise LoaderError("operation.cancelled")
		remaining = end - time.monotonic()
		if remaining <= 0:
			_stopPowerShell(process)
			raise LoaderError("powershell.failed", _failureDetail(script, "timeout", started, budget))
		try:
			stdout, _stderr = process.communicate(timeout=min(0.1, remaining))
		except subprocess.TimeoutExpired:
			continue
		if process.returncode:
			raise LoaderError(
				"powershell.failed",
				_failureDetail(script, f"exit={process.returncode}", started, budget),
			)
		if stdout is None:
			# Undecodable output must never look like "no processes".
			raise LoaderError("powershell.failed", _failureDetail(script, "decode", started, budget))
		return stdout


def _stopPowerShell(process) -> None:
	try:
		process.kill()
	except OSError:
		pass
	try:
		process.communicate(timeout=1.0)
	except (subprocess.TimeoutExpired, OSError, UnicodeError):
		# On Windows communicate() uses daemon pipe readers. A descendant may
		# keep a pipe open after its parent is killed. Closing a buffered stream
		# here can block on that reader's lock; let the reader close it on EOF.
		# The operation worker must return even if that OS pipe outlives it.
		pass


def _rows(rawText: str) -> list[object]:
	try:
		raw = json.loads(rawText or "[]")
	except (TypeError, ValueError) as error:
		raise LoaderError("powershell.json", type(error).__name__) from error
	return raw if isinstance(raw, list) else [raw]


def findPackage(policy: ChannelPolicy, runner: PowerShellRunner = runPowerShell) -> PackageInfo | None:
	packageName = policy.packageFamily.rsplit("_", 1)[0].replace("'", "''")
	script = (
		f"Get-AppxPackage -Name '{packageName}' -ErrorAction Stop | Select-Object PackageFullName,PackageFamilyName,InstallLocation "
		"| ConvertTo-Json -Compress"
	)
	matches = [
		row
		for row in _rows(runner(PowerShellCommand(script, "package.lookup", 30)))
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
	*,
	native: bool = False,
) -> tuple[int, ...]:
	script = (
		"Get-CimInstance Win32_Process | Select-Object ProcessId,ExecutablePath | ConvertTo-Json -Compress"
	)
	rows = None
	if native:
		try:
			rows = nativeProbes.processRows(details=True)
		except nativeProbes.NativeProbeUnavailable as error:
			nativeProbes.noteFallback("package", error)
	if rows is None:
		rows = _rows(runner(PowerShellCommand(script, "package.processes", 20)))
	root = pathlib.PureWindowsPath(package.installLocation)
	pids: set[int] = set()
	for row in rows:
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


def packageProcessesStartedWithin(package: PackageInfo, seconds: float) -> bool:
	"""True when WhatsApp is running and every one of its processes started within ``seconds``.

	Only the direct Windows check is used. If it is unavailable, the answer is False, so a WhatsApp
	that may have been open for a long time is never closed automatically.
	"""
	try:
		rows = nativeProbes.processRows(details=True)
	except nativeProbes.NativeProbeUnavailable as error:
		nativeProbes.noteFallback("autoConnect", error)
		return False
	root = pathlib.PureWindowsPath(package.installLocation)
	# FILETIME counts 100-nanosecond intervals since 1601-01-01.
	now = int((time.time() + 11644473600) * 10_000_000)
	limit = int(seconds * 10_000_000)
	found = False
	for row in rows:
		path = row.get("ExecutablePath")
		if not path:
			continue
		try:
			pathlib.PureWindowsPath(str(path)).relative_to(root)
		except ValueError:
			continue
		created = row.get("Created")
		if not isinstance(created, int) or created <= 0 or now - created > limit:
			return False
		found = True
	return found


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
	rows = _rows(runner(PowerShellCommand(script, "package.close", 20)))
	if len(rows) != 1 or not isinstance(rows[0], dict):
		raise LoaderError("processes.closeResult", f"family={package.familyName}")
	foundCount = int(rows[0].get("Found") or 0)
	remainingCount = int(rows[0].get("Remaining") or 0)
	if foundCount < 0 or remainingCount < 0 or remainingCount > foundCount:
		raise LoaderError("processes.closeResult", f"family={package.familyName}")
	return PackageProcessCloseResult(foundCount, remainingCount)
