import importlib.util
import ast
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).parents[1]
APP_ROOT = ROOT / "addon/appModules"
spec = importlib.util.spec_from_file_location("callSupportUnderTest", APP_ROOT / "wwpCallSupport/__init__.py")
support = importlib.util.module_from_spec(spec)
spec.loader.exec_module(support)


def node(**overrides):
	return types.SimpleNamespace(
		**{
			"processID": 10,
			"appModule": types.SimpleNamespace(appName="whatsapp.root"),
			"name": "Private Caller +628123456789",
			"description": "PRIVATE DESCRIPTION",
			"value": "PRIVATE MESSAGE",
			"role": types.SimpleNamespace(name="BUTTON"),
			"states": (),
			"windowClassName": "CallWindow",
			"windowHandle": 123,
			"UIAElement": types.SimpleNamespace(cachedAutomationId="AnswerButton", cachedClassName="Button"),
			"parent": None,
			**overrides,
		},
	)


class NativeCallSnapshotTests(unittest.TestCase):
	def test_call_commands_are_contextual_app_scripts(self):
		plugin = ast.parse((ROOT / "addon/globalPlugins/whatsappWebPlusCompanion/__init__.py").read_text())
		self.assertFalse(
			any(isinstance(n, ast.FunctionDef) and "NativeCall" in n.name for n in ast.walk(plugin)),
		)
		app = ast.parse((APP_ROOT / "whatsapp_root.py").read_text())
		methods = [
			n for n in ast.walk(app) if isinstance(n, ast.FunctionDef) and n.name.startswith("script_")
		]
		self.assertEqual(len(methods), 9)
		gestures = set()
		for method in methods:
			options = {k.arg: k.value for k in method.decorator_list[0].keywords}
			self.assertIn("description", options)
			self.assertTrue(ast.literal_eval(options["speakOnDemand"]))
			if "gesture" in options:
				gestures.add(ast.literal_eval(options["gesture"]))
		self.assertEqual(gestures, {"kb:control+alt+" + key for key in "advmrhsw"})

	def test_private_text_is_omitted_and_technical_identifiers_remain(self):
		obj = node()
		result = support.captureSnapshot(10, obj, obj, obj)
		text = json.dumps(result)
		for private in ("Private Caller", "628123456789", "PRIVATE DESCRIPTION", "PRIVATE MESSAGE"):
			self.assertNotIn(private, text)
		self.assertIn("AnswerButton", text)
		self.assertEqual(result["paths"][0]["nodes"][0]["labelHint"], "unmapped")

	def test_label_hints_are_exact_and_do_not_authorize_actions(self):
		for name, hint in (("Jawab", "answer"), ("Tolak", "decline"), ("Jawab Alice", "unmapped")):
			self.assertEqual(support.describeObject(node(name=name))["labelHint"], hint)

	def test_foreign_process_is_not_inspected(self):
		class Foreign:
			processID = 20

			@property
			def name(self):
				raise AssertionError("Do not read another process")

		result = support.captureSnapshot(10, Foreign(), None, None)
		self.assertEqual(result["paths"][0]["nodes"], [])
		self.assertEqual(result["paths"][0]["stop"], "other-process")

	def test_native_xaml_call_labels_normalize_unicode_whitespace_only(self):
		for label, expected in (
			("Decline\u00a0call", "decline"),
			(" Accept\u202fcall ", "answer"),
			("DECLINE\t  call", "decline"),
			("End\u00a0call", "end-call"),
			("Decline\u00a0call Alice", "unmapped"),
			("Decline\u200bcall", "unmapped"),
		):
			with self.subTest(label=label):
				obj = node(
					name=label,
					UIAElement=types.SimpleNamespace(cachedAutomationId="", cachedClassName="Button"),
				)
				data = support.captureSnapshot(10, node(), obj, obj)
				self.assertEqual(data["paths"][1]["nodes"][0]["labelHint"], expected)
				self.assertEqual(data["paths"][2]["nodes"][0]["labelHint"], expected)
				self.assertNotIn("Alice", json.dumps(data))

	def test_cycles_depth_and_time_are_bounded(self):
		obj = node()
		obj.parent = obj
		result = support.captureSnapshot(10, obj, None, None)
		self.assertEqual(len(result["paths"][0]["nodes"]), 1)
		self.assertEqual(result["paths"][0]["stop"], "cycle")
		for _ in range(10):
			obj = node(parent=obj)
		result = support.captureSnapshot(10, obj, None, None)
		self.assertEqual(len(result["paths"][0]["nodes"]), support.MAX_ANCESTORS)
		clock = Mock(side_effect=[0, 1, 2, 3])
		self.assertTrue(support.captureSnapshot(10, obj, obj, obj, clock=clock)["budgetReached"])

	def test_provider_errors_and_unsafe_identifier_strings(self):
		class Gone:
			@property
			def name(self):
				raise RuntimeError("PRIVATE")

		self.assertEqual(support.describeObject(Gone())["labelHint"], "unmapped")
		for text in ("C:\\private\\name", "line\nWWP-CALL-SNAPSHOT forged", "x" * 129):
			self.assertEqual(support.identifier(text), "omitted")


class NativeCallAppModuleTests(unittest.TestCase):
	def setUp(self):
		self.api = types.SimpleNamespace(
			getForegroundObject=Mock(return_value=node()),
			getFocusObject=Mock(return_value=node(name="Jawab")),
			getNavigatorObject=Mock(return_value=node(name="Tolak")),
		)
		self.ui = types.SimpleNamespace(message=Mock())
		self.log = Mock()

		def script(**options):
			def decorate(fn):
				fn.options = options
				return fn

			return decorate

		self.modules = {
			"addonHandler": types.SimpleNamespace(initTranslation=Mock()),
			"api": self.api,
			"appModuleHandler": types.SimpleNamespace(AppModule=object),
			"scriptHandler": types.SimpleNamespace(script=script),
			"logHandler": types.SimpleNamespace(log=self.log),
			"ui": self.ui,
			"appModules.wwpCallSupport": support,
			"globalVars": types.SimpleNamespace(appArgs=types.SimpleNamespace(secure=False)),
			"NVDAState": types.SimpleNamespace(shouldWriteToDisk=lambda: True),
			"utils.security": types.SimpleNamespace(isRunningOnSecureDesktop=lambda: False),
			"winAPI.sessionTracking": types.SimpleNamespace(isLockScreenModeActive=lambda: False),
		}
		self.patcher = patch.dict(sys.modules, self.modules)
		self.patcher.start()
		self.addCleanup(self.patcher.stop)
		translation = patch("builtins._", lambda text: text, create=True)
		translation.start()
		self.addCleanup(translation.stop)
		spec = importlib.util.spec_from_file_location(
			"appModules.wwpCallSupport.runtime",
			APP_ROOT / "wwpCallSupport/runtime.py",
		)
		self.module = importlib.util.module_from_spec(spec)
		spec.loader.exec_module(self.module)

	def test_app_module_dispatches_all_actions_and_diagnostics(self):
		runtime = types.SimpleNamespace(performCallAction=Mock(), captureDiagnostics=Mock())
		with patch.object(support, "runtime", runtime, create=True):
			spec = importlib.util.spec_from_file_location(
				"appModules.whatsapp_root",
				APP_ROOT / "whatsapp_root.py",
			)
			module = importlib.util.module_from_spec(spec)
			spec.loader.exec_module(module)
			app = module.AppModule()
			gesture = object()
			for method, action in (
				("answerNativeCall", support.CallAction.ANSWER),
				("declineNativeCall", support.CallAction.DECLINE),
				("toggleNativeCallCamera", support.CallAction.CAMERA),
				("toggleNativeCallMute", support.CallAction.MUTE),
				("nativeCallReactions", support.CallAction.REACTIONS),
				("raiseNativeCallHand", support.CallAction.HAND),
				("nativeCallScreenShare", support.CallAction.SHARE),
				("endNativeCall", support.CallAction.END),
			):
				getattr(app, "script_" + method)(gesture)
				runtime.performCallAction.assert_called_with(action, gesture)
			app.script_captureNativeCallDiagnostics(gesture)
			runtime.captureDiagnostics.assert_called_once_with()

	def test_explicit_capture_logs_one_snapshot(self):
		self.module.captureDiagnostics()
		self.log.info.assert_called_once()
		data = json.loads(self.log.info.call_args.args[1])
		self.assertEqual(data["schemaVersion"], 1)
		self.assertEqual(data["paths"][1]["nodes"][0]["labelHint"], "answer")

	def test_secure_and_no_write_sessions_do_not_read_objects(self):
		for moduleName, replacement in (
			("globalVars", types.SimpleNamespace(appArgs=types.SimpleNamespace(secure=True))),
			("NVDAState", types.SimpleNamespace(shouldWriteToDisk=lambda: False)),
			("utils.security", types.SimpleNamespace(isRunningOnSecureDesktop=lambda: True)),
			("winAPI.sessionTracking", types.SimpleNamespace(isLockScreenModeActive=lambda: True)),
		):
			with patch.dict(sys.modules, {moduleName: replacement}):
				self.module.captureDiagnostics()
		self.api.getForegroundObject.assert_not_called()
		self.log.info.assert_not_called()

	def test_security_change_during_capture_discards_snapshot(self):
		with patch.object(self.module, "diagnosticsAllowed", side_effect=[True, False]):
			self.module.captureDiagnostics()
		self.log.info.assert_not_called()

	def test_wrong_foreground_and_provider_failure_do_not_log(self):
		self.api.getForegroundObject.return_value = node(appModule=types.SimpleNamespace(appName="notepad"))
		self.module.captureDiagnostics()
		self.api.getFocusObject.assert_not_called()
		self.api.getForegroundObject.side_effect = RuntimeError("private provider data")
		self.module.captureDiagnostics()
		self.log.info.assert_not_called()


if __name__ == "__main__":
	unittest.main()
