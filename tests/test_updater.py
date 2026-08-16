import hashlib
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest import mock

from _path import installPackagePath

installPackagePath()

from globalPlugins.whatsappWebPlusCompanion import bundle, updater


def userscript(version: str, *, name: str = "WhatsApp Web Plus") -> bytes:
	return f"""// ==UserScript==
// @name         {name}
// @author       Muhammad Gagah
// @namespace    https://github.com/muhammadGagah/whatsapp-web-plus
// @version      {version}
// @match        https://web.whatsapp.com/*
// @run-at       document-start
// @updateURL    {updater.SCRIPT_METADATA_URL}
// @downloadURL  {updater.SCRIPT_DOWNLOAD_URL}
// @grant        none
// ==/UserScript==
(() => {{ globalThis.testVersion = {version!r}; }})();
""".encode()


def writePackagedBundle(root: Path, version: str) -> bytes:
	payload = userscript(version)
	digest = hashlib.sha256(payload).hexdigest()
	(root / bundle.PACKAGED_ASSET).write_bytes(payload)
	(root / bundle.PACKAGED_MANIFEST).write_text(
		json.dumps({"version": version, "sha256": digest, "bytes": len(payload)}),
		encoding="utf-8",
	)
	return payload


class FakeResponse:
	def __init__(self, payload: bytes) -> None:
		self.payload = payload
		self.offset = 0

	def __enter__(self):
		return self

	def __exit__(self, excType, excValue, traceback) -> None:
		return None

	def read(self, amount: int) -> bytes:
		chunk = self.payload[self.offset : self.offset + amount]
		self.offset += len(chunk)
		return chunk


class FakeOpener:
	def __init__(self, *payloads: bytes) -> None:
		self.payloads = list(payloads)
		self.requests = []
		self.timeouts = []

	def open(self, httpRequest, *, timeout: float):
		self.requests.append(httpRequest)
		self.timeouts.append(timeout)
		return FakeResponse(self.payloads.pop(0))


class UpdaterTests(unittest.TestCase):
	def test_numeric_version_comparison_pads_components(self) -> None:
		self.assertGreater(updater.compareVersions("2.6.74", "2.6.73"), 0)
		self.assertEqual(updater.compareVersions("2.6.73.0", "2.6.73"), 0)
		self.assertLess(updater.compareVersions("2.6.9", "2.6.73"), 0)

	def test_invalid_versions_are_rejected(self) -> None:
		for version in ("", "2.6.beta", "v2.6.73", "2..73"):
			with self.subTest(version=version), self.assertRaises(updater.UpdateCheckError):
				updater.compareVersions(version, "2.6.73")

	def test_metadata_requires_one_numeric_version_directive(self) -> None:
		self.assertEqual(updater.parseMetadataVersion(b"// @version 2.6.74\n"), "2.6.74")
		for payload in (
			b"// @name WhatsApp Web Plus\n",
			b"// @version 2.6.74\n// @version 9.0.0\n",
			b"// @version next\n",
			b"\xff",
		):
			with self.subTest(payload=payload), self.assertRaises(updater.UpdateCheckError):
				updater.parseMetadataVersion(payload)

	def test_metadata_and_script_sizes_are_bounded(self) -> None:
		with self.assertRaises(updater.UpdateCheckError):
			updater.parseMetadataVersion(b"x" * (updater._MAX_METADATA_BYTES + 1))
		with self.assertRaises(updater.UpdateCheckError):
			updater.validateDownloadedScript(b"x" * (updater._MAX_SCRIPT_BYTES + 1), "2.6.75")

	def test_download_requires_exact_official_identity_and_version(self) -> None:
		_source, digest = updater.validateDownloadedScript(userscript("2.6.75"), "2.6.75")
		self.assertEqual(digest, hashlib.sha256(userscript("2.6.75")).hexdigest())
		for payload, version in (
			(userscript("2.6.74"), "2.6.75"),
			(userscript("2.6.75", name="Other Script"), "2.6.75"),
			(b"\xff", "2.6.75"),
		):
			with self.subTest(version=version), self.assertRaises(updater.UpdateCheckError):
				updater.validateDownloadedScript(payload, version)
		missingRunAt = userscript("2.6.75").replace(b"// @run-at       document-start\n", b"")
		with self.assertRaises(updater.UpdateCheckError):
			updater.validateDownloadedScript(missingRunAt, "2.6.75")

	def test_fetch_uses_only_fixed_urls_no_redirects_and_timeout(self) -> None:
		fakeOpener = FakeOpener(b"// @version 2.6.75\n", userscript("2.6.75"))
		self.assertEqual(updater.fetchLatestVersion(fakeOpener), "2.6.75")
		_payload, _digest = updater.fetchScript("2.6.75", fakeOpener)
		self.assertEqual(
			[httpRequest.full_url for httpRequest in fakeOpener.requests],
			[updater.SCRIPT_METADATA_URL, updater.SCRIPT_DOWNLOAD_URL],
		)
		self.assertEqual(fakeOpener.timeouts, [updater._REQUEST_TIMEOUT_SECONDS] * 2)
		handler = updater._NoRedirectHandler()
		self.assertIsNone(handler.redirect_request(None, None, 302, "Found", None, "https://example.test"))

	def test_timeout_is_a_safe_network_error(self) -> None:
		fakeOpener = mock.Mock()
		fakeOpener.open.side_effect = TimeoutError("timed out")
		with self.assertRaises(updater.UpdateCheckError) as raised:
			updater.fetchLatestVersion(fakeOpener)
		self.assertEqual(raised.exception.code, "network")

	def test_cancellation_interrupts_a_chunked_response_read(self) -> None:
		cancel = threading.Event()

		class CancellingResponse(FakeResponse):
			def read(self, amount: int) -> bytes:
				chunk = super().read(amount)
				cancel.set()
				return chunk

		class CancellingOpener:
			def open(self, httpRequest, *, timeout: float):
				return CancellingResponse(b"x" * (updater._MAX_METADATA_BYTES // 2))

		with self.assertRaises(updater.UpdateCheckError) as raised:
			updater.fetchLatestVersion(CancellingOpener(), cancel)
		self.assertEqual(raised.exception.code, "cancelled")

	def test_current_version_downloads_and_confirms_the_script_digest(self) -> None:
		with tempfile.TemporaryDirectory() as directory:
			root = Path(directory)
			packagedPayload = writePackagedBundle(root, "2.6.74")
			opener = FakeOpener(b"// @version 2.6.74\n", packagedPayload)
			result = updater.checkForUpdate(resources=root, updateStore=root / "updates", opener=opener)
		self.assertEqual(result.status, updater.UpdateStatus.CURRENT)
		self.assertEqual(len(opener.requests), 2)

	def test_newer_version_is_installed_and_selected_atomically(self) -> None:
		with tempfile.TemporaryDirectory() as directory:
			root = Path(directory)
			store = root / "updates"
			writePackagedBundle(root, "2.6.74")
			opener = FakeOpener(b"// @version 2.6.75\n", userscript("2.6.75"))
			result = updater.checkForUpdate(resources=root, updateStore=store, opener=opener)
			_source, version, digest = bundle.loadEmbeddedBundle(root, store)
			manifest = json.loads((store / bundle.UPDATE_MANIFEST).read_text(encoding="utf-8"))

			self.assertEqual(result.status, updater.UpdateStatus.UPDATED)
			self.assertEqual((result.currentVersion, result.latestVersion), ("2.6.74", "2.6.75"))
			self.assertEqual(version, "2.6.75")
			self.assertEqual(manifest["sha256"], digest)
			self.assertTrue((store / manifest["asset"]).is_file())

	def test_stale_worker_cannot_replace_a_newer_bundle_after_acquiring_the_lock(self) -> None:
		with tempfile.TemporaryDirectory() as directory:
			root = Path(directory)
			store = root / "updates"
			packagedPayload = writePackagedBundle(root, "2.6.74")
			packagedDigest = hashlib.sha256(packagedPayload).hexdigest()
			newerPayload = userscript("2.6.76")
			newerDigest = hashlib.sha256(newerPayload).hexdigest()
			stalePayload = userscript("2.6.75")
			staleDigest = hashlib.sha256(stalePayload).hexdigest()

			self.assertTrue(
				updater.installDownloadedBundle(
					newerPayload,
					"2.6.76",
					newerDigest,
					resources=root,
					updateStore=store,
					expectedCurrentVersion="2.6.74",
					expectedCurrentDigest=packagedDigest,
				),
			)
			self.assertFalse(
				updater.installDownloadedBundle(
					stalePayload,
					"2.6.75",
					staleDigest,
					resources=root,
					updateStore=store,
					expectedCurrentVersion="2.6.74",
					expectedCurrentDigest=packagedDigest,
				),
			)
			_source, version, digest = bundle.loadEmbeddedBundle(root, store)
			self.assertEqual((version, digest), ("2.6.76", newerDigest))

	def test_stale_same_version_worker_cannot_replace_a_changed_digest(self) -> None:
		with tempfile.TemporaryDirectory() as directory:
			root = Path(directory)
			store = root / "updates"
			packagedPayload = writePackagedBundle(root, "2.6.74")
			packagedDigest = hashlib.sha256(packagedPayload).hexdigest()
			firstPayload = userscript("2.6.75")
			firstDigest = hashlib.sha256(firstPayload).hexdigest()
			stalePayload = firstPayload.replace(b"globalThis.testVersion", b"globalThis.staleVersion")
			staleDigest = hashlib.sha256(stalePayload).hexdigest()

			self.assertTrue(
				updater.installDownloadedBundle(
					firstPayload,
					"2.6.75",
					firstDigest,
					resources=root,
					updateStore=store,
					expectedCurrentVersion="2.6.74",
					expectedCurrentDigest=packagedDigest,
				),
			)
			self.assertFalse(
				updater.installDownloadedBundle(
					stalePayload,
					"2.6.75",
					staleDigest,
					resources=root,
					updateStore=store,
					expectedCurrentVersion="2.6.74",
					expectedCurrentDigest=packagedDigest,
				),
			)
			_source, version, digest = bundle.loadEmbeddedBundle(root, store)
			self.assertEqual((version, digest), ("2.6.75", firstDigest))

	def test_changed_content_at_the_same_version_is_refreshed(self) -> None:
		with tempfile.TemporaryDirectory() as directory:
			root = Path(directory)
			store = root / "updates"
			packagedPayload = writePackagedBundle(root, "2.6.74")
			changedPayload = packagedPayload.replace(b"globalThis.testVersion", b"globalThis.changedVersion")
			opener = FakeOpener(b"// @version 2.6.74\n", changedPayload)
			result = updater.checkForUpdate(resources=root, updateStore=store, opener=opener)
			source, version, digest = bundle.loadEmbeddedBundle(root, store)

			self.assertEqual(result.status, updater.UpdateStatus.UPDATED)
			self.assertTrue(result.contentChanged)
			self.assertEqual((result.currentVersion, result.latestVersion), ("2.6.74", "2.6.74"))
			self.assertEqual(version, "2.6.74")
			self.assertEqual(source.encode(), changedPayload)
			self.assertEqual(digest, hashlib.sha256(changedPayload).hexdigest())

	def test_version_mismatch_never_changes_selected_bundle(self) -> None:
		with tempfile.TemporaryDirectory() as directory:
			root = Path(directory)
			store = root / "updates"
			writePackagedBundle(root, "2.6.74")
			opener = FakeOpener(b"// @version 2.6.75\n", userscript("2.6.76"))
			result = updater.checkForUpdate(resources=root, updateStore=store, opener=opener)
			_source, version, _digest = bundle.loadEmbeddedBundle(root, store)
			self.assertEqual(result.status, updater.UpdateStatus.ERROR)
			self.assertEqual(result.errorCode, "validation")
			self.assertEqual(version, "2.6.74")
			self.assertFalse((store / bundle.UPDATE_MANIFEST).exists())

	def test_older_remote_version_is_current_and_is_not_downloaded(self) -> None:
		with tempfile.TemporaryDirectory() as directory:
			root = Path(directory)
			store = root / "updates"
			writePackagedBundle(root, "2.6.74")
			opener = FakeOpener(b"// @version 2.6.73\n")
			result = updater.checkForUpdate(resources=root, updateStore=store, opener=opener)
			_source, version, _digest = bundle.loadEmbeddedBundle(root, store)
			self.assertEqual(result.status, updater.UpdateStatus.CURRENT)
			self.assertEqual(result.latestVersion, "2.6.73")
			self.assertEqual(len(opener.requests), 1)
			self.assertEqual(version, "2.6.74")
			self.assertFalse((store / bundle.UPDATE_MANIFEST).exists())

	def test_cancel_before_commit_keeps_packaged_bundle_selected(self) -> None:
		with tempfile.TemporaryDirectory() as directory:
			root = Path(directory)
			store = root / "updates"
			writePackagedBundle(root, "2.6.74")
			payload = userscript("2.6.75")
			cancel = threading.Event()
			cancel.set()
			with self.assertRaises(updater.UpdateCheckError) as raised:
				updater.installDownloadedBundle(
					payload,
					"2.6.75",
					hashlib.sha256(payload).hexdigest(),
					resources=root,
					updateStore=store,
					cancelEvent=cancel,
				)
			_source, version, _digest = bundle.loadEmbeddedBundle(root, store)
		self.assertEqual(raised.exception.code, "cancelled")
		self.assertEqual(version, "2.6.74")

	def test_corrupt_or_older_overlay_falls_back_to_packaged_bundle(self) -> None:
		with tempfile.TemporaryDirectory() as directory:
			root = Path(directory)
			store = root / "updates"
			writePackagedBundle(root, "2.6.74")
			payload = userscript("2.6.75")
			_source, digest = updater.validateDownloadedScript(payload, "2.6.75")
			updater.installDownloadedBundle(
				payload,
				"2.6.75",
				digest,
				resources=root,
				updateStore=store,
			)
			writePackagedBundle(root, "2.6.76")
			_source, version, _digest = bundle.loadEmbeddedBundle(root, store)
			self.assertEqual(version, "2.6.76")
			(store / bundle.UPDATE_MANIFEST).write_text("not json", encoding="utf-8")
			_source, version, _digest = bundle.loadEmbeddedBundle(root, store)
			self.assertEqual(version, "2.6.76")

	def test_failed_post_commit_verification_restores_previous_manifest(self) -> None:
		with tempfile.TemporaryDirectory() as directory:
			root = Path(directory)
			store = root / "updates"
			writePackagedBundle(root, "2.6.74")
			firstPayload = userscript("2.6.75")
			_source, firstDigest = updater.validateDownloadedScript(firstPayload, "2.6.75")
			updater.installDownloadedBundle(
				firstPayload,
				"2.6.75",
				firstDigest,
				resources=root,
				updateStore=store,
			)
			secondPayload = userscript("2.6.76")
			_source, secondDigest = updater.validateDownloadedScript(secondPayload, "2.6.76")
			with mock.patch.object(updater, "loadEmbeddedBundle", side_effect=RuntimeError("verify")):
				with self.assertRaises(updater.UpdateCheckError) as raised:
					updater.installDownloadedBundle(
						secondPayload,
						"2.6.76",
						secondDigest,
						resources=root,
						updateStore=store,
					)
			_source, selectedVersion, selectedDigest = bundle.loadEmbeddedBundle(root, store)
			self.assertEqual(raised.exception.code, "save")
			self.assertEqual(selectedVersion, "2.6.75")
			self.assertEqual(selectedDigest, firstDigest)

	def test_failed_updated_bundle_can_be_quarantined_without_touching_a_newer_manifest(self) -> None:
		with tempfile.TemporaryDirectory() as directory:
			root = Path(directory)
			store = root / "updates"
			writePackagedBundle(root, "2.6.74")
			payload = userscript("2.6.75")
			_source, digest = updater.validateDownloadedScript(payload, "2.6.75")
			updater.installDownloadedBundle(
				payload,
				"2.6.75",
				digest,
				resources=root,
				updateStore=store,
			)
			self.assertFalse(bundle.quarantineUpdatedBundle("0" * 64, store))
			_source, version, _digest = bundle.loadEmbeddedBundle(root, store)
			self.assertEqual(version, "2.6.75")
			self.assertTrue(bundle.quarantineUpdatedBundle(digest, store))
			_source, version, _digest = bundle.loadEmbeddedBundle(root, store)
			self.assertEqual(version, "2.6.74")
			self.assertFalse((store / bundle.UPDATE_MANIFEST).exists())
			self.assertTrue((store / f"bundle-update.quarantined.{digest}.json").is_file())

	def test_equal_overlay_is_used_only_while_its_packaged_base_is_unchanged(self) -> None:
		with tempfile.TemporaryDirectory() as directory:
			root = Path(directory)
			store = root / "updates"
			packagedPayload = writePackagedBundle(root, "2.6.75")
			packagedDigest = hashlib.sha256(packagedPayload).hexdigest()
			overlayPayload = userscript("2.6.75.0")
			_source, digest = updater.validateDownloadedScript(overlayPayload, "2.6.75.0")
			store.mkdir()
			assetName = bundle.updateAssetName(digest)
			(store / assetName).write_bytes(overlayPayload)
			(store / bundle.UPDATE_MANIFEST).write_text(
				json.dumps(
					{
						"schemaVersion": 1,
						"asset": assetName,
						"version": "2.6.75.0",
						"sha256": digest,
						"bytes": len(overlayPayload),
						"source": updater.SCRIPT_DOWNLOAD_URL,
						"baseSha256": packagedDigest,
					},
				),
				encoding="utf-8",
			)
			source, version, _digest = bundle.loadEmbeddedBundle(root, store)
			self.assertEqual(version, "2.6.75.0")
			self.assertEqual(source.encode(), overlayPayload)
			newPackagedPayload = packagedPayload.replace(
				b"globalThis.testVersion",
				b"globalThis.packagedVersion",
			)
			newPackagedDigest = hashlib.sha256(newPackagedPayload).hexdigest()
			(root / bundle.PACKAGED_ASSET).write_bytes(newPackagedPayload)
			(root / bundle.PACKAGED_MANIFEST).write_text(
				json.dumps(
					{
						"version": "2.6.75",
						"sha256": newPackagedDigest,
						"bytes": len(newPackagedPayload),
					},
				),
				encoding="utf-8",
			)
			source, version, _digest = bundle.loadEmbeddedBundle(root, store)
			self.assertEqual(version, "2.6.75")
			self.assertEqual(source.encode(), newPackagedPayload)

	def test_bundled_version_is_read_from_packaged_metadata(self) -> None:
		self.assertEqual(updater.loadBundledVersion(), "2.6.76")


if __name__ == "__main__":
	unittest.main()
