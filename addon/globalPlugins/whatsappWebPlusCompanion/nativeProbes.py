"""In-process Win32 snapshots of TCP listeners and processes.

The PowerShell probes query WMI. On a busy or freshly started computer, or when WMI is
unhealthy, those queries can take long enough to exhaust the whole launch budget. These helpers ask Windows directly and return rows
with the same keys as the PowerShell JSON, so the callers keep one validation path.

Every failure raises NativeProbeUnavailable; callers then fall back to PowerShell.
"""

import ctypes
import socket
import struct
from ctypes import wintypes

try:
	from logHandler import log
except ImportError:
	import logging

	log = logging.getLogger(__name__)

AF_INET = 2
AF_INET6 = 23
TCP_TABLE_OWNER_PID_LISTENER = 3
TCP_TABLE_OWNER_PID_ALL = 5
MIB_TCP_STATE_LISTEN = 2
MIB_TCP_STATE_ESTAB = 5
ERROR_INSUFFICIENT_BUFFER = 122
NO_ERROR = 0
TH32CS_SNAPPROCESS = 0x00000002
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
_MAX_PATH_CHARS = 32768


class NativeProbeUnavailable(Exception):
	"""The native snapshot could not be taken; use the PowerShell probe instead."""


def noteFallback(stage: str, error: Exception) -> None:
	log.info("WhatsApp Companion native %s probe unavailable, using PowerShell: %s", stage, error)


class _TcpRow(ctypes.Structure):
	_fields_ = [
		("dwState", wintypes.DWORD),
		("dwLocalAddr", wintypes.DWORD),
		("dwLocalPort", wintypes.DWORD),
		("dwRemoteAddr", wintypes.DWORD),
		("dwRemotePort", wintypes.DWORD),
		("dwOwningPid", wintypes.DWORD),
	]


class _Tcp6Row(ctypes.Structure):
	_fields_ = [
		("ucLocalAddr", ctypes.c_ubyte * 16),
		("dwLocalScopeId", wintypes.DWORD),
		("dwLocalPort", wintypes.DWORD),
		("ucRemoteAddr", ctypes.c_ubyte * 16),
		("dwRemoteScopeId", wintypes.DWORD),
		("dwRemotePort", wintypes.DWORD),
		("dwState", wintypes.DWORD),
		("dwOwningPid", wintypes.DWORD),
	]


class _ProcessEntry(ctypes.Structure):
	_fields_ = [
		("dwSize", wintypes.DWORD),
		("cntUsage", wintypes.DWORD),
		("th32ProcessID", wintypes.DWORD),
		("th32DefaultHeapID", ctypes.c_size_t),
		("th32ModuleID", wintypes.DWORD),
		("cntThreads", wintypes.DWORD),
		("th32ParentProcessID", wintypes.DWORD),
		("pcPriClassBase", wintypes.LONG),
		("dwFlags", wintypes.DWORD),
		("szExeFile", wintypes.WCHAR * 260),
	]


def _libraries():
	try:
		iphlpapi = ctypes.WinDLL("iphlpapi", use_last_error=True)
		kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
	except (AttributeError, OSError) as error:
		raise NativeProbeUnavailable("libraries") from error
	iphlpapi.GetExtendedTcpTable.argtypes = [
		ctypes.c_void_p,
		ctypes.POINTER(wintypes.DWORD),
		wintypes.BOOL,
		wintypes.ULONG,
		ctypes.c_int,
		wintypes.ULONG,
	]
	iphlpapi.GetExtendedTcpTable.restype = wintypes.DWORD
	kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
	kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
	kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_ProcessEntry)]
	kernel32.Process32FirstW.restype = wintypes.BOOL
	kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_ProcessEntry)]
	kernel32.Process32NextW.restype = wintypes.BOOL
	kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
	kernel32.OpenProcess.restype = wintypes.HANDLE
	kernel32.QueryFullProcessImageNameW.argtypes = [
		wintypes.HANDLE,
		wintypes.DWORD,
		wintypes.LPWSTR,
		ctypes.POINTER(wintypes.DWORD),
	]
	kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
	kernel32.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
	kernel32.GetProcessTimes.restype = wintypes.BOOL
	kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
	kernel32.CloseHandle.restype = wintypes.BOOL
	return iphlpapi, kernel32


def _tcpTable(iphlpapi, family: int, tableClass: int) -> bytes:
	size = wintypes.DWORD(0)
	for _attempt in range(8):
		buffer = ctypes.create_string_buffer(max(size.value, 4))
		result = iphlpapi.GetExtendedTcpTable(buffer, ctypes.byref(size), False, family, tableClass, 0)
		if result == NO_ERROR:
			return buffer.raw
		if result != ERROR_INSUFFICIENT_BUFFER:
			raise NativeProbeUnavailable(f"tcpTable={result}")
	raise NativeProbeUnavailable("tcpTable=growing")


def _rows(raw: bytes, rowType) -> list:
	(count,) = struct.unpack_from("<I", raw, 0)
	rowSize = ctypes.sizeof(rowType)
	if 4 + count * rowSize > len(raw):
		raise NativeProbeUnavailable("tcpTable=truncated")
	return [rowType.from_buffer_copy(raw, 4 + index * rowSize) for index in range(count)]


def _port(value: int) -> int:
	return socket.ntohs(value & 0xFFFF)


def tcpRows(state: str, localPort: int, remotePort: int | None = None) -> list[dict]:
	"""Rows shaped like Get-NetTCPConnection output for one local port, both IP families."""
	if state == "listen":
		tableClass, wanted = TCP_TABLE_OWNER_PID_LISTENER, MIB_TCP_STATE_LISTEN
	elif state == "established":
		tableClass, wanted = TCP_TABLE_OWNER_PID_ALL, MIB_TCP_STATE_ESTAB
	else:
		raise ValueError(state)
	iphlpapi, _kernel32 = _libraries()
	result = []
	try:
		for row in _rows(_tcpTable(iphlpapi, AF_INET, tableClass), _TcpRow):
			if row.dwState != wanted or _port(row.dwLocalPort) != localPort:
				continue
			if remotePort is not None and _port(row.dwRemotePort) != remotePort:
				continue
			result.append(
				{
					"LocalAddress": socket.inet_ntoa(struct.pack("<I", row.dwLocalAddr)),
					"RemoteAddress": socket.inet_ntoa(struct.pack("<I", row.dwRemoteAddr)),
					"LocalPort": _port(row.dwLocalPort),
					"RemotePort": _port(row.dwRemotePort),
					"OwningProcess": int(row.dwOwningPid),
				},
			)
		for row in _rows(_tcpTable(iphlpapi, AF_INET6, tableClass), _Tcp6Row):
			if row.dwState != wanted or _port(row.dwLocalPort) != localPort:
				continue
			if remotePort is not None and _port(row.dwRemotePort) != remotePort:
				continue
			result.append(
				{
					"LocalAddress": socket.inet_ntop(socket.AF_INET6, bytes(row.ucLocalAddr)),
					"RemoteAddress": socket.inet_ntop(socket.AF_INET6, bytes(row.ucRemoteAddr)),
					"LocalPort": _port(row.dwLocalPort),
					"RemotePort": _port(row.dwRemotePort),
					"OwningProcess": int(row.dwOwningPid),
				},
			)
	except (OSError, ValueError, struct.error) as error:
		raise NativeProbeUnavailable("tcpTable=parse") from error
	return result


def _details(kernel32, pid: int) -> tuple[str, int]:
	"""Return the Win32 image path and creation FILETIME, or ("", 0) when access is denied."""
	handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
	if not handle:
		return "", 0
	try:
		path = ""
		buffer = ctypes.create_unicode_buffer(_MAX_PATH_CHARS)
		length = wintypes.DWORD(_MAX_PATH_CHARS)
		if kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(length)):
			path = buffer.value
		created = 0
		times = [wintypes.FILETIME() for _ in range(4)]
		if kernel32.GetProcessTimes(handle, *(ctypes.byref(item) for item in times)):
			created = (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
			# WMI's CreationDate, used by the PowerShell probe, keeps microseconds only.
			created -= created % 10
		return path, created
	finally:
		kernel32.CloseHandle(handle)


def processRows(*, details: bool) -> list[dict]:
	"""Rows shaped like Win32_Process output: ProcessId, ParentProcessId and, with details,
	ExecutablePath and Created (FILETIME UTC, as PowerShell's ToFileTimeUtc())."""
	_iphlpapi, kernel32 = _libraries()
	snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
	if not snapshot or snapshot == _INVALID_HANDLE_VALUE:
		raise NativeProbeUnavailable(f"snapshot={ctypes.get_last_error()}")
	entries: list[tuple[int, int]] = []
	try:
		entry = _ProcessEntry()
		entry.dwSize = ctypes.sizeof(_ProcessEntry)
		ok = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
		if not ok:
			raise NativeProbeUnavailable(f"snapshotFirst={ctypes.get_last_error()}")
		while ok:
			entries.append((int(entry.th32ProcessID), int(entry.th32ParentProcessID)))
			ok = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
	finally:
		kernel32.CloseHandle(snapshot)
	rows = []
	for pid, parent in entries:
		row = {"ProcessId": pid, "ParentProcessId": parent}
		if details:
			path, created = _details(kernel32, pid) if pid else ("", 0)
			row["ExecutablePath"] = path or None
			row["Created"] = created
		rows.append(row)
	return rows


def processDetails(pid: int) -> tuple[str, int]:
	"""Image path and creation FILETIME of one process, or ("", 0) when it cannot be read."""
	if pid <= 0:
		return "", 0
	_iphlpapi, kernel32 = _libraries()
	return _details(kernel32, pid)


def processAgeSeconds(pid: int, now: float | None = None) -> float | None:
	"""Seconds since the process started, or None when Windows does not say."""
	import time

	_path, created = processDetails(pid)
	if created <= 0:
		return None
	current = time.time() if now is None else now
	return current - (created / 10_000_000 - 11644473600)
