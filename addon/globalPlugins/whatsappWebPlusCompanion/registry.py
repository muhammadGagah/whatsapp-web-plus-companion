from __future__ import annotations

import ctypes
import re
import winreg
from ctypes import wintypes
from dataclasses import dataclass, field
from typing import NoReturn, Protocol

from .models import LoaderError
from .policy import REGISTRY_PATH, ChannelPolicy
from .registryJournal import JournalEntry, JournalError, RegistryJournal

_REGISTRY_MUTEX_NAME = "Local\\WhatsAppWebPlusCompanionRegistryLease"
_REMOTE_DEBUGGING_ARGUMENT = re.compile(r"--remote-debugging-port=\d+")
_WAIT_OBJECT_0 = 0
_WAIT_ABANDONED = 0x80
_WAIT_TIMEOUT = 0x102
_WAIT_FAILED = 0xFFFFFFFF
_ACCESS_DENIED_WINERROR = 5
# Value types the Companion accepts for a pre-existing WebView2 argument value.
# The original type is preserved exactly on restore.
_SUPPORTED_VALUE_TYPES = frozenset({winreg.REG_SZ, winreg.REG_EXPAND_SZ})


def _raiseStageError(stage: str, error: OSError) -> NoReturn:
	winerror = getattr(error, "winerror", None)
	# winreg reports ERROR_ACCESS_DENIED through winerror; some Python paths
	# surface EACCES through errno only. Both mean the same user-visible denial.
	errnoValue = getattr(error, "errno", None)
	if winerror == _ACCESS_DENIED_WINERROR or errnoValue in (5, 13):
		code = f"registry.{stage}AccessDenied"
	else:
		code = f"registry.{stage}Failed"
	raise LoaderError(code, f"stage={stage};winerror={winerror}")


def acquireRegistryMutex() -> int:
	kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
	createMutex = kernel32.CreateMutexW
	createMutex.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR)
	createMutex.restype = wintypes.HANDLE
	waitForSingleObject = kernel32.WaitForSingleObject
	waitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
	waitForSingleObject.restype = wintypes.DWORD
	closeHandle = kernel32.CloseHandle
	closeHandle.argtypes = (wintypes.HANDLE,)
	closeHandle.restype = wintypes.BOOL

	handle = createMutex(None, False, _REGISTRY_MUTEX_NAME)
	if not handle:
		raise LoaderError(
			"registry.mutex.createFailed",
			f"stage=mutex.create;winerror={ctypes.get_last_error()}",
		)
	result = waitForSingleObject(handle, 0)
	if result == _WAIT_FAILED:
		closeHandle(handle)
		raise LoaderError(
			"registry.mutex.waitFailed",
			f"stage=mutex.wait;winerror={ctypes.get_last_error()}",
		)
	if result not in (_WAIT_OBJECT_0, _WAIT_ABANDONED):
		closeHandle(handle)
		raise LoaderError("registry.mutex.busy", "stage=mutex.wait;winerror=258")
	return int(handle)


def releaseRegistryMutex(handle: int) -> None:
	kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
	releaseMutex = kernel32.ReleaseMutex
	releaseMutex.argtypes = (wintypes.HANDLE,)
	releaseMutex.restype = wintypes.BOOL
	closeHandle = kernel32.CloseHandle
	closeHandle.argtypes = (wintypes.HANDLE,)
	closeHandle.restype = wintypes.BOOL
	try:
		releaseMutex(handle)
	finally:
		closeHandle(handle)


@dataclass(frozen=True, slots=True)
class RegistryValue:
	data: str
	valueType: int


class RegistryApi(Protocol):
	def readMachinePolicy(self, valueName: str) -> RegistryValue | None: ...

	def readUserValue(self, valueName: str) -> RegistryValue | None: ...

	def openOrCreateUserLeaf(self, stage: str = "user.openCreate") -> object: ...

	def openUserLeafReadOnly(self, stage: str = "user.open") -> object | None: ...

	def closeUserLeaf(self, key: object) -> None: ...

	def setUserValue(
		self,
		key: object,
		valueName: str,
		value: RegistryValue,
		stage: str = "user.set",
	) -> None: ...

	def deleteUserValue(self, key: object, valueName: str, stage: str = "restore.delete") -> None: ...

	def verifyUserValue(self, valueName: str, expected: RegistryValue | None) -> bool: ...


@dataclass(slots=True)
class RegistryLease:
	policy: ChannelPolicy
	port: int
	registry: RegistryApi
	prior: RegistryValue | None = None
	owned: bool = False
	journal: RegistryJournal | None = None
	operationId: str = ""
	_mutexHandle: int | None = field(default=None, init=False, repr=False)
	_temporary: RegistryValue | None = field(default=None, init=False, repr=False)

	def _journalWrite(self, phase: str) -> None:
		if self.journal is None or self._temporary is None:
			return
		prior = self.prior
		self.journal.write(
			JournalEntry(
				schemaVersion=1,
				sid=self.journal.sid,
				aumid=self.policy.aumid,
				priorPresent=prior is not None,
				priorData=prior.data if prior is not None else "",
				priorType=prior.valueType if prior is not None else 0,
				ownedData=self._temporary.data,
				operationId=self.operationId or "",
				phase=phase,
			),
		)

	def acquire(self) -> None:
		if self.owned:
			raise LoaderError("registry.alreadyOwned")
		if isinstance(self.registry, WinRegistry):
			self._mutexHandle = acquireRegistryMutex()
		mutationAttempted = False
		try:
			self._checkMachinePolicy()
			self.prior = self.registry.readUserValue(self.policy.aumid)
			if self.prior is not None and self.prior.valueType not in _SUPPORTED_VALUE_TYPES:
				raise LoaderError(
					"registry.user.invalidValueType",
					f"stage=user.read;valueType={self.prior.valueType}",
				)
			if self.prior is not None and _REMOTE_DEBUGGING_ARGUMENT.fullmatch(self.prior.data.strip()):
				raise LoaderError("registry.user.debugArgumentPresent", "stage=user.read")
			temporary = RegistryValue(f"--remote-debugging-port={self.port}", winreg.REG_SZ)
			self._temporary = temporary
			try:
				self._journalWrite("prepared")
			except JournalError as error:
				raise LoaderError(
					"registry.recovery.unreadable",
					f"stage=journal.prepare;code={error.code}",
				) from error
			# Treat the write as possibly committed even when the API raises. A
			# provider can fail after changing the live value, so every path from
			# here must compare-and-restore before releasing the mutex.
			mutationAttempted = True
			self._writeValue(
				self.policy.aumid,
				temporary,
				openStage="user.openCreate",
				setStage="user.set",
			)
			if not self.registry.verifyUserValue(self.policy.aumid, temporary):
				raise LoaderError("registry.user.verifyMismatch", "stage=user.verify")
			try:
				self._journalWrite("applied")
			except JournalError as error:
				raise LoaderError(
					"registry.recovery.unreadable",
					f"stage=journal.apply;code={error.code}",
				) from error
		except Exception as acquireError:
			rollbackError: Exception | None = None
			if mutationAttempted:
				try:
					self._restoreValue()
				except Exception as error:
					rollbackError = error
			self._releaseMutex()
			if rollbackError is not None:
				if isinstance(rollbackError, LoaderError):
					raise rollbackError from acquireError
				if isinstance(rollbackError, JournalError):
					raise LoaderError(
						"registry.recovery.unreadable",
						f"stage=journal.rollback;code={rollbackError.code}",
					) from acquireError
				raise LoaderError(
					"registry.restore.verifyMismatch",
					"stage=acquire.rollback",
				) from rollbackError
			raise
		self.owned = True

	def _checkMachinePolicy(self) -> None:
		for valueName, code in (
			(self.policy.aumid, "registry.machine.policyAumid"),
			("*", "registry.machine.policyWildcard"),
		):
			if self.registry.readMachinePolicy(valueName) is not None:
				raise LoaderError(code, f"stage=machine.read;value={valueName}")

	def _writeValue(
		self,
		valueName: str,
		value: RegistryValue,
		*,
		openStage: str,
		setStage: str,
	) -> None:
		key = self.registry.openOrCreateUserLeaf(stage=openStage)
		try:
			self.registry.setUserValue(key, valueName, value, stage=setStage)
		finally:
			self.registry.closeUserLeaf(key)

	def restore(self) -> None:
		if not self.owned:
			return
		try:
			self._restoreValue()
		except LoaderError:
			# The transaction ends even when restoration fails: the encrypted
			# journal keeps the evidence and pre-launch recovery retries it.
			self.owned = False
			self._releaseMutex()
			raise
		self.owned = False
		self._releaseMutex()

	def _restoreValue(self) -> None:
		current = self.registry.readUserValue(self.policy.aumid)
		if current == self.prior:
			# Already at the prior state: consider restoration complete.
			if self.journal is not None:
				self.journal.clear()
			return
		if current != self._temporary:
			raise LoaderError(
				"registry.restore.conflict",
				"stage=restore.read",
				values={"conflict": True},
			)
		if self.prior is None:
			key = self.registry.openOrCreateUserLeaf(stage="restore.open")
			try:
				self.registry.deleteUserValue(key, self.policy.aumid, stage="restore.delete")
			finally:
				self.registry.closeUserLeaf(key)
		else:
			self._writeValue(
				self.policy.aumid,
				self.prior,
				openStage="restore.open",
				setStage="restore.set",
			)
		if not self.registry.verifyUserValue(self.policy.aumid, self.prior):
			raise LoaderError("registry.restore.verifyMismatch", "stage=restore.verify")
		if self.journal is not None:
			self.journal.clear()

	def _releaseMutex(self) -> None:
		if self._mutexHandle is None:
			return
		releaseRegistryMutex(self._mutexHandle)
		self._mutexHandle = None

	def __enter__(self) -> RegistryLease:
		self.acquire()
		return self

	def __exit__(self, excType, excValue, traceback) -> None:
		self.restore()


class WinRegistry:
	@staticmethod
	def _read(root, valueName: str, stage: str) -> RegistryValue | None:
		try:
			with winreg.OpenKey(root, REGISTRY_PATH, 0, winreg.KEY_QUERY_VALUE) as key:
				value, valueType = winreg.QueryValueEx(key, valueName)
		except FileNotFoundError:
			return None
		except OSError as error:
			_raiseStageError(stage, error)
		if not isinstance(value, str):
			if stage == "machine.read":
				# Presence is all the machine-policy check needs; the value
				# type is irrelevant to a policy conflict.
				return RegistryValue(str(value), valueType)
			raise LoaderError("registry.user.invalidValueType", f"stage=user.read;valueType={valueType}")
		return RegistryValue(value, valueType)

	def readMachinePolicy(self, valueName: str) -> RegistryValue | None:
		return self._read(winreg.HKEY_LOCAL_MACHINE, valueName, "machine.read")

	def readUserValue(self, valueName: str) -> RegistryValue | None:
		return self._read(winreg.HKEY_CURRENT_USER, valueName, "user.read")

	def openOrCreateUserLeaf(self, stage: str = "user.openCreate") -> winreg.HKEYType:
		try:
			return winreg.CreateKeyEx(
				winreg.HKEY_CURRENT_USER,
				REGISTRY_PATH,
				0,
				winreg.KEY_QUERY_VALUE | winreg.KEY_SET_VALUE,
			)
		except OSError as error:
			_raiseStageError(stage, error)

	def openUserLeafReadOnly(self, stage: str = "user.open") -> winreg.HKEYType | None:
		try:
			return winreg.OpenKey(
				winreg.HKEY_CURRENT_USER,
				REGISTRY_PATH,
				0,
				winreg.KEY_QUERY_VALUE | winreg.KEY_SET_VALUE,
			)
		except FileNotFoundError:
			return None
		except OSError as error:
			_raiseStageError(stage, error)

	def closeUserLeaf(self, key: object) -> None:
		if isinstance(key, winreg.HKEYType):
			key.Close()

	def setUserValue(
		self,
		key: object,
		valueName: str,
		value: RegistryValue,
		stage: str = "user.set",
	) -> None:
		try:
			winreg.SetValueEx(key, valueName, 0, value.valueType, value.data)
		except OSError as error:
			_raiseStageError(stage, error)

	def deleteUserValue(self, key: object, valueName: str, stage: str = "restore.delete") -> None:
		try:
			winreg.DeleteValue(key, valueName)
		except OSError as error:
			_raiseStageError(stage, error)

	def verifyUserValue(self, valueName: str, expected: RegistryValue | None) -> bool:
		return self.readUserValue(valueName) == expected


class MemoryRegistry:
	def __init__(self, prior: RegistryValue | None = None, machinePolicy: bool = False) -> None:
		super().__init__()
		self.current = prior
		self.machinePolicy = machinePolicy

	def readMachinePolicy(self, valueName: str) -> RegistryValue | None:
		return RegistryValue("machine", 1) if self.machinePolicy else None

	def readUserValue(self, valueName: str) -> RegistryValue | None:
		return self.current

	def openOrCreateUserLeaf(self, stage: str = "user.openCreate") -> object:
		return object()

	def openUserLeafReadOnly(self, stage: str = "user.open") -> object | None:
		return object()

	def closeUserLeaf(self, key: object) -> None:
		return

	def setUserValue(
		self,
		key: object,
		valueName: str,
		value: RegistryValue,
		stage: str = "user.set",
	) -> None:
		self.current = value

	def deleteUserValue(self, key: object, valueName: str, stage: str = "restore.delete") -> None:
		self.current = None

	def verifyUserValue(self, valueName: str, expected: RegistryValue | None) -> bool:
		return self.current == expected


def recoverPendingRegistryState(
	registry: RegistryApi,
	journal: RegistryJournal,
) -> tuple[str, str]:
	"""Resolve any pending recovery journal before a new lease is applied.

	Returns (code, detail) where code is a stable launch-safe outcome:
	"registry.recovery.none", "registry.recovery.restored", or
	"registry.recovery.alreadyPrior". Foreign live values raise
	"registry.restore.conflict" without mutation.
	"""
	entry = journal.load()
	if entry is None:
		return "registry.recovery.none", "stage=recovery.load;entry=none"
	live = registry.readUserValue(entry.aumid)
	prior = RegistryValue(entry.priorData, entry.priorType) if entry.priorPresent else None
	owned = RegistryValue(entry.ownedData, winreg.REG_SZ)
	if live == prior:
		journal.clear()
		return "registry.recovery.alreadyPrior", "stage=recovery.read;entry=prior"
	if live != owned:
		raise LoaderError(
			"registry.restore.conflict",
			"stage=recovery.read",
			values={"conflict": True},
		)
	key = registry.openOrCreateUserLeaf(stage="restore.open")
	try:
		if prior is None:
			registry.deleteUserValue(key, entry.aumid, stage="restore.delete")
		else:
			registry.setUserValue(key, entry.aumid, prior, stage="restore.set")
	finally:
		registry.closeUserLeaf(key)
	if not registry.verifyUserValue(entry.aumid, prior):
		raise LoaderError("registry.restore.verifyMismatch", "stage=recovery.verify")
	journal.clear()
	return "registry.recovery.restored", "stage=recovery.restore;entry=applied"
