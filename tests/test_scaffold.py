import ast
import pathlib
import unittest


ROOT = pathlib.Path(__file__).parents[1]


class ScaffoldTests(unittest.TestCase):
	def test_manifest_versions_and_complete_template_engine_exist(self) -> None:
		buildVarsSource = (ROOT / "buildVars.py").read_text(encoding="utf-8")
		buildVars = ast.parse(buildVarsSource)
		text = ast.unparse(buildVars)
		self.assertIn("2024.1.0", text)
		self.assertIn("2026.1.1", text)
		self.assertIn('addon_name="whatsappWebPlusCompanion"', buildVarsSource)
		self.assertIn('addon_summary=_("WhatsApp Companion")', buildVarsSource)
		self.assertIn('markdownExtensions: list[str] = ["tables"]', buildVarsSource)
		self.assertTrue((ROOT / "addon/globalPlugins/whatsappWebPlusCompanion/__init__.py").is_file())
		self.assertTrue((ROOT / "site_scons/site_tools/NVDATool/__init__.py").is_file())
		self.assertTrue((ROOT / "manifest.ini.tpl").is_file())
		self.assertTrue((ROOT / "manifest-translated.ini.tpl").is_file())

	def test_official_template_builds_markdown_docs_and_packages_addon_tree(self) -> None:
		buildVars = (ROOT / "buildVars.py").read_text(encoding="utf-8")
		sconstruct = (ROOT / "sconstruct").read_text(encoding="utf-8")
		self.assertIn('"addon/globalPlugins/whatsappWebPlusCompanion/*.py"', buildVars)
		self.assertNotIn("packageSources", buildVars)
		self.assertIn('Path("readme.md")', sconstruct)
		self.assertIn("env.md2html", sconstruct)
		self.assertTrue((ROOT / "addon/doc/id/readme.md").is_file())
		self.assertEqual(
			(ROOT / "COPYING.txt").read_bytes(),
			(ROOT / "addon/COPYING.txt").read_bytes(),
		)

	def test_runtime_sources_keep_python_311_compatibility(self) -> None:
		runtimeRoot = ROOT / "addon/globalPlugins/whatsappWebPlusCompanion"
		sources = "\n".join(path.read_text(encoding="utf-8") for path in runtimeRoot.glob("*.py"))
		self.assertNotIn("import secrets", sources)
		self.assertNotIn("from typing import Any, override", sources)
		self.assertNotIn(
			"from gui.message import MessageDialog, Payload",
			(runtimeRoot / "__init__.py").read_text(encoding="utf-8"),
		)
		self.assertTrue((runtimeRoot / "dialogs.py").is_file())


if __name__ == "__main__":
	unittest.main()
