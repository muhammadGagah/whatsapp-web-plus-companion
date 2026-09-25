import importlib.util
import hashlib
import json
import pathlib
import tempfile
import unittest
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("release_verifier", ROOT / "scripts/verify-release.py")
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)


class ReleaseIdentityTests(unittest.TestCase):
	def setUp(self):
		self.tmp = tempfile.TemporaryDirectory()
		self.addCleanup(self.tmp.cleanup)
		self.root = pathlib.Path(self.tmp.name)
		self.version = "2026.09.23"
		self.name = "whatsappWebPlusCompanion"
		(self.root / "buildVars.py").write_text(
			f"addon_info = AddonInfo(addon_name={self.name!r}, addon_version={self.version!r})",
			encoding="utf-8",
		)
		(self.root / "package.json").write_text(json.dumps({"version": self.version}), encoding="utf-8")
		self.package = self.root / f"{self.name}-{self.version}.nvda-addon"
		self.bundle = b"// @version      2.6.85\nconsole.log('release');\n"
		self.lock = {
			"schemaVersion": 2,
			"signedManifestSchemaVersion": 2,
			"asset": "whatsapp_web_plus.user.js",
			"source": "https://update.greasyfork.org/scripts/587557/WhatsApp%20Web%20Plus.user.js",
			"version": "2.6.85",
			"sha256": hashlib.sha256(self.bundle).hexdigest(),
			"bytes": len(self.bundle),
			"releaseSequence": 2026092501,
			"keyId": "release-key",
		}
		(self.root / "upstream.json").write_text(json.dumps(self.lock), encoding="utf-8")
		self.writePackage(self.version)

	def writePackage(self, version):
		with zipfile.ZipFile(self.package, "w") as archive:
			archive.writestr("manifest.ini", f"name = {self.name}\r\nversion = {version}\r\n")
			base = "globalPlugins/whatsappWebPlusCompanion/resources/"
			archive.writestr(base + "whatsapp_web_plus.user.js", self.bundle)
			metadata = {
				key: self.lock[key] for key in ("version", "sha256", "bytes", "releaseSequence", "keyId")
			}
			metadata["upstream"] = self.lock["source"]
			archive.writestr(base + "bundle.json", json.dumps(metadata))

	def test_corrupt_userscript_rejected_even_with_correct_addon_version(self):
		self.bundle += b"modified"
		self.writePackage(self.version)
		with self.assertRaisesRegex(ValueError, "Userscript"):
			verifier.verifyRelease(self.root)

	def test_stale_upstream_lock_rejected(self):
		self.lock["releaseSequence"] -= 1
		(self.root / "upstream.json").write_text(json.dumps(self.lock), encoding="utf-8")
		with self.assertRaisesRegex(ValueError, "bundle metadata"):
			verifier.verifyRelease(self.root)

	def test_userscript_header_must_match_locked_version(self):
		self.bundle = self.bundle.replace(b"2.6.85", b"2.6.84")
		self.lock["sha256"] = hashlib.sha256(self.bundle).hexdigest()
		(self.root / "upstream.json").write_text(json.dumps(self.lock), encoding="utf-8")
		self.writePackage(self.version)
		with self.assertRaisesRegex(ValueError, "Userscript version"):
			verifier.verifyRelease(self.root)

	def test_matching_tag_and_non_tag_build_pass(self):
		for tag in (None, "v2026.09.23"):
			self.assertEqual(verifier.verifyRelease(self.root, tag=tag, artifactsDir=self.root), self.package)

	def test_wrong_tag_rejected_before_build(self):
		self.package.unlink()
		with self.assertRaisesRegex(ValueError, "tag"):
			verifier.verifyRelease(self.root, tag="v2026.09.24", sourceOnly=True)
		verifier.verifyRelease(self.root, tag="v2026.09.23", sourceOnly=True)

	def test_inconsistent_source_versions_rejected(self):
		(self.root / "package.json").write_text('{"version":"2026.09.21"}', encoding="utf-8")
		with self.assertRaisesRegex(ValueError, "package.json"):
			verifier.verifyRelease(self.root, sourceOnly=True)

	def test_old_manifest_in_renamed_package_rejected(self):
		self.writePackage("2026.09.21")
		with self.assertRaisesRegex(ValueError, "manifest version"):
			verifier.verifyRelease(self.root, tag="v2026.09.23")

	def test_extra_old_artifact_rejected(self):
		(self.root / f"{self.name}-2026.09.21.nvda-addon").write_bytes(b"old")
		with self.assertRaisesRegex(ValueError, "Unexpected release assets"):
			verifier.verifyRelease(self.root, artifactsDir=self.root)

	def test_wrong_filename_rejected(self):
		with self.assertRaisesRegex(ValueError, "filename"):
			verifier.verifyRelease(self.root, package=self.root / "wrong.nvda-addon")

	def test_missing_artifact_rejected(self):
		self.package.unlink()
		with self.assertRaisesRegex(ValueError, "Unexpected release assets"):
			verifier.verifyRelease(self.root, artifactsDir=self.root)


if __name__ == "__main__":
	unittest.main()
