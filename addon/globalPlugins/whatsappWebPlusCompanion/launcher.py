import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

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
from .models import Channel, LoaderError, OperationResult, OperationState
from .packages import findRunningPackageProcesses, resolvePackage
from .policy import BUNDLE_HEALTH_DEADLINE, CHANNELS, CONNECT_DEADLINE, TARGET_DEADLINE
from .processes import collectProcessTopology, validateListener
from .registry import (
	RegistryLease,
	WinRegistry,
	releaseRegistryMutex,
	recoverPendingRegistryState,
)
from .registryJournal import JournalError, RegistryJournal, newOperationId
from .registryRepair import tryAcquireRegistryMutex
from .security import buildSecurityProbe, checkPreflight
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
) -> None:
	batch = readCompanionAnnouncements(
		session,
		state.lastAcknowledgedSequence,
		state.generation,
	)
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
		if not _reportDelivered(
			reportObserver,
			OperationResult(
				True,
				"companion.announcement",
				"companion.announcement",
				{
					"sequence": announcement.sequence,
					"session": announcement.sessionToken,
					"generation": announcement.generation,
					"context": announcement.context,
					"source": announcement.source,
					"language": announcement.language,
					"privacy": announcement.privacy,
					"text": announcement.text,
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


def _discoverTarget(port: int) -> Target:
	return selectTarget(
		httpGetJson(port, "/json/version"),
		httpGetJson(port, "/json/list"),
		port,
	)


def _waitForTarget(port: int, cancelEvent: threading.Event) -> Target:
	end = time.monotonic() + TARGET_DEADLINE
	lastError: LoaderError | None = None
	while time.monotonic() < end:
		if cancelEvent.is_set():
			raise LoaderError("operation.cancelled")
		try:
			return _discoverTarget(port)
		except LoaderError as error:
			lastError = error
		if cancelEvent.wait(0.25):
			raise LoaderError("operation.cancelled")
	raise LoaderError("target.timeout", lastError.code if lastError else "noTarget")


def _waitForPackageProcesses(package, cancelEvent: threading.Event) -> set[int]:
	end = time.monotonic() + TARGET_DEADLINE
	while time.monotonic() < end:
		pids = set(findRunningPackageProcesses(package))
		if pids:
			return pids
		if cancelEvent.wait(0.25):
			raise LoaderError("operation.cancelled")
	raise LoaderError("package.processTimeout")


def _waitForValidatedListener(
	port: int,
	packagePids: set[int],
	cancelEvent: threading.Event,
) -> int:
	end = time.monotonic() + TARGET_DEADLINE
	lastError: LoaderError | None = None
	while time.monotonic() < end:
		if cancelEvent.is_set():
			raise LoaderError("operation.cancelled")
		listeners, parents = collectProcessTopology(port)
		try:
			return validateListener(port, listeners, parents, packagePids)
		except LoaderError as error:
			if not error.code.startswith("listener."):
				raise
			lastError = error
		if cancelEvent.wait(0.25):
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
) -> tuple[CdpSession, dict, Callable[[], None]]:
	webSocket = WebSocket.connect(target.webSocketUrl, CONNECT_DEADLINE)
	session = CdpSession(webSocket)
	unregisterSession = registerCloser(session.interrupt)
	try:
		health, _identifier = installAndVerify(
			session,
			source,
			bundleVersion,
			bundleHash,
			cancelEvent,
			healthDeadline=BUNDLE_HEALTH_DEADLINE,
		)
	except Exception:
		unregisterSession()
		session.close()
		raise
	return session, health, unregisterSession


def _waitForInitialAttachment(
	port: int,
	target: Target,
	source: str,
	bundleVersion: str,
	bundleHash: str,
	cancelEvent: threading.Event,
	registerCloser: RegisterCloser = _noopRegister,
) -> tuple[Target, CdpSession, dict, Callable[[], None]]:
	end = time.monotonic() + TARGET_DEADLINE
	lastError: LoaderError | None = None
	current: Target | None = target
	while time.monotonic() < end:
		if cancelEvent.is_set():
			raise LoaderError("operation.cancelled")
		try:
			if current is None:
				current = _discoverTarget(port)
			session, health, unregisterSession = _connectAndInstall(
				current,
				source,
				bundleVersion,
				bundleHash,
				cancelEvent,
				registerCloser,
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
) -> OperationResult:
	policy = CHANNELS[channel]
	setState(OperationState.PREPARING_LAUNCH)
	checkPreflight(buildSecurityProbe())
	package = resolvePackage(policy)
	gateObserver("package")
	if findRunningPackageProcesses(package):
		raise LoaderError("package.running")
	gateObserver("notRunning")

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
		activateAumid(policy)
		gateObserver("activation")
		setState(OperationState.WAITING_FOR_ENDPOINT)
		waitForEndpoint(port, endpointResponds, cancelEvent)
		lease.restore()
		gateObserver("registryRestored")

		packagePids = _waitForPackageProcesses(package, cancelEvent)
		_waitForValidatedListener(port, packagePids, cancelEvent)
		gateObserver("loopbackOnly")

		setState(OperationState.DISCOVERING_TARGET)
		target = _waitForTarget(port, cancelEvent)
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

		announcementState = _AnnouncementState()
		nextTargetHealthCheck = time.monotonic() + _TARGET_HEALTH_INTERVAL
		while not cancelEvent.wait(_ANNOUNCEMENT_POLL_INTERVAL):
			try:
				_forwardCompanionAnnouncements(session, announcementState, reportObserver)
				now = time.monotonic()
				if now >= nextTargetHealthCheck:
					current = _discoverTarget(port)
					nextTargetHealthCheck = now + _TARGET_HEALTH_INTERVAL
					if current.id != target.id:
						raise LoaderError("target.replaced")
			except LoaderError:
				if not findRunningPackageProcesses(package):
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
						),
					)

				target, session, _health, unregisterSession = reconnect(
					lambda: _discoverTarget(port),
					connect,
					cancelEvent,
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
