import json
import re
import socket
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar, cast
from urllib.parse import urlsplit

from .models import LoaderError
from .policy import (
	EXPECTED_HOST,
	EXPECTED_ORIGIN,
	LOOPBACK_HOST,
	RECONNECT_DEADLINE,
	RECONNECT_DELAYS,
	REQUEST_DEADLINE,
)
from .websocket import WebSocket


_COMPANION_BRIDGE_SOURCE = r"""
(() => {
	const property = '__whatsappWebPlusCompanionBridge';
	if (globalThis[property]) return;
	const queue = [];
	let sequence = 0;
	let generation = 1;
	let dropped = 0;
	let lastInvalidation = 'startup';
	let invalidatedSource = '';
	const maxQueue = 50;
	const maxText = 1800;
	const validSources = new Set(['status', 'message-log', 'alert']);
	const statusSelector = '#wa-plus-live-region[role="status"]';
	const logSelector = '#wa-plus-message-log[role="log"]';
	const alertSelector = '#wa-plus-settings-alert, #wa-plus-custom-text-error';
	const randomTokenPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
	const createRandomToken = () => {
		const cryptoApi = globalThis.crypto;
		if (typeof cryptoApi?.randomUUID === 'function') {
			try {
				const token = String(cryptoApi.randomUUID());
				if (randomTokenPattern.test(token)) return token;
			} catch {
				// Fall through to getRandomValues(), which is available in more contexts.
			}
		}
		if (typeof cryptoApi?.getRandomValues !== 'function') return '';
		try {
			const bytes = cryptoApi.getRandomValues(new Uint8Array(16));
			bytes[6] = (bytes[6] & 0x0f) | 0x40;
			bytes[8] = (bytes[8] & 0x3f) | 0x80;
			const hex = Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('');
			return [
				hex.slice(0, 8),
				hex.slice(8, 12),
				hex.slice(12, 16),
				hex.slice(16, 20),
				hex.slice(20)
			].join('-');
		} catch {
			return '';
		}
	};
	const sessionToken = createRandomToken();
	let contextToken = createRandomToken();
	if (!sessionToken || !contextToken) return;
	let previousMain = null;
	let previousTitle = '';
	let previousLanguage = '';
	let previousPrivacy = false;
	let contextInitialized = false;
	const elementFor = node => node?.nodeType === 1 ? node : node?.parentElement;
	const isInside = (node, selector) => {
		const element = elementFor(node);
		return Boolean(element?.matches?.(selector) || element?.closest?.(selector));
	};
	const languageFor = node => {
		const element = elementFor(node);
		let configured = '';
		try {
			configured = localStorage.getItem('wa-plus-language') || '';
		} catch {
			// Fall back to the nearest DOM language when storage is unavailable.
		}
		return String(configured || element?.closest?.('[lang]')?.getAttribute?.('lang') ||
			document.documentElement?.getAttribute?.('lang') || '').trim();
	};
	const privacyEnabled = () => {
		try {
			return localStorage.getItem('wa-plus-privacy') === 'true';
		} catch {
			return false;
		}
	};
	const currentTitle = main => String(
		main?.querySelector?.('header [data-testid="conversation-info-header-chat-title"], header [title]')
			?.textContent || ''
	).trim();
	const invalidate = (reason, source = '') => {
		const scopedSource = validSources.has(source) ? source : '';
		generation++;
		if (scopedSource) {
			for (let index = queue.length - 1; index >= 0; index--) {
				if (queue[index].source === scopedSource) queue.splice(index, 1);
			}
		} else {
			queue.length = 0;
		}
		dropped = 0;
		lastInvalidation = String(reason || 'context-changed').slice(0, 64);
		invalidatedSource = scopedSource;
		return generation;
	};
	const syncContext = () => {
		const main = document.querySelector?.('#main') || null;
		const title = currentTitle(main);
		const language = languageFor(document.documentElement);
		const privacy = privacyEnabled();
		if (!contextInitialized) {
			contextInitialized = true;
			previousMain = main;
			previousTitle = title;
			previousLanguage = language;
			previousPrivacy = privacy;
			return;
		}
		let reason = '';
		if (privacy !== previousPrivacy) reason = 'privacy-changed';
		else if (language !== previousLanguage) reason = 'language-changed';
		else if (main !== previousMain || title !== previousTitle) reason = 'chat-context-changed';
		previousMain = main;
		previousTitle = title;
		previousLanguage = language;
		previousPrivacy = privacy;
		if (reason) {
			contextToken = createRandomToken() || `${sessionToken}:${generation + 1}`;
			invalidate(reason);
		}
	};
	const append = (text, source, node) => {
		if (!validSources.has(source)) return;
		let value = String(text || '').trim();
		if (!value) return;
		if (value.length > maxText) value = `${value.slice(0, maxText - 1).trimEnd()}…`;
		queue.push(Object.freeze({
			sequence: ++sequence,
			generation,
			sessionToken,
			context: contextToken,
			source,
			language: languageFor(node),
			privacy: privacyEnabled(),
			text: value
		}));
		if (queue.length > maxQueue) {
			dropped += queue.length - maxQueue;
			queue.splice(0, queue.length - maxQueue);
		}
	};
	const observer = new MutationObserver(records => {
		syncContext();
		let statusChanged = false;
		const alertNodes = new Set();
		const passiveMessages = [];
		for (const record of records) {
			if (isInside(record.target, statusSelector)) statusChanged = true;
			if (isInside(record.target, alertSelector)) {
				alertNodes.add(elementFor(record.target)?.closest?.(alertSelector));
			}
			for (const node of record.addedNodes || []) {
				if (isInside(node, statusSelector)) statusChanged = true;
				if (isInside(node, logSelector) || isInside(record.target, logSelector)) {
					passiveMessages.push(node);
				}
				if (isInside(node, alertSelector)) {
					alertNodes.add(elementFor(node)?.closest?.(alertSelector));
				}
			}
		}
		const status = document.querySelector(statusSelector);
		if (statusChanged) append(status?.textContent, 'status', status);
		for (const node of passiveMessages) append(node.textContent, 'message-log', node);
		for (const node of alertNodes) append(node?.textContent, 'alert', node);
	});
	syncContext();
	observer.observe(document.documentElement || document, {
		subtree: true,
		childList: true,
		characterData: true,
		attributes: true,
		attributeFilter: ['lang']
	});
	Object.defineProperty(globalThis, property, {
		value: Object.freeze({
			contractVersion: 2,
			readSince(lastSequence = 0, expectedGeneration = generation) {
				syncContext();
				const cursor = Number.isSafeInteger(lastSequence) && lastSequence >= 0 ? lastSequence : 0;
				const requestedGeneration = Number.isSafeInteger(expectedGeneration) && expectedGeneration > 0
					? expectedGeneration
					: generation;
				const invalidated = requestedGeneration !== generation;
				const entries = invalidated ? queue.slice() : queue.filter(entry => entry.sequence > cursor);
				const oldestSequence = queue[0]?.sequence ?? sequence + 1;
				return Object.freeze({
					contractVersion: 2,
					sessionToken,
					generation,
					context: contextToken,
					invalidated,
					lastInvalidation,
					invalidatedSource,
					oldestSequence,
					latestSequence: sequence,
					overflowed: (!invalidated && cursor > 0 && cursor < oldestSequence - 1) ||
						(dropped > 0 && cursor < oldestSequence),
					entries: Object.freeze(entries)
				});
			}
		}),
		writable: false,
		configurable: false,
		enumerable: false
	});
})();
"""

_READINESS_PROPERTY = "__whatsappWebPlusCompanionReadiness"
_READINESS_CONTRACT_VERSION = 2
_READINESS_REQUIRED_KEYS = ("documentComplete", "body", "appShell", "primaryNavigation", "chatList")
_CHAT_LIST_SELECTOR = (
	'#pane-side [data-testid="chat-list"], '
	'#pane-side [aria-label="Chat list"][role="grid"], '
	'#pane-side [aria-label="Daftar chat"][role="grid"]'
)


@dataclass(frozen=True, slots=True)
class Target:
	id: str
	url: str
	webSocketUrl: str


_MAX_ANNOUNCEMENTS = 50
_MAX_ANNOUNCEMENT_TEXT = 1800
_VALID_ANNOUNCEMENT_SOURCES = frozenset({"status", "message-log", "alert"})
_LANGUAGE_PATTERN = re.compile(r"^[a-z]{2,3}(?:-[a-z0-9]{2,8})*$", re.IGNORECASE)
_SEMANTIC_HEALTH_CONTRACT_VERSION = 1
_SEMANTIC_HEALTH_CHECK_KEYS = frozenset(
	{
		"settingsMenu",
		"statusRegion",
		"messageLog",
		"messageGrid",
		"messageGridName",
		"messageGridTabStop",
		"messageGridFocusTarget",
		"messageInput",
		"messageInputName",
		"messageInputFocusTarget",
	},
)
_SEMANTIC_HEALTH_STATES = frozenset({"pass", "fail", "notApplicable"})
_SEMANTIC_HEALTH_ERROR_CODES = frozenset(
	{"semantic.probe"} | {f"semantic.{key}" for key in _SEMANTIC_HEALTH_CHECK_KEYS},
)


@dataclass(frozen=True, slots=True)
class CompanionAnnouncement:
	sequence: int
	generation: int
	sessionToken: str
	context: str
	source: str
	language: str
	privacy: bool
	text: str


@dataclass(frozen=True, slots=True)
class CompanionAnnouncementBatch:
	sessionToken: str
	generation: int
	context: str
	latestSequence: int
	invalidated: bool
	lastInvalidation: str
	invalidatedSource: str
	overflowed: bool
	entries: tuple[CompanionAnnouncement, ...]


def selectTarget(version: object, targets: object, port: int) -> Target:
	if not isinstance(version, dict) or version.get("Protocol-Version") != "1.3":
		raise LoaderError("target.protocol")
	if not isinstance(targets, list):
		raise LoaderError("target.discoveryFormat")
	matches: list[Target] = []
	for row in targets:
		if not isinstance(row, dict) or row.get("type") != "page":
			continue
		page = urlsplit(str(row.get("url", "")))
		ws = urlsplit(str(row.get("webSocketDebuggerUrl", "")))
		if (
			page.scheme == "https"
			and page.hostname == EXPECTED_HOST
			and page.port in (None, 443)
			and not page.username
			and not page.password
			and not page.fragment
			and ws.scheme == "ws"
			and ws.hostname == LOOPBACK_HOST
			and ws.port == port
			and not ws.username
			and not ws.password
			and not ws.fragment
			and ws.path.startswith("/devtools/page/")
		):
			targetId = str(row.get("id", ""))
			if targetId:
				matches.append(Target(targetId, str(row["url"]), str(row["webSocketDebuggerUrl"])))
	if len(matches) != 1:
		raise LoaderError("target.ambiguous", f"matches={len(matches)}")
	return matches[0]


class CdpSession:
	def __init__(self, webSocket: WebSocket) -> None:
		super().__init__()
		self.webSocket = webSocket
		self.nextId = 1

	def request(
		self,
		method: str,
		params: dict,
		deadline: float = REQUEST_DEADLINE,
		*,
		cancelEvent: object | None = None,
	) -> dict:
		requestId = self.nextId
		self.nextId += 1
		payload = json.dumps(
			{"id": requestId, "method": method, "params": params},
			separators=(",", ":"),
		)
		submitUnlessSet = getattr(cancelEvent, "submitUnlessSet", None)
		if callable(submitUnlessSet):
			submitted, _result = cast(
				tuple[bool, object],
				submitUnlessSet(lambda: self.webSocket.sendText(payload)),
			)
			if not submitted:
				raise LoaderError("operation.cancelled")
		elif cancelEvent is not None:
			isSet = getattr(cancelEvent, "is_set", None)
			if callable(isSet) and isSet():
				raise LoaderError("operation.cancelled")
			self.webSocket.sendText(payload)
		else:
			self.webSocket.sendText(payload)
		end = time.monotonic() + deadline
		while True:
			remaining = end - time.monotonic()
			if remaining <= 0:
				raise LoaderError("cdp.timeout", f"method={method}")
			self.webSocket.sock.settimeout(remaining)
			try:
				message = json.loads(self.webSocket.receiveText())
			except socket.timeout as error:
				raise LoaderError("cdp.timeout", f"method={method}") from error
			except ValueError as error:
				raise LoaderError("cdp.json", f"method={method}") from error
			if not isinstance(message, dict):
				raise LoaderError("cdp.json", f"method={method}")
			if "id" not in message:
				continue
			if message.get("id") != requestId:
				raise LoaderError("cdp.responseOrder", f"method={method}")
			if "error" in message:
				raise LoaderError("cdp.response", f"method={method}")
			result = message.get("result", {})
			if not isinstance(result, dict):
				raise LoaderError("cdp.response", f"method={method}")
			return result

	def close(self) -> None:
		self.webSocket.close()

	def interrupt(self) -> None:
		self.webSocket.interrupt()


def makeReadinessWrapper(bundleHash: str) -> str:
	if len(bundleHash) != 64 or any(character not in "0123456789abcdef" for character in bundleHash):
		raise LoaderError("bundle.hash")
	return f"""(() => {{
	if (window !== window.top || location.origin !== {json.dumps(EXPECTED_ORIGIN)}) return;
	const property = {json.dumps(_READINESS_PROPERTY)};
	const bundleIdentifier = {json.dumps(bundleHash)};
	const previous = globalThis[property];
	if (previous?.contractVersion === {_READINESS_CONTRACT_VERSION} &&
		previous.bundleIdentifier === bundleIdentifier && typeof previous.claim === 'function' &&
		['waiting', 'starting', 'ready'].includes(previous.state)) return;
	const readCandidate = () => {{
		const body = document.body || null;
		const side = document.querySelector?.('div#side') || null;
		const primaryNavigation = document.querySelector?.('[data-testid="navbar-primary-section"]') || null;
		const chatList = side?.querySelector?.({json.dumps(_CHAT_LIST_SELECTOR)}) || null;
		const requiredNodes = Object.freeze({{
			documentComplete: document.readyState === 'complete',
			body: Boolean(body?.isConnected),
			appShell: Boolean(side?.isConnected),
			primaryNavigation: Boolean(primaryNavigation?.isConnected),
			chatList: Boolean(chatList?.isConnected)
		}});
		return {{body, side, primaryNavigation, chatList, requiredNodes}};
	}};
	const publish = (state, nodes = readCandidate().requiredNodes, errorCode = '') => {{
		Object.defineProperty(globalThis, property, {{
			value: Object.freeze({{
				contractVersion: {_READINESS_CONTRACT_VERSION},
				bundleIdentifier,
				state,
				requiredNodes: nodes,
				errorCode,
				claim,
				complete,
				fail
			}}),
			writable: false,
			configurable: true,
			enumerable: false
		}});
	}};
	let observer = null;
	let frame = 0;
	let stableFrames = 0;
	let candidate = null;
	const sameCandidate = (left, right) => Boolean(
		left && right &&
		left.body === right.body &&
		left.side === right.side &&
		left.primaryNavigation === right.primaryNavigation &&
		left.chatList === right.chatList
	);
	const stopWaiting = () => {{
		observer?.disconnect();
		observer = null;
		if (frame) cancelAnimationFrame(frame);
		frame = 0;
		document.removeEventListener?.('readystatechange', check);
		document.removeEventListener?.('DOMContentLoaded', check);
		window.removeEventListener?.('load', check);
		window.removeEventListener?.('pageshow', check);
	}};
	const start = nodes => {{
		stopWaiting();
		candidate = nodes;
		publish('ready', nodes.requiredNodes);
	}};
	const confirm = () => {{
		frame = 0;
		const current = readCandidate();
		if (!sameCandidate(candidate, current) || !Object.values(current.requiredNodes).every(Boolean)) {{
			candidate = null;
			stableFrames = 0;
			check();
			return;
		}}
		stableFrames++;
		if (stableFrames < 2) {{
			frame = requestAnimationFrame(confirm);
			return;
		}}
		start(current);
	}};
	const check = () => {{
		const state = globalThis[property]?.state;
		if (state === 'starting' || state === 'ready' || state === 'failed') return;
		const current = readCandidate();
		if (!Object.values(current.requiredNodes).every(Boolean)) {{
			candidate = null;
			stableFrames = 0;
			if (frame) cancelAnimationFrame(frame);
			frame = 0;
			publish('waiting', current.requiredNodes);
			return;
		}}
		if (!sameCandidate(candidate, current)) {{
			candidate = current;
			stableFrames = 0;
		}}
		if (!frame) frame = requestAnimationFrame(confirm);
	}};
	const arm = () => {{
		if (!observer) {{
			observer = new MutationObserver(check);
			observer.observe(document, {{
				subtree: true,
				childList: true,
				attributes: true,
				attributeFilter: ['id', 'data-testid', 'role', 'aria-label']
			}});
			document.addEventListener?.('readystatechange', check);
			document.addEventListener?.('DOMContentLoaded', check);
			window.addEventListener?.('load', check);
			window.addEventListener?.('pageshow', check);
		}}
		check();
	}};
	const claim = () => {{
		if (globalThis[property]?.state !== 'ready') return false;
		const current = readCandidate();
		if (!sameCandidate(candidate, current) || !Object.values(current.requiredNodes).every(Boolean)) {{
			candidate = null;
			stableFrames = 0;
			publish('waiting', current.requiredNodes);
			arm();
			return false;
		}}
		publish('starting', current.requiredNodes);
		return true;
	}};
	const complete = () => {{
		if (globalThis[property]?.state !== 'starting') return false;
		const current = readCandidate();
		if (!sameCandidate(candidate, current) || !Object.values(current.requiredNodes).every(Boolean)) {{
			candidate = null;
			stableFrames = 0;
			publish('waiting', current.requiredNodes);
			arm();
			return false;
		}}
		publish('ready', current.requiredNodes);
		return true;
	}};
	const fail = errorCode => {{
		publish('failed', readCandidate().requiredNodes, errorCode);
		return false;
	}};
	publish('waiting');
	arm();
}})();"""


def makeInjectionWrapper(source: str, bundleHash: str) -> str:
	if len(bundleHash) != 64 or any(character not in "0123456789abcdef" for character in bundleHash):
		raise LoaderError("bundle.hash")
	return f"""(() => {{
	if (window !== window.top || location.origin !== {json.dumps(EXPECTED_ORIGIN)}) return false;
	const gate = globalThis.{_READINESS_PROPERTY};
	if (gate?.contractVersion !== {_READINESS_CONTRACT_VERSION} ||
		gate.bundleIdentifier !== {json.dumps(bundleHash)} || gate.state !== 'ready' ||
		!Object.values(gate.requiredNodes || {{}}).every(Boolean)) return false;
	if (globalThis.__whatsappWebPlusLoaderHealth || globalThis.__whatsappWebPlusLoader) return true;
	if (typeof gate.claim !== 'function' || gate.claim() !== true) return false;
	try {{
		globalThis.__whatsappWebPlusBundleHash = {json.dumps(bundleHash)};
		{source}
		{_COMPANION_BRIDGE_SOURCE}
		return globalThis.{_READINESS_PROPERTY}?.complete?.() === true;
	}} catch (_error) {{
		return globalThis.{_READINESS_PROPERTY}?.fail?.('bundle.evaluate') ?? false;
	}}
}})();"""


def _runtimeValue(response: dict) -> object:
	result = response.get("result")
	if not isinstance(result, dict):
		return None
	if result.get("subtype") == "error" or "exceptionDetails" in response:
		raise LoaderError("cdp.evaluate")
	return result.get("value")


def _positiveInteger(value: object, *, allowZero: bool = False) -> int | None:
	if isinstance(value, bool) or not isinstance(value, int):
		return None
	if value < 0 or (value == 0 and not allowZero):
		return None
	return value


def _boundedToken(value: object, limit: int = 128) -> str:
	if not isinstance(value, str):
		return ""
	result = value.strip()
	return result if result and len(result) <= limit else ""


def readCompanionAnnouncements(
	session: CdpSession,
	lastAcknowledgedSequence: int = 0,
	expectedGeneration: int = 0,
) -> CompanionAnnouncementBatch:
	lastAcknowledgedSequence = _positiveInteger(lastAcknowledgedSequence, allowZero=True) or 0
	expectedGeneration = _positiveInteger(expectedGeneration, allowZero=True) or 0
	expression = (
		"(() => { const bridge=globalThis.__whatsappWebPlusCompanionBridge; "
		"return bridge&&bridge.contractVersion===2&&typeof bridge.readSince==='function'"
		f"?bridge.readSince({lastAcknowledgedSequence},{expectedGeneration}):null; }})()"
	)
	value = _runtimeValue(
		session.request(
			"Runtime.evaluate",
			{
				"expression": expression,
				"returnByValue": True,
			},
			deadline=2.0,
		),
	)
	if not isinstance(value, dict) or value.get("contractVersion") != 2:
		raise LoaderError("cdp.announcement")
	sessionToken = _boundedToken(value.get("sessionToken"))
	generation = _positiveInteger(value.get("generation"))
	if not sessionToken or generation is None:
		raise LoaderError("cdp.announcement")
	context = _boundedToken(value.get("context")) or f"{sessionToken}:{generation}"
	lastInvalidation = _boundedToken(value.get("lastInvalidation"), 64) or "context-changed"
	invalidatedSource = value.get("invalidatedSource", "")
	if invalidatedSource not in _VALID_ANNOUNCEMENT_SOURCES:
		invalidatedSource = ""
	rawEntries = value.get("entries")
	latestSequence = _positiveInteger(value.get("latestSequence"), allowZero=True)
	if not isinstance(rawEntries, list) or latestSequence is None:
		raise LoaderError("cdp.announcement")
	overflowed = value.get("overflowed") is True or len(rawEntries) > _MAX_ANNOUNCEMENTS
	entries: list[CompanionAnnouncement] = []
	previousSequence = lastAcknowledgedSequence
	for item in rawEntries[-_MAX_ANNOUNCEMENTS:]:
		if not isinstance(item, dict):
			continue
		sequence = _positiveInteger(item.get("sequence"))
		itemGeneration = _positiveInteger(item.get("generation"))
		source = item.get("source")
		privacy = item.get("privacy")
		text = item.get("text")
		retainedAcrossScopedInvalidation = (
			itemGeneration is not None
			and itemGeneration < generation
			and invalidatedSource in _VALID_ANNOUNCEMENT_SOURCES
			and source != invalidatedSource
		)
		if (
			sequence is None
			or sequence <= previousSequence
			or (itemGeneration != generation and not retainedAcrossScopedInvalidation)
			or source not in _VALID_ANNOUNCEMENT_SOURCES
			or not isinstance(privacy, bool)
			or not isinstance(text, str)
		):
			continue
		text = text.strip()
		if not text:
			continue
		if len(text) > _MAX_ANNOUNCEMENT_TEXT:
			text = f"{text[: _MAX_ANNOUNCEMENT_TEXT - 1].rstrip()}…"
		itemSession = _boundedToken(item.get("sessionToken")) or sessionToken
		itemContext = _boundedToken(item.get("context")) or context
		if itemSession != sessionToken or itemContext != context:
			continue
		language = item.get("language", "")
		if not isinstance(language, str) or not _LANGUAGE_PATTERN.fullmatch(language):
			language = ""
		entries.append(
			CompanionAnnouncement(
				sequence=sequence,
				# A scoped invalidation intentionally retains entries from the
				# other sources. Normalize those entries to the current envelope;
				# downstream consumers validate one coherent generation/context.
				generation=generation,
				sessionToken=sessionToken,
				context=context,
				source=source,
				language=language,
				privacy=privacy,
				text=text,
			),
		)
		previousSequence = sequence
	return CompanionAnnouncementBatch(
		sessionToken=sessionToken,
		generation=generation,
		context=context,
		latestSequence=latestSequence,
		invalidated=value.get("invalidated") is True,
		lastInvalidation=lastInvalidation,
		invalidatedSource=invalidatedSource,
		overflowed=overflowed,
		entries=tuple(entries),
	)


def _isValidSemanticHealth(value: object) -> bool:
	if not isinstance(value, dict) or set(value) != {
		"contractVersion",
		"overall",
		"checks",
		"errorCode",
	}:
		return False
	if value.get("contractVersion") != _SEMANTIC_HEALTH_CONTRACT_VERSION:
		return False
	checks = value.get("checks")
	if not isinstance(checks, dict) or set(checks) != set(_SEMANTIC_HEALTH_CHECK_KEYS):
		return False
	if any(state not in _SEMANTIC_HEALTH_STATES for state in checks.values()):
		return False
	values = tuple(checks.values())
	expectedOverall = (
		"fail"
		if "fail" in values
		else "notApplicable"
		if all(state == "notApplicable" for state in values)
		else "pass"
	)
	if value.get("overall") != expectedOverall:
		return False
	errorCode = value.get("errorCode")
	if expectedOverall == "fail":
		return isinstance(errorCode, str) and errorCode in _SEMANTIC_HEALTH_ERROR_CODES
	return errorCode == ""


def installAndVerify(
	session: CdpSession,
	source: str,
	bundleVersion: str,
	bundleHash: str,
	cancelEvent: threading.Event,
	healthDeadline: float | None = None,
) -> tuple[dict, str]:
	readinessWrapper = makeReadinessWrapper(bundleHash)
	injectionWrapper = makeInjectionWrapper(source, bundleHash)
	session.request("Page.enable", {})
	session.request("Runtime.enable", {})
	probe = _runtimeValue(
		session.request(
			"Runtime.evaluate",
			{
				"expression": f"({{origin:location.origin,top:window===window.top,health:globalThis.__whatsappWebPlusLoaderHealth||null,sentinel:globalThis.__whatsappWebPlusLoader||null,readiness:globalThis.{_READINESS_PROPERTY}||null}})",
				"returnByValue": True,
			},
		),
	)
	if not isinstance(probe, dict) or probe.get("origin") != EXPECTED_ORIGIN or probe.get("top") is not True:
		raise LoaderError("cdp.context")
	if (probe.get("health") is not None or probe.get("sentinel") is not None) and probe.get(
		"readiness",
	) is None:
		raise LoaderError("bundle.healthMismatch")
	registration = session.request("Page.addScriptToEvaluateOnNewDocument", {"source": readinessWrapper})
	identifier = registration.get("identifier")
	if not isinstance(identifier, str) or not identifier:
		raise LoaderError("cdp.registration")
	probeReadiness = probe.get("readiness")
	if (
		not isinstance(probeReadiness, dict)
		or probeReadiness.get("contractVersion") != _READINESS_CONTRACT_VERSION
		or probeReadiness.get("bundleIdentifier") != bundleHash
	):
		_runtimeValue(
			session.request(
				"Runtime.evaluate",
				{"expression": readinessWrapper, "returnByValue": True},
			),
		)
	injectionRequested = probe.get("health") is not None or probe.get("sentinel") is not None
	healthEnd: float | None = None
	while True:
		if cancelEvent.wait(0.25):
			raise LoaderError("operation.cancelled")
		status = _runtimeValue(
			session.request(
				"Runtime.evaluate",
				{
					"expression": f"({{health:globalThis.__whatsappWebPlusLoaderHealth||null,sentinel:globalThis.__whatsappWebPlusLoader||null,readiness:globalThis.{_READINESS_PROPERTY}||null}})",
					"returnByValue": True,
				},
			),
		)
		if not isinstance(status, dict):
			continue
		readiness = status.get("readiness")
		if not isinstance(readiness, dict):
			if status.get("health") is not None:
				raise LoaderError("bundle.healthMismatch")
			continue
		readinessNodes = readiness.get("requiredNodes")
		if (
			readiness.get("contractVersion") != _READINESS_CONTRACT_VERSION
			or readiness.get("bundleIdentifier") != bundleHash
			or readiness.get("state") not in {"waiting", "starting", "ready", "failed"}
			or not isinstance(readinessNodes, dict)
		):
			raise LoaderError("bundle.healthMismatch")
		if readiness.get("state") == "failed":
			raise LoaderError("bundle.failed", str(readiness.get("errorCode", "")))
		readinessReady = readiness.get("state") == "ready" and all(
			readinessNodes.get(key) is True for key in _READINESS_REQUIRED_KEYS
		)
		if not readinessReady:
			# A renderer reload can leave the previous userscript health object in the
			# main world while WhatsApp rebuilds its application shell. Readiness owns
			# this transition, so stale health must not turn normal loading into a
			# terminal bundle failure or start the post-injection health deadline.
			healthEnd = None
			continue
		health = status.get("health")
		if not injectionRequested and health is None and status.get("sentinel") is None:
			if cancelEvent.is_set():
				raise LoaderError("operation.cancelled")
			try:
				injected = _runtimeValue(
					session.request(
						"Runtime.evaluate",
						{"expression": injectionWrapper, "returnByValue": True},
						cancelEvent=cancelEvent,
					),
				)
			except LoaderError as error:
				if error.code == "cdp.evaluate":
					raise LoaderError("bundle.failed", "injection.evaluate") from error
				if error.code == "cdp.timeout":
					raise LoaderError("bundle.healthTimeout", "injection.timeout") from error
				raise
			if injected is not True:
				continue
			injectionRequested = True
			if healthDeadline is not None:
				healthEnd = time.monotonic() + healthDeadline
			continue
		if injectionRequested and healthDeadline is not None and healthEnd is None:
			healthEnd = time.monotonic() + healthDeadline
		if healthEnd is not None and time.monotonic() >= healthEnd:
			raise LoaderError("bundle.healthTimeout")
		if not isinstance(health, dict):
			continue
		if health.get("state") == "failed":
			raise LoaderError("bundle.failed", str(health.get("errorCode", "")))
		requiredNodes = health.get("requiredNodes")
		baseHealthReady = (
			readinessReady
			and health.get("contractVersion") == 1
			and health.get("scriptVersion") == bundleVersion
			and health.get("state") == "ready"
			and health.get("origin") == EXPECTED_ORIGIN
			and health.get("topFrame") is True
			and health.get("bundleIdentifier") == bundleHash
			and isinstance(requiredNodes, dict)
			and all(requiredNodes.get(key) is True for key in ("settingsMenu", "statusRegion", "messageLog"))
		)
		if baseHealthReady:
			semanticHealth = health.get("semanticHealth")
			if not isinstance(semanticHealth, dict) or not _isValidSemanticHealth(semanticHealth):
				raise LoaderError("bundle.healthMismatch")
			if semanticHealth.get("overall") != "pass":
				continue
			postInstall = _runtimeValue(
				session.request(
					"Runtime.evaluate",
					{
						"expression": (
							"({bridgeContractVersion:globalThis."
							"__whatsappWebPlusCompanionBridge?.contractVersion||0,"
							"chatListReady:Boolean(document.querySelector('div#side')?.querySelector("
							f"{json.dumps(_CHAT_LIST_SELECTOR)})?.isConnected),"
							"semanticNodesReady:["
							'document.querySelectorAll(\'[id="wa-plus-settings-menu"][role="menu"]\').length===1,'
							'document.querySelectorAll(\'[id="wa-plus-live-region"][role="status"]'
							'[aria-live="polite"][aria-atomic="true"]\').length===1,'
							'document.querySelectorAll(\'[id="wa-plus-message-log"][role="log"]'
							'[aria-live="polite"][aria-relevant="additions"]'
							'[aria-atomic="false"]\').length===1].every(Boolean)})'
						),
						"returnByValue": True,
					},
				),
			)
			if (
				not isinstance(postInstall, dict)
				or postInstall.get("bridgeContractVersion") != 2
				or postInstall.get("semanticNodesReady") is not True
				or (
					postInstall.get("chatListReady") is not True
					and postInstall.get("chatListReady") is not False
				)
			):
				raise LoaderError("bundle.healthMismatch")
			if postInstall.get("chatListReady") is not True:
				# The userscript and its owned semantic nodes are healthy, but
				# WhatsApp replaced or detached the chat shell between readiness
				# and this final probe. Keep waiting without charging that page-load
				# time against the bundle health deadline.
				healthEnd = None
				continue
			return health, identifier
		if health.get("state") == "ready":
			raise LoaderError("bundle.healthMismatch")


def removeRegistration(session: CdpSession, identifier: str) -> None:
	session.request("Page.removeScriptToEvaluateOnNewDocument", {"identifier": identifier})


T = TypeVar("T")


def reconnect(
	discover: Callable[[], Target],
	connect: Callable[[Target], T],
	cancelEvent: threading.Event,
) -> T:
	end = time.monotonic() + RECONNECT_DEADLINE
	lastError: LoaderError | None = None
	for index, delay in enumerate(RECONNECT_DELAYS):
		if cancelEvent.is_set():
			raise LoaderError("operation.cancelled")
		try:
			return connect(discover())
		except LoaderError as error:
			lastError = error
		if index < len(RECONNECT_DELAYS) - 1:
			remaining = end - time.monotonic()
			if remaining <= delay or cancelEvent.wait(delay):
				break
	raise LoaderError("cdp.reconnect", lastError.code if lastError else "noTarget")
