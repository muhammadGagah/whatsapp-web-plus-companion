"""Fail closed when release source, tag, or packaged identity disagree."""

import argparse
import ast
import hashlib
import json
import os
import re
import runpy
import zipfile
from pathlib import Path


def verifyUserscript(archive: zipfile.ZipFile, root: Path) -> None:
	lock = json.loads((root / "upstream.json").read_text(encoding="utf-8"))
	if (
		lock.get("schemaVersion") != 2
		or lock.get("signedManifestSchemaVersion") != 2
		or lock.get("asset") != "whatsapp_web_plus.user.js"
		or lock.get("source") != "https://update.greasyfork.org/scripts/587557/WhatsApp%20Web%20Plus.user.js"
	):
		raise ValueError("Invalid userscript upstream lock")
	base = "globalPlugins/whatsappWebPlusCompanion/resources/"
	for name in ("bundle.json", "whatsapp_web_plus.user.js"):
		if archive.namelist().count(base + name) != 1:
			raise ValueError(f"Userscript package must contain exactly one {name}")
	metadata = json.loads(archive.read(base + "bundle.json").decode("utf-8"))
	for key in ("version", "sha256", "bytes", "releaseSequence", "keyId"):
		if key not in lock or metadata.get(key) != lock[key]:
			raise ValueError(f"Packaged bundle metadata differs from upstream lock: {key}")
	if metadata.get("upstream") != lock["source"]:
		raise ValueError("Packaged bundle metadata has an unexpected upstream URL")
	if metadata.get("developmentSnapshot") or lock.get("developmentSnapshot"):
		raise ValueError("Userscript development snapshot cannot be packaged for release")
	payload = archive.read(base + "whatsapp_web_plus.user.js")
	if len(payload) != lock["bytes"] or hashlib.sha256(payload).hexdigest() != lock["sha256"]:
		raise ValueError("Userscript bytes differ from upstream lock")
	versions = re.findall(r"^// @version[ \t]+([^\r\n]+)", payload.decode("utf-8"), re.MULTILINE)
	if versions != [lock["version"]]:
		raise ValueError("Userscript version differs from upstream lock")


def sourceIdentity(root: Path) -> tuple[str, str]:
	module = ast.parse((root / "buildVars.py").read_text(encoding="utf-8-sig"))
	assignments = [
		node.value
		for node in module.body
		if isinstance(node, ast.Assign)
		and any(isinstance(target, ast.Name) and target.id == "addon_info" for target in node.targets)
	]
	if len(assignments) != 1 or not isinstance(assignments[0], ast.Call):
		raise ValueError("Expected one addon_info declaration in buildVars.py")
	values = {
		item.arg: ast.literal_eval(item.value)
		for item in assignments[0].keywords
		if item.arg in ("addon_name", "addon_version")
	}
	name, version = values.get("addon_name"), values.get("addon_version")
	if not isinstance(name, str) or re.fullmatch(r"[A-Za-z0-9_-]+", name) is None:
		raise ValueError("Invalid add-on name")
	if (
		not isinstance(version, str)
		or re.fullmatch(r"[0-9]+(?:\.[0-9]+)*(?:-[A-Za-z0-9.-]+)?", version) is None
	):
		raise ValueError("Invalid add-on version")
	if json.loads((root / "package.json").read_text(encoding="utf-8"))["version"] != version:
		raise ValueError("package.json version differs from buildVars.py")
	return name, version


def verifyRelease(
	root: Path,
	*,
	tag: str | None = None,
	package: Path | None = None,
	sourceOnly: bool = False,
	artifactsDir: Path | None = None,
) -> Path:
	name, version = sourceIdentity(root)
	if tag is not None and tag != f"v{version}":
		raise ValueError(f"Release tag {tag!r} does not match source version v{version}")
	expectedName = f"{name}-{version}.nvda-addon"
	package = package or (artifactsDir or root) / expectedName
	if package.name != expectedName:
		raise ValueError(f"Expected package filename {expectedName}, got {package.name}")
	if sourceOnly:
		return package
	if artifactsDir is not None:
		assets = sorted(path.name for path in artifactsDir.glob("*.nvda-addon"))
		if assets != [expectedName]:
			raise ValueError(f"Unexpected release assets: {assets!r}; expected only {expectedName}")
	with zipfile.ZipFile(package) as archive:
		if archive.namelist().count("manifest.ini") != 1:
			raise ValueError("Package must contain exactly one manifest.ini")
		manifest = archive.read("manifest.ini").decode("utf-8-sig").replace("\r\n", "\n")
		for key, expected in (("name", name), ("version", version)):
			values = re.findall(rf"^{key}\s*=\s*([^\r\n]+)$", manifest, re.MULTILINE)
			if len(values) != 1 or values[0].strip().strip("\"'") != expected:
				raise ValueError(f"Packaged manifest {key} differs from release source")
		verifyUserscript(archive, root)
	return package


def main() -> None:
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("--tag")
	parser.add_argument("--source-only", action="store_true")
	parser.add_argument("--artifacts-dir", type=Path)
	args = parser.parse_args()
	ref = os.environ.get("GITHUB_REF", "")
	tag = (
		args.tag
		if args.tag is not None
		else (ref.removeprefix("refs/tags/") if ref.startswith("refs/tags/") else None)
	)
	root = Path(__file__).resolve().parents[1]
	package = verifyRelease(root, tag=tag, sourceOnly=args.source_only, artifactsDir=args.artifacts_dir)
	if not args.source_only:
		# Verify again after artifact download, not just before upload.
		verifier = runpy.run_path(str(root / "scripts" / "verify-registry-helper.py"))
		verifier["verifyPackage"](package, root)
	print(f"Release identity verified: {package.name}; tag={tag or '(non-tag build)'}")


if __name__ == "__main__":
	main()
