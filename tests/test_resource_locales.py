import ast
import hashlib
import json
import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).parents[1]
RESOURCE = ROOT / "addon/globalPlugins/whatsappWebPlusCompanion/resources/whatsapp_web_plus.user.js"
LOCK = ROOT / "upstream.json"


def catalog(path: pathlib.Path) -> dict[str, str]:
	text = path.read_text(encoding="utf-8")
	return dict(re.findall(r'^msgid "(.+)"\nmsgstr "(.*)"$', text, re.MULTILINE))


class ResourceLocaleTests(unittest.TestCase):
	def test_resource_matches_upstream_lock_and_bundle_metadata(self) -> None:
		resourceBytes = RESOURCE.read_bytes()
		resourceText = resourceBytes.decode("utf-8")
		locked = json.loads(LOCK.read_text(encoding="utf-8"))
		metadata = json.loads(RESOURCE.with_name("bundle.json").read_text(encoding="utf-8"))
		sha256 = hashlib.sha256(resourceBytes).hexdigest()
		version = re.search(r"^// @version\s+(.+)$", resourceText, re.MULTILINE)

		self.assertIsNotNone(version)
		self.assertEqual(version.group(1).strip(), locked["version"])
		self.assertEqual(sha256, locked["sha256"])
		self.assertEqual(metadata["sha256"], sha256)
		self.assertEqual(metadata["bytes"], len(resourceBytes))
		self.assertEqual(metadata["upstream"], locked["source"])

	def test_english_and_indonesian_catalogs_have_nonempty_parity(self) -> None:
		localeRoot = ROOT / "addon/locale"
		en = catalog(localeRoot / "en/LC_MESSAGES/nvda.po")
		indonesian = catalog(localeRoot / "id/LC_MESSAGES/nvda.po")
		self.assertEqual(set(en), set(indonesian))
		self.assertTrue(en)
		self.assertTrue(all(en.values()))
		self.assertTrue(all(indonesian.values()))

	def test_all_source_messages_are_present_in_both_catalogs(self) -> None:
		sourceMessages: set[str] = set()
		for path in (
			ROOT / "buildVars.py",
			ROOT / "addon/globalPlugins/whatsappWebPlusCompanion/__init__.py",
			ROOT / "addon/globalPlugins/whatsappWebPlusCompanion/forceCloseDialog.py",
		):
			tree = ast.parse(path.read_text(encoding="utf-8"))
			for node in ast.walk(tree):
				if (
					isinstance(node, ast.Call)
					and isinstance(node.func, ast.Name)
					and node.func.id == "_"
					and node.args
					and isinstance(node.args[0], ast.Constant)
					and isinstance(node.args[0].value, str)
				):
					sourceMessages.add(node.args[0].value)
		localeRoot = ROOT / "addon/locale"
		en = catalog(localeRoot / "en/LC_MESSAGES/nvda.po")
		indonesian = catalog(localeRoot / "id/LC_MESSAGES/nvda.po")
		self.assertTrue(sourceMessages)
		self.assertEqual(sourceMessages - set(en), set())
		self.assertEqual(sourceMessages - set(indonesian), set())


if __name__ == "__main__":
	unittest.main()
