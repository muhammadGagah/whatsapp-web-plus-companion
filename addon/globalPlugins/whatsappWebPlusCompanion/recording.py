"""Process-isolated recording. No endpoint-wide loopback fallback is permitted."""

import contextlib
import json
import ctypes
import os
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime
from uuid import uuid4

from .packages import findPackage, PowerShellCommand, runPowerShell
from .policy import CHANNELS
from .security import buildSecurityProbe, checkPreflight
from .callAvailability import probeCalls


class CallUnavailable(Exception):
	pass


class FocusChanged(Exception):
	"""The call window lost the foreground before capture could start."""


HELPER = Path(__file__).parent / "resources" / "recording" / "record.ps1"


def helperCommand(request: Path) -> list[str]:
	# Use the Windows-supplied host, not a program resolved from a writable PATH.
	windows = Path(os.environ["SystemRoot"])
	system = "Sysnative" if (windows / "Sysnative").is_dir() else "System32"
	host = windows / system / "WindowsPowerShell/v1.0/powershell.exe"
	return [
		str(host),
		"-NoProfile",
		"-NonInteractive",
		"-Mta",
		# Process scope only: the default client policy (Restricted) otherwise refuses every helper script.
		"-ExecutionPolicy",
		"Bypass",
		"-File",
		str(HELPER),
		"-Request",
		str(request),
	]


def foregroundWindow() -> tuple[int, int]:
	"""Return the foreground window handle and its process ID."""
	user32 = ctypes.windll.user32
	window = int(user32.GetForegroundWindow() or 0)
	processId = ctypes.c_ulong()
	if window:
		user32.GetWindowThreadProcessId(window, ctypes.byref(processId))
	return window, int(processId.value)


def supported() -> bool:
	return sys.platform == "win32" and sys.getwindowsversion().build >= 20348


def writeRequest(folder: str, options: dict) -> Path:
	path = Path(folder) / "request.json"
	path.write_text(json.dumps(options), encoding="utf-8")
	return path


def listMicrophones() -> list[dict[str, str]]:
	if not supported():
		raise RuntimeError("unsupported Windows")
	with tempfile.TemporaryDirectory(prefix="wwp-recording-") as folder:
		request = writeRequest(folder, {"action": "devices"})
		result = subprocess.run(
			helperCommand(request),
			stdin=subprocess.DEVNULL,
			capture_output=True,
			encoding="utf-8",
			timeout=25,
			check=True,
			creationflags=subprocess.CREATE_NO_WINDOW,
		)
		devices = json.loads(result.stdout)
		if not isinstance(devices, list):
			raise RuntimeError("invalid microphone list")
		# One unnamed or malformed endpoint must not hide every other microphone. The dialog labels
		# a device without a friendly name; a device without an ID cannot be opened and is skipped.
		usable = [
			{"id": d["id"], "name": d["name"].strip() if isinstance(d.get("name"), str) else ""}
			for d in devices
			if isinstance(d, dict) and isinstance(d.get("id"), str) and d["id"]
		]
		if not usable:
			raise RuntimeError("no microphones")
		return usable


def _hasAudio(path) -> bool:
	"""A WAV that holds only its 44-byte header is not a partial recording."""
	try:
		return path is not None and path.stat().st_size > 44
	except OSError:
		return False


def packageRootPid(rows: list[dict], root: str) -> int:
	from pathlib import PureWindowsPath

	packagePath = PureWindowsPath(root)
	parents = {int(row["ProcessId"]): int(row.get("ParentProcessId") or 0) for row in rows}
	pids = set()
	for row in rows:
		path = row.get("ExecutablePath")
		if not path:
			continue
		if PureWindowsPath(path).is_relative_to(packagePath):
			pids.add(int(row["ProcessId"]))
	roots = set()
	for pid in pids:
		parent = parents.get(pid, 0)
		seen = {pid}
		while parent and parent not in seen and parent not in pids:
			seen.add(parent)
			parent = parents.get(parent, 0)
		if parent not in pids:
			roots.add(pid)
	if len(roots) != 1 or next(iter(roots)) <= 0:
		raise RuntimeError("ambiguous or missing WhatsApp process")
	return roots.pop()


def recordingTarget(channel) -> tuple[int, str]:
	package = findPackage(CHANNELS[channel])
	if package is None:
		raise RuntimeError("WhatsApp not installed")
	rows = json.loads(
		runPowerShell(
			PowerShellCommand(
				"ConvertTo-Json -InputObject @(Get-CimInstance Win32_Process -ErrorAction Stop "
				"| Select-Object ProcessId,ParentProcessId,ExecutablePath) -Compress",
				"recording.processes",
				20,
			),
		),
	)
	return packageRootPid(rows, package.installLocation), package.installLocation


class Recording:
	"""One recording per plugin instance. All I/O stays off NVDA's GUI thread."""

	def __init__(self, report):
		self.report = report
		self.cancel = threading.Event()
		self.worker = None
		# Set once the helper reports STARTED, so Stop can tell preparation from capture.
		self.captureStarted = False

	@property
	def active(self) -> bool:
		return self.worker is not None and self.worker.is_alive()

	def start(self, channel, microphone: str, directory: str, foreground: int | None = None) -> bool:
		if self.active:
			return False
		self.cancel.clear()
		self.captureStarted = False
		if foreground is None:
			foreground = foregroundWindow()[0]
		self.worker = threading.Thread(
			target=self._run,
			args=(channel, microphone, directory, foreground),
			name="WhatsAppRecording",
			daemon=True,
		)
		self.worker.start()
		return True

	def stop(self) -> None:
		self.cancel.set()

	def _run(self, channel, microphone: str, directory: str, foreground: int = 0) -> None:
		path = None
		try:
			checkPreflight(buildSecurityProbe())
			if not supported():
				raise RuntimeError("unsupported Windows")
			pid, root = recordingTarget(channel)
			if self.cancel.is_set():
				self.report("cancelled", "")
				return
			checkPreflight(buildSecurityProbe())
			folder = Path(directory).expanduser()
			call = probeCalls().get(channel)
			if self.cancel.is_set():
				self.report("cancelled", "")
				return
			if call is None or call.pid != pid:
				raise CallUnavailable()
			folder.mkdir(parents=True, exist_ok=True)
			path = folder / f"WhatsApp-{datetime.now():%Y%m%d-%H%M%S}-{uuid4().hex[:8]}.wav"
			options = {
				"action": "record",
				"pid": pid,
				"root": root,
				"microphone": microphone,
				"output": str(path),
				"parent": os.getpid(),
				"callWindow": call.window,
				"foreground": foreground,
			}
			with tempfile.TemporaryDirectory(prefix="wwp-recording-") as temporary:
				self._capture(writeRequest(temporary, options), path)
		except CallUnavailable:
			# Stop during preparation also makes the call view checks fail. That is a cancellation.
			self.report("cancelled" if self.cancel.is_set() else "unavailable", "")
		except FocusChanged:
			self.report("cancelled" if self.cancel.is_set() else "focus-changed", "")
		except Exception:
			# Error text from a helper or provider may include private paths. Do not log it.
			if self.cancel.is_set() and not self.captureStarted and not _hasAudio(path):
				# Stop or a lock during preparation can make any later step fail. Nothing was recorded.
				self.report("cancelled", "")
			else:
				self.report("failed", str(path) if _hasAudio(path) else "")

	def _capture(self, request: Path, path: Path) -> None:
		process = subprocess.Popen(
			helperCommand(request),
			stdin=subprocess.PIPE,
			stdout=subprocess.PIPE,
			stderr=subprocess.STDOUT,
			text=True,
			encoding="utf-8",
			errors="replace",
			creationflags=subprocess.CREATE_NO_WINDOW,
		)
		messages = queue.Queue(maxsize=32)

		def readOutput():
			try:
				for line in iter(lambda: process.stdout.readline(1024), ""):
					value = line.strip()
					if value in {
						"STARTED",
						"SAVED",
						"CANCELLED",
						"ERROR",
						"CALL_UNAVAILABLE",
						"LIMIT",
						"CALL_ENDED",
						"FOCUS_CHANGED",
					}:
						try:
							messages.put_nowait(value)
						except queue.Full:
							pass
			finally:
				process.stdout.close()

		reader = threading.Thread(target=readOutput, daemon=True)
		reader.start()

		def forwardStop():
			# Pass Stop to the helper at once, not after the next 100 ms poll, so a Stop pressed just
			# before capture starts reaches the helper's last cancellation check.
			while process.poll() is None:
				if self.cancel.wait(0.05):
					with contextlib.suppress(OSError, ValueError):
						process.stdin.write("stop\n")
						process.stdin.flush()
					return

		threading.Thread(target=forwardStop, daemon=True).start()
		started = saved = cancelled = stoppedBeforeStart = False
		ending = "saved"
		deadline = time.monotonic() + 30
		stopDeadline = None
		try:
			while True:
				try:
					message = messages.get(timeout=0.1)
				except queue.Empty:
					message = ""
				if message == "STARTED":
					started = True
					self.captureStarted = True
					if not self.cancel.is_set():
						self.report("started", str(path))
				elif message == "SAVED":
					saved = True
				elif message == "CANCELLED":
					cancelled = True
				elif message == "LIMIT":
					ending = "limit"
				elif message == "CALL_ENDED":
					ending = "call-ended"
				elif message == "ERROR":
					raise RuntimeError("capture failed")
				elif message == "CALL_UNAVAILABLE":
					if not self.cancel.is_set():
						raise CallUnavailable()
					# The helper's call checks fail once Stop arrives during preparation.
					cancelled = stoppedBeforeStart = True
				elif message == "FOCUS_CHANGED":
					if not self.cancel.is_set():
						raise FocusChanged()
					cancelled = stoppedBeforeStart = True
				if self.cancel.is_set() and stopDeadline is None:
					stopDeadline = time.monotonic() + 12
				if process.poll() is not None and not reader.is_alive() and messages.empty():
					if not (saved or cancelled) or (process.returncode != 0 and not stoppedBeforeStart):
						raise RuntimeError("capture incomplete")
					break
				if (not started and time.monotonic() > deadline) or (
					stopDeadline is not None and time.monotonic() > stopDeadline
				):
					raise TimeoutError("recorder")
			self.report("cancelled", "") if cancelled else self.report(ending, str(path))
		finally:
			if process.poll() is None:
				process.kill()
			process.wait(timeout=5)
			# A stop line written after the helper exited stays buffered, so closing reports the same
			# broken pipe. The outcome was already reported; do not turn it into an error.
			with contextlib.suppress(OSError):
				process.stdin.close()
			reader.join(timeout=1)
