import hashlib
import json
import pathlib
import tempfile
import unittest
from unittest import mock

from _path import installPackagePath

installPackagePath()

from globalPlugins.whatsappWebPlusCompanion.models import LoaderError
from globalPlugins.whatsappWebPlusCompanion.registry import MemoryRegistry, RegistryValue
from globalPlugins.whatsappWebPlusCompanion.registryRepair import (
	RegistryPermissionStatus,
	RepairIdentity,
	diagnoseRegistryPermissions,
	elevateHelper,
	runRegistryRepair,
	verifyHelperIntegrity,
)
from globalPlugins.whatsappWebPlusCompanion.security import SecurityProbe


def _probe(**overrides) -> SecurityProbe:
	values = dict(canWrite=True, secureDesktop=False, locked=False, elevated=False)
	values.update(overrides)
	return SecurityProbe(**values)


class _SpyMutex:
	def __init__(self, available: bool = True) -> None:
		self.available = available
		self.acquired = 0
		self.released = 0

	def acquire(self) -> int | None:
		if not self.available:
			return None
		self.acquired += 1
		return self.acquired

	def release(self, handle: int) -> None:
		self.released += 1


class RegistryDiagnosisTests(unittest.TestCase):
	def _diagnose(self, registry=None, *, probe=None, mutex=None, running=False):
		mutex = mutex or _SpyMutex()
		return diagnoseRegistryPermissions(
			registry or MemoryRegistry(None),
			probe or _probe(),
			tryAcquireMutex=mutex.acquire,
			releaseMutex=mutex.release,
			whatsappRunning=lambda: running,
		), mutex

	def test_usable_rights_return_not_needed_without_write(self) -> None:
		registry = MemoryRegistry(None)
		status, mutex = self._diagnose(registry)
		self.assertEqual(status, RegistryPermissionStatus.USABLE)
		self.assertIsNone(registry.current)
		self.assertEqual(mutex.acquired, mutex.released)

	def test_access_denied_leaf_is_repairable(self) -> None:
		class DeniedRegistry(MemoryRegistry):
			def openUserLeafReadOnly(self, stage="user.open"):
				raise LoaderError("registry.user.openAccessDenied", "stage=user.open;winerror=5")

		status, mutex = self._diagnose(DeniedRegistry())
		self.assertEqual(status, RegistryPermissionStatus.REPAIRABLE_ACCESS_DENIED)
		self.assertEqual(mutex.acquired, mutex.released)

	def test_machine_policy_is_not_repairable(self) -> None:
		status, mutex = self._diagnose(MemoryRegistry(None, machinePolicy=True))
		self.assertEqual(status, RegistryPermissionStatus.MACHINE_POLICY)
		self.assertEqual(mutex.acquired, mutex.released)

	def test_machine_read_failure_does_not_hide_repairable_user_denial(self) -> None:
		class DeniedMachineAndUserRegistry(MemoryRegistry):
			def readMachinePolicy(self, valueName):
				raise LoaderError("registry.machine.readAccessDenied", "stage=machine.read;winerror=5")

			def openUserLeafReadOnly(self, stage="user.open"):
				raise LoaderError("registry.user.openAccessDenied", "stage=user.open;winerror=5")

		status, mutex = self._diagnose(DeniedMachineAndUserRegistry())
		self.assertEqual(status, RegistryPermissionStatus.REPAIRABLE_ACCESS_DENIED)
		self.assertEqual(mutex.acquired, mutex.released)

	def test_machine_read_failure_with_usable_user_key_raises_exact_code(self) -> None:
		class DeniedMachineRegistry(MemoryRegistry):
			def readMachinePolicy(self, valueName):
				raise LoaderError("registry.machine.readAccessDenied", "stage=machine.read;winerror=5")

		mutex = _SpyMutex()
		with self.assertRaisesRegex(LoaderError, "registry.machine.readAccessDenied"):
			diagnoseRegistryPermissions(
				DeniedMachineRegistry(),
				_probe(),
				tryAcquireMutex=mutex.acquire,
				releaseMutex=mutex.release,
				whatsappRunning=lambda: False,
			)
		self.assertEqual(mutex.acquired, mutex.released)

	def test_user_failure_without_machine_error_is_managed_or_unknown(self) -> None:
		class BrokenRegistry(MemoryRegistry):
			def openUserLeafReadOnly(self, stage="user.open"):
				raise LoaderError("registry.user.openFailed", "stage=user.open;winerror=87")

		status, mutex = self._diagnose(BrokenRegistry())
		self.assertEqual(status, RegistryPermissionStatus.MANAGED_OR_UNKNOWN)
		self.assertEqual(mutex.acquired, mutex.released)

	def test_arbitrary_failure_is_not_repairable(self) -> None:
		class BrokenRegistry(MemoryRegistry):
			def openUserLeafReadOnly(self, stage="user.open"):
				raise LoaderError("registry.user.openFailed", "stage=user.open;winerror=87")

		status, mutex = self._diagnose(BrokenRegistry())
		self.assertEqual(status, RegistryPermissionStatus.MANAGED_OR_UNKNOWN)
		self.assertEqual(mutex.acquired, mutex.released)

	def test_busy_mutex_is_not_repairable_and_releases_nothing(self) -> None:
		mutex = _SpyMutex(available=False)
		status, mutex = self._diagnose(mutex=mutex)
		self.assertEqual(status, RegistryPermissionStatus.BUSY)
		self.assertEqual((mutex.acquired, mutex.released), (0, 0))

	def test_running_whatsapp_is_not_repairable(self) -> None:
		status, mutex = self._diagnose(running=True)
		self.assertEqual(status, RegistryPermissionStatus.WHATSAPP_RUNNING)
		self.assertEqual((mutex.acquired, mutex.released), (0, 0))

	def test_unsafe_context_is_not_repairable(self) -> None:
		for field in ("secureDesktop", "locked", "elevated"):
			with self.subTest(field=field):
				status, mutex = self._diagnose(probe=_probe(**{field: True}))
				self.assertEqual(status, RegistryPermissionStatus.UNSUPPORTED)
				self.assertEqual((mutex.acquired, mutex.released), (0, 0))
		status, mutex = self._diagnose(probe=_probe(canWrite=False))
		self.assertEqual(status, RegistryPermissionStatus.UNSUPPORTED)
		self.assertEqual((mutex.acquired, mutex.released), (0, 0))

	def test_no_value_is_written_during_diagnosis(self) -> None:
		registry = MemoryRegistry(RegistryValue("--existing", 1))
		status, mutex = self._diagnose(registry)
		self.assertEqual(status, RegistryPermissionStatus.USABLE)
		self.assertEqual(registry.current, RegistryValue("--existing", 1))
		self.assertEqual(mutex.acquired, mutex.released)

	def test_missing_leaf_is_not_created_during_diagnosis(self) -> None:
		class MissingLeafRegistry(MemoryRegistry):
			def __init__(self) -> None:
				super().__init__(None)
				self.createCalled = False

			def openUserLeafReadOnly(self, stage="user.open"):
				return None

			def openOrCreateUserLeaf(self, stage="user.openCreate"):
				self.createCalled = True
				return super().openOrCreateUserLeaf(stage)

		registry = MissingLeafRegistry()
		status, _mutex = self._diagnose(registry)

		self.assertEqual(status, RegistryPermissionStatus.USABLE)
		self.assertFalse(registry.createCalled)


def _writeHelperPackage(root: pathlib.Path, *, tamper: bool = False) -> None:
	helperDir = root / "registryRepair"
	helperDir.mkdir(parents=True, exist_ok=True)
	ps1 = b"# fixed helper\n"
	bat = b"@echo off\n"
	(helperDir / "registryRepair.ps1").write_bytes(ps1)
	(helperDir / "registryRepair.bat").write_bytes(b"@echo off\n" if not tamper else b"@echo tampered\n")
	metadata = {
		"schemaVersion": 1,
		"protocolVersion": 1,
		"helper": {
			"ps1": {
				"file": "registryRepair.ps1",
				"sha256": hashlib.sha256(ps1).hexdigest(),
				"bytes": len(ps1),
			},
			"bat": {
				"file": "registryRepair.bat",
				"sha256": hashlib.sha256(bat).hexdigest(),
				"bytes": len(bat),
			},
		},
	}
	(root / "registry-repair.json").write_text(json.dumps(metadata), encoding="utf-8")


class _UsableRegistry(MemoryRegistry):
	def openOrCreateUserLeaf(self, stage="user"):
		return object()

	def closeUserLeaf(self, key):
		return None


class RegistryRepairOrchestrationTests(unittest.TestCase):
	def setUp(self) -> None:
		self.tmp = tempfile.TemporaryDirectory()
		self.addCleanup(self.tmp.cleanup)
		_writeHelperPackage(pathlib.Path(self.tmp.name))
		self.identity = RepairIdentity(10, 133700000000000000, "S-1-5-21-1-2-3")

	def _run(self, *, exitCode=None, winerror=None, registry=None, recover=None):
		return runRegistryRepair(
			self.identity,
			helperDir=pathlib.Path(self.tmp.name) / "registryRepair",
			registry=registry or _UsableRegistry(),
			elevate=lambda path, ident, hwnd: (exitCode, winerror),
			recover=recover or (lambda: ""),
		)

	def test_integrity_verification_passes_for_packaged_helper(self) -> None:
		bat, ps1 = verifyHelperIntegrity(pathlib.Path(self.tmp.name) / "registryRepair")
		self.assertTrue(bat.name.endswith(".bat"))
		self.assertTrue(ps1.name.endswith(".ps1"))

	def test_missing_helper_is_reported(self) -> None:
		missing = pathlib.Path(self.tmp.name) / "empty"
		with self.assertRaisesRegex(Exception, "registry.repair.helperMissing"):
			verifyHelperIntegrity(missing)

	def test_tampered_helper_is_untrusted(self) -> None:
		_writeHelperPackage(pathlib.Path(self.tmp.name), tamper=True)
		with self.assertRaisesRegex(Exception, "registry.repair.helperUntrusted"):
			verifyHelperIntegrity(pathlib.Path(self.tmp.name) / "registryRepair")

	def test_bom_prefixed_metadata_is_tolerated(self) -> None:
		helperDir = pathlib.Path(self.tmp.name) / "registryRepair"
		metadataPath = helperDir.parent / "registry-repair.json"
		raw = metadataPath.read_bytes()
		metadataPath.write_bytes(b"\xef\xbb\xbf" + raw)
		bat, ps1 = verifyHelperIntegrity(helperDir)
		self.assertTrue(bat.name.endswith(".bat"))
		self.assertTrue(ps1.name.endswith(".ps1"))

	def test_successful_repair_maps_and_postchecks(self) -> None:
		outcome = self._run(exitCode=0)
		self.assertTrue(outcome.ok)
		self.assertEqual(outcome.code, "registry.repair.repaired")

	def test_helper_exit_codes_map_to_stable_codes(self) -> None:
		for exitCode, expected in (
			(1, "registry.repair.notNeeded"),
			(8, "registry.repair.busy"),
			(10, "registry.repair.managedDeny"),
			(11, "registry.repair.insufficientAdminRights"),
			(13, "registry.repair.verificationFailedRolledBack"),
			(14, "registry.repair.rollbackFailed"),
			(5, "registry.repair.parentIdentityMismatch"),
			(99, "registry.repair.applyFailed"),
		):
			with self.subTest(exitCode=exitCode):
				outcome = self._run(exitCode=exitCode)
				self.assertFalse(outcome.ok)
				self.assertEqual(outcome.code, expected)

	def test_uac_cancellation_is_normal_outcome(self) -> None:
		outcome = self._run(winerror=1223)
		self.assertFalse(outcome.ok)
		self.assertEqual(outcome.code, "registry.repair.uacCancelled")

	def test_elevation_timeout_claims_no_success(self) -> None:
		outcome = self._run(exitCode=None, winerror=None)
		self.assertFalse(outcome.ok)
		self.assertEqual(outcome.code, "registry.repair.helperTimeout")

	def test_postcheck_failure_overrides_helper_success(self) -> None:
		class DeniedRegistry(MemoryRegistry):
			def openOrCreateUserLeaf(self, stage="user"):
				raise LoaderError("registry.user.openCreateAccessDenied", "stage=user;winerror=5")

		outcome = self._run(exitCode=0, registry=DeniedRegistry())
		self.assertFalse(outcome.ok)
		self.assertEqual(outcome.code, "registry.repair.postVerifyFailed")

	def test_recovery_after_repair_is_reported(self) -> None:
		outcome = self._run(exitCode=0, recover=lambda: "registry.recovery.restored")
		self.assertTrue(outcome.ok)
		self.assertEqual(outcome.code, "registry.repair.recoveryRestored")
		self.assertEqual(outcome.values, {"recovery": True})

	def test_recovery_conflict_is_non_mutating(self) -> None:
		def recover():
			raise LoaderError("registry.restore.conflict", "stage=recovery.read", {"conflict": True})

		outcome = self._run(exitCode=0, recover=recover)
		self.assertFalse(outcome.ok)
		self.assertEqual(outcome.code, "registry.repair.recoveryConflict")

	def test_elevate_helper_ctypes_setup_does_not_crash(self) -> None:
		class _FakeFn:
			def __init__(self, result) -> None:
				self._result = result

			def __call__(self, *args, **kwargs):
				return self._result

		class _FakeDll:
			def __init__(self, results) -> None:
				self._results = results

			def __getattr__(self, name):
				return _FakeFn(self._results.get(name, True))

		results = {"ShellExecuteExW": False}
		with mock.patch(
			"globalPlugins.whatsappWebPlusCompanion.registryRepair.ctypes.WinDLL",
			side_effect=lambda name, **kwargs: _FakeDll(results),
		):
			exitCode, winerror = elevateHelper(
				pathlib.Path("registryRepair.bat"),
				self.identity,
				deadline=0.01,
			)
		self.assertIsNone(exitCode)
		self.assertIsInstance(winerror, int)


if __name__ == "__main__":
	unittest.main()
