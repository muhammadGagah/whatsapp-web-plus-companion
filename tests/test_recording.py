import importlib
import io
from pathlib import Path
import tempfile
import threading
import sys
import types
import unittest
from unittest import mock

from _path import installPackagePath

installPackagePath()

from globalPlugins.whatsappWebPlusCompanion import recording


class RecordingTests(unittest.TestCase):
	def test_no_call_never_creates_output_or_launches_capture(self):
		report = mock.Mock()
		recorder = recording.Recording(report)
		with (
			mock.patch.object(recording, "checkPreflight"),
			mock.patch.object(recording, "buildSecurityProbe"),
			mock.patch.object(recording, "supported", return_value=True),
			mock.patch.object(recording, "recordingTarget", return_value=(10, "root")),
			mock.patch.object(recording, "probeCalls", return_value={}),
			mock.patch.object(Path, "mkdir") as mkdir,
			mock.patch.object(recorder, "_capture") as capture,
		):
			recorder._run(None, "mic", "unused")
		capture.assert_not_called()
		mkdir.assert_not_called()
		report.assert_called_once_with("unavailable", "")

	def test_stop_command_finishes_helper_and_reports_saved(self):
		started = threading.Event()
		reports = []

		def report(state, path):
			reports.append(state)
			if state == "started":
				started.set()

		recorder = recording.Recording(report)
		command = [
			sys.executable,
			"-u",
			"-c",
			"print('STARTED', flush=True); input(); print('SAVED', flush=True)",
		]
		with mock.patch.object(recording, "helperCommand", return_value=command):
			worker = threading.Thread(target=recorder._capture, args=(Path("request"), Path("record.wav")))
			worker.start()
			try:
				self.assertTrue(started.wait(3))
			finally:
				recorder.stop()
				worker.join(5)
		self.assertFalse(worker.is_alive())
		self.assertEqual(reports, ["started", "saved"])

	def test_target_is_verified_package_root_not_unrelated_audio_process(self):
		rows = [
			{"ProcessId": 10, "ParentProcessId": 1, "ExecutablePath": r"C:\Apps\WhatsApp\WhatsApp.exe"},
			{"ProcessId": 11, "ParentProcessId": 10, "ExecutablePath": r"C:\Apps\WhatsApp\helper.exe"},
			{"ProcessId": 12, "ParentProcessId": 11, "ExecutablePath": r"C:\WebView\msedgewebview2.exe"},
			{"ProcessId": 20, "ParentProcessId": 1, "ExecutablePath": r"C:\NVDA\nvda.exe"},
			{"ProcessId": 30, "ParentProcessId": 1, "ExecutablePath": r"C:\Apps\WhatsAppOther\app.exe"},
		]
		self.assertEqual(recording.packageRootPid(rows, r"C:\Apps\WhatsApp"), 10)
		with self.assertRaises(RuntimeError):
			recording.packageRootPid(rows, r"C:\Missing")
		rows.append({"ProcessId": 40, "ParentProcessId": 1, "ExecutablePath": r"C:\Apps\WhatsApp\second.exe"})
		with self.assertRaises(RuntimeError):
			recording.packageRootPid(rows, r"C:\Apps\WhatsApp")

	def test_cancelled_preparation_never_launches_capture(self):
		report = mock.Mock()
		recorder = recording.Recording(report)
		recorder.stop()
		with (
			mock.patch.object(recording, "checkPreflight"),
			mock.patch.object(recording, "buildSecurityProbe"),
			mock.patch.object(recording, "supported", return_value=True),
			mock.patch.object(recording, "recordingTarget", return_value=(10, "root")),
			mock.patch.object(recorder, "_capture") as capture,
		):
			recorder._run(None, "mic", "unused")
		capture.assert_not_called()
		report.assert_called_once_with("cancelled", "")

	def test_security_failure_does_not_discover_or_capture(self):
		report = mock.Mock()
		recorder = recording.Recording(report)
		with (
			mock.patch.object(recording, "checkPreflight", side_effect=RuntimeError),
			mock.patch.object(recording, "buildSecurityProbe"),
			mock.patch.object(recording, "recordingTarget") as target,
		):
			recorder._run(None, "mic", "unused")
		target.assert_not_called()
		report.assert_called_once_with("failed", "")

	def test_existing_recording_cannot_be_started_twice(self):
		recorder = recording.Recording(mock.Mock())
		recorder.worker = mock.Mock()
		recorder.worker.is_alive.return_value = True
		self.assertFalse(recorder.start(None, "mic", "unused"))

	def test_success_requires_final_save_acknowledgment(self):
		for output, expected in (("STARTED\nSAVED\n", True), ("STARTED\n", False), ("ERROR\n", False)):
			with self.subTest(output=output):
				report = mock.Mock()
				recorder = recording.Recording(report)
				process = mock.Mock()
				process.stdout = io.StringIO(output)
				process.stdin = io.StringIO()
				process.poll.return_value = 0
				process.returncode = 0
				with mock.patch.object(recording.subprocess, "Popen", return_value=process):
					if expected:
						recorder._capture(Path("request"), Path("record.wav"))
						self.assertEqual(report.call_args, mock.call("saved", "record.wav"))
					else:
						with self.assertRaises(RuntimeError):
							recorder._capture(Path("request"), Path("record.wav"))

	def test_worker_is_nonblocking_and_reports_failure(self):
		report = mock.Mock()
		recorder = recording.Recording(report)
		entered = threading.Event()
		release = threading.Event()

		def target(channel):
			entered.set()
			release.wait(2)
			raise RuntimeError("missing target")

		with (
			mock.patch.object(recording, "checkPreflight"),
			mock.patch.object(recording, "buildSecurityProbe"),
			mock.patch.object(recording, "supported", return_value=True),
			mock.patch.object(recording, "recordingTarget", side_effect=target),
			tempfile.TemporaryDirectory() as folder,
		):
			self.assertTrue(recorder.start(None, "mic", folder))
			self.assertTrue(entered.wait(1))
			self.assertTrue(recorder.active)
			release.set()
			recorder.worker.join(2)
		self.assertFalse(recorder.active)
		report.assert_called_once_with("failed", "")

	def test_helper_bypasses_execution_policy_for_its_own_process_only(self):
		with mock.patch.dict(recording.os.environ, {"SystemRoot": r"C:\Windows"}):
			command = recording.helperCommand(Path("request.json"))
		self.assertTrue(command[0].casefold().endswith("powershell.exe"))
		self.assertIn("-ExecutionPolicy", command)
		self.assertEqual(command[command.index("-ExecutionPolicy") + 1], "Bypass")
		# PowerShell treats everything after -File as script arguments.
		self.assertLess(command.index("-ExecutionPolicy"), command.index("-File"))
		self.assertNotIn("Scope", " ".join(command))

	def capture(self, output, *, cancel=False, returncode=0):
		report = mock.Mock()
		recorder = recording.Recording(report)
		if cancel:
			recorder.stop()
		process = mock.Mock()
		process.stdout = io.StringIO(output)
		process.stdin = io.StringIO()
		process.poll.return_value = returncode
		process.returncode = returncode
		with mock.patch.object(recording.subprocess, "Popen", return_value=process):
			recorder._capture(Path("request"), Path("record.wav"))
		return report

	def test_stop_during_preparation_is_cancelled_not_no_call(self):
		report = self.capture("CALL_UNAVAILABLE\n", cancel=True, returncode=1)
		report.assert_called_once_with("cancelled", "")
		with self.assertRaises(recording.CallUnavailable):
			self.capture("CALL_UNAVAILABLE\n", returncode=1)

	def test_run_reports_cancelled_when_stop_races_call_checks(self):
		for raceInProbe in (False, True):
			with self.subTest(raceInProbe=raceInProbe):
				report = mock.Mock()
				recorder = recording.Recording(report)

				def probe():
					if raceInProbe:
						recorder.stop()
					return {}

				def capture(request, path):
					recorder.stop()
					raise recording.CallUnavailable()

				with (
					mock.patch.object(recording, "checkPreflight"),
					mock.patch.object(recording, "buildSecurityProbe"),
					mock.patch.object(recording, "supported", return_value=True),
					mock.patch.object(recording, "recordingTarget", return_value=(10, "root")),
					mock.patch.object(
						recording,
						"probeCalls",
						side_effect=probe if raceInProbe else lambda: {None: mock.Mock(pid=10, window=1)},
					),
					mock.patch.object(Path, "mkdir"),
					mock.patch.object(recorder, "_capture", side_effect=capture) as captured,
					tempfile.TemporaryDirectory() as folder,
				):
					recorder._run(None, "mic", folder)
				self.assertEqual(captured.called, not raceInProbe)
				report.assert_called_once_with("cancelled", "")

	def test_focus_change_is_reported_separately_unless_stopped(self):
		with self.assertRaises(recording.FocusChanged):
			self.capture("FOCUS_CHANGED\n", returncode=1)
		report = self.capture("FOCUS_CHANGED\n", cancel=True, returncode=1)
		report.assert_called_once_with("cancelled", "")

	def run_with_capture(self, capture, *, cancel=False):
		report = mock.Mock()
		recorder = recording.Recording(report)
		if cancel:
			recorder.stop()
		with (
			mock.patch.object(recording, "checkPreflight"),
			mock.patch.object(recording, "buildSecurityProbe"),
			mock.patch.object(recording, "supported", return_value=True),
			mock.patch.object(recording, "recordingTarget", return_value=(10, "root")),
			mock.patch.object(recording, "probeCalls", return_value={None: mock.Mock(pid=10, window=1)}),
			mock.patch.object(recorder, "_capture", side_effect=capture),
			tempfile.TemporaryDirectory() as folder,
		):
			recorder._run(None, "mic", folder)
		return report, recorder

	def test_run_maps_focus_change_to_its_own_state(self):
		def capture(request, path):
			raise recording.FocusChanged()

		report, _recorder = self.run_with_capture(capture)
		report.assert_called_once_with("focus-changed", "")

	def test_any_failure_after_stop_during_preparation_is_a_cancellation(self):
		for error in (RuntimeError("capture failed"), TimeoutError("recorder")):
			with self.subTest(error=type(error).__name__):
				recorderRef = []

				def capture(request, path, error=error):
					recorderRef[0].stop()
					raise error

				report = mock.Mock()
				recorder = recording.Recording(report)
				recorderRef.append(recorder)
				with (
					mock.patch.object(recording, "checkPreflight"),
					mock.patch.object(recording, "buildSecurityProbe"),
					mock.patch.object(recording, "supported", return_value=True),
					mock.patch.object(recording, "recordingTarget", return_value=(10, "root")),
					mock.patch.object(
						recording,
						"probeCalls",
						return_value={None: mock.Mock(pid=10, window=1)},
					),
					mock.patch.object(recorder, "_capture", side_effect=capture),
					tempfile.TemporaryDirectory() as folder,
				):
					recorder._run(None, "mic", folder)
				report.assert_called_once_with("cancelled", "")

	def test_failure_after_capture_started_is_still_an_error(self):
		recorderRef = []

		def capture(request, path):
			recorderRef[0].captureStarted = True
			recorderRef[0].stop()
			raise RuntimeError("capture failed")

		report = mock.Mock()
		recorder = recording.Recording(report)
		recorderRef.append(recorder)
		with (
			mock.patch.object(recording, "checkPreflight"),
			mock.patch.object(recording, "buildSecurityProbe"),
			mock.patch.object(recording, "supported", return_value=True),
			mock.patch.object(recording, "recordingTarget", return_value=(10, "root")),
			mock.patch.object(recording, "probeCalls", return_value={None: mock.Mock(pid=10, window=1)}),
			mock.patch.object(recorder, "_capture", side_effect=capture),
			tempfile.TemporaryDirectory() as folder,
		):
			recorder._run(None, "mic", folder)
		report.assert_called_once_with("failed", "")

	def test_started_marker_records_capture_start(self):
		report = mock.Mock()
		recorder = recording.Recording(report)
		process = mock.Mock()
		process.stdout = io.StringIO("STARTED\nSAVED\n")
		process.stdin = io.StringIO()
		process.poll.return_value = 0
		process.returncode = 0
		with mock.patch.object(recording.subprocess, "Popen", return_value=process):
			recorder._capture(Path("request"), Path("record.wav"))
		self.assertTrue(recorder.captureStarted)

	def test_stop_after_the_helper_already_exited_reports_once(self):
		realPopen = recording.subprocess.Popen

		def exitedPopen(*args, **kwargs):
			process = realPopen(*args, **kwargs)
			process.wait()  # the helper stopped by itself before the worker loop sees Stop
			return process

		reports = []
		recorder = recording.Recording(lambda state, path: reports.append(state))
		recorder.cancel.set()
		command = [sys.executable, "-c", "print('STARTED'); print('CALL_ENDED'); print('SAVED')"]
		with (
			mock.patch.object(recording, "helperCommand", return_value=command),
			mock.patch.object(recording.subprocess, "Popen", side_effect=exitedPopen),
		):
			recorder._capture(Path("request.json"), Path("record.wav"))
		self.assertEqual(reports, ["call-ended"])

	def test_limit_and_call_end_are_clean_saved_states(self):
		for marker, state in (("LIMIT", "limit"), ("CALL_ENDED", "call-ended")):
			with self.subTest(marker=marker):
				report = self.capture(f"STARTED\n{marker}\nSAVED\n")
				self.assertEqual(report.call_args, mock.call(state, "record.wav"))

	def test_failure_mentions_partial_file_only_when_audio_was_written(self):
		for size, expected in ((None, False), (0, False), (44, False), (48, True)):
			with self.subTest(size=size), tempfile.TemporaryDirectory() as folder:
				report = mock.Mock()
				recorder = recording.Recording(report)
				written = []

				def capture(request, path):
					written.append(path)
					if size is not None:
						path.write_bytes(b"\0" * size)
					raise RuntimeError("capture failed")

				with (
					mock.patch.object(recording, "checkPreflight"),
					mock.patch.object(recording, "buildSecurityProbe"),
					mock.patch.object(recording, "supported", return_value=True),
					mock.patch.object(recording, "recordingTarget", return_value=(10, "root")),
					mock.patch.object(
						recording,
						"probeCalls",
						return_value={None: mock.Mock(pid=10, window=1)},
					),
					mock.patch.object(recorder, "_capture", side_effect=capture),
				):
					recorder._run(None, "mic", folder)
				report.assert_called_once_with("failed", str(written[0]) if expected else "")

	def test_unnamed_or_invalid_microphone_does_not_hide_other_devices(self):
		devices = [
			{"id": "{0.0.1}.a", "name": "Headset"},
			{"id": "{0.0.1}.b", "name": None},
			{"id": "", "name": "No id"},
			{"name": "Missing id"},
			"garbage",
		]
		result = types.SimpleNamespace(stdout=recording.json.dumps(devices))
		with (
			mock.patch.object(recording, "supported", return_value=True),
			mock.patch.object(recording, "helperCommand", return_value=["helper"]),
			mock.patch.object(recording.subprocess, "run", return_value=result),
		):
			self.assertEqual(
				recording.listMicrophones(),
				[{"id": "{0.0.1}.a", "name": "Headset"}, {"id": "{0.0.1}.b", "name": ""}],
			)
			result.stdout = recording.json.dumps([{"id": "", "name": "x"}])
			with self.assertRaises(RuntimeError):
				recording.listMicrophones()

	def test_dialog_labels_unnamed_microphones_and_translates_channels(self):
		fakeModules = {
			"wx": types.SimpleNamespace(Dialog=object),
			"addonHandler": types.SimpleNamespace(initTranslation=lambda: None),
		}
		with (
			mock.patch.dict(sys.modules, fakeModules),
			mock.patch("builtins._", lambda text: "T:" + text, create=True),
		):
			sys.modules.pop("globalPlugins.whatsappWebPlusCompanion.recordingDialog", None)
			dialog = importlib.import_module("globalPlugins.whatsappWebPlusCompanion.recordingDialog")
			labels = dialog.microphoneLabels([{"id": "a", "name": "Headset"}, {"id": "b", "name": ""}])
			sys.modules.pop("globalPlugins.whatsappWebPlusCompanion.recordingDialog", None)
		self.assertEqual(labels, ["Headset", "T:Unnamed microphone 2"])
		source = Path(dialog.__file__).read_text(encoding="utf-8")
		self.assertIn('choices=[_("Stable"), _("Beta")]', source)


if __name__ == "__main__":
	unittest.main()
