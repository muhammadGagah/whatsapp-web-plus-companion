from __future__ import annotations

import ctypes
import hashlib
import json
import os
from collections.abc import Callable, Mapping
from ctypes import wintypes
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

try:
	from logHandler import log
except ImportError:
	import logging

	log = logging.getLogger(__name__)

from .models import LoaderError
from .policy import CHANNELS
from .registry import (
	RegistryApi,
	WinRegistry,
	acquireRegistryMutex,
	releaseRegistryMutex,
	recoverPendingRegistryState,
)
from .registryJournal import JournalError, RegistryJournal, currentUserSid
from .security import SecurityProbe

_HELPER_PROTOCOL_VERSION = 1
_HELPER_DEADLINE_SECONDS = 90.0
_SEE_MASK_NOCLOSEPROCESS = 0x00000040
_SEE_MASK_NOASYNC = 0x00000100
_SW_HIDE = 0
_COINIT_APARTMENTTHREADED = 0
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_WAIT_TIMEOUT = 0x102
_UAC_CANCELLED_WINERROR = 1223

_HELPER_EXIT_CODES = {
	0: "registry.repair.repaired",
	1: "registry.repair.notNeeded",
	2: "registry.repair.helperUntrusted",
	3: "registry.repair.helperBlocked",
	4: "registry.repair.parentIdentityMismatch",
	5: "registry.repair.parentIdentityMismatch",
	6: "registry.repair.parentIdentityMismatch",
	7: "registry.repair.userHiveUnavailable",
	8: "registry.repair.busy",
	9: "registry.repair.applyFailed",
	10: "registry.repair.managedDeny",
	11: "registry.repair.insufficientAdminRights",
	12: "registry.repair.applyFailed",
	13: "registry.repair.verificationFailedRolledBack",
	14: "registry.repair.rollbackFailed",
	15: "registry.repair.applyFailed",
}


class RegistryPermissionStatus(StrEnum):
	USABLE = "usable"
	REPAIRABLE_ACCESS_DENIED = "repairableAccessDenied"
	MACHINE_POLICY = "machinePolicy"
	BUSY = "busy"
	MANAGED_OR_UNKNOWN = "managedOrUnknown"
	UNSUPPORTED = "unsupported"
	WHATSAPP_RUNNING = "whatsappRunning"


@dataclass(frozen=True, slots=True)
class RepairIdentity:
	pid: int
	creationTicks: int
	sid: str


@dataclass(frozen=True, slots=True)
class RegistryRepairOutcome:
	ok: bool
	code: str
	values: Mapping[str, object] = field(default_factory=dict)


class _SHELLEXECUTEINFOW(ctypes.Structure):
	_fields_ = (
		("cbSize", wintypes.DWORD),
		("fMask", wintypes.ULONG),
		("hwnd", wintypes.HWND),
		("lpVerb", wintypes.LPCWSTR),
		("lpFile", wintypes.LPCWSTR),
		("lpParameters", wintypes.LPCWSTR),
		("lpDirectory", wintypes.LPCWSTR),
		("nShow", ctypes.c_int),
		("hInstApp", wintypes.HINSTANCE),
		("lpIDList", wintypes.LPVOID),
		("lpClass", wintypes.LPCWSTR),
		("hKeyClass", wintypes.HKEY),
		("dwHotKey", wintypes.DWORD),
		("hIconOrMonitor", wintypes.HANDLE),
		("hProcess", wintypes.HANDLE),
	)


class _FILETIME(ctypes.Structure):
	_fields_ = (
		("dwLowDateTime", wintypes.DWORD),
		("dwHighDateTime", wintypes.DWORD),
	)


def tryAcquireRegistryMutex() -> int | None:
	try:
		return acquireRegistryMutex()
	except LoaderError as error:
		if error.code == "registry.mutex.busy":
			return None
		raise


def diagnoseRegistryPermissions(
	registry: RegistryApi,
	probe: SecurityProbe,
	*,
	tryAcquireMutex: Callable[[], int | None],
	releaseMutex: Callable[[int], None],
	whatsappRunning: Callable[[], bool],
	isCancelled: Callable[[], bool] = lambda: False,
) -> RegistryPermissionStatus:
	"""Read-only diagnosis of the fixed per-user WebView2 policy leaf.

	Never writes, deletes, or probes a Registry value. Only access denied on
	the exact leaf is classified as repairable.
	"""
	if isCancelled():
		raise LoaderError("operation.cancelled")
	if probe.secureDesktop or probe.locked or not probe.canWrite or probe.elevated:
		return RegistryPermissionStatus.UNSUPPORTED
	if whatsappRunning():
		return RegistryPermissionStatus.WHATSAPP_RUNNING
	handle = tryAcquireMutex()
	if handle is None:
		return RegistryPermissionStatus.BUSY
	try:
		if isCancelled():
			raise LoaderError("operation.cancelled")
		machineError = ""
		try:
			for channel in CHANNELS.values():
				if isCancelled():
					raise LoaderError("operation.cancelled")
				if registry.readMachinePolicy(channel.aumid) is not None:
					return RegistryPermissionStatus.MACHINE_POLICY
			if registry.readMachinePolicy("*") is not None:
				return RegistryPermissionStatus.MACHINE_POLICY
		except LoaderError as error:
			# A machine-policy read failure must not hide a repairable user-key
			# denial; the repair only touches HKCU. Surface the machine error
			# only when the user key does not already decide the outcome.
			machineError = error.code
			log.warning("WhatsApp Companion machine policy probe: code=%s", error.code)
		try:
			if isCancelled():
				raise LoaderError("operation.cancelled")
			key = registry.openUserLeafReadOnly()
			if key is not None:
				registry.closeUserLeaf(key)
		except LoaderError as error:
			if error.code == "registry.user.openAccessDenied":
				return RegistryPermissionStatus.REPAIRABLE_ACCESS_DENIED
			log.warning("WhatsApp Companion user leaf probe: code=%s", error.code)
			if machineError:
				raise LoaderError(machineError, "stage=diagnosis.machine")
			return RegistryPermissionStatus.MANAGED_OR_UNKNOWN
		if machineError:
			raise LoaderError(machineError, "stage=diagnosis.machine")
		return RegistryPermissionStatus.USABLE
	finally:
		releaseMutex(handle)


def captureRequestIdentity() -> RepairIdentity:
	"""Capture parent-process identity on the GUI thread before elevation."""
	kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
	kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
	kernel32.OpenProcess.restype = wintypes.HANDLE
	kernel32.GetProcessTimes.argtypes = (
		wintypes.HANDLE,
		ctypes.POINTER(_FILETIME),
		ctypes.POINTER(_FILETIME),
		ctypes.POINTER(_FILETIME),
		ctypes.POINTER(_FILETIME),
	)
	kernel32.GetProcessTimes.restype = wintypes.BOOL
	kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
	kernel32.CloseHandle.restype = wintypes.BOOL
	handle = kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, os.getpid())
	if not handle:
		raise LoaderError("registry.repair.context", "stage=identity.open")
	try:
		creation = _FILETIME()
		_exit = _FILETIME()
		_kernel = _FILETIME()
		user = _FILETIME()
		if not kernel32.GetProcessTimes(
			handle,
			ctypes.byref(creation),
			ctypes.byref(_exit),
			ctypes.byref(_kernel),
			ctypes.byref(user),
		):
			raise LoaderError("registry.repair.context", "stage=identity.times")
		ticks = (creation.dwHighDateTime << 32) | creation.dwLowDateTime
		return RepairIdentity(os.getpid(), ticks, currentUserSid())
	finally:
		kernel32.CloseHandle(handle)


def _helperDir() -> Path:
	return Path(__file__).with_name("resources") / "registryRepair"


def verifyHelperIntegrity(helperDir: Path | None = None) -> tuple[Path, Path]:
	"""Verify the packaged helper scripts against the registry-repair.json lock."""
	helperDir = helperDir or _helperDir()
	metadataPath = helperDir.parent / "registry-repair.json"
	try:
		# utf-8-sig tolerates a UTF-8 BOM, which some Windows tooling (for
		# example PowerShell 5.1 Set-Content -Encoding utf8) writes by default.
		metadata = json.loads(metadataPath.read_text(encoding="utf-8-sig"))
	except OSError as error:
		raise LoaderError("registry.repair.helperMissing", "stage=helper.metadata") from error
	except ValueError as error:
		raise LoaderError("registry.repair.helperUntrusted", "stage=helper.metadata") from error
	if not isinstance(metadata, dict) or metadata.get("schemaVersion") != 1:
		raise LoaderError("registry.repair.helperUntrusted", "stage=helper.metadata")
	helper = metadata.get("helper")
	if not isinstance(helper, dict):
		raise LoaderError("registry.repair.helperUntrusted", "stage=helper.metadata")
	expected: dict[str, Path] = {
		"bat": helperDir / "registryRepair.bat",
		"ps1": helperDir / "registryRepair.ps1",
	}
	for name, path in expected.items():
		entry = helper.get(name)
		if (
			not isinstance(entry, dict)
			or not isinstance(entry.get("sha256"), str)
			or not isinstance(entry.get("bytes"), int)
		):
			raise LoaderError("registry.repair.helperUntrusted", f"stage=helper.metadata;file={name}")
		try:
			payload = path.read_bytes()
		except OSError as error:
			raise LoaderError("registry.repair.helperMissing", f"stage=helper.read;file={name}") from error
		if len(payload) != entry["bytes"] or hashlib.sha256(payload).hexdigest() != entry["sha256"]:
			raise LoaderError("registry.repair.helperUntrusted", f"stage=helper.hash;file={name}")
	return expected["bat"], expected["ps1"]


def elevateHelper(
	batPath: Path,
	identity: RepairIdentity,
	*,
	hwnd: int = 0,
	deadline: float = _HELPER_DEADLINE_SECONDS,
) -> tuple[int | None, int | None]:
	"""Run the fixed helper elevated and wait for its exit.

	Returns (exitCode, winerror). A timeout returns (None, None); a failed
	elevation returns (None, winerror).
	"""
	parameters = (
		f"-ProtocolVersion {_HELPER_PROTOCOL_VERSION} "
		f"-ParentPid {identity.pid} "
		f"-ParentCreationTicks {identity.creationTicks} "
		f"-RequestedSid {identity.sid}"
	)
	shell32 = ctypes.WinDLL("shell32", use_last_error=True)
	shell32.ShellExecuteExW.argtypes = (ctypes.POINTER(_SHELLEXECUTEINFOW),)
	shell32.ShellExecuteExW.restype = wintypes.BOOL
	kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
	kernel32.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
	kernel32.WaitForSingleObject.restype = wintypes.DWORD
	kernel32.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
	kernel32.GetExitCodeProcess.restype = wintypes.BOOL
	kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
	kernel32.CloseHandle.restype = wintypes.BOOL
	ole32 = ctypes.WinDLL("ole32", use_last_error=True)
	ole32.CoInitializeEx.argtypes = (wintypes.LPVOID, wintypes.DWORD)
	ole32.CoInitializeEx.restype = ctypes.HRESULT
	ole32.CoUninitialize.argtypes = ()
	ole32.CoUninitialize.restype = None

	ole32.CoInitializeEx(None, _COINIT_APARTMENTTHREADED)
	try:
		sei = _SHELLEXECUTEINFOW()
		sei.cbSize = ctypes.sizeof(_SHELLEXECUTEINFOW)
		sei.fMask = _SEE_MASK_NOCLOSEPROCESS | _SEE_MASK_NOASYNC
		sei.hwnd = hwnd
		sei.lpVerb = "runas"
		sei.lpFile = str(batPath)
		sei.lpParameters = parameters
		sei.nShow = _SW_HIDE
		if not shell32.ShellExecuteExW(ctypes.byref(sei)):
			return None, ctypes.get_last_error()
		handle = sei.hProcess
		if kernel32.WaitForSingleObject(handle, max(1, int(deadline * 1000))) == _WAIT_TIMEOUT:
			kernel32.CloseHandle(handle)
			return None, None
		code = wintypes.DWORD()
		if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
			code.value = 15
		kernel32.CloseHandle(handle)
		return int(code.value), None
	finally:
		ole32.CoUninitialize()


def _mapElevationFailure(winerror: int | None) -> str:
	if winerror == _UAC_CANCELLED_WINERROR:
		return "registry.repair.uacCancelled"
	if winerror in (2, 3):
		return "registry.repair.helperMissing"
	if winerror == 193:
		return "registry.repair.unsupportedPlatform"
	return "registry.repair.helperBlocked"


def _postcheckLeafUsable(registry: RegistryApi) -> bool:
	try:
		key = registry.openOrCreateUserLeaf()
		registry.closeUserLeaf(key)
	except LoaderError as error:
		log.warning("WhatsApp Companion repair postcheck: code=%s", error.code)
		return False
	return True


def _recoverJournalAfterRepair() -> str:
	journal = RegistryJournal.createDefault()
	try:
		if journal.load() is None:
			return ""
	except JournalError as error:
		raise LoaderError(
			"registry.recovery.unreadable",
			f"stage=recovery.load;code={error.code}",
		) from error
	handle = tryAcquireRegistryMutex()
	if handle is None:
		raise LoaderError("registry.mutex.busy", "stage=recovery.mutex")
	try:
		code, _detail = recoverPendingRegistryState(WinRegistry(), journal)
		return code
	finally:
		releaseRegistryMutex(handle)


def runRegistryRepair(
	identity: RepairIdentity,
	*,
	helperDir: Path | None = None,
	hwnd: int = 0,
	registry: RegistryApi | None = None,
	elevate: Callable[[Path, RepairIdentity, int], tuple[int | None, int | None]] | None = None,
	recover: Callable[[], str] | None = None,
) -> RegistryRepairOutcome:
	"""Diagnose, elevate the fixed helper, postcheck, and retry journal recovery."""
	batPath, _ps1Path = verifyHelperIntegrity(helperDir)
	elevateFn: Callable[[Path, RepairIdentity, int], tuple[int | None, int | None]]
	if elevate is None:

		def elevateFn(path: Path, ident: RepairIdentity, owner: int, /) -> tuple[int | None, int | None]:
			return elevateHelper(path, ident, hwnd=owner)
	else:
		elevateFn = elevate
	exitCode, winerror = elevateFn(batPath, identity, hwnd)
	log.info(
		"WhatsApp Companion registry repair helper exit: code=%s winerror=%s",
		exitCode,
		winerror,
	)
	if winerror is not None:
		return RegistryRepairOutcome(False, _mapElevationFailure(winerror))
	if exitCode is None:
		return RegistryRepairOutcome(False, "registry.repair.helperTimeout")
	code = _HELPER_EXIT_CODES.get(exitCode, "registry.repair.applyFailed")
	if code != "registry.repair.repaired":
		return RegistryRepairOutcome(False, code)
	postcheck = _postcheckLeafUsable(registry or WinRegistry())
	if not postcheck:
		return RegistryRepairOutcome(False, "registry.repair.postVerifyFailed")
	recoverFn = recover or _recoverJournalAfterRepair
	try:
		recoveryCode = recoverFn()
	except LoaderError as error:
		if error.code == "registry.restore.conflict":
			return RegistryRepairOutcome(False, "registry.repair.recoveryConflict", {"conflict": True})
		raise
	if recoveryCode in ("registry.recovery.restored", "registry.recovery.alreadyPrior"):
		return RegistryRepairOutcome(True, "registry.repair.recoveryRestored", {"recovery": True})
	return RegistryRepairOutcome(True, "registry.repair.repaired")
