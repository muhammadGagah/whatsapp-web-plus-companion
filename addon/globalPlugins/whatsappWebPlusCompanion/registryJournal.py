from __future__ import annotations

import ctypes
import json
import os
import uuid
from ctypes import wintypes
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol

_JOURNAL_SCHEMA_VERSION = 1
_JOURNAL_PHASES = frozenset({"prepared", "applied"})
_SID_BUFFER_BYTES = 512


class JournalError(RuntimeError):
	def __init__(self, code: str) -> None:
		super().__init__(code)
		self.code = code


class JournalCrypto(Protocol):
	def protect(self, payload: bytes) -> bytes: ...

	def unprotect(self, payload: bytes) -> bytes: ...


class JournalStorage(Protocol):
	def read(self) -> bytes | None: ...

	def write(self, payload: bytes) -> None: ...

	def clear(self) -> None: ...


class _DATA_BLOB(ctypes.Structure):
	_fields_ = (
		("cbData", wintypes.DWORD),
		("pbData", ctypes.POINTER(ctypes.c_char)),
	)


def _blobFromBytes(data: bytes) -> _DATA_BLOB:
	buffer = ctypes.create_string_buffer(data)
	return _DATA_BLOB(
		len(data),
		ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char)),
	)


class DpapiCrypto:
	"""Current-user DPAPI protection for the recovery journal payload."""

	def __init__(self) -> None:
		super().__init__()
		self._crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
		self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
		self._crypt32.CryptProtectData.argtypes = (
			ctypes.POINTER(_DATA_BLOB),
			wintypes.LPCWSTR,
			ctypes.POINTER(_DATA_BLOB),
			wintypes.LPVOID,
			wintypes.LPVOID,
			wintypes.DWORD,
			ctypes.POINTER(_DATA_BLOB),
		)
		self._crypt32.CryptProtectData.restype = wintypes.BOOL
		self._crypt32.CryptUnprotectData.argtypes = (
			ctypes.POINTER(_DATA_BLOB),
			wintypes.LPVOID,
			ctypes.POINTER(_DATA_BLOB),
			wintypes.LPVOID,
			wintypes.LPVOID,
			wintypes.DWORD,
			ctypes.POINTER(_DATA_BLOB),
		)
		self._crypt32.CryptUnprotectData.restype = wintypes.BOOL
		self._kernel32.LocalFree.argtypes = (ctypes.c_void_p,)
		self._kernel32.LocalFree.restype = ctypes.c_void_p

	def protect(self, payload: bytes) -> bytes:
		blobIn = _blobFromBytes(payload)
		blobOut = _DATA_BLOB()
		if not self._crypt32.CryptProtectData(
			ctypes.byref(blobIn),
			None,
			None,
			None,
			None,
			0,
			ctypes.byref(blobOut),
		):
			raise OSError(ctypes.get_last_error(), "CryptProtectData failed")
		try:
			return ctypes.string_at(blobOut.pbData, blobOut.cbData)
		finally:
			self._kernel32.LocalFree(blobOut.pbData)

	def unprotect(self, payload: bytes) -> bytes:
		blobIn = _blobFromBytes(payload)
		blobOut = _DATA_BLOB()
		if not self._crypt32.CryptUnprotectData(
			ctypes.byref(blobIn),
			None,
			None,
			None,
			None,
			0,
			ctypes.byref(blobOut),
		):
			raise OSError(ctypes.get_last_error(), "CryptUnprotectData failed")
		try:
			return ctypes.string_at(blobOut.pbData, blobOut.cbData)
		finally:
			self._kernel32.LocalFree(blobOut.pbData)


class FileJournalStorage:
	def __init__(self, path: Path) -> None:
		super().__init__()
		self._path = path

	def read(self) -> bytes | None:
		try:
			return self._path.read_bytes()
		except FileNotFoundError:
			return None
		except OSError as error:
			raise JournalError("storageRead") from error

	def write(self, payload: bytes) -> None:
		try:
			self._path.parent.mkdir(parents=True, exist_ok=True)
			temporary = self._path.with_suffix(f"{self._path.suffix}.tmp")
			with temporary.open("wb") as handle:
				handle.write(payload)
				handle.flush()
				os.fsync(handle.fileno())
			os.replace(temporary, self._path)
		except OSError as error:
			raise JournalError("storageWrite") from error

	def clear(self) -> None:
		try:
			self._path.unlink(missing_ok=True)
		except OSError as error:
			raise JournalError("storageClear") from error


@dataclass(frozen=True, slots=True)
class JournalEntry:
	schemaVersion: int
	sid: str
	aumid: str
	priorPresent: bool
	priorData: str
	priorType: int
	ownedData: str
	operationId: str
	phase: str


def _parseEntry(payload: object) -> JournalEntry:
	if not isinstance(payload, dict):
		raise JournalError("shape")
	try:
		entry = JournalEntry(**payload)
	except TypeError as error:
		raise JournalError("shape") from error
	if entry.schemaVersion != _JOURNAL_SCHEMA_VERSION:
		raise JournalError("schema")
	if entry.phase not in _JOURNAL_PHASES:
		raise JournalError("phase")
	if not entry.sid or not entry.aumid or not entry.ownedData:
		raise JournalError("shape")
	if not isinstance(entry.priorData, str) or not isinstance(entry.priorType, int):
		raise JournalError("shape")
	return entry


def currentUserSid() -> str:
	kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
	advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
	kernel32.GetCurrentProcess.argtypes = ()
	kernel32.GetCurrentProcess.restype = wintypes.HANDLE
	kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
	kernel32.CloseHandle.restype = wintypes.BOOL
	kernel32.LocalFree.argtypes = (ctypes.c_void_p,)
	kernel32.LocalFree.restype = ctypes.c_void_p
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
	advapi32.ConvertSidToStringSidW.argtypes = (
		wintypes.LPVOID,
		ctypes.POINTER(wintypes.LPWSTR),
	)
	advapi32.ConvertSidToStringSidW.restype = wintypes.BOOL

	token = wintypes.HANDLE()
	if not advapi32.OpenProcessToken(
		kernel32.GetCurrentProcess(),
		0x0008,
		ctypes.byref(token),
	):
		raise JournalError("sidToken")
	try:
		buffer = ctypes.create_string_buffer(_SID_BUFFER_BYTES)
		returned = wintypes.DWORD()
		if not advapi32.GetTokenInformation(
			token,
			1,
			buffer,
			_SID_BUFFER_BYTES,
			ctypes.byref(returned),
		):
			raise JournalError("sidTokenInfo")
		sidPointer = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_void_p))[0]
		if not sidPointer:
			raise JournalError("sidTokenInfo")
		stringPointer = wintypes.LPWSTR()
		if not advapi32.ConvertSidToStringSidW(sidPointer, ctypes.byref(stringPointer)):
			raise JournalError("sidString")
		try:
			return str(stringPointer.value)
		finally:
			kernel32.LocalFree(stringPointer)
	finally:
		kernel32.CloseHandle(token)


def defaultJournalPath() -> Path:
	base: Path | None = None
	try:
		import NVDAState

		writePaths = getattr(NVDAState, "WritePaths", None)
		configDir = getattr(writePaths, "configDir", None)
		if configDir:
			base = Path(configDir)
	except ImportError:
		pass
	if base is None:
		# NVDA 2024.1 exposes the active --config-path through appArgs. Keep
		# this fallback for older supported builds and test environments.
		try:
			import globalVars

			configPath = getattr(globalVars.appArgs, "configPath", None)
			if configPath:
				base = Path(configPath)
		except (AttributeError, ImportError):
			pass
	if base is None:
		appData = os.environ.get("APPDATA")
		if not appData:
			raise JournalError("configPath")
		base = Path(appData) / "nvda"
	return base / "whatsappWebPlusCompanion" / "registry-recovery.bin"


class RegistryJournal:
	def __init__(
		self,
		sid: str,
		crypto: JournalCrypto | None = None,
		storage: JournalStorage | None = None,
	) -> None:
		super().__init__()
		self.sid = sid
		self._crypto = crypto or DpapiCrypto()
		self._storage = storage or FileJournalStorage(defaultJournalPath())

	@classmethod
	def createDefault(cls) -> RegistryJournal:
		return cls(currentUserSid())

	def load(self) -> JournalEntry | None:
		raw = self._storage.read()
		if raw is None:
			return None
		try:
			plaintext = self._crypto.unprotect(raw)
		except OSError as error:
			raise JournalError("decrypt") from error
		try:
			payload = json.loads(plaintext.decode("utf-8", "strict"))
		except (UnicodeDecodeError, json.JSONDecodeError) as error:
			raise JournalError("json") from error
		entry = _parseEntry(payload)
		if entry.sid != self.sid:
			raise JournalError("identity")
		return entry

	def write(self, entry: JournalEntry) -> None:
		if entry.sid != self.sid:
			raise JournalError("identity")
		payload = json.dumps(
			asdict(entry),
			separators=(",", ":"),
			sort_keys=True,
		).encode("utf-8")
		self._storage.write(self._crypto.protect(payload))

	def clear(self) -> None:
		self._storage.clear()


def newOperationId() -> str:
	return uuid.uuid4().hex
