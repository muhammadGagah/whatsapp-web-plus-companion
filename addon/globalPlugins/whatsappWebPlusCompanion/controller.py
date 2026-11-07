import contextlib
import threading
from collections.abc import Callable
from dataclasses import dataclass, field

try:
	from logHandler import log
except ImportError:
	import logging

	log = logging.getLogger(__name__)

from .models import CancellationEvent, Channel, LoaderError, OperationResult, OperationState

RegisterCloser = Callable[[Callable[[], None]], Callable[[], None]]
LaunchOperation = Callable[
	[
		Channel,
		CancellationEvent,
		Callable[[OperationState], None],
		RegisterCloser,
		Callable[[OperationResult], bool | None],
	],
	OperationResult,
]
ForceCloseOperation = Callable[[], OperationResult]
ForceCloseComplete = Callable[[OperationResult], None]
LaunchNotify = Callable[[OperationResult, int], bool | None]


@dataclass(eq=False)
class _ChannelRun:
	"""One launch worker for one WhatsApp channel. Stable and Beta each have their own."""

	channel: Channel
	token: int
	cancelEvent: CancellationEvent
	worker: threading.Thread | None = None
	state: OperationState = OperationState.PREPARING_LAUNCH
	closers: list[Callable[[], None]] = field(default_factory=list)
	activeReported: bool = False
	replaceRecent: bool = False
	# Set when a force close of this channel cancelled the run; its late results are not reported.
	invalidated: bool = False


class Controller:
	def __init__(
		self,
		operation: LaunchOperation,
		notify: Callable[[OperationResult], bool | None],
		forceCloseOperation: ForceCloseOperation | None = None,
		launchNotify: LaunchNotify | None = None,
	) -> None:
		super().__init__()
		self.operation = operation
		self.notify = notify
		self.forceCloseOperation = forceCloseOperation
		self.launchNotify = launchNotify
		self.lock = threading.RLock()
		self.forceCloseWorker: threading.Thread | None = None
		self.repairWorker: threading.Thread | None = None
		self.accepting = True
		# The latest run of each channel. A finished run stays until the channel starts again,
		# so its final result can still be matched to its token.
		self._runs: dict[Channel, _ChannelRun] = {}
		self.channel = Channel.STABLE
		self.operationToken = 0
		self.invalidatedThrough = 0

	@property
	def worker(self) -> threading.Thread | None:
		"""The most recently started launch worker that has not finished, if any."""
		with self.lock:
			runs = [run for run in self._runs.values() if run.worker is not None]
			return max(runs, key=lambda run: run.token).worker if runs else None

	@property
	def state(self) -> OperationState:
		with self.lock:
			if not self.accepting or self.forceCloseWorker is not None:
				return OperationState.STOPPING
			if not self._runs:
				return OperationState.IDLE
			return max(self._runs.values(), key=lambda run: run.token).state

	@property
	def closers(self) -> list[Callable[[], None]]:
		with self.lock:
			return [closer for run in self._runs.values() for closer in run.closers]

	@property
	def forceClosing(self) -> bool:
		with self.lock:
			return self.forceCloseWorker is not None

	@property
	def repairing(self) -> bool:
		with self.lock:
			return self.repairWorker is not None

	def launching(self) -> bool:
		"""True while any channel is launching or attached."""
		with self.lock:
			return any(self._alive(run) for run in self._runs.values())

	def channelActive(self, channel: Channel) -> bool:
		with self.lock:
			run = self._runs.get(channel)
			return run is not None and self._alive(run)

	def channelState(self, channel: Channel) -> OperationState:
		with self.lock:
			run = self._runs.get(channel)
			return run.state if run is not None and self._alive(run) else OperationState.IDLE

	def activeChannels(self) -> tuple[Channel, ...]:
		with self.lock:
			return tuple(channel for channel in Channel if self.channelActive(channel))

	@staticmethod
	def _alive(run: _ChannelRun) -> bool:
		return run.worker is not None and run.worker.is_alive()

	def _runForToken(self, token: int | None) -> _ChannelRun | None:
		if token is None:
			return None
		for run in self._runs.values():
			if run.token == token:
				return run
		return None

	def channelForToken(self, token: int) -> Channel | None:
		with self.lock:
			run = self._runForToken(token)
			return run.channel if run is not None else None

	def launchTokenIsActive(self, token: int) -> bool:
		with self.lock:
			run = self._runForToken(token)
			return (
				self.accepting and token > self.invalidatedThrough and run is not None and not run.invalidated
			)

	def _setState(self, state: OperationState, token: int) -> None:
		shouldNotify = False
		with self.lock:
			run = self._runForToken(token)
			if not self.accepting or run is None or run.invalidated or token <= self.invalidatedThrough:
				return
			run.state = state
			if state == OperationState.ATTACHED and not run.activeReported:
				run.activeReported = True
				shouldNotify = True
			channel = run.channel
		if shouldNotify:
			self._notifyLaunch(
				OperationResult(
					True,
					"attached",
					"active",
					{"channel": channel.value},
				),
				token,
			)

	def _notifyLaunch(self, result: OperationResult, token: int) -> bool | None:
		if not self.launchTokenIsActive(token):
			return False
		if self.launchNotify is not None:
			return self.launchNotify(result, token)
		return self.notify(result)

	def registerCloser(self, closer: Callable[[], None], token: int | None = None) -> Callable[[], None]:
		with self.lock:
			run = self._runForToken(token)
			if token is None and self._runs:
				run = max(self._runs.values(), key=lambda item: item.token)
			if not self.accepting or run is None or run.cancelEvent.is_set():
				closer()
				return lambda: None
			run.closers.append(closer)

		def unregister() -> None:
			with self.lock:
				if closer in run.closers:
					run.closers.remove(closer)

		return unregister

	def start(self, channel: Channel, *, replaceRecent: bool = False) -> bool:
		"""Start one channel. With ``replaceRecent``, a WhatsApp the user just opened is reopened."""
		with self.lock:
			if (
				not self.accepting
				or self.forceCloseWorker is not None
				or (self.repairWorker is not None and self.repairWorker.is_alive())
				or self.channelActive(channel)
			):
				return False
			self.channel = channel
			self.operationToken += 1
			run = _ChannelRun(channel, self.operationToken, CancellationEvent(), replaceRecent=replaceRecent)
			self._runs[channel] = run
			run.worker = threading.Thread(
				target=self._run,
				args=(run,),
				name="WhatsAppWebPlus" + ("Beta" if channel == Channel.BETA else "Stable"),
				daemon=True,
			)
			run.worker.start()
			return True

	def startRegistryRepair(
		self,
		run: Callable[[], OperationResult],
	) -> bool:
		with self.lock:
			if (
				not self.accepting
				or self.forceCloseWorker is not None
				or (self.repairWorker is not None and self.repairWorker.is_alive())
				or self.launching()
			):
				return False
			self.repairWorker = threading.Thread(
				target=self._runRepair,
				args=(run,),
				name="WhatsAppWebPlusRegistryRepair",
				daemon=True,
			)
			self.repairWorker.start()
			return True

	def _runRepair(self, run: Callable[[], OperationResult]) -> None:
		try:
			result = run()
		except LoaderError as error:
			log.warning(
				"WhatsApp Companion registry repair failed: code=%s detail=%s",
				error.code,
				error.safeDetail,
			)
			result = OperationResult(False, error.code, error.code, dict(error.values))
		except Exception:
			log.exception("Unexpected WhatsApp Companion registry repair failure")
			result = OperationResult(False, "internal.error", "internal.error", {})
		with self.lock:
			stopping = not self.accepting
			if self.repairWorker is threading.current_thread():
				self.repairWorker = None
		if not stopping:
			self.notify(result)

	def _run(self, run: _ChannelRun) -> None:
		token = run.token
		channel = run.channel
		options = {"replaceRecentInstance": True} if run.replaceRecent else {}
		try:
			result = self.operation(
				channel,
				run.cancelEvent,
				lambda state: self._setState(state, token),
				lambda closer: self.registerCloser(closer, token),
				lambda result: self._notifyLaunch(result, token),
				**options,
			)
		except LoaderError as error:
			log.warning(
				"WhatsApp Companion launch failed: channel=%s code=%s detail=%s",
				channel.value,
				error.code,
				error.safeDetail,
			)
			result = OperationResult(False, error.code, error.code, dict(error.values))
		except Exception:
			log.exception("Unexpected WhatsApp Companion launch failure")
			result = OperationResult(False, "internal.error", "internal.error", {})
		with self.lock:
			stopping = not self.accepting
			suppressed = token <= self.invalidatedThrough or run.invalidated
			if run.worker is threading.current_thread():
				run.worker = None
			run.state = (
				OperationState.STOPPING
				if stopping or self.forceCloseWorker is not None
				else OperationState.IDLE
			)
			activeReported = run.activeReported
		if not stopping and not suppressed and not (result.messageKey == "active" and activeReported):
			self._notifyLaunch(result, token)

	def forceClose(
		self,
		onComplete: ForceCloseComplete | None = None,
		*,
		channels: tuple[Channel, ...] | None = None,
	) -> bool:
		"""Force close the selected channels, or every channel when ``channels`` is None."""
		operation = self.forceCloseOperation
		if operation is None:
			return False
		with self.lock:
			if (
				not self.accepting
				or self.forceCloseWorker is not None
				or (self.repairWorker is not None and self.repairWorker.is_alive())
			):
				return False
			if channels is None:
				self.invalidatedThrough = max(self.invalidatedThrough, self.operationToken)
			closers: list[Callable[[], None]] = []
			launchWorkers: list[threading.Thread] = []
			for run in self._runs.values():
				if channels is not None and run.channel not in channels:
					continue
				run.invalidated = True
				run.cancelEvent.set()
				closers.extend(reversed(run.closers))
				run.closers.clear()
				run.state = OperationState.STOPPING
				if run.worker is not None:
					launchWorkers.append(run.worker)
			self.forceCloseWorker = threading.Thread(
				target=self._runForceClose,
				args=(tuple(launchWorkers), tuple(closers), onComplete, channels),
				name="WhatsAppWebPlusForceClose",
				daemon=True,
			)
			self.forceCloseWorker.start()
		return True

	def _runForceClose(
		self,
		launchWorkers: tuple[threading.Thread, ...],
		closers: tuple[Callable[[], None], ...],
		onComplete: ForceCloseComplete | None,
		channels: tuple[Channel, ...] | None = None,
	) -> None:
		for closer in closers:
			with contextlib.suppress(Exception):
				closer()
		for launchWorker in launchWorkers:
			if launchWorker is threading.current_thread():
				continue
			launchWorker.join(timeout=5.0)
			if launchWorker.is_alive():
				# Do not kill the app or start another Registry lease while cleanup still owns it.
				with self.lock:
					self.forceCloseWorker = None
					accepting = self.accepting
				if accepting:
					result = OperationResult(False, "registry.busy", "registry.busy", {})
					self.notify(result)
					if onComplete is not None:
						try:
							onComplete(result)
						except Exception:
							log.exception("Unexpected WhatsApp Companion force-close completion failure")
				return
		with self.lock:
			if not self.accepting:
				if self.forceCloseWorker is threading.current_thread():
					self.forceCloseWorker = None
				return
		try:
			result = (
				(
					self.forceCloseOperation()
					if channels is None
					else self.forceCloseOperation(channels=channels)
				)
				if self.forceCloseOperation is not None
				else OperationResult(
					False,
					"processes.failed",
					"processes.failed",
					{},
				)
			)
		except LoaderError as error:
			log.warning(
				"WhatsApp Companion force close failed: code=%s detail=%s",
				error.code,
				error.safeDetail,
			)
			messageKey = "processes.context" if error.code.startswith("security.") else "processes.failed"
			result = OperationResult(False, error.code, messageKey, dict(error.values))
		except Exception:
			log.exception("Unexpected WhatsApp Companion force close failure")
			result = OperationResult(False, "internal.error", "processes.failed", {})
		with self.lock:
			stopping = not self.accepting
			if self.forceCloseWorker is threading.current_thread():
				self.forceCloseWorker = None
			if not stopping:
				for run in self._runs.values():
					if run.worker is None and run.state == OperationState.STOPPING:
						run.state = OperationState.IDLE
		if not stopping:
			self.notify(result)
			if onComplete is not None:
				try:
					onComplete(result)
				except Exception:
					log.exception("Unexpected WhatsApp Companion force-close completion failure")

	def stop(self) -> None:
		with self.lock:
			self.accepting = False
			closers: list[Callable[[], None]] = []
			runs = tuple(self._runs.values())
			for run in runs:
				run.state = OperationState.STOPPING
				closers.extend(reversed(run.closers))
				run.closers.clear()
		for run in runs:
			run.cancelEvent.set()
		for closer in closers:
			with contextlib.suppress(Exception):
				closer()
