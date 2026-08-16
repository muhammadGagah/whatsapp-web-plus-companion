import json
import pathlib
import sys
import types
import unittest
from dataclasses import asdict
from unittest import mock

from _path import installPackagePath

installPackagePath()

from globalPlugins.whatsappWebPlusCompanion.registryJournal import (
	JournalEntry,
	JournalError,
	RegistryJournal,
	_parseEntry,
	defaultJournalPath,
)


class _PrefixCrypto:
	def protect(self, payload: bytes) -> bytes:
		return b"enc:" + payload

	def unprotect(self, payload: bytes) -> bytes:
		if not payload.startswith(b"enc:"):
			raise OSError(5, "invalid ciphertext")
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


class _MemoryJournal(RegistryJournal):
	def __init__(self, sid: str, storage: _MemoryStorage | None = None) -> None:
		super().__init__(
			sid,
			crypto=_PrefixCrypto(),
			storage=storage or _MemoryStorage(),
		)


def _entry(**overrides) -> JournalEntry:
	values = dict(
		schemaVersion=1,
		sid="S-1-5-21-test",
		aumid="5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App",
		priorPresent=True,
		priorData="--old",
		priorType=1,
		ownedData="--remote-debugging-port=49223",
		operationId="op-1",
		phase="prepared",
	)
	values.update(overrides)
	return JournalEntry(**values)


class RegistryJournalTests(unittest.TestCase):
	def test_default_path_uses_nvda_write_paths_config_directory(self) -> None:
		with mock.patch.dict(
			sys.modules,
			{
				"NVDAState": types.SimpleNamespace(
					WritePaths=types.SimpleNamespace(configDir="X:/portable/userConfig"),
				),
			},
		):
			path = defaultJournalPath()

		self.assertEqual(
			path,
			pathlib.Path("X:/portable/userConfig/whatsappWebPlusCompanion/registry-recovery.bin"),
		)

	def test_default_path_falls_back_to_active_legacy_config_path(self) -> None:
		with mock.patch.dict(
			sys.modules,
			{
				"NVDAState": types.SimpleNamespace(),
				"globalVars": types.SimpleNamespace(
					appArgs=types.SimpleNamespace(configPath="Y:/custom-nvda"),
				),
			},
		):
			path = defaultJournalPath()

		self.assertEqual(
			path,
			pathlib.Path("Y:/custom-nvda/whatsappWebPlusCompanion/registry-recovery.bin"),
		)

	def test_prepared_and_applied_phases_round_trip(self) -> None:
		storage = _MemoryStorage()
		journal = _MemoryJournal("S-1-5-21-test", storage)
		journal.write(_entry(phase="prepared"))
		journal.write(_entry(phase="applied"))
		loaded = journal.load()
		self.assertEqual(loaded, _entry(phase="applied"))

	def test_clear_removes_journal(self) -> None:
		storage = _MemoryStorage()
		journal = _MemoryJournal("S-1-5-21-test", storage)
		journal.write(_entry())
		journal.clear()
		self.assertIsNone(journal.load())

	def test_unknown_schema_is_rejected(self) -> None:
		storage = _MemoryStorage()
		storage.write(b"enc:" + json.dumps(asdict(_entry(schemaVersion=99))).encode())
		journal = _MemoryJournal("S-1-5-21-test", storage)
		with self.assertRaises(JournalError) as raised:
			journal.load()
		self.assertEqual(raised.exception.code, "schema")

	def test_wrong_user_sid_is_rejected(self) -> None:
		storage = _MemoryStorage()
		journal = _MemoryJournal("S-1-5-21-test", storage)
		journal.write(_entry())
		other = _MemoryJournal("S-1-5-21-other", storage)
		with self.assertRaises(JournalError) as raised:
			other.load()
		self.assertEqual(raised.exception.code, "identity")

	def test_write_with_wrong_sid_is_rejected(self) -> None:
		journal = _MemoryJournal("S-1-5-21-test")
		with self.assertRaises(JournalError) as raised:
			journal.write(_entry(sid="S-1-5-21-other"))
		self.assertEqual(raised.exception.code, "identity")

	def test_decryption_failure_is_non_destructive(self) -> None:
		storage = _MemoryStorage()
		storage.payload = b"not-encrypted-junk"
		journal = _MemoryJournal("S-1-5-21-test", storage)
		with self.assertRaises(JournalError) as raised:
			journal.load()
		self.assertEqual(raised.exception.code, "decrypt")
		self.assertEqual(storage.payload, b"not-encrypted-junk")

	def test_malformed_json_is_rejected(self) -> None:
		storage = _MemoryStorage()
		storage.payload = b"enc:{not-json"
		journal = _MemoryJournal("S-1-5-21-test", storage)
		with self.assertRaises(JournalError) as raised:
			journal.load()
		self.assertEqual(raised.exception.code, "json")

	def test_unknown_phase_is_rejected(self) -> None:
		with self.assertRaises(JournalError) as raised:
			_parseEntry(asdict(_entry(phase="unknown")))
		self.assertEqual(raised.exception.code, "phase")

	def test_missing_fields_are_rejected(self) -> None:
		with self.assertRaises(JournalError) as raised:
			_parseEntry({"schemaVersion": 1})
		self.assertEqual(raised.exception.code, "shape")

	def test_errors_never_expose_plaintext_value(self) -> None:
		storage = _MemoryStorage()
		storage.payload = b"enc:" + json.dumps(asdict(_entry())).encode()
		other = _MemoryJournal("S-1-5-21-other", storage)
		try:
			other.load()
		except JournalError as error:
			self.assertNotIn("--old", str(error))
			self.assertNotIn("remote-debugging", str(error))
		else:
			self.fail("expected identity JournalError")


if __name__ == "__main__":
	unittest.main()
