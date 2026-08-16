import pathlib
import unittest
from unittest.mock import patch

from _path import installPackagePath

installPackagePath()

from globalPlugins.whatsappWebPlusCompanion.models import Channel, LoaderError
from globalPlugins.whatsappWebPlusCompanion.policy import CHANNELS
from globalPlugins.whatsappWebPlusCompanion.registry import (
	MemoryRegistry,
	RegistryLease,
	RegistryValue,
	acquireRegistryMutex,
	_raiseStageError,
	recoverPendingRegistryState,
)
from globalPlugins.whatsappWebPlusCompanion.registryJournal import (
	JournalEntry,
	JournalError,
	RegistryJournal,
)


class _FakeCallable:
	def __init__(self, impl) -> None:
		self._impl = impl

	def __call__(self, *args, **kwargs):
		return self._impl(*args, **kwargs)


class _FakeKernel32:
	def __init__(self, *, createHandle=7, waitResult=0, releaseResult=True) -> None:
		self.createHandle = createHandle
		self.waitResult = waitResult
		self.releaseResult = releaseResult
		self.CreateMutexW = _FakeCallable(lambda *a: self.createHandle)
		self.WaitForSingleObject = _FakeCallable(lambda *a: self.waitResult)
		self.CloseHandle = _FakeCallable(lambda *a: True)
		self.ReleaseMutex = _FakeCallable(lambda *a: self.releaseResult)


class RegistryErrorMappingTests(unittest.TestCase):
	def test_access_denied_maps_to_exact_stage_code(self) -> None:
		with self.assertRaises(LoaderError) as raised:
			_raiseStageError("user.openCreate", OSError(13, "denied", None, 5))
		self.assertEqual(raised.exception.code, "registry.user.openCreateAccessDenied")
		self.assertIn("stage=user.openCreate;winerror=5", raised.exception.safeDetail)

	def test_other_windows_error_maps_to_stage_failed_code(self) -> None:
		with self.assertRaises(LoaderError) as raised:
			_raiseStageError("restore.open", OSError(87, "bad parameter", None, 87))
		self.assertEqual(raised.exception.code, "registry.restore.openFailed")
		self.assertIn("winerror=87", raised.exception.safeDetail)

	def test_errno_access_denied_without_winerror_maps_to_denied_code(self) -> None:
		with self.assertRaises(LoaderError) as raised:
			_raiseStageError("user.openCreate", PermissionError(13, "Permission denied"))
		self.assertEqual(raised.exception.code, "registry.user.openCreateAccessDenied")

	def test_safe_detail_never_contains_value_data(self) -> None:
		with self.assertRaises(LoaderError) as raised:
			_raiseStageError("user.set", OSError(5, "denied", None, 5))
		self.assertNotIn("remote-debugging", raised.exception.safeDetail)
		self.assertEqual(raised.exception.values, {})

	def test_winregistry_stages_map_to_exact_plan_codes(self) -> None:
		for stage, expected in (
			("machine.read", "registry.machine.readAccessDenied"),
			("user.read", "registry.user.readAccessDenied"),
			("user.openCreate", "registry.user.openCreateAccessDenied"),
			("user.set", "registry.user.setAccessDenied"),
			("restore.open", "registry.restore.openAccessDenied"),
			("restore.delete", "registry.restore.deleteAccessDenied"),
			("restore.set", "registry.restore.setAccessDenied"),
		):
			with self.subTest(stage=stage):
				with self.assertRaises(LoaderError) as raised:
					_raiseStageError(stage, OSError(13, "denied", None, 5))
				self.assertEqual(raised.exception.code, expected)

	def test_no_literal_wow6432node(self) -> None:
		from globalPlugins.whatsappWebPlusCompanion import registry as registryModule

		source = pathlib.Path(registryModule.__file__).read_text(encoding="utf-8")
		self.assertNotIn("Wow6432Node", source)


class RegistryMutexTests(unittest.TestCase):
	@patch("globalPlugins.whatsappWebPlusCompanion.registry.ctypes.WinDLL")
	def test_mutex_creation_failure(self, winDll) -> None:
		winDll.return_value = _FakeKernel32(createHandle=None)
		with self.assertRaisesRegex(LoaderError, "registry.mutex.createFailed"):
			acquireRegistryMutex()

	@patch("globalPlugins.whatsappWebPlusCompanion.registry.ctypes.WinDLL")
	def test_mutex_wait_failure(self, winDll) -> None:
		winDll.return_value = _FakeKernel32(waitResult=0xFFFFFFFF)
		with self.assertRaisesRegex(LoaderError, "registry.mutex.waitFailed"):
			acquireRegistryMutex()

	@patch("globalPlugins.whatsappWebPlusCompanion.registry.ctypes.WinDLL")
	def test_mutex_busy_contention(self, winDll) -> None:
		winDll.return_value = _FakeKernel32(waitResult=0x102)
		with self.assertRaisesRegex(LoaderError, "registry.mutex.busy"):
			acquireRegistryMutex()

	@patch("globalPlugins.whatsappWebPlusCompanion.registry.ctypes.WinDLL")
	def test_mutex_abandoned_ownership_is_taken(self, winDll) -> None:
		winDll.return_value = _FakeKernel32(waitResult=0x80)
		handle = acquireRegistryMutex()
		self.assertEqual(handle, 7)


class RegistryLeaseTests(unittest.TestCase):
	def test_acquire_and_restore_preserve_absent_and_existing_prior(self) -> None:
		for prior in (None, RegistryValue("--old", 1)):
			registry = MemoryRegistry(prior)
			lease = RegistryLease(CHANNELS[Channel.BETA], 49223, registry)
			lease.acquire()
			self.assertEqual(
				registry.current,
				RegistryValue("--remote-debugging-port=49223", 1),
			)
			lease.restore()
			self.assertEqual(registry.current, prior)
			self.assertFalse(lease.owned)

	def test_restore_is_idempotent_when_live_value_already_prior(self) -> None:
		prior = RegistryValue("--old", 1)
		registry = MemoryRegistry(prior)
		lease = RegistryLease(CHANNELS[Channel.BETA], 49223, registry)
		lease.acquire()
		registry.current = prior
		lease.restore()
		self.assertFalse(lease.owned)
		self.assertEqual(registry.current, prior)

	def test_restore_conflict_never_overwrites_foreign_value(self) -> None:
		registry = MemoryRegistry(RegistryValue("--old", 1))
		lease = RegistryLease(CHANNELS[Channel.BETA], 49223, registry)
		lease.acquire()
		foreign = RegistryValue("--foreign", 1)
		registry.current = foreign
		with self.assertRaisesRegex(LoaderError, "registry.restore.conflict"):
			lease.restore()
		self.assertEqual(registry.current, foreign)
		self.assertFalse(lease.owned)

	def test_restore_verification_mismatch_raises_exact_code(self) -> None:
		class FailRestoreVerifyRegistry(MemoryRegistry):
			def __init__(self) -> None:
				super().__init__(None)
				self.failVerify = False

			def verifyUserValue(self, valueName, expected):
				if self.failVerify:
					return False
				return super().verifyUserValue(valueName, expected)

		registry = FailRestoreVerifyRegistry()
		lease = RegistryLease(CHANNELS[Channel.BETA], 49223, registry)
		lease.acquire()
		registry.failVerify = True
		with self.assertRaisesRegex(LoaderError, "registry.restore.verifyMismatch"):
			lease.restore()
		self.assertFalse(lease.owned)

	def test_failed_acquire_verification_rolls_back_before_returning(self) -> None:
		prior = RegistryValue("--old", 1)

		class FailAcquireVerifyRegistry(MemoryRegistry):
			def verifyUserValue(self, valueName, expected):
				if expected is not None and expected.data.startswith("--remote-debugging-port="):
					return False
				return super().verifyUserValue(valueName, expected)

		registry = FailAcquireVerifyRegistry(prior)
		lease = RegistryLease(CHANNELS[Channel.BETA], 49223, registry)

		with self.assertRaisesRegex(LoaderError, "registry.user.verifyMismatch"):
			lease.acquire()

		self.assertEqual(registry.current, prior)
		self.assertFalse(lease.owned)

	def test_write_that_mutates_then_raises_is_rolled_back(self) -> None:
		prior = RegistryValue("--old", 1)

		class MutateThenFailRegistry(MemoryRegistry):
			def setUserValue(self, key, valueName, value, stage="user.set"):
				super().setUserValue(key, valueName, value, stage)
				if stage == "user.set":
					raise LoaderError("registry.user.setFailed", "stage=user.set")

		registry = MutateThenFailRegistry(prior)
		lease = RegistryLease(CHANNELS[Channel.BETA], 49223, registry)

		with self.assertRaisesRegex(LoaderError, "registry.user.setFailed"):
			lease.acquire()

		self.assertEqual(registry.current, prior)

	def test_applied_journal_failure_rolls_back_live_value(self) -> None:
		prior = RegistryValue("--old", 1)

		class FailAppliedJournal:
			sid = "S-1-5-21-test"

			def __init__(self) -> None:
				self.phases: list[str] = []
				self.cleared = False

			def write(self, entry) -> None:
				self.phases.append(entry.phase)
				if entry.phase == "applied":
					raise JournalError("write")

			def clear(self) -> None:
				self.cleared = True

		journal = FailAppliedJournal()
		registry = MemoryRegistry(prior)
		lease = RegistryLease(
			CHANNELS[Channel.BETA],
			49223,
			registry,
			journal=journal,
			operationId="op-test",
		)

		with self.assertRaisesRegex(LoaderError, "registry.recovery.unreadable"):
			lease.acquire()

		self.assertEqual(journal.phases, ["prepared", "applied"])
		self.assertTrue(journal.cleared)
		self.assertEqual(registry.current, prior)

	def test_failed_acquire_rollback_keeps_journal_for_next_launch(self) -> None:
		class VerifyThenRollbackFailsRegistry(MemoryRegistry):
			def verifyUserValue(self, valueName, expected):
				if expected is not None:
					return False
				return super().verifyUserValue(valueName, expected)

			def deleteUserValue(self, key, valueName, stage="restore.delete"):
				raise LoaderError("registry.restore.deleteAccessDenied", "stage=restore.delete")

		storage = _MemoryStorage()
		journal = _journal(storage)
		registry = VerifyThenRollbackFailsRegistry(None)
		lease = RegistryLease(
			CHANNELS[Channel.BETA],
			49223,
			registry,
			journal=journal,
			operationId="op-test",
		)

		with self.assertRaisesRegex(LoaderError, "registry.restore.deleteAccessDenied"):
			lease.acquire()

		self.assertEqual(registry.current, RegistryValue("--remote-debugging-port=49223", 1))
		self.assertIsNotNone(storage.payload)

	def test_existing_remote_debugging_argument_is_not_adopted(self) -> None:
		lease = RegistryLease(
			CHANNELS[Channel.BETA],
			49223,
			MemoryRegistry(RegistryValue("--remote-debugging-port=49152", 1)),
		)
		with self.assertRaisesRegex(LoaderError, "registry.user.debugArgumentPresent"):
			lease.acquire()
		self.assertFalse(lease.owned)

	def test_invalid_value_type_is_rejected_before_mutation(self) -> None:
		lease = RegistryLease(
			CHANNELS[Channel.BETA],
			49223,
			MemoryRegistry(RegistryValue("binary", 3)),
		)
		with self.assertRaisesRegex(LoaderError, "registry.user.invalidValueType"):
			lease.acquire()
		self.assertFalse(lease.owned)

	def test_machine_policy_blocks_with_exact_aumid_code(self) -> None:
		lease = RegistryLease(
			CHANNELS[Channel.BETA],
			49223,
			MemoryRegistry(None, machinePolicy=True),
		)
		with self.assertRaisesRegex(LoaderError, "registry.machine.policyAumid"):
			lease.acquire()
		self.assertFalse(lease.owned)

	def test_machine_policy_read_access_denied_maps_exact_code(self) -> None:
		class DeniedMachineRegistry(MemoryRegistry):
			def readMachinePolicy(self, valueName):
				raise LoaderError("registry.machine.readAccessDenied", "stage=machine.read;winerror=5")

		lease = RegistryLease(CHANNELS[Channel.BETA], 49223, DeniedMachineRegistry())
		with self.assertRaisesRegex(LoaderError, "registry.machine.readAccessDenied"):
			lease.acquire()
		self.assertFalse(lease.owned)

	def test_open_create_access_denied_maps_exact_launch_code(self) -> None:
		class DeniedCreateRegistry(MemoryRegistry):
			def openOrCreateUserLeaf(self, stage="user"):
				raise LoaderError("registry.user.openCreateAccessDenied", "stage=user.openCreate;winerror=5")

		lease = RegistryLease(CHANNELS[Channel.STABLE], 49223, DeniedCreateRegistry())
		with self.assertRaisesRegex(LoaderError, "registry.user.openCreateAccessDenied"):
			lease.acquire()
		self.assertFalse(lease.owned)

	def test_restore_open_access_denied_maps_exact_restore_code(self) -> None:
		class DeniedRestoreOpenRegistry(MemoryRegistry):
			def openOrCreateUserLeaf(self, stage="user.openCreate"):
				if stage == "restore.open":
					raise LoaderError("registry.restore.openAccessDenied", "stage=restore;winerror=5")
				return super().openOrCreateUserLeaf(stage)

		lease = RegistryLease(CHANNELS[Channel.BETA], 49223, DeniedRestoreOpenRegistry())
		lease.acquire()
		with self.assertRaisesRegex(LoaderError, "registry.restore.openAccessDenied"):
			lease.restore()
		self.assertFalse(lease.owned)

	def test_set_access_denied_maps_exact_launch_code(self) -> None:
		class DeniedSetRegistry(MemoryRegistry):
			def setUserValue(self, key, valueName, value, stage="user.set"):
				code = (
					"registry.restore.setAccessDenied"
					if stage == "restore.set"
					else "registry.user.setAccessDenied"
				)
				raise LoaderError(code, f"stage={stage};winerror=5")

		lease = RegistryLease(CHANNELS[Channel.BETA], 49223, DeniedSetRegistry())
		with self.assertRaisesRegex(LoaderError, "registry.user.setAccessDenied"):
			lease.acquire()
		self.assertFalse(lease.owned)

	def test_restore_set_access_denied_maps_exact_restore_code(self) -> None:
		class DeniedRestoreSetRegistry(MemoryRegistry):
			def setUserValue(self, key, valueName, value, stage="user.set"):
				if stage == "restore.set":
					raise LoaderError("registry.restore.setAccessDenied", "stage=restore;winerror=5")
				return super().setUserValue(key, valueName, value, stage)

		lease = RegistryLease(
			CHANNELS[Channel.BETA],
			49223,
			DeniedRestoreSetRegistry(RegistryValue("--old", 1)),
		)
		lease.acquire()
		with self.assertRaisesRegex(LoaderError, "registry.restore.setAccessDenied"):
			lease.restore()
		self.assertFalse(lease.owned)

	def test_delete_access_denied_maps_exact_restore_code(self) -> None:
		class DeniedDeleteRegistry(MemoryRegistry):
			def deleteUserValue(self, key, valueName, stage="restore.delete"):
				raise LoaderError("registry.restore.deleteAccessDenied", "stage=restore;winerror=5")

		lease = RegistryLease(CHANNELS[Channel.BETA], 49223, DeniedDeleteRegistry())
		lease.acquire()
		with self.assertRaisesRegex(LoaderError, "registry.restore.deleteAccessDenied"):
			lease.restore()
		self.assertFalse(lease.owned)


class _PrefixCrypto:
	def protect(self, payload: bytes) -> bytes:
		return b"enc:" + payload

	def unprotect(self, payload: bytes) -> bytes:
		return payload[4:]


class _MemoryStorage:
	def __init__(self) -> None:
		self.payload: bytes | None = None

	def read(self) -> bytes | None:
		return self.payload

	def write(self, payload: bytes) -> None:
		self.payload = payload

	def clear(self) -> None:
		self.payload = None


def _journal(storage) -> RegistryJournal:
	return RegistryJournal("S-1-5-21-test", crypto=_PrefixCrypto(), storage=storage)


def _recoveryEntry(*, aumid="AUMID!App", prior=None, owned="--remote-debugging-port=49223", phase="applied"):
	return JournalEntry(
		schemaVersion=1,
		sid="S-1-5-21-test",
		aumid=aumid,
		priorPresent=prior is not None,
		priorData=prior.data if prior is not None else "",
		priorType=prior.valueType if prior is not None else 0,
		ownedData=owned,
		operationId="op-1",
		phase=phase,
	)


class RegistryRecoveryTests(unittest.TestCase):
	def test_no_journal_is_a_noop(self) -> None:
		registry = MemoryRegistry(None)
		journal = _journal(_MemoryStorage())
		code, _detail = recoverPendingRegistryState(registry, journal)
		self.assertEqual(code, "registry.recovery.none")

	def test_owned_temporary_value_is_restored_and_journal_cleared(self) -> None:
		for prior in (None, RegistryValue("--old", 1)):
			with self.subTest(prior=prior):
				storage = _MemoryStorage()
				journal = _journal(storage)
				journal.write(_recoveryEntry(prior=prior))
				registry = MemoryRegistry(RegistryValue("--remote-debugging-port=49223", 1))
				code, _detail = recoverPendingRegistryState(registry, journal)
				self.assertEqual(code, "registry.recovery.restored")
				self.assertEqual(registry.current, prior)
				self.assertIsNone(storage.payload)

	def test_live_value_already_prior_clears_journal_idempotently(self) -> None:
		storage = _MemoryStorage()
		journal = _journal(storage)
		journal.write(_recoveryEntry(prior=RegistryValue("--old", 1)))
		registry = MemoryRegistry(RegistryValue("--old", 1))
		code, _detail = recoverPendingRegistryState(registry, journal)
		self.assertEqual(code, "registry.recovery.alreadyPrior")
		self.assertIsNone(storage.payload)
		self.assertEqual(registry.current, RegistryValue("--old", 1))

	def test_foreign_live_value_conflicts_without_mutation(self) -> None:
		storage = _MemoryStorage()
		journal = _journal(storage)
		journal.write(_recoveryEntry(prior=None))
		registry = MemoryRegistry(RegistryValue("--foreign", 1))
		with self.assertRaisesRegex(LoaderError, "registry.restore.conflict"):
			recoverPendingRegistryState(registry, journal)
		self.assertEqual(registry.current, RegistryValue("--foreign", 1))
		self.assertIsNotNone(storage.payload)

	def test_restore_verification_mismatch_keeps_journal(self) -> None:
		class NoVerifyRegistry(MemoryRegistry):
			def verifyUserValue(self, valueName, expected):
				return False

		storage = _MemoryStorage()
		journal = _journal(storage)
		journal.write(_recoveryEntry(prior=None))
		registry = NoVerifyRegistry(RegistryValue("--remote-debugging-port=49223", 1))
		with self.assertRaisesRegex(LoaderError, "registry.restore.verifyMismatch"):
			recoverPendingRegistryState(registry, journal)
		self.assertIsNotNone(storage.payload)


if __name__ == "__main__":
	unittest.main()
