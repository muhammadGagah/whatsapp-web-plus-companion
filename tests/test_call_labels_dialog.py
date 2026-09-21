import builtins
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest import mock

from _path import installPackagePath

installPackagePath()


class Editor:
	def __init__(self, value=""):
		self.value = value
		self.focused = False

	def GetValue(self):
		return self.value

	def ChangeValue(self, value):
		self.value = value

	def SetFocus(self):
		self.focused = True


class CallLabelsDialogTests(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		fakeWx = types.SimpleNamespace(Dialog=object)
		path = Path(__file__).parents[1] / "addon/globalPlugins/whatsappWebPlusCompanion/callLabelsDialog.py"
		spec = importlib.util.spec_from_file_location("callLabelsDialogTest", path)
		cls.module = importlib.util.module_from_spec(spec)
		with (
			mock.patch.dict(
				sys.modules,
				{
					"wx": fakeWx,
					"addonHandler": types.SimpleNamespace(initTranslation=lambda: None),
				},
			),
			mock.patch.object(builtins, "_", lambda text: text, create=True),
		):
			spec.loader.exec_module(cls.module)
		cls.module._ = lambda text: text

	def setUp(self):
		self.dialog = self.module.CallLabelsDialog.__new__(self.module.CallLabelsDialog)
		d = self.dialog
		d._names = self.module.actionNames()
		d._actions = list(d._names)
		d._index = 0
		d._drafts = {"answer": "Terima lokal", "end-call": "Akhiri lokal"}
		d.custom = Editor("Terima baru")
		d.defaults = Editor()
		d.action = mock.Mock()
		d._allowed = lambda: True
		d.Close = mock.Mock()
		d._onSaved = mock.Mock()
		d._error = mock.Mock()

	def test_switch_retains_unsaved_edits_and_displays_other_action(self):
		d = self.dialog
		d.action.GetSelection.return_value = 7
		with mock.patch.object(self.module.labels, "saveOverrides") as save:
			d._selectAction(None)
			save.assert_not_called()
		self.assertEqual(d._drafts["answer"], "Terima baru")
		self.assertEqual(d.custom.value, "Akhiri lokal")
		self.assertIn("end call", d.defaults.value)

	def test_save_failure_keeps_edits_and_does_not_report_success(self):
		d = self.dialog
		with mock.patch.object(self.module.labels, "saveOverrides", side_effect=OSError):
			d._save(None)
		d.Close.assert_not_called()
		d._onSaved.assert_not_called()
		self.assertEqual(d._drafts["answer"], "Terima baru")
		d._error.assert_called_once()

	def test_validation_identifies_other_action_and_preserves_drafts(self):
		d = self.dialog
		error = self.module.labels.ValidationError("end-call")
		with mock.patch.object(self.module.labels, "saveOverrides", side_effect=error):
			d._save(None)
		self.assertEqual(d._index, 7)
		self.assertEqual(d.custom.value, "Akhiri lokal")
		self.assertIn("End call", d._error.call_args.args[0])
		self.assertEqual(d._drafts["answer"], "Terima baru")
		d.Close.assert_not_called()

	def test_success_saves_all_staged_actions_then_closes(self):
		d = self.dialog
		with mock.patch.object(self.module.labels, "saveOverrides") as save:
			d._save(None)
			save.assert_called_once_with({"answer": "Terima baru", "end-call": "Akhiri lokal"})
		d.Close.assert_called_once()
		d._onSaved.assert_called_once()

	def test_blocked_context_never_saves(self):
		d = self.dialog
		d._allowed = lambda: False
		with mock.patch.object(self.module.labels, "saveOverrides") as save:
			d._save(None)
			save.assert_not_called()
		d._onSaved.assert_not_called()

	def test_reset_is_staged_and_cancel_does_not_save(self):
		d = self.dialog
		message = mock.MagicMock()
		with (
			mock.patch.object(
				self.module,
				"wx",
				types.SimpleNamespace(
					MessageDialog=message,
					OK=1,
					ICON_INFORMATION=2,
				),
			),
			mock.patch.object(self.module.labels, "saveOverrides") as save,
		):
			d._reset(None)
			d.Close()
			save.assert_not_called()
		self.assertEqual(d._drafts, {})
		self.assertEqual(d.custom.value, "")


if __name__ == "__main__":
	unittest.main()
