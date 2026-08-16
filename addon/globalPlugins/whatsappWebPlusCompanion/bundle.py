from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import time

try:
	import msvcrt
except ImportError:
	msvcrt = None

try:
	import fcntl
except ImportError:
	fcntl = None

from .models import LoaderError


SCRIPT_METADATA_URL = "https://update.greasyfork.org/scripts/587557/WhatsApp%20Web%20Plus.meta.js"
SCRIPT_DOWNLOAD_URL = "https://update.greasyfork.org/scripts/587557/WhatsApp%20Web%20Plus.user.js"
PACKAGED_ASSET = "whatsapp_web_plus.user.js"
PACKAGED_MANIFEST = "bundle.json"
UPDATE_MANIFEST = "bundle-update.json"
_UPDATE_ASSET_PATTERN = re.compile(r"whatsapp_web_plus\.update\.([0-9a-f]{64})\.user\.js")
_VERSION_PATTERN = re.compile(r"\d+(?:\.\d+)*")
_STORE_LOCK_TIMEOUT_SECONDS = 10.0


@dataclass(frozen=True, slots=True)
class EmbeddedBundle:
	source: str
	version: str
	sha256: str
	asset: Path
	baseSha256: str | None = None
	isUpdate: bool = False


def resourcesPath() -> Path:
	return Path(__file__).with_name("resources")


def updateStorePath() -> Path | None:
	try:
		import NVDAState

		configDir = NVDAState.WritePaths.configDir
	except (ImportError, AttributeError):
		return None
	return Path(configDir) / "whatsappWebPlusCompanion" / "bundleUpdates"


def updateAssetName(sha256: str) -> str:
	if re.fullmatch(r"[0-9a-f]{64}", sha256) is None:
		raise ValueError("invalid bundle digest")
	return f"whatsapp_web_plus.update.{sha256}.user.js"


@contextmanager
def updateStoreLock(root: Path, cancelEvent: object | None = None) -> Iterator[None]:
	root.mkdir(parents=True, exist_ok=True)
	lockPath = root / "bundle-update.lock"
	with lockPath.open("a+b") as lockFile:
		lockFile.seek(0, os.SEEK_END)
		if lockFile.tell() == 0:
			lockFile.write(b"\0")
			lockFile.flush()
		lockFile.seek(0)
		deadline = time.monotonic() + _STORE_LOCK_TIMEOUT_SECONDS
		while True:
			if cancelEvent is not None and cancelEvent.is_set():
				raise InterruptedError("bundle update cancelled")
			try:
				if msvcrt is not None:
					msvcrt.locking(lockFile.fileno(), msvcrt.LK_NBLCK, 1)
				elif fcntl is not None:
					fcntl.flock(lockFile.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
				else:
					raise RuntimeError("no supported file-lock API is available")
				break
			except OSError:
				if time.monotonic() >= deadline:
					raise TimeoutError("bundle update store is busy")
				if cancelEvent is not None:
					cancelEvent.wait(0.05)
				else:
					time.sleep(0.05)
		try:
			yield
		finally:
			if msvcrt is not None:
				lockFile.seek(0)
				msvcrt.locking(lockFile.fileno(), msvcrt.LK_UNLCK, 1)
			elif fcntl is not None:
				fcntl.flock(lockFile.fileno(), fcntl.LOCK_UN)


def _versionParts(version: str) -> tuple[int, ...]:
	if _VERSION_PATTERN.fullmatch(version) is None:
		raise LoaderError("bundle.integrity")
	return tuple(int(part) for part in version.split("."))


def _compareVersions(left: str, right: str) -> int:
	leftParts = _versionParts(left)
	rightParts = _versionParts(right)
	length = max(len(leftParts), len(rightParts))
	leftParts += (0,) * (length - len(leftParts))
	rightParts += (0,) * (length - len(rightParts))
	return (leftParts > rightParts) - (leftParts < rightParts)


def _loadManifest(path: Path) -> dict:
	try:
		value = json.loads(path.read_text(encoding="utf-8"))
	except FileNotFoundError:
		raise
	except (OSError, UnicodeError, ValueError) as error:
		raise LoaderError("bundle.metadata", type(error).__name__) from error
	if not isinstance(value, dict):
		raise LoaderError("bundle.metadata", "type")
	return value


def _loadCandidate(resources: Path, manifestName: str, *, updated: bool) -> EmbeddedBundle:
	metadata = _loadManifest(resources / manifestName)
	assetName = metadata.get("asset", PACKAGED_ASSET if not updated else None)
	version = metadata.get("version")
	digest = metadata.get("sha256")
	byteCount = metadata.get("bytes")
	baseDigest = metadata.get("baseSha256") if updated else None
	if (
		not isinstance(version, str)
		or not isinstance(digest, str)
		or not isinstance(byteCount, int)
		or isinstance(byteCount, bool)
		or not isinstance(assetName, str)
	):
		raise LoaderError("bundle.integrity")
	_ = _versionParts(version)
	if updated:
		match = _UPDATE_ASSET_PATTERN.fullmatch(assetName)
		if (
			metadata.get("schemaVersion") != 1
			or metadata.get("source") != SCRIPT_DOWNLOAD_URL
			or match is None
			or match.group(1) != digest
			or not isinstance(baseDigest, str)
			or re.fullmatch(r"[0-9a-f]{64}", baseDigest) is None
		):
			raise LoaderError("bundle.integrity")
	elif assetName != PACKAGED_ASSET:
		raise LoaderError("bundle.integrity")
	try:
		sourceBytes = (resources / assetName).read_bytes()
	except OSError as error:
		raise LoaderError("bundle.integrity", type(error).__name__) from error
	actualDigest = hashlib.sha256(sourceBytes).hexdigest()
	if actualDigest != digest or len(sourceBytes) != byteCount:
		raise LoaderError("bundle.integrity")
	try:
		source = sourceBytes.decode("utf-8", "strict")
	except UnicodeDecodeError as error:
		raise LoaderError("bundle.encoding") from error
	return EmbeddedBundle(source, version, digest, resources / assetName, baseDigest, updated)


def loadPackagedBundle(resources: Path | None = None) -> tuple[str, str, str]:
	packagedRoot = resources if resources is not None else resourcesPath()
	bundle = _loadCandidate(packagedRoot, PACKAGED_MANIFEST, updated=False)
	return bundle.source, bundle.version, bundle.sha256


def selectEmbeddedBundle(
	resources: Path | None = None,
	updateStore: Path | None = None,
) -> EmbeddedBundle:
	packagedRoot = resources if resources is not None else resourcesPath()
	updatesRoot = updateStore if updateStore is not None else updateStorePath()
	packagedBundle = _loadCandidate(packagedRoot, PACKAGED_MANIFEST, updated=False)
	if updatesRoot is not None:
		try:
			updatedBundle = _loadCandidate(updatesRoot, UPDATE_MANIFEST, updated=True)
		except (FileNotFoundError, LoaderError):
			bundle = packagedBundle
		else:
			versionComparison = _compareVersions(updatedBundle.version, packagedBundle.version)
			bundle = (
				updatedBundle
				if versionComparison > 0
				or (versionComparison == 0 and updatedBundle.baseSha256 == packagedBundle.sha256)
				else packagedBundle
			)
	else:
		bundle = packagedBundle
	return bundle


def loadEmbeddedBundle(
	resources: Path | None = None,
	updateStore: Path | None = None,
) -> tuple[str, str, str]:
	bundle = selectEmbeddedBundle(resources, updateStore)
	return bundle.source, bundle.version, bundle.sha256


def quarantineUpdatedBundle(
	expectedDigest: str,
	updateStore: Path | None = None,
) -> bool:
	if re.fullmatch(r"[0-9a-f]{64}", expectedDigest) is None:
		return False
	root = updateStore if updateStore is not None else updateStorePath()
	if root is None:
		return False
	try:
		with updateStoreLock(root):
			manifestPath = root / UPDATE_MANIFEST
			metadata = _loadManifest(manifestPath)
			if metadata.get("sha256") != expectedDigest:
				return False
			quarantinePath = root / f"bundle-update.quarantined.{expectedDigest}.json"
			os.replace(manifestPath, quarantinePath)
	except (FileNotFoundError, LoaderError, OSError, TimeoutError):
		return False
	return True
