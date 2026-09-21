from dataclasses import dataclass
import base64
import binascii
import hashlib
import json
from pathlib import Path
import re
from typing import Any


SIGNED_MANIFEST_SCHEMA_VERSION = 2
TRUST_STORE_SCHEMA_VERSION = 1
SIGNATURE_BYTES = 64
MAX_MANIFEST_BYTES = 16 * 1024
MAX_SIGNATURE_FILE_BYTES = 256
MAX_USERSCRIPT_BYTES = 2 * 1024 * 1024
OFFICIAL_DOWNLOAD_URL = "https://update.greasyfork.org/scripts/587557/WhatsApp%20Web%20Plus.user.js"
_VERSION_PATTERN = re.compile(r"\d+(?:\.\d+)*")
_KEY_ID_PATTERN = re.compile(r"[a-z0-9](?:[a-z0-9._-]{0,62}[a-z0-9])?")
_DIGEST_PATTERN = re.compile(r"[0-9a-f]{64}")
_SIGNATURE_PATTERN = re.compile(rb"[A-Za-z0-9+/]{86}==\n")
_MANIFEST_FIELDS = {
	"schemaVersion",
	"keyId",
	"releaseSequence",
	"version",
	"downloadUrl",
	"sha256",
	"bytes",
}
_TRUST_STORE_FIELDS = {"schemaVersion", "keys"}
_TRUST_KEY_REQUIRED_FIELDS = {"keyId", "algorithm", "publicKey", "status", "fingerprint"}
_TRUST_KEY_OPTIONAL_FIELDS = {"minimumReleaseSequence", "maximumReleaseSequence"}


class SignedManifestError(RuntimeError):
	def __init__(self, code: str) -> None:
		super().__init__(code)
		self.code = code


@dataclass(frozen=True, slots=True)
class SignedRelease:
	keyId: str
	releaseSequence: int
	version: str
	downloadUrl: str
	sha256: str
	bytes: int
	manifestSha256: str


def _rejectDuplicateObject(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
	result: dict[str, Any] = {}
	for key, value in pairs:
		if key in result:
			raise SignedManifestError("manifestDuplicateKey")
		result[key] = value
	return result


def _loadJson(payload: bytes, *, errorCode: str) -> Any:
	if payload.startswith(b"\xef\xbb\xbf"):
		raise SignedManifestError(errorCode)
	try:
		text = payload.decode("utf-8", "strict")
		return json.loads(text, object_pairs_hook=_rejectDuplicateObject)
	except SignedManifestError as error:
		if errorCode == "manifestInvalid":
			raise
		raise SignedManifestError(errorCode) from error
	except (UnicodeDecodeError, json.JSONDecodeError) as error:
		raise SignedManifestError(errorCode) from error


def _canonicalManifestBytes(value: dict[str, Any]) -> bytes:
	return (f"{json.dumps(value, indent=2, ensure_ascii=False)}\n").encode("utf-8")


def _validateManifestShape(value: Any, payload: bytes) -> dict[str, Any]:
	if not isinstance(value, dict) or set(value) != _MANIFEST_FIELDS:
		raise SignedManifestError("manifestInvalid")
	if _canonicalManifestBytes(value) != payload:
		raise SignedManifestError("manifestInvalid")
	if value.get("schemaVersion") != SIGNED_MANIFEST_SCHEMA_VERSION:
		raise SignedManifestError("manifestInvalid")
	keyId = value.get("keyId")
	releaseSequence = value.get("releaseSequence")
	version = value.get("version")
	downloadUrl = value.get("downloadUrl")
	digest = value.get("sha256")
	byteCount = value.get("bytes")
	if not isinstance(keyId, str) or _KEY_ID_PATTERN.fullmatch(keyId) is None:
		raise SignedManifestError("manifestInvalid")
	if (
		not isinstance(releaseSequence, int)
		or isinstance(releaseSequence, bool)
		or releaseSequence <= 0
		or releaseSequence > 9_999_999_999
	):
		raise SignedManifestError("manifestInvalid")
	if not isinstance(version, str) or _VERSION_PATTERN.fullmatch(version) is None:
		raise SignedManifestError("manifestInvalid")
	if downloadUrl != OFFICIAL_DOWNLOAD_URL:
		raise SignedManifestError("urlDisallowed")
	if not isinstance(digest, str) or _DIGEST_PATTERN.fullmatch(digest) is None:
		raise SignedManifestError("manifestInvalid")
	if (
		not isinstance(byteCount, int)
		or isinstance(byteCount, bool)
		or byteCount <= 0
		or byteCount > MAX_USERSCRIPT_BYTES
	):
		raise SignedManifestError("manifestInvalid")
	return value


def _loadTrustStore(path: Path) -> dict[str, dict[str, Any]]:
	try:
		payload = path.read_bytes()
	except OSError as error:
		raise SignedManifestError("trustStoreInvalid") from error
	value = _loadJson(payload, errorCode="trustStoreInvalid")
	if not isinstance(value, dict) or set(value) != _TRUST_STORE_FIELDS:
		raise SignedManifestError("trustStoreInvalid")
	if value.get("schemaVersion") != TRUST_STORE_SCHEMA_VERSION:
		raise SignedManifestError("trustStoreInvalid")
	keys = value.get("keys")
	if not isinstance(keys, list) or not keys:
		raise SignedManifestError("trustStoreInvalid")
	result: dict[str, dict[str, Any]] = {}
	for entry in keys:
		if not isinstance(entry, dict):
			raise SignedManifestError("trustStoreInvalid")
		fields = set(entry)
		if not _TRUST_KEY_REQUIRED_FIELDS.issubset(fields) or not fields.issubset(
			_TRUST_KEY_REQUIRED_FIELDS | _TRUST_KEY_OPTIONAL_FIELDS,
		):
			raise SignedManifestError("trustStoreInvalid")
		keyId = entry.get("keyId")
		if not isinstance(keyId, str) or _KEY_ID_PATTERN.fullmatch(keyId) is None or keyId in result:
			raise SignedManifestError("trustStoreInvalid")
		if entry.get("algorithm") != "Ed25519" or entry.get("status") not in {
			"active",
			"transition",
			"revoked",
		}:
			raise SignedManifestError("trustStoreInvalid")
		for limitName in _TRUST_KEY_OPTIONAL_FIELDS:
			limit = entry.get(limitName)
			if limit is not None and (not isinstance(limit, int) or isinstance(limit, bool) or limit <= 0):
				raise SignedManifestError("trustStoreInvalid")
		result[keyId] = entry
	return result


def _decodeSignature(payload: bytes) -> bytes:
	if len(payload) > MAX_SIGNATURE_FILE_BYTES or _SIGNATURE_PATTERN.fullmatch(payload) is None:
		raise SignedManifestError("signatureInvalid")
	try:
		signature = base64.b64decode(payload[:-1], validate=True)
	except (ValueError, binascii.Error) as error:
		raise SignedManifestError("signatureInvalid") from error
	if len(signature) != SIGNATURE_BYTES or base64.b64encode(signature) != payload[:-1]:
		raise SignedManifestError("signatureInvalid")
	return signature


def verifySignedManifest(
	manifestBytes: bytes,
	signatureFileBytes: bytes,
	trustStorePath: Path,
) -> SignedRelease:
	if not manifestBytes or len(manifestBytes) > MAX_MANIFEST_BYTES:
		raise SignedManifestError("manifestInvalid")
	value = _loadJson(manifestBytes, errorCode="manifestInvalid")
	manifest = _validateManifestShape(value, manifestBytes)
	trustStore = _loadTrustStore(trustStorePath)
	keyId = manifest["keyId"]
	entry = trustStore.get(keyId)
	if entry is None:
		raise SignedManifestError("keyUnknown")
	if entry["status"] == "revoked":
		raise SignedManifestError("keyRevoked")
	releaseSequence = manifest["releaseSequence"]
	minimum = entry.get("minimumReleaseSequence")
	maximum = entry.get("maximumReleaseSequence")
	if (minimum is not None and releaseSequence < minimum) or (
		maximum is not None and releaseSequence > maximum
	):
		raise SignedManifestError("keySequence")
	try:
		publicKeyBytes = base64.b64decode(entry["publicKey"], validate=True)
	except (TypeError, ValueError, binascii.Error) as error:
		raise SignedManifestError("trustStoreInvalid") from error
	if len(publicKeyBytes) != 32 or base64.b64encode(publicKeyBytes).decode("ascii") != entry["publicKey"]:
		raise SignedManifestError("trustStoreInvalid")
	if hashlib.sha256(publicKeyBytes).hexdigest() != entry["fingerprint"]:
		raise SignedManifestError("trustStoreInvalid")
	signature = _decodeSignature(signatureFileBytes)
	try:
		from cryptography.exceptions import InvalidSignature
		from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
	except ImportError as error:
		raise SignedManifestError("verifierUnavailable") from error
	try:
		Ed25519PublicKey.from_public_bytes(publicKeyBytes).verify(signature, manifestBytes)
	except InvalidSignature as error:
		raise SignedManifestError("signatureInvalid") from error
	except ValueError as error:
		raise SignedManifestError("trustStoreInvalid") from error
	return SignedRelease(
		keyId=keyId,
		releaseSequence=releaseSequence,
		version=manifest["version"],
		downloadUrl=manifest["downloadUrl"],
		sha256=manifest["sha256"],
		bytes=manifest["bytes"],
		manifestSha256=hashlib.sha256(manifestBytes).hexdigest(),
	)
