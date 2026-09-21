from dataclasses import dataclass
from enum import StrEnum
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import threading
from typing import Any
from urllib import request

from .bundle import (
	SCRIPT_DOWNLOAD_URL,
	SCRIPT_METADATA_URL,
	SIGNED_MANIFEST_SIGNATURE_URL,
	SIGNED_MANIFEST_URL,
	TRUST_STORE,
	UPDATE_MANIFEST,
	loadEmbeddedBundle,
	loadPackagedBundle,
	selectEmbeddedBundle,
	resourcesPath,
	updateStoreLock,
	updateStorePath,
	updateAssetName,
)
from .updateSignature import SignedManifestError, SignedRelease, verifySignedManifest


_MAX_METADATA_BYTES = 16 * 1024
_MAX_SCRIPT_BYTES = 2 * 1024 * 1024
_REQUEST_TIMEOUT_SECONDS = 10.0
_VERSION_PATTERN = re.compile(r"\d+(?:\.\d+)*")
_VERSION_DIRECTIVE_PATTERN = re.compile(r"^//\s*@version\s+([^\s]+)\s*$", re.MULTILINE)
_REQUIRED_DIRECTIVES = {
	"name": "WhatsApp Web Plus",
	"namespace": "https://github.com/muhammadGagah/whatsapp-web-plus",
	"match": "https://web.whatsapp.com/*",
	"run-at": "document-start",
	"updateURL": SCRIPT_METADATA_URL,
	"downloadURL": SCRIPT_DOWNLOAD_URL,
	"grant": "none",
}


class UpdateStatus(StrEnum):
	CURRENT = "current"
	UPDATED = "updated"
	ERROR = "error"


@dataclass(frozen=True, slots=True)
class UpdateCheckResult:
	status: UpdateStatus
	currentVersion: str
	latestVersion: str = ""
	errorCode: str = ""
	contentChanged: bool = False
	latestSequence: int = 0


class UpdateCheckError(RuntimeError):
	def __init__(self, code: str) -> None:
		super().__init__(code)
		self.code = code


class _NoRedirectHandler(request.HTTPRedirectHandler):
	def redirect_request(
		self,
		req: request.Request,
		fp: Any,
		code: int,
		msg: str,
		headers: Any,
		newurl: str,
	) -> None:
		return None


def _versionParts(version: str) -> tuple[int, ...]:
	if _VERSION_PATTERN.fullmatch(version) is None:
		raise UpdateCheckError("validation")
	return tuple(int(part) for part in version.split("."))


def compareVersions(left: str, right: str) -> int:
	leftParts = _versionParts(left)
	rightParts = _versionParts(right)
	length = max(len(leftParts), len(rightParts))
	leftParts += (0,) * (length - len(leftParts))
	rightParts += (0,) * (length - len(rightParts))
	return (leftParts > rightParts) - (leftParts < rightParts)


def parseMetadataVersion(metadata: bytes) -> str:
	if len(metadata) > _MAX_METADATA_BYTES:
		raise UpdateCheckError("validation")
	try:
		text = metadata.decode("utf-8", errors="strict")
	except UnicodeDecodeError as error:
		raise UpdateCheckError("validation") from error
	versions = _VERSION_DIRECTIVE_PATTERN.findall(text)
	if len(versions) != 1:
		raise UpdateCheckError("validation")
	_ = _versionParts(versions[0])
	return versions[0]


def _readBounded(
	opener: Any,
	url: str,
	maximumBytes: int,
	cancelEvent: threading.Event | None = None,
) -> bytes:
	httpRequest = request.Request(
		url,
		headers={"User-Agent": "WhatsAppWebPlusCompanion/0.1"},
		method="GET",
	)
	try:
		with opener.open(httpRequest, timeout=_REQUEST_TIMEOUT_SECONDS) as response:
			chunks: list[bytes] = []
			byteCount = 0
			while byteCount <= maximumBytes:
				if cancelEvent is not None and cancelEvent.is_set():
					raise UpdateCheckError("cancelled")
				chunk = response.read(min(64 * 1024, maximumBytes + 1 - byteCount))
				if not chunk:
					break
				chunks.append(chunk)
				byteCount += len(chunk)
	except OSError as error:
		raise UpdateCheckError("network") from error
	payload = b"".join(chunks)
	if len(payload) > maximumBytes:
		raise UpdateCheckError("validation")
	return payload


def _opener() -> Any:
	return request.build_opener(_NoRedirectHandler())


def fetchLatestVersion(
	opener: Any | None = None,
	cancelEvent: threading.Event | None = None,
) -> str:
	return parseMetadataVersion(
		_readBounded(
			opener if opener is not None else _opener(),
			SCRIPT_METADATA_URL,
			_MAX_METADATA_BYTES,
			cancelEvent,
		),
	)


def fetchSignedRelease(
	opener: Any | None = None,
	cancelEvent: threading.Event | None = None,
	*,
	resources: Path | None = None,
) -> SignedRelease:
	httpOpener = opener if opener is not None else _opener()
	manifestBytes = _readBounded(
		httpOpener,
		SIGNED_MANIFEST_URL,
		_MAX_METADATA_BYTES,
		cancelEvent,
	)
	signatureBytes = _readBounded(
		httpOpener,
		SIGNED_MANIFEST_SIGNATURE_URL,
		256,
		cancelEvent,
	)
	try:
		return verifySignedManifest(
			manifestBytes,
			signatureBytes,
			(resources if resources is not None else resourcesPath()) / TRUST_STORE,
		)
	except SignedManifestError as error:
		raise UpdateCheckError(error.code) from error


def _directives(source: str) -> dict[str, list[str]]:
	start = source.find("// ==UserScript==")
	end = source.find("// ==/UserScript==")
	if start != 0 or end <= start or end > 16 * 1024:
		raise UpdateCheckError("validation")
	result: dict[str, list[str]] = {}
	for line in source[start:end].splitlines():
		match = re.fullmatch(r"//\s*@([^\s]+)\s+(.+?)\s*", line)
		if match is not None:
			result.setdefault(match.group(1), []).append(match.group(2))
	return result


def validateDownloadedScript(payload: bytes, expectedVersion: str) -> tuple[str, str]:
	if len(payload) > _MAX_SCRIPT_BYTES:
		raise UpdateCheckError("validation")
	try:
		source = payload.decode("utf-8", errors="strict")
	except UnicodeDecodeError as error:
		raise UpdateCheckError("validation") from error
	directives = _directives(source)
	for name, expected in _REQUIRED_DIRECTIVES.items():
		if directives.get(name) != [expected]:
			raise UpdateCheckError("validation")
	versions = directives.get("version", [])
	if len(versions) != 1 or versions[0] != expectedVersion:
		raise UpdateCheckError("validation")
	_ = _versionParts(expectedVersion)
	return source, hashlib.sha256(payload).hexdigest()


def fetchScript(
	expectedVersion: str,
	opener: Any | None = None,
	cancelEvent: threading.Event | None = None,
) -> tuple[bytes, str]:
	payload = _readBounded(
		opener if opener is not None else _opener(),
		SCRIPT_DOWNLOAD_URL,
		_MAX_SCRIPT_BYTES,
		cancelEvent,
	)
	_source, digest = validateDownloadedScript(payload, expectedVersion)
	return payload, digest


def fetchReleaseScript(
	release: SignedRelease,
	opener: Any | None = None,
	cancelEvent: threading.Event | None = None,
) -> tuple[bytes, str]:
	payload = _readBounded(
		opener if opener is not None else _opener(),
		release.downloadUrl,
		_MAX_SCRIPT_BYTES,
		cancelEvent,
	)
	if len(payload) != release.bytes:
		raise UpdateCheckError("assetMismatch")
	_source, digest = validateDownloadedScript(payload, release.version)
	if digest != release.sha256:
		raise UpdateCheckError("assetMismatch")
	return payload, digest


def loadBundledVersion(resources: Path | None = None, updateStore: Path | None = None) -> str:
	version, _digest = loadBundledIdentity(resources, updateStore)
	return version


def loadBundledIdentity(
	resources: Path | None = None,
	updateStore: Path | None = None,
) -> tuple[str, str]:
	try:
		_source, version, digest = loadEmbeddedBundle(resources, updateStore)
	except Exception as error:
		raise UpdateCheckError("validation") from error
	_ = _versionParts(version)
	return version, digest


def _atomicWrite(path: Path, payload: bytes) -> None:
	temporaryPath: Path | None = None
	try:
		with tempfile.NamedTemporaryFile(
			mode="wb",
			dir=path.parent,
			prefix=f".{path.name}.",
			suffix=".tmp",
			delete=False,
		) as temporary:
			temporaryPath = Path(temporary.name)
			temporary.write(payload)
			temporary.flush()
			os.fsync(temporary.fileno())
		os.replace(temporaryPath, path)
		temporaryPath = None
	except OSError as error:
		raise UpdateCheckError("save") from error
	finally:
		if temporaryPath is not None:
			try:
				temporaryPath.unlink()
			except OSError:
				pass


def installDownloadedBundle(
	payload: bytes,
	release: SignedRelease,
	*,
	resources: Path | None = None,
	updateStore: Path | None = None,
	cancelEvent: threading.Event | None = None,
	expectedCurrentVersion: str | None = None,
	expectedCurrentDigest: str | None = None,
	expectedCurrentSequence: int | None = None,
) -> bool:
	_source, actualDigest = validateDownloadedScript(payload, release.version)
	if actualDigest != release.sha256 or len(payload) != release.bytes:
		raise UpdateCheckError("assetMismatch")
	root = updateStore if updateStore is not None else updateStorePath()
	if root is None:
		raise UpdateCheckError("save")
	try:
		root.mkdir(parents=True, exist_ok=True)
	except OSError as error:
		raise UpdateCheckError("save") from error
	if expectedCurrentVersion is None or expectedCurrentDigest is None or expectedCurrentSequence is None:
		try:
			expected = selectEmbeddedBundle(resources, root)
		except Exception as error:
			raise UpdateCheckError("validation") from error
		expectedCurrentVersion = expected.version
		expectedCurrentDigest = expected.sha256
		expectedCurrentSequence = expected.releaseSequence
	assetName = updateAssetName(release.sha256)
	manifest = {
		"schemaVersion": 2,
		"asset": assetName,
		"version": release.version,
		"sha256": release.sha256,
		"bytes": len(payload),
		"source": release.downloadUrl,
		"releaseSequence": release.releaseSequence,
		"keyId": release.keyId,
		"signedManifestSha256": release.manifestSha256,
	}
	try:
		_packagedSource, _packagedVersion, packagedDigest = loadPackagedBundle(resources)
	except Exception as error:
		raise UpdateCheckError("validation") from error
	manifest["baseSha256"] = packagedDigest
	try:
		with updateStoreLock(root, cancelEvent):
			if cancelEvent is not None and cancelEvent.is_set():
				raise UpdateCheckError("cancelled")
			selected = selectEmbeddedBundle(resources, root)
			candidateComparison = compareVersions(release.version, selected.version)
			if (
				release.releaseSequence <= selected.releaseSequence
				or candidateComparison < 0
				or selected.version != expectedCurrentVersion
				or selected.sha256 != expectedCurrentDigest
				or selected.releaseSequence != expectedCurrentSequence
			):
				return False
			_atomicWrite(root / assetName, payload)
			if cancelEvent is not None and cancelEvent.is_set():
				raise UpdateCheckError("cancelled")
			manifestPath = root / UPDATE_MANIFEST
			try:
				previousManifest = manifestPath.read_bytes()
			except FileNotFoundError:
				previousManifest = None
			except OSError as error:
				raise UpdateCheckError("save") from error
			candidateManifest = (f"{json.dumps(manifest, indent=2)}\n").encode("utf-8")
			_atomicWrite(manifestPath, candidateManifest)
			try:
				_source, installedVersion, installedDigest = loadEmbeddedBundle(resources, root)
			except Exception as error:
				verificationError = error
			else:
				verificationError = (
					None
					if installedVersion == release.version and installedDigest == release.sha256
					else UpdateCheckError("save")
				)
			if verificationError is not None:
				try:
					if manifestPath.read_bytes() == candidateManifest:
						if previousManifest is None:
							manifestPath.unlink()
						else:
							_atomicWrite(manifestPath, previousManifest)
				except (OSError, UpdateCheckError):
					pass
				raise UpdateCheckError("save") from verificationError
			return True
	except InterruptedError as error:
		raise UpdateCheckError("cancelled") from error
	except (OSError, TimeoutError) as error:
		raise UpdateCheckError("save") from error


def checkForUpdate(
	cancelEvent: threading.Event | None = None,
	*,
	resources: Path | None = None,
	updateStore: Path | None = None,
	opener: Any | None = None,
) -> UpdateCheckResult:
	currentVersion = ""
	try:
		try:
			current = selectEmbeddedBundle(resources, updateStore)
		except Exception as error:
			raise UpdateCheckError("validation") from error
		currentVersion = current.version
		currentDigest = current.sha256
		httpOpener = opener if opener is not None else _opener()
		release = fetchSignedRelease(httpOpener, cancelEvent, resources=resources)
		if release.releaseSequence < current.releaseSequence:
			raise UpdateCheckError("replay")
		if release.releaseSequence == current.releaseSequence:
			if (
				release.version == current.version
				and release.sha256 == current.sha256
				and release.keyId == current.keyId
				and (
					current.signedManifestSha256 is None
					or release.manifestSha256 == current.signedManifestSha256
				)
			):
				return UpdateCheckResult(
					UpdateStatus.CURRENT,
					currentVersion,
					release.version,
					latestSequence=release.releaseSequence,
				)
			raise UpdateCheckError("replay")
		comparison = compareVersions(release.version, currentVersion)
		if comparison < 0:
			raise UpdateCheckError("downgrade")
		payload, _digest = fetchReleaseScript(release, httpOpener, cancelEvent)
		installed = installDownloadedBundle(
			payload,
			release,
			resources=resources,
			updateStore=updateStore,
			cancelEvent=cancelEvent,
			expectedCurrentVersion=currentVersion,
			expectedCurrentDigest=currentDigest,
			expectedCurrentSequence=current.releaseSequence,
		)
		if not installed:
			selectedVersion, _selectedDigest = loadBundledIdentity(resources, updateStore)
			return UpdateCheckResult(
				UpdateStatus.CURRENT,
				selectedVersion,
				release.version,
				latestSequence=release.releaseSequence,
			)
	except UpdateCheckError as error:
		return UpdateCheckResult(UpdateStatus.ERROR, currentVersion, errorCode=error.code)
	return UpdateCheckResult(
		UpdateStatus.UPDATED,
		currentVersion,
		release.version,
		contentChanged=comparison == 0,
		latestSequence=release.releaseSequence,
	)
