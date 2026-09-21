import base64
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from typing import Any
from unittest import mock

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from _path import installPackagePath

installPackagePath()

from globalPlugins.whatsappWebPlusCompanion import updateSignature


class SignedManifestTests(unittest.TestCase):
	def setUp(self) -> None:
		self.temporaryDirectory = tempfile.TemporaryDirectory()
		self.addCleanup(self.temporaryDirectory.cleanup)
		self.root = Path(self.temporaryDirectory.name)
		self.privateKey = Ed25519PrivateKey.generate()
		publicKey = self.privateKey.public_key().public_bytes(
			serialization.Encoding.Raw,
			serialization.PublicFormat.Raw,
		)
		self.keyId = "test-ed25519-2026-01"
		self.trustStore = self.root / "update-public-keys.json"
		self.trustStore.write_text(
			json.dumps(
				{
					"schemaVersion": 1,
					"keys": [
						{
							"keyId": self.keyId,
							"algorithm": "Ed25519",
							"publicKey": base64.b64encode(publicKey).decode("ascii"),
							"status": "active",
							"minimumReleaseSequence": 2026082001,
							"fingerprint": hashlib.sha256(publicKey).hexdigest(),
						},
					],
				},
				indent=2,
			)
			+ "\n",
			encoding="utf-8",
		)

	def signedManifest(
		self,
		*,
		releaseSequence: int = 2026082001,
		version: str = "2.6.76",
		digest: str = "a" * 64,
		byteCount: int = 321293,
		keyId: str | None = None,
	) -> tuple[bytes, bytes]:
		value = {
			"schemaVersion": 2,
			"keyId": keyId if keyId is not None else self.keyId,
			"releaseSequence": releaseSequence,
			"version": version,
			"downloadUrl": updateSignature.OFFICIAL_DOWNLOAD_URL,
			"sha256": digest,
			"bytes": byteCount,
		}
		manifest = (f"{json.dumps(value, indent=2)}\n").encode()
		signature = self.privateKey.sign(manifest)
		return manifest, base64.b64encode(signature) + b"\n"

	def assertError(self, code: str, manifest: bytes, signature: bytes) -> None:
		with self.assertRaises(updateSignature.SignedManifestError) as raised:
			updateSignature.verifySignedManifest(manifest, signature, self.trustStore)
		self.assertEqual(raised.exception.code, code)

	def test_valid_manifest_verifies_and_returns_authenticated_fields(self) -> None:
		manifest, signature = self.signedManifest()
		release = updateSignature.verifySignedManifest(manifest, signature, self.trustStore)
		self.assertEqual(release.keyId, self.keyId)
		self.assertEqual(release.releaseSequence, 2026082001)
		self.assertEqual(release.version, "2.6.76")
		self.assertEqual(release.manifestSha256, hashlib.sha256(manifest).hexdigest())

	def test_modified_manifest_and_signature_are_rejected(self) -> None:
		manifest, signature = self.signedManifest()
		modifiedManifest = manifest.replace(b"2.6.76", b"2.6.77")
		self.assertError("signatureInvalid", modifiedManifest, signature)
		modifiedSignature = bytearray(signature)
		modifiedSignature[5] = ord("A") if modifiedSignature[5] != ord("A") else ord("B")
		self.assertError("signatureInvalid", manifest, bytes(modifiedSignature))

	def test_unknown_and_revoked_keys_fail_closed(self) -> None:
		manifest, signature = self.signedManifest(keyId="test-unknown-key")
		self.assertError("keyUnknown", manifest, signature)
		store = json.loads(self.trustStore.read_text(encoding="utf-8"))
		store["keys"][0]["status"] = "revoked"
		self.trustStore.write_text(json.dumps(store), encoding="utf-8")
		manifest, signature = self.signedManifest()
		self.assertError("keyRevoked", manifest, signature)

	def test_duplicate_unknown_and_noncanonical_fields_are_rejected(self) -> None:
		manifest, signature = self.signedManifest()
		duplicate = manifest.replace(b'"version": "2.6.76",', b'"version": "2.6.76",\n  "version": "2.6.76",')
		self.assertError("manifestDuplicateKey", duplicate, signature)
		unknown = manifest.replace(b'"bytes": 321293', b'"extra": 1,\n  "bytes": 321293')
		self.assertError("manifestInvalid", unknown, signature)
		self.assertError("manifestInvalid", manifest.replace(b"\n", b"\r\n"), signature)

	def test_signature_encoding_key_limits_and_trust_store_are_strict(self) -> None:
		manifest, signature = self.signedManifest(releaseSequence=2026082000)
		self.assertError("keySequence", manifest, signature)
		manifest, signature = self.signedManifest()
		self.assertError("signatureInvalid", manifest, signature.rstrip(b"\n"))
		store = json.loads(self.trustStore.read_text(encoding="utf-8"))
		store["keys"][0]["fingerprint"] = "0" * 64
		self.trustStore.write_text(json.dumps(store), encoding="utf-8")
		self.assertError("trustStoreInvalid", manifest, signature)

	def test_missing_runtime_verifier_fails_closed(self) -> None:
		manifest, signature = self.signedManifest()
		realImport = __import__

		def importWithoutCryptography(name: str, *args: Any, **kwargs: Any) -> Any:
			if name.startswith("cryptography"):
				raise ImportError(name)
			return realImport(name, *args, **kwargs)

		with mock.patch("builtins.__import__", side_effect=importWithoutCryptography):
			self.assertError("verifierUnavailable", manifest, signature)


if __name__ == "__main__":
	unittest.main()
