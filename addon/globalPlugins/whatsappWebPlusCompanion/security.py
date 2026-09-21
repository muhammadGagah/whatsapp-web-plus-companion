import ctypes
import threading
from ctypes import wintypes
from dataclasses import dataclass

from .models import LoaderError


@dataclass(frozen=True, slots=True)
class SecurityProbe:
	canWrite: bool
	secureDesktop: bool
	locked: bool
	elevated: bool


def checkPreflight(probe: SecurityProbe) -> None:
	checks = (
		(not probe.canWrite, "security.noWrite"),
		(probe.secureDesktop, "security.secureDesktop"),
		(probe.locked, "security.locked"),
		(probe.elevated, "security.elevated"),
	)
	for failed, code in checks:
		if failed:
			raise LoaderError(code)


def _inputDesktopName() -> str | None:
	user32 = ctypes.WinDLL("user32", use_last_error=True)
	openInputDesktop = user32.OpenInputDesktop
	openInputDesktop.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
	openInputDesktop.restype = wintypes.HANDLE
	closeDesktop = user32.CloseDesktop
	closeDesktop.argtypes = (wintypes.HANDLE,)
	closeDesktop.restype = wintypes.BOOL
	getUserObjectInformation = user32.GetUserObjectInformationW
	getUserObjectInformation.argtypes = (
		wintypes.HANDLE,
		ctypes.c_int,
		wintypes.LPVOID,
		wintypes.DWORD,
		ctypes.POINTER(wintypes.DWORD),
	)
	getUserObjectInformation.restype = wintypes.BOOL
	desktop = openInputDesktop(0, False, 0x0001)
	if not desktop:
		return None
	try:
		needed = wintypes.DWORD()
		getUserObjectInformation(desktop, 2, None, 0, ctypes.byref(needed))
		if not needed.value:
			return None
		buffer = ctypes.create_unicode_buffer(needed.value // ctypes.sizeof(ctypes.c_wchar))
		if not getUserObjectInformation(desktop, 2, buffer, needed.value, ctypes.byref(needed)):
			return None
		return buffer.value
	finally:
		closeDesktop(desktop)


def _isElevated() -> bool:
	kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
	advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
	kernel32.GetCurrentProcess.argtypes = ()
	kernel32.GetCurrentProcess.restype = wintypes.HANDLE
	kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
	kernel32.CloseHandle.restype = wintypes.BOOL
	advapi32.OpenProcessToken.argtypes = (
		wintypes.HANDLE,
		wintypes.DWORD,
		ctypes.POINTER(wintypes.HANDLE),
	)
	advapi32.OpenProcessToken.restype = wintypes.BOOL
	advapi32.GetTokenInformation.argtypes = (
		wintypes.HANDLE,
		ctypes.c_int,
		wintypes.LPVOID,
		wintypes.DWORD,
		ctypes.POINTER(wintypes.DWORD),
	)
	advapi32.GetTokenInformation.restype = wintypes.BOOL
	token = wintypes.HANDLE()
	if not advapi32.OpenProcessToken(kernel32.GetCurrentProcess(), 0x0008, ctypes.byref(token)):
		raise LoaderError("security.probe", "openToken")
	try:
		elevation = wintypes.DWORD()
		returned = wintypes.DWORD()
		if not advapi32.GetTokenInformation(
			token,
			20,
			ctypes.byref(elevation),
			ctypes.sizeof(elevation),
			ctypes.byref(returned),
		):
			raise LoaderError("security.probe", "tokenElevation")
		return bool(elevation.value)
	finally:
		kernel32.CloseHandle(token)


def buildSecurityProbe() -> SecurityProbe:
	import NVDAState

	desktopName = _inputDesktopName()
	return SecurityProbe(
		canWrite=bool(NVDAState.shouldWriteToDisk()),
		secureDesktop=desktopName is None,
		locked=desktopName is not None and desktopName.casefold() != "default",
		elevated=_isElevated(),
	)


def announcementOutputAllowed() -> bool:
	"""Fail closed on lock, secure desktop, unknown session state or missing NVDA APIs."""
	try:
		import globalVars
		import NVDAState
		from utils.security import isRunningOnSecureDesktop
		from winAPI import sessionTracking

		if globalVars.appArgs.secure or not NVDAState.shouldWriteToDisk() or isRunningOnSecureDesktop():
			return False
		if (_inputDesktopName() or "").casefold() != "default":
			return False
		# The public predicate intentionally treats an unknown WTS state as unlocked.
		# Private WhatsApp content needs the stricter result. Both supported NVDA
		# branches expose this helper; a future incompatible API fails closed.
		state = sessionTracking._getSessionLockedValue()
		return int(state) == 1 and not sessionTracking.isLockScreenModeActive()
	except Exception:
		return False


class AnnouncementGuard:
	"""Share a security generation across the worker, GUI queue and braille timers."""

	def __init__(self, probe=None):
		self._probe = probe or announcementOutputAllowed
		self._lock = threading.RLock()
		self._blocks = set()
		self._allowed = None
		self._epoch = 0

	def setBlocked(self, source: str, blocked: bool) -> None:
		with self._lock:
			before = source in self._blocks
			if blocked:
				self._blocks.add(source)
			else:
				self._blocks.discard(source)
			if before != blocked:
				# Invalidate even a short lock/unlock that occurs between worker polls.
				self._epoch += 1
				self._allowed = None

	def snapshot(self) -> tuple[bool, int]:
		with self._lock:
			try:
				allowed = not self._blocks and self._probe() is True
			except Exception:
				allowed = False
			if self._allowed is not None and allowed != self._allowed:
				self._epoch += 1
			self._allowed = allowed
			return allowed, self._epoch

	def permits(self, epoch: int | None = None) -> bool:
		allowed, current = self.snapshot()
		return allowed and (epoch is None or current == epoch)
