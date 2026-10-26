"""Fresh, channel-specific call evidence. Read UIA only in a bounded helper process."""

from dataclasses import dataclass
import json
import subprocess
import tempfile
import threading
import time

from .models import Channel
from .policy import CHANNELS


PROBE_TIMEOUT = 25


@dataclass(frozen=True)
class ConnectedCall:
	channel: Channel
	pid: int
	window: int
	state: str = "connected"


def probeCalls() -> dict[Channel, ConnectedCall]:
	from .recording import helperCommand, writeRequest

	with tempfile.TemporaryDirectory(prefix="wwp-call-state-") as folder:
		request = writeRequest(
			folder,
			{
				"action": "calls",
				"channels": [
					{"channel": channel.value, "family": policy.packageFamily}
					for channel, policy in CHANNELS.items()
				],
			},
		)
		result = subprocess.run(
			helperCommand(request),
			stdin=subprocess.DEVNULL,
			capture_output=True,
			encoding="utf-8",
			# PowerShell start-up, the C# compile and Get-AppxPackage alone can take several seconds.
			timeout=PROBE_TIMEOUT,
			check=True,
			creationflags=subprocess.CREATE_NO_WINDOW,
		)
		rows = json.loads(result.stdout)
		if not isinstance(rows, list):
			raise ValueError("call state")
		calls = {}
		for row in rows:
			channel = Channel(row["channel"])
			if (
				row["state"] in {"connected", "compact"}
				and type(row["pid"]) is int
				and type(row["window"]) is int
			):
				if row["pid"] > 0 and row["window"] != 0:
					calls[channel] = ConnectedCall(channel, row["pid"], row["window"], row["state"])

		return calls


def restoreCallView(pid, window, cancel) -> bool:
	from .recording import helperCommand, writeRequest

	with tempfile.TemporaryDirectory(prefix="wwp-call-restore-") as folder:
		request = writeRequest(
			folder,
			{
				"action": "restore",
				"pid": pid,
				"window": window,
				"channels": [
					{"channel": ch.value, "family": policy.packageFamily} for ch, policy in CHANNELS.items()
				],
			},
		)
		if cancel.is_set():
			return False
		with subprocess.Popen(
			helperCommand(request),
			stdin=subprocess.PIPE,
			stdout=subprocess.PIPE,
			stderr=subprocess.DEVNULL,
			text=True,
			encoding="utf-8",
			creationflags=subprocess.CREATE_NO_WINDOW,
		) as process:
			deadline = time.monotonic() + 12
			while process.poll() is None:
				if cancel.wait(0.05) or time.monotonic() >= deadline:
					try:
						process.stdin.close()
						process.wait(timeout=1)
					except (OSError, subprocess.TimeoutExpired):
						process.kill()
						process.wait()
					return False
			return (
				not cancel.is_set()
				and process.returncode == 0
				and process.stdout.read().strip() == "RESTORED"
			)


class CallAvailability:
	"""Owned by the GUI thread, including completion callbacks dispatched back to it.

	Each probe starts PowerShell, compiles the helper and walks UIA, so passive refreshes from the
	menu and the recording dialog reuse evidence for REFRESH seconds and never overlap. Only a forced
	request (Start) probes at once. A failed probe is unknown, never a definitive "no call".
	"""

	TTL = 40.0
	REFRESH = 15.0

	def __init__(self, dispatch, changed, *, probe=probeCalls, clock=time.monotonic):
		self._dispatch = dispatch
		self._changed = changed
		self._probe = probe
		self._clock = clock
		self._time = float("-inf")
		self._attempt = float("-inf")
		self._calls = {}
		self._generation = 0
		self._pending = False
		self._pendingGeneration = None
		self._restartRequested = False
		self._callbacks = []

	def known(self) -> bool:
		return self._clock() - self._time < self.TTL

	def current(self):
		return dict(self._calls) if self.known() else {}

	def available(self, channel=None):
		"""True or False from unexpired evidence, or None when the call state is unknown."""
		if not self.known():
			return None
		return bool(self._calls) if channel is None else channel in self._calls

	def invalidate(self):
		self._generation += 1
		self._restartRequested = False
		self._calls = {}
		self._time = float("-inf")
		self._attempt = float("-inf")
		callbacks, self._callbacks = self._callbacks, []
		for callback in callbacks:
			callback({})

	def request(self, *, force=False, callback=None):
		"""Callbacks receive the current calls, or None when the probe failed or timed out."""
		if not force and not self._pending and self._clock() - self._attempt < self.REFRESH:
			if callback:
				callback(self.current() if self.known() else None)
			return
		if callback:
			self._callbacks.append(callback)
		if self._pending:
			if self._pendingGeneration != self._generation:
				self._restartRequested = True
			return
		self._pending = True
		generation = self._generation
		self._pendingGeneration = generation

		def work():
			try:
				calls = self._probe()
			except Exception:
				calls = None
			self._dispatch(self._finish, generation, calls)

		threading.Thread(target=work, name="WhatsAppCallState", daemon=True).start()

	def _finish(self, generation, calls):
		self._pending = False
		if generation != self._generation:
			if self._restartRequested:
				self._restartRequested = False
				self.request(force=True)
			return
		self._attempt = self._clock()
		if calls is not None:
			self._calls, self._time = calls, self._attempt
		callbacks, self._callbacks = self._callbacks, []
		self._changed()
		for callback in callbacks:
			callback(None if calls is None else self.current())
