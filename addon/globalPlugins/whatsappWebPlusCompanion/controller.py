import contextlib
import threading
from collections.abc import Callable

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
		self.cancelEvent = CancellationEvent()
		self.state = OperationState.IDLE
		self.lock = threading.RLock()
		self.worker: threading.Thread | None = None
		self.forceCloseWorker: threading.Thread | None = None
		self.repairWorker: threading.Thread | None = None
		self.accepting = True
		self.closers: list[Callable[[], None]] = []
		self.activeReported = False
		self.channel = Channel.STABLE
		self.operationToken = 0
		self.workerToken = 0
		self.invalidatedThrough = 0

	@property
	def forceClosing(self) -> bool:
		with self.lock:
			return self.forceCloseWorker is not None

	@property
	def repairing(self) -> bool:
		with self.lock:
			return self.repairWorker is not None

	def launchTokenIsActive(self, token: int) -> bool:
		with self.lock:
			return self.accepting and token == self.workerToken and token > self.invalidatedThrough

	def _setState(self, state: OperationState, token: int) -> None:
		shouldNotify = False
		with self.lock:
			if not self.accepting or token != self.workerToken or token <= self.invalidatedThrough:
				return
			self.state = state
			if state == OperationState.ATTACHED and not self.activeReported:
				self.activeReported = True
				shouldNotify = True
		if shouldNotify:
			self._notifyLaunch(
				OperationResult(
					True,
					"attached",
					"active",
					{"channel": self.channel.value},
				),
				token,
			)

	def _notifyLaunch(self, result: OperationResult, token: int) -> bool | None:
		if not self.launchTokenIsActive(token):
			return False
		if self.launchNotify is not None:
			return self.launchNotify(result, token)
		return self.notify(result)

	def registerCloser(self, closer: Callable[[], None]) -> Callable[[], None]:
		with self.lock:
			if not self.accepting:
				closer()
				return lambda: None
			self.closers.append(closer)

		def unregister() -> None:
			with self.lock:
				if closer in self.closers:
					self.closers.remove(closer)

		return unregister

	def start(self, channel: Channel) -> bool:
		with self.lock:
			if (
				not self.accepting
				or self.forceCloseWorker is not None
				or (self.repairWorker is not None and self.repairWorker.is_alive())
				or (self.worker is not None and self.worker.is_alive())
			):
				return False
			self.cancelEvent.clear()
			self.activeReported = False
			self.channel = channel
			self.operationToken += 1
			self.workerToken = self.operationToken
			self.state = OperationState.PREPARING_LAUNCH
			self.worker = threading.Thread(
				target=self._run,
				args=(channel, self.workerToken),
				name="WhatsAppWebPlus",
				daemon=True,
			)
			self.worker.start()
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
				or (self.worker is not None and self.worker.is_alive())
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

	def _run(self, channel: Channel, token: int) -> None:
		try:
			result = self.operation(
				channel,
				self.cancelEvent,
				lambda state: self._setState(state, token),
				self.registerCloser,
				lambda result: self._notifyLaunch(result, token),
			)
		except LoaderError as error:
			log.warning(
				"WhatsApp Companion launch failed: code=%s detail=%s",
				error.code,
				error.safeDetail,
			)
			result = OperationResult(False, error.code, error.code, dict(error.values))
		except Exception:
			log.exception("Unexpected WhatsApp Companion launch failure")
			result = OperationResult(False, "internal.error", "internal.error", {})
		with self.lock:
			stopping = not self.accepting
			suppressed = token <= self.invalidatedThrough
			if self.worker is threading.current_thread():
				self.worker = None
			self.state = (
				OperationState.STOPPING
				if stopping or self.forceCloseWorker is not None
				else OperationState.IDLE
			)
		if not stopping and not suppressed and not (result.messageKey == "active" and self.activeReported):
			self._notifyLaunch(result, token)

	def forceClose(self, onComplete: ForceCloseComplete | None = None) -> bool:
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
			self.invalidatedThrough = max(self.invalidatedThrough, self.workerToken)
			self.cancelEvent.set()
			closers = tuple(reversed(self.closers))
			self.closers.clear()
			launchWorker = self.worker
			self.state = OperationState.STOPPING
			self.forceCloseWorker = threading.Thread(
				target=self._runForceClose,
				args=(launchWorker, closers, onComplete),
				name="WhatsAppWebPlusForceClose",
				daemon=True,
			)
			self.forceCloseWorker.start()
		return True

	def _runForceClose(
		self,
		launchWorker: threading.Thread | None,
		closers: tuple[Callable[[], None], ...],
		onComplete: ForceCloseComplete | None,
	) -> None:
		for closer in closers:
			with contextlib.suppress(Exception):
				closer()
		if launchWorker is not None and launchWorker is not threading.current_thread():
			launchWorker.join()
		with self.lock:
			if not self.accepting:
				if self.forceCloseWorker is threading.current_thread():
					self.forceCloseWorker = None
				self.state = OperationState.STOPPING
				return
		try:
			result = (
				self.forceCloseOperation()
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
			self.state = OperationState.STOPPING if not self.accepting else OperationState.IDLE
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
			self.state = OperationState.STOPPING
			closers = tuple(reversed(self.closers))
			self.closers.clear()
		self.cancelEvent.set()
		for closer in closers:
			with contextlib.suppress(Exception):
				closer()
