"""Verify the exact helper bytes shipped in the built add-on. Never rewrite hashes."""

from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from pathlib import Path


def verifyPackage(package: Path, root: Path) -> None:
	resources = "globalPlugins/whatsappWebPlusCompanion/resources"
	lockPath = f"{resources}/registry-repair.json"
	lock = json.loads((root / "addon" / lockPath).read_text(encoding="utf-8-sig"))
	with zipfile.ZipFile(package) as archive:
		if json.loads(archive.read(lockPath).decode("utf-8-sig")) != lock:
			raise ValueError("Packaged repair integrity lock differs from source")
		for extension in ("bat", "ps1"):
			name = f"{resources}/registryRepair/registryRepair.{extension}"
			payload = archive.read(name)
			entry = lock["helper"][extension]
			if len(payload) != entry["bytes"] or hashlib.sha256(payload).hexdigest() != entry["sha256"]:
				raise ValueError(f"Packaged repair helper integrity mismatch: {name}")
			if payload != (root / "addon" / name).read_bytes():
				raise ValueError(f"Packaged repair helper differs from source: {name}")
	print(f"Verified both repair helpers in {package.name}")


if __name__ == "__main__":
	projectRoot = Path(__file__).resolve().parents[1]
	version = json.loads((projectRoot / "package.json").read_text(encoding="utf-8"))["version"]
	packagePath = (
		Path(sys.argv[1])
		if len(sys.argv) > 1
		else projectRoot / f"whatsappWebPlusCompanion-{version}.nvda-addon"
	)
	verifyPackage(packagePath, projectRoot)
