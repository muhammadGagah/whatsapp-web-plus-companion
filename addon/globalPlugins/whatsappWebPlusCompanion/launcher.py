import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, replace

try:
	from logHandler import log
except ImportError:
	import logging

	log = logging.getLogger(__name__)

from .activation import activateAumid, reserveLoopbackPort, waitForEndpoint
from .bundle import quarantineUpdatedBundle, selectEmbeddedBundle
from .cdp import (
	CdpSession,
	Target,
	installAndVerify,
	readCompanionAnnouncements,
	reconnect,
	selectTarget,
)
from .http import endpointResponds, httpGetJson
from .ioDeadline import Deadline
from .models import Channel, LoaderError, OperationResult, OperationState
from .packages import findRunningPackageProcesses, resolvePackage, runPowerShellCancellable
from .policy import BUNDLE_HEALTH_DEADLINE, CHANNELS, CONNECT_DEADLINE, TARGET_DEADLINE, RECONNECT_DEADLINE
from .processes import collectProcessTopology, validateListener, captureEndpointIdentity
from .registry import (
	RegistryLease,
	WinRegistry,
	releaseRegistryMutex,
	recoverPendingRegistryState,
)
from .registryJournal import JournalError, RegistryJournal, newOperationId
from .registryRepair import tryAcquireRegistryMutex
from .security import buildSecurityProbe, checkPreflight, AnnouncementGuard
from .websocket import WebSocket

StateCallback = Callable[[OperationState], None]
GateCallback = Callable[[str], None]
RegisterCloser = Callable[[Callable[[], None]], Callable[[], None]]
ReportCallback = Callable[[OperationResult], bool | None]

_ANNOUNCEMENT_POLL_INTERVAL = 0.1
_TARGET_HEALTH_INTERVAL = 1.0

_TRANSIENT_INITIAL_ATTACH_ERRORS = frozenset(
	{
		"cdp.context",
		"websocket.closed",
		"websocket.handshake",
		"websocket.receive",
		"websocket.send",
	},
)

_UPDATED_BUNDLE_HEALTH_ERRORS = frozenset(
	{
		"bundle.failed",
		"bundle.healthMismatch",
		"bundle.healthTimeout",
	},
)


@dataclass(slots=True)
class _AnnouncementState:
	sessionToken: str = ""
	generation: int = 0
	context: str = ""
	lastAcknowledgedSequence: int = 0
	securityEpoch: int | None = None
	suppressed: bool = False


def _raiseBundleInstallError(bundle: object, error: LoaderError) -> None:
	if getattr(bundle, "isUpdate", False) and error.code in _UPDATED_BUNDLE_HEALTH_ERRORS:
		digest = getattr(bundle, "sha256", "")
		quarantined = quarantineUpdatedBundle(digest)
		log.warning(
			"WhatsApp Companion update health failure: code=%s quarantined=%s",
			error.code,
			quarantined,
		)
		if quarantined:
			raise LoaderError("bundle.updateQuarantined", error.code) from error
	raise error


def _reportDelivered(reportObserver: ReportCallback, result: OperationResult) -> bool:
	try:
		return reportObserver(result) is True
	except Exception:
		return False


def _forwardCompanionAnnouncements(
	session: CdpSession,
	state: _AnnouncementState,
	reportObserver: ReportCallback,
	announcementGuard: AnnouncementGuard | None = None,
) -> None:
	epoch = None
	if announcementGuard is not None:
		allowed, epoch = announcementGuard.snapshot()
		if not allowed:
			state.suppressed = True
			return
		if state.securityEpoch is not None and state.securityEpoch != epoch:
			state.suppressed = True
		state.securityEpoch = epoch
		originalObserver = reportObserver

		def guardedReport(result):
			if not announcementGuard.permits(epoch):
				state.suppressed = True
				return True
			return originalObserver(replace(result, values={**result.values, "securityEpoch": epoch}))

		reportObserver = guardedReport
	batch = readCompanionAnnouncements(
		session,
		state.lastAcknowledgedSequence,
		state.generation,
	)
	if announcementGuard is not None and not announcementGuard.permits(epoch):
		state.suppressed = True
		return
	if state.suppressed:
		# Do not replay content accumulated while locked, including a new renderer.
		if not _reportDelivered(
			reportObserver,
			OperationResult(
				True,
				"companion.invalidate",
				"companion.invalidate",
				{
					"session": batch.sessionToken,
					"generation": batch.generation,
					"context": batch.context,
					"reason": "security-resumed",
					"source": "",
				},
			),
		):
			return
		state.sessionToken = batch.sessionToken
		state.generation = batch.generation
		state.context = batch.context
		state.lastAcknowledgedSequence = batch.latestSequence
		state.suppressed = False
		return
	sessionChanged = bool(state.sessionToken) and batch.sessionToken != state.sessionToken
	if sessionChanged:
		# The first read used the previous renderer's cursor. Sequence numbers
		# restart in a replacement renderer, so read again from zero before any
		# entry can be filtered or acknowledged under the new session identity.
		batch = readCompanionAnnouncements(session, 0, 0)
		sessionChanged = batch.sessionToken != state.sessionToken
	contextChanged = (
		not state.sessionToken
		or sessionChanged
		or batch.invalidated
		or batch.generation != state.generation
		or batch.context != state.context
	)
	if contextChanged:
		if not _reportDelivered(
			reportObserver,
			OperationResult(
				True,
				"companion.invalidate",
				"companion.invalidate",
				{
					"session": batch.sessionToken,
					"generation": batch.generation,
					"context": batch.context,
					"reason": "session-changed" if sessionChanged else batch.lastInvalidation,
					"source": batch.invalidatedSource,
				},
			),
		):
			return
		if sessionChanged:
			state.lastAcknowledgedSequence = 0
		state.sessionToken = batch.sessionToken
		state.generation = batch.generation
		state.context = batch.context
	if batch.overflowed and not _reportDelivered(
		reportObserver,
		OperationResult(
			False,
			"companion.overflow",
			"companion.overflow",
			{
				"session": batch.sessionToken,
				"generation": batch.generation,
				"context": batch.context,
			},
		),
	):
		return
	for announcement in batch.entries:
		messageKey = "companion.reader" if announcement.reader is not None else "companion.announcement"
		if not _reportDelivered(
			reportObserver,
			OperationResult(
				True,
				messageKey,
				messageKey,
				{
					"sequence": announcement.sequence,
					"session": announcement.sessionToken,
					"generation": announcement.generation,
					"context": announcement.context,
					"source": announcement.source,
					"language": announcement.language,
					"privacy": announcement.privacy,
					"text": announcement.text,
					**(
						{
							"reader": announcement.reader,
							"readerProcessIds": getattr(session, "readerProcessIds", ()),
							"readerExpiresAt": announcement.readerExpiresAt,
						}
						if announcement.reader is not None
						else {}
					),
				},
			),
		):
			return
		state.lastAcknowledgedSequence = announcement.sequence
	# Entries omitted by the bridge/parser have either been invalidated or
	# intentionally rejected. Advance past them only after every report above
	# succeeded, otherwise an invalidated tail can trigger overflow forever.
	state.lastAcknowledgedSequence = max(state.lastAcknowledgedSequence, batch.latestSequence)


def _noopUnregister() -> None:
	return


def _noopRegister(closer: Callable[[], None]) -> Callable[[], None]:
	return _noopUnregister


def _noopReport(result: OperationResult) -> None:
	return


@dataclass(frozen=True)
class _OperationIO:
	cancelEvent: object
	registerCloser: RegisterCloser
	end: float

	def remaining(self):
		try:
			return Deadline(self.end, self.cancelEvent).remaining()
		except TimeoutError as error:
			raise LoaderError("operation.timeout") from error

	def child(self, seconds):
		return replace(self, end=min(self.end, time.monotonic() + seconds))

	def runner(self, script):
		self.remaining()
		return runPowerShellCancellable(script, self.cancelEvent, deadline=self.end)

	def httpOptions(self):
		self.remaining()
		return {"cancelEvent": self.cancelEvent, "registerCloser": self.registerCloser, "deadline": self.end}


def _endpointValidator(port, package, io):
	def validate(*, deadline=None, clientPort=None):
		operation = replace(io, end=min(io.end, deadline)) if deadline is not None else io
		return captureEndpointIdentity(port, package, runner=operation.runner, clientPort=clientPort)

	return validate


def _discoverTarget(port: int, *, io: _OperationIO | None = None, validator=None) -> Target:
	identity = validator(deadline=io.end if io is not None else None) if validator is not None else None
	opts = io.httpOptions() if io is not None else {}
	target = selectTarget(
		httpGetJson(port, "/json/version", **opts),
		httpGetJson(port, "/json/list", **opts),
		port,
	)
	if io is not None:
		io.remaining()
	return replace(target, endpointIdentity=identity) if identity is not None else target


def _waitForTarget(port: int, cancelEvent: threading.Event, *, io=None, validator=None) -> Target:
	io = (io or _OperationIO(cancelEvent, _noopRegister, time.monotonic() + TARGET_DEADLINE)).child(
		TARGET_DEADLINE,
	)
	lastError = None
	while time.monotonic() < io.end:
		io.remaining()
		try:
			return _discoverTarget(port, io=io, validator=validator)
		except LoaderError as error:
			if error.code == "operation.cancelled":
				raise
			lastError = error
		if cancelEvent.wait(min(0.25, max(0, io.end - time.monotonic()))):
			raise LoaderError("operation.cancelled")
	raise LoaderError("target.timeout", lastError.code if lastError else "noTarget")


def _waitForPackageProcesses(package, cancelEvent: threading.Event, *, io=None) -> set[int]:
	io = (io or _OperationIO(cancelEvent, _noopRegister, time.monotonic() + TARGET_DEADLINE)).child(
		TARGET_DEADLINE,
	)
	while time.monotonic() < io.end:
		io.remaining()
		pids = set(findRunningPackageProcesses(package, runner=io.runner))
		if pids:
			return pids
		if cancelEvent.wait(min(0.25, max(0, io.end - time.monotonic()))):
			raise LoaderError("operation.cancelled")
	raise LoaderError("package.processTimeout")


def _waitForValidatedListener(
	port: int,
	packagePids: set[int],
	cancelEvent: threading.Event,
	*,
	io=None,
) -> int:
	io = (io or _OperationIO(cancelEvent, _noopRegister, time.monotonic() + TARGET_DEADLINE)).child(
		TARGET_DEADLINE,
	)
	lastError = None
	while time.monotonic() < io.end:
		io.remaining()
		listeners, parents = collectProcessTopology(port, runner=io.runner)
		try:
			return validateListener(port, listeners, parents, packagePids)
		except LoaderError as error:
			if not error.code.startswith("listener."):
				raise
			lastError = error
		if cancelEvent.wait(min(0.25, max(0, io.end - time.monotonic()))):
			raise LoaderError("operation.cancelled")
	raise LoaderError("listener.timeout", lastError.code if lastError else "noListener")


def _recoverPendingRegistryState() -> None:
	"""Resolve a journal from an interrupted launch before applying a new lease."""
	registry = WinRegistry()
	journal = RegistryJournal.createDefault()
	try:
		if journal.load() is None:
			return
	except JournalError as error:
		raise LoaderError(
			"registry.recovery.unreadable",
			f"stage=recovery.load;code={error.code}",
		) from error
	handle = tryAcquireRegistryMutex()
	if handle is None:
		raise LoaderError("registry.mutex.busy", "stage=recovery.mutex")
	try:
		code, detail = recoverPendingRegistryState(registry, journal)
		log.info("WhatsApp Companion registry recovery: code=%s detail=%s", code, detail)
	finally:
		releaseRegistryMutex(handle)


def _connectAndInstall(
	target: Target,
	source: str,
	bundleVersion: str,
	bundleHash: str,
	cancelEvent: threading.Event,
	registerCloser: RegisterCloser = _noopRegister,
	*,
	deadline: float | None = None,
	validator=None,
) -> tuple[CdpSession, dict, Callable[[], None]]:
	budget = Deadline.after(45.0, cancelEvent, deadline)
	try:
		budget.remaining()
	except TimeoutError as error:
		raise LoaderError("cdp.timeout", "attach") from error
	identity = validator(deadline=budget.end) if validator is not None else None
	if validator is not None and target.endpointIdentity != identity:
		raise LoaderError("listener.changed", "beforeConnect")
	webSocket = WebSocket.connect(
		target.webSocketUrl,
		CONNECT_DEADLINE,
		cancelEvent=cancelEvent,
		registerCloser=registerCloser,
		deadline=budget.end,
	)
	session = CdpSession(webSocket)
	session.readerProcessIds = tuple(row[0] for row in getattr(identity, "ancestry", ()))
	session.cancelEvent = cancelEvent
	session.absoluteDeadline = budget.end
	unregisterSession = registerCloser(session.interrupt)
	# Hand over the temporary raw-socket closer only after the session is registered.
	webSocket._unregister()
	webSocket._unregister = _noopUnregister
	try:
		budget.remaining()
		if (
			validator is not None
			and validator(deadline=budget.end, clientPort=webSocket.sock.getsockname()[1]) != identity
		):
			raise LoaderError("listener.changed", "afterHandshake")
		health, _identifier = installAndVerify(
			session,
			source,
			bundleVersion,
			bundleHash,
			cancelEvent,
			healthDeadline=BUNDLE_HEALTH_DEADLINE,
			deadline=budget.end,
		)
	except Exception as error:
		unregisterSession()
		session.close()
		if isinstance(error, TimeoutError):
			raise LoaderError("cdp.timeout", "attach") from error
		raise
	session.absoluteDeadline = None
	return session, health, unregisterSession


def _waitForInitialAttachment(
	port: int,
	target: Target,
	source: str,
	bundleVersion: str,
	bundleHash: str,
	cancelEvent: threading.Event,
	registerCloser: RegisterCloser = _noopRegister,
	*,
	io=None,
	validator=None,
) -> tuple[Target, CdpSession, dict, Callable[[], None]]:
	io = (io or _OperationIO(cancelEvent, registerCloser, time.monotonic() + 45)).child(45)
	end = io.end
	lastError: LoaderError | None = None
	current: Target | None = target
	while time.monotonic() < end:
		if cancelEvent.is_set():
			raise LoaderError("operation.cancelled")
		try:
			if current is None:
				current = _discoverTarget(port, io=io, validator=validator)
			session, health, unregisterSession = _connectAndInstall(
				current,
				source,
				bundleVersion,
				bundleHash,
				cancelEvent,
				registerCloser,
				deadline=end,
				validator=validator,
			)
			return current, session, health, unregisterSession
		except LoaderError as error:
			if not (
				error.code in _TRANSIENT_INITIAL_ATTACH_ERRORS
				or error.code.startswith("target.")
				or error.code == "http.transport"
			):
				raise
			lastError = error
			current = None
		if cancelEvent.wait(0.25):
			raise LoaderError("operation.cancelled")
	raise LoaderError("cdp.initialAttach", lastError.code if lastError else "noTarget")


def launchOperation(
	channel: Channel,
	cancelEvent: threading.Event,
	setState: StateCallback,
	registerCloser: RegisterCloser = _noopRegister,
	reportObserver: ReportCallback = _noopReport,
	gateObserver: GateCallback = lambda name: None,
	stayAttached: bool = True,
	announcementGuard: AnnouncementGuard | None = None,
) -> OperationResult:
	io = _OperationIO(cancelEvent, registerCloser, time.monotonic() + 90.0)
	io.remaining()
	announcementGuard = announcementGuard or AnnouncementGuard()
	policy = CHANNELS[channel]
	setState(OperationState.PREPARING_LAUNCH)
	checkPreflight(buildSecurityProbe())
	package = resolvePackage(policy, runner=io.runner)
	gateObserver("package")
	if findRunningPackageProcesses(package, runner=io.runner):
		raise LoaderError("package.running")
	gateObserver("notRunning")

	io.remaining()
	port = reserveLoopbackPort()
	_recoverPendingRegistryState()
	lease = RegistryLease(
		policy,
		port,
		WinRegistry(),
		journal=RegistryJournal.createDefault(),
		operationId=newOperationId(),
	)
	lease.acquire()
	gateObserver("registry")
	session: CdpSession | None = None
	unregisterSession = _noopUnregister
	try:
		io.remaining()
		activateAumid(policy)
		gateObserver("activation")
		setState(OperationState.WAITING_FOR_ENDPOINT)
		endpointIO = io.child(20.0)
		waitForEndpoint(
			port,
			lambda selected: endpointResponds(selected, **endpointIO.httpOptions()),
			cancelEvent,
			deadline=endpointIO.remaining(),
		)
		lease.restore()
		gateObserver("registryRestored")

		packagePids = _waitForPackageProcesses(package, cancelEvent, io=io)
		_waitForValidatedListener(port, packagePids, cancelEvent, io=io)
		gateObserver("loopbackOnly")

		setState(OperationState.DISCOVERING_TARGET)
		validator = _endpointValidator(port, package, io)
		target = _waitForTarget(port, cancelEvent, io=io, validator=validator)
		gateObserver("oneTarget")
		bundle = selectEmbeddedBundle()
		setState(OperationState.ATTACHING)
		try:
			target, session, _health, unregisterSession = _waitForInitialAttachment(
				port,
				target,
				bundle.source,
				bundle.version,
				bundle.sha256,
				cancelEvent,
				registerCloser,
				io=io,
				validator=validator,
			)
		except LoaderError as error:
			_raiseBundleInstallError(bundle, error)
		gateObserver("webSocket")
		gateObserver("mainWorld")
		gateObserver("pageReady")
		gateObserver("bundleHealth")
		setState(OperationState.ATTACHED)
		if not stayAttached:
			return OperationResult(True, "attached", "active", {"channel": channel.value})

		announcementState = _AnnouncementState(securityEpoch=announcementGuard.snapshot()[1])
		nextTargetHealthCheck = time.monotonic() + _TARGET_HEALTH_INTERVAL
		while not cancelEvent.wait(_ANNOUNCEMENT_POLL_INTERVAL):
			try:
				_forwardCompanionAnnouncements(session, announcementState, reportObserver, announcementGuard)
				now = time.monotonic()
				if now >= nextTargetHealthCheck:
					current = _discoverTarget(
						port,
						io=_OperationIO(cancelEvent, registerCloser, time.monotonic() + 5),
					)
					nextTargetHealthCheck = now + _TARGET_HEALTH_INTERVAL
					if current.id != target.id:
						raise LoaderError("target.replaced")
			except LoaderError as error:
				if error.code == "operation.cancelled" or cancelEvent.is_set():
					raise LoaderError("operation.cancelled")
				io = _OperationIO(cancelEvent, registerCloser, time.monotonic() + RECONNECT_DEADLINE)
				validator = _endpointValidator(port, package, io)
				if not findRunningPackageProcesses(package, runner=io.runner):
					return OperationResult(
						True,
						"package.closed",
						"package.closed",
						{"channel": channel.value},
					)
				setState(OperationState.RECONNECTING)
				session.close()
				unregisterSession()

				def connect(
					replacement: Target,
				) -> tuple[Target, CdpSession, dict, Callable[[], None]]:
					return (
						replacement,
						*_connectAndInstall(
							replacement,
							bundle.source,
							bundle.version,
							bundle.sha256,
							cancelEvent,
							registerCloser,
							deadline=io.end,
							validator=validator,
						),
					)

				target, session, _health, unregisterSession = reconnect(
					lambda: _discoverTarget(port, io=io, validator=validator),
					connect,
					cancelEvent,
					deadline=io.end,
				)
				nextTargetHealthCheck = time.monotonic() + _TARGET_HEALTH_INTERVAL
				gateObserver("pageReady")
				setState(OperationState.ATTACHED)
		raise LoaderError("operation.cancelled")
	finally:
		if session is not None:
			session.close()
			unregisterSession()
		if lease.owned:
			lease.restore()
