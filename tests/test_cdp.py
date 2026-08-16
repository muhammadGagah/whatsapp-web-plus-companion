import json
import subprocess
import textwrap
import threading
import unittest

from _path import installPackagePath

installPackagePath()

from globalPlugins.whatsappWebPlusCompanion.cdp import (
	_COMPANION_BRIDGE_SOURCE,
	CdpSession,
	installAndVerify,
	makeInjectionWrapper,
	makeReadinessWrapper,
	readCompanionAnnouncements,
	selectTarget,
)
from globalPlugins.whatsappWebPlusCompanion.models import LoaderError
from globalPlugins.whatsappWebPlusCompanion.models import CancellationEvent


VALID = {
	"id": "p1",
	"type": "page",
	"url": "https://web.whatsapp.com/",
	"webSocketDebuggerUrl": "ws://127.0.0.1:49223/devtools/page/p1",
}


class FakeSocketHandle:
	def settimeout(self, timeout) -> None:
		self.timeout = timeout


class FakeWebSocket:
	def __init__(self) -> None:
		self.sock = FakeSocketHandle()
		self.sent: list[dict] = []
		self.messages = [json.dumps({"id": 1, "result": {"identifier": "x"}})]

	def sendText(self, text: str) -> None:
		self.sent.append(json.loads(text))

	def receiveText(self) -> str:
		return self.messages.pop(0)

	def close(self) -> None:
		return

	def interrupt(self) -> None:
		return


class ImmediateCancel:
	def is_set(self) -> bool:
		return False

	def wait(self, timeout: float) -> bool:
		return False


class CancelAfterOneReadinessCheck:
	def __init__(self) -> None:
		self.waits = 0

	def is_set(self) -> bool:
		return False

	def wait(self, timeout: float) -> bool:
		self.waits += 1
		return self.waits > 1


def semanticHealth(**overrides) -> dict:
	checks = {
		"settingsMenu": "pass",
		"statusRegion": "pass",
		"messageLog": "pass",
		"messageGrid": "notApplicable",
		"messageGridName": "notApplicable",
		"messageGridTabStop": "notApplicable",
		"messageGridFocusTarget": "notApplicable",
		"messageInput": "notApplicable",
		"messageInputName": "notApplicable",
		"messageInputFocusTarget": "notApplicable",
	}
	checks.update(overrides.pop("checks", {}))
	value = {
		"contractVersion": 1,
		"overall": "pass",
		"checks": checks,
		"errorCode": "",
	}
	value.update(overrides)
	return value


class HealthSession:
	def __init__(
		self,
		version: str = "2.6.73",
		semantic: dict | None = None,
		postInstallSemantic: bool = True,
		postInstallBridge: int = 2,
	) -> None:
		self.version = version
		self.activated = False
		self.semantic = semantic or semanticHealth()
		self.postInstallSemantic = postInstallSemantic
		self.postInstallBridge = postInstallBridge

	def readiness(self, state: str = "ready") -> dict:
		return {
			"contractVersion": 2,
			"bundleIdentifier": "a" * 64,
			"state": state,
			"requiredNodes": {
				"documentComplete": state == "ready",
				"body": state == "ready",
				"appShell": state == "ready",
				"primaryNavigation": state == "ready",
				"chatList": state == "ready",
			},
			"errorCode": "",
		}

	def request(
		self,
		method: str,
		params: dict,
		deadline: float = 5.0,
		*,
		cancelEvent: object | None = None,
	) -> dict:
		if method == "Page.addScriptToEvaluateOnNewDocument":
			return {"identifier": "registered"}
		if method != "Runtime.evaluate":
			return {}
		expression = params["expression"]
		if expression.startswith("({origin:"):
			return {
				"result": {
					"value": {
						"origin": "https://web.whatsapp.com",
						"top": True,
						"health": None,
						"sentinel": None,
						"readiness": self.readiness(),
					},
				},
			}
		if expression.startswith("({health:"):
			return {
				"result": {
					"value": {
						"health": (
							{
								"contractVersion": 1,
								"scriptVersion": self.version,
								"bundleIdentifier": "a" * 64,
								"origin": "https://web.whatsapp.com",
								"topFrame": True,
								"state": "ready",
								"readyStateAtInstall": "complete",
								"requiredNodes": {
									"settingsMenu": True,
									"statusRegion": True,
									"messageLog": True,
								},
								"semanticHealth": self.semantic,
								"errorCode": "",
							}
							if self.activated
							else None
						),
						"sentinel": {"contractVersion": 1} if self.activated else None,
						"readiness": self.readiness(),
					},
				},
			}
		if expression.startswith("({bridgeContractVersion:"):
			return {
				"result": {
					"value": {
						"bridgeContractVersion": self.postInstallBridge,
						"chatListReady": True,
						"semanticNodesReady": self.postInstallSemantic,
					},
				},
			}
		if "const gate = globalThis.__whatsappWebPlusCompanionReadiness" in expression:

			def activate():
				self.activated = True
				return {"result": {"value": True}}

			submitUnlessSet = getattr(cancelEvent, "submitUnlessSet", None)
			if callable(submitUnlessSet):
				submitted, response = submitUnlessSet(activate)
				if not submitted:
					raise LoaderError("operation.cancelled")
				return response
			return activate()
		return {"result": {"value": None}}


class WaitingHealthSession(HealthSession):
	def readiness(self, state: str = "waiting") -> dict:
		return super().readiness("waiting")


class StaleHealthWhileWaitingSession(WaitingHealthSession):
	def __init__(self) -> None:
		super().__init__()
		self.activated = True


class PostInstallChatListSession(HealthSession):
	def __init__(self, states: tuple[bool, ...]) -> None:
		super().__init__()
		self.states = states
		self.postInstallChecks = 0

	def request(
		self,
		method: str,
		params: dict,
		deadline: float = 5.0,
		*,
		cancelEvent: object | None = None,
	) -> dict:
		response = super().request(method, params, deadline, cancelEvent=cancelEvent)
		if method == "Runtime.evaluate" and params["expression"].startswith(
			"({bridgeContractVersion:",
		):
			index = min(self.postInstallChecks, len(self.states) - 1)
			response["result"]["value"]["chatListReady"] = self.states[index]
			self.postInstallChecks += 1
		return response


class NeverHealthySession(HealthSession):
	def request(
		self,
		method: str,
		params: dict,
		deadline: float = 5.0,
		*,
		cancelEvent: object | None = None,
	) -> dict:
		response = super().request(method, params, deadline, cancelEvent=cancelEvent)
		if method == "Runtime.evaluate" and params["expression"].startswith("({health:"):
			response["result"]["value"]["health"] = None
		return response


class FailingInjectionSession(HealthSession):
	def __init__(self, code: str) -> None:
		super().__init__()
		self.code = code

	def request(
		self,
		method: str,
		params: dict,
		deadline: float = 5.0,
		*,
		cancelEvent: object | None = None,
	) -> dict:
		if (
			method == "Runtime.evaluate"
			and "const gate = globalThis.__whatsappWebPlusCompanionReadiness" in params["expression"]
		):
			raise LoaderError(self.code)
		return super().request(method, params, deadline, cancelEvent=cancelEvent)


class CancelDuringReadyStatusSession(HealthSession):
	def __init__(self, cancelEvent: threading.Event) -> None:
		super().__init__()
		self.cancelEvent = cancelEvent

	def request(
		self,
		method: str,
		params: dict,
		deadline: float = 5.0,
		*,
		cancelEvent: object | None = None,
	) -> dict:
		response = super().request(method, params, deadline, cancelEvent=cancelEvent)
		if method == "Runtime.evaluate" and params["expression"].startswith("({health:"):
			self.cancelEvent.set()
		return response


class CancelAfterTwoStatusChecks:
	def __init__(self) -> None:
		self.waits = 0

	def is_set(self) -> bool:
		return False

	def wait(self, timeout: float) -> bool:
		self.waits += 1
		return self.waits > 2


class PauseBeforeSubmissionEvent(CancellationEvent):
	def __init__(self) -> None:
		super().__init__()
		self.atBoundary = threading.Event()
		self.release = threading.Event()

	def submitUnlessSet(self, action):
		self.atBoundary.set()
		self.release.wait(1.0)
		return super().submitUnlessSet(action)


class AnnouncementSession:
	def __init__(self, value) -> None:
		self.value = value
		self.expressions: list[str] = []

	def request(self, method: str, params: dict, deadline: float = 5.0) -> dict:
		self.expressions.append(params["expression"])
		return {"result": {"value": self.value}}


def announcementBatch(entries, **overrides):
	value = {
		"contractVersion": 2,
		"sessionToken": "session-1",
		"generation": 3,
		"context": "chat-2",
		"invalidated": False,
		"lastInvalidation": "startup",
		"invalidatedSource": "",
		"oldestSequence": 1,
		"latestSequence": max(
			(entry.get("sequence", 0) for entry in entries if isinstance(entry, dict)),
			default=0,
		),
		"overflowed": False,
		"entries": entries,
	}
	value.update(overrides)
	return value


class CdpTests(unittest.TestCase):
	def test_request_ids_and_target_validation(self) -> None:
		webSocket = FakeWebSocket()
		session = CdpSession(webSocket)
		self.assertEqual(session.request("Page.enable", {}), {"identifier": "x"})
		self.assertEqual(webSocket.sent[0]["id"], 1)
		self.assertEqual(selectTarget({"Protocol-Version": "1.3"}, [VALID], 49223).id, "p1")
		for rows in (
			[],
			[VALID, dict(VALID, id="p2")],
			[dict(VALID, webSocketDebuggerUrl="ws://localhost:49223/x")],
		):
			with self.assertRaises(LoaderError):
				selectTarget({"Protocol-Version": "1.3"}, rows, 49223)

	def test_request_discards_unsolicited_events_without_accumulating_them(self) -> None:
		webSocket = FakeWebSocket()
		webSocket.messages = [
			json.dumps({"method": "Runtime.consoleAPICalled", "params": {"type": "log"}}),
			json.dumps({"id": 1, "result": {"identifier": "x"}}),
		]
		session = CdpSession(webSocket)

		self.assertEqual(session.request("Page.enable", {}), {"identifier": "x"})
		self.assertFalse(hasattr(session, "events"))

	def test_wrapper_and_complete_health_contract(self) -> None:
		readinessWrapper = makeReadinessWrapper("a" * 64)
		wrapper = makeInjectionWrapper("window.loaded=true;", "a" * 64)
		self.assertIn("window !== window.top", wrapper)
		self.assertIn("https://web.whatsapp.com", wrapper)
		self.assertIn("__whatsappWebPlusCompanionBridge", wrapper)
		self.assertIn("MutationObserver", readinessWrapper)
		self.assertIn("requestAnimationFrame", readinessWrapper)
		self.assertIn("#pane-side", readinessWrapper)
		health, identifier = installAndVerify(
			HealthSession(),
			"window.loaded=true;",
			"2.6.73",
			"a" * 64,
			ImmediateCancel(),
			healthDeadline=0.01,
		)
		self.assertEqual(identifier, "registered")
		self.assertEqual(health["readyStateAtInstall"], "complete")
		self.assertEqual(health["semanticHealth"], semanticHealth())

	def test_semantic_health_failures_wait_for_recovery_then_time_out(self) -> None:
		failing = semanticHealth(
			overall="fail",
			checks={"messageInputName": "fail"},
			errorCode="semantic.messageInputName",
		)
		with self.assertRaisesRegex(LoaderError, "bundle.healthTimeout"):
			installAndVerify(
				HealthSession(semantic=failing),
				"window.loaded=true;",
				"2.6.73",
				"a" * 64,
				ImmediateCancel(),
				healthDeadline=0.001,
			)

	def test_malformed_or_privacy_expanding_semantic_health_is_rejected(self) -> None:
		for malformed in (
			semanticHealth(contractVersion=2),
			semanticHealth(messageText="must not cross the contract"),
			semanticHealth(overall="pass", checks={"messageInputName": "fail"}),
			semanticHealth(overall="fail", checks={"messageInputName": "fail"}, errorCode="raw DOM"),
		):
			with (
				self.subTest(malformed=malformed),
				self.assertRaisesRegex(
					LoaderError,
					"bundle.healthMismatch",
				),
			):
				installAndVerify(
					HealthSession(semantic=malformed),
					"window.loaded=true;",
					"2.6.73",
					"a" * 64,
					ImmediateCancel(),
					healthDeadline=0.001,
				)

	def test_post_install_bridge_and_semantic_nodes_are_rechecked(self) -> None:
		for session in (
			HealthSession(postInstallSemantic=False),
			HealthSession(postInstallBridge=1),
		):
			with (
				self.subTest(session=session),
				self.assertRaisesRegex(
					LoaderError,
					"bundle.healthMismatch",
				),
			):
				installAndVerify(
					session,
					"window.loaded=true;",
					"2.6.73",
					"a" * 64,
					ImmediateCancel(),
					healthDeadline=0.001,
				)

	def test_post_install_chat_list_loading_recovers_without_bundle_failure(self) -> None:
		session = PostInstallChatListSession((False, True))
		health, identifier = installAndVerify(
			session,
			"window.loaded=true;",
			"2.6.73",
			"a" * 64,
			ImmediateCancel(),
			healthDeadline=0.001,
		)

		self.assertEqual(health["state"], "ready")
		self.assertEqual(identifier, "registered")
		self.assertEqual(session.postInstallChecks, 2)

	def test_post_install_chat_list_loading_remains_cancellable(self) -> None:
		session = PostInstallChatListSession((False,))
		with self.assertRaisesRegex(LoaderError, "operation.cancelled"):
			installAndVerify(
				session,
				"window.loaded=true;",
				"2.6.73",
				"a" * 64,
				CancelAfterTwoStatusChecks(),
				healthDeadline=0.001,
			)
		self.assertEqual(session.postInstallChecks, 1)

	def test_readiness_gate_does_not_inject_until_whatsapp_shell_is_stable(self) -> None:
		sources = json.dumps(
			{
				"readiness": makeReadinessWrapper("a" * 64),
				"injection": makeInjectionWrapper(
					"window.loaded=true; if (globalThis.replaceDuringInjection) { side=makeSide(); "
					"globalThis.replaceDuringInjection=false; }",
					"a" * 64,
				),
			},
		)
		harness = textwrap.dedent(
			r"""
			const fs = require('fs');
			const sources = JSON.parse(fs.readFileSync(0, 'utf8'));
			let shellReady = false;
			let recognizedChatList = false;
			let readinessObserver = null;
			let readinessObserverOptions = null;
			const frames = [];
			const listeners = new Map();
			let chatList = {isConnected: true};
			const makeSide = () => ({
				isConnected: true,
				querySelector(selector) {
					return shellReady && recognizedChatList && selector.includes('[data-testid="chat-list"]')
						? chatList : null;
				}
			});
			let side = makeSide();
			const navigation = {isConnected: true};
			global.window = globalThis;
			window.top = window;
			global.location = {origin: 'https://web.whatsapp.com'};
			global.localStorage = {getItem() { return null; }};
			global.document = {
				readyState: 'loading',
				body: null,
				documentElement: {isConnected: true, getAttribute() { return ''; }},
				querySelector(selector) {
					if (!shellReady) return null;
					if (selector === 'div#side') return side;
					if (selector === '[data-testid="navbar-primary-section"]') return navigation;
					return null;
				},
				addEventListener(type, callback) { listeners.set(`document:${type}`, callback); },
				removeEventListener(type) { listeners.delete(`document:${type}`); }
			};
			window.addEventListener = (type, callback) => listeners.set(`window:${type}`, callback);
			window.removeEventListener = type => listeners.delete(`window:${type}`);
			global.MutationObserver = class {
				constructor(callback) {
					this.isReadinessObserver = !readinessObserver;
					if (this.isReadinessObserver) readinessObserver = callback;
				}
				observe(_target, options) {
					if (this.isReadinessObserver) readinessObserverOptions = options;
				}
				disconnect() {}
			};
			global.requestAnimationFrame = callback => { frames.push(callback); return frames.length; };
			global.cancelAnimationFrame = () => {};
			eval(sources.readiness);
			const earlyActivation = eval(sources.injection);
			const before = {state: globalThis.__whatsappWebPlusCompanionReadiness.state,
				loaded: Boolean(window.loaded), activated: earlyActivation};
			document.readyState = 'complete';
			document.body = {isConnected: true};
			shellReady = true;
			readinessObserver([]);
			while (frames.length) frames.shift()();
			const genericGrid = {state: globalThis.__whatsappWebPlusCompanionReadiness.state,
				loaded: Boolean(window.loaded)};
			recognizedChatList = true;
			if (readinessObserverOptions?.attributes &&
				readinessObserverOptions.attributeFilter?.includes('data-testid')) {
				readinessObserver([{type: 'attributes', attributeName: 'data-testid'}]);
			}
			while (frames.length) frames.shift()();
			const waitingFinished = {state: globalThis.__whatsappWebPlusCompanionReadiness.state,
				loaded: Boolean(window.loaded)};
			chatList = {isConnected: true};
			side = makeSide();
			const staleActivation = eval(sources.injection);
			const afterReplacement = {state: globalThis.__whatsappWebPlusCompanionReadiness.state,
				loaded: Boolean(window.loaded), activated: staleActivation};
			while (frames.length) frames.shift()();
			globalThis.replaceDuringInjection = true;
			const midInjectionActivation = eval(sources.injection);
			const afterMidInjectionReplacement = {
				state: globalThis.__whatsappWebPlusCompanionReadiness.state,
				loaded: Boolean(window.loaded), activated: midInjectionActivation};
			while (frames.length) frames.shift()();
			const activation = eval(sources.injection);
			console.log(JSON.stringify({before, genericGrid, waitingFinished, afterReplacement,
				afterMidInjectionReplacement, activation,
				loaded: Boolean(window.loaded), bridge: globalThis.__whatsappWebPlusCompanionBridge?.contractVersion,
				finalState: globalThis.__whatsappWebPlusCompanionReadiness.state,
				attributeFilter: readinessObserverOptions?.attributeFilter || []}));
			""",
		)
		result = subprocess.run(
			["node", "-e", harness],
			input=sources,
			text=True,
			capture_output=True,
			check=True,
		)
		value = json.loads(result.stdout)
		self.assertEqual(value["before"], {"state": "waiting", "loaded": False, "activated": False})
		self.assertEqual(value["genericGrid"], {"state": "waiting", "loaded": False})
		self.assertEqual(value["waitingFinished"], {"state": "ready", "loaded": False})
		self.assertEqual(value["afterReplacement"], {"state": "waiting", "loaded": False, "activated": False})
		self.assertEqual(
			value["afterMidInjectionReplacement"],
			{"state": "waiting", "loaded": True, "activated": False},
		)
		self.assertTrue(value["activation"])
		self.assertTrue(value["loaded"])
		self.assertEqual(value["bridge"], 2)
		self.assertEqual(value["finalState"], "ready")
		self.assertEqual(value["attributeFilter"], ["id", "data-testid", "role", "aria-label"])

	def test_wrong_userscript_version_is_not_accepted(self) -> None:
		with self.assertRaisesRegex(LoaderError, "bundle.healthMismatch"):
			installAndVerify(
				HealthSession("9.9.9"),
				"window.loaded=true;",
				"2.6.73",
				"a" * 64,
				ImmediateCancel(),
				healthDeadline=0.001,
			)

	def test_waiting_for_whatsapp_readiness_has_no_fixed_production_deadline_and_is_cancellable(self) -> None:
		with self.assertRaisesRegex(LoaderError, "operation.cancelled"):
			installAndVerify(
				WaitingHealthSession(),
				"window.loaded=true;",
				"2.6.73",
				"a" * 64,
				CancelAfterOneReadinessCheck(),
			)

	def test_stale_ready_health_during_renderer_loading_is_not_a_terminal_mismatch(self) -> None:
		with self.assertRaisesRegex(LoaderError, "operation.cancelled"):
			installAndVerify(
				StaleHealthWhileWaitingSession(),
				"window.loaded=true;",
				"2.6.73",
				"a" * 64,
				CancelAfterOneReadinessCheck(),
				healthDeadline=0.001,
			)

	def test_health_deadline_starts_after_injection_and_times_out_missing_health(self) -> None:
		session = NeverHealthySession()
		with self.assertRaisesRegex(LoaderError, "bundle.healthTimeout"):
			installAndVerify(
				session,
				"window.loaded=true;",
				"2.6.73",
				"a" * 64,
				ImmediateCancel(),
				healthDeadline=0.001,
			)
		self.assertTrue(session.activated)

	def test_injection_evaluation_and_timeout_errors_become_bundle_health_failures(self) -> None:
		for cdpCode, bundleCode, detail in (
			("cdp.evaluate", "bundle.failed", "injection.evaluate"),
			("cdp.timeout", "bundle.healthTimeout", "injection.timeout"),
		):
			with self.subTest(cdpCode=cdpCode), self.assertRaisesRegex(LoaderError, bundleCode) as raised:
				installAndVerify(
					FailingInjectionSession(cdpCode),
					"window.loaded=true;",
					"2.6.73",
					"a" * 64,
					ImmediateCancel(),
					healthDeadline=0.01,
				)
			self.assertEqual(raised.exception.safeDetail, detail)

	def test_cancellation_from_ready_status_prevents_injection(self) -> None:
		cancelEvent = threading.Event()
		session = CancelDuringReadyStatusSession(cancelEvent)
		with self.assertRaisesRegex(LoaderError, "operation.cancelled"):
			installAndVerify(
				session,
				"window.loaded=true;",
				"2.6.73",
				"a" * 64,
				cancelEvent,
				healthDeadline=0.01,
			)
		self.assertFalse(session.activated)

	def test_cancellation_wins_before_atomic_injection_submission(self) -> None:
		cancelEvent = PauseBeforeSubmissionEvent()
		session = HealthSession()
		errors: list[Exception] = []

		def install() -> None:
			try:
				installAndVerify(
					session,
					"window.loaded=true;",
					"2.6.73",
					"a" * 64,
					cancelEvent,
					healthDeadline=0.1,
				)
			except Exception as error:
				errors.append(error)

		worker = threading.Thread(target=install)
		worker.start()
		self.assertTrue(cancelEvent.atBoundary.wait(1.0))
		cancelEvent.set()
		cancelEvent.release.set()
		worker.join(1.0)

		self.assertFalse(worker.is_alive())
		self.assertEqual([str(error) for error in errors], ["operation.cancelled"])
		self.assertFalse(session.activated)

	def test_companion_announcements_use_cursor_and_preserve_metadata(self) -> None:
		session = AnnouncementSession(
			announcementBatch(
				[
					{
						"sequence": 8,
						"generation": 3,
						"sessionToken": "session-1",
						"context": "chat-2",
						"source": "status",
						"language": "id",
						"privacy": True,
						"text": "Tidak ada pesan",
					},
				],
			),
		)
		batch = readCompanionAnnouncements(session, 7, 3)
		self.assertIn("readSince(7,3)", session.expressions[0])
		self.assertNotIn(".take(", session.expressions[0])
		self.assertEqual(batch.sessionToken, "session-1")
		self.assertEqual(batch.generation, 3)
		self.assertEqual(batch.context, "chat-2")
		self.assertEqual(batch.entries[0].source, "status")
		self.assertEqual(batch.entries[0].language, "id")
		self.assertTrue(batch.entries[0].privacy)
		self.assertEqual(batch.entries[0].text, "Tidak ada pesan")

	def test_invalid_items_are_skipped_and_long_text_is_truncated_without_dropping_batch(self) -> None:
		longText = "x" * 2200
		batch = readCompanionAnnouncements(
			AnnouncementSession(
				announcementBatch(
					[
						{"sequence": True, "text": "invalid"},
						{
							"sequence": 2,
							"generation": 3,
							"source": "message-log",
							"language": "not a language",
							"privacy": False,
							"text": longText,
						},
						{
							"sequence": 3,
							"generation": 99,
							"source": "status",
							"language": "en",
							"privacy": False,
							"text": "wrong generation",
						},
					],
				),
			),
		)
		self.assertEqual(len(batch.entries), 1)
		self.assertEqual(batch.entries[0].language, "")
		self.assertEqual(len(batch.entries[0].text), 1800)
		self.assertTrue(batch.entries[0].text.endswith("…"))

	def test_entries_from_a_stale_session_or_context_are_not_delivered(self) -> None:
		batch = readCompanionAnnouncements(
			AnnouncementSession(
				announcementBatch(
					[
						{
							"sequence": 1,
							"generation": 3,
							"sessionToken": "session-1",
							"context": "chat-old",
							"source": "status",
							"language": "en",
							"privacy": False,
							"text": "Old chat",
						},
						{
							"sequence": 2,
							"generation": 3,
							"sessionToken": "session-old",
							"context": "chat-current",
							"source": "status",
							"language": "en",
							"privacy": False,
							"text": "Old renderer",
						},
						{
							"sequence": 3,
							"generation": 3,
							"sessionToken": "session-1",
							"context": "chat-current",
							"source": "status",
							"language": "en",
							"privacy": False,
							"text": "Current chat",
						},
					],
					context="chat-current",
				),
			),
		)

		self.assertEqual([entry.text for entry in batch.entries], ["Current chat"])

	def test_bridge_mutations_publish_metadata_and_privacy_change_invalidates_before_delivery(self) -> None:
		harness = textwrap.dedent(
			r"""
			const fs = require('fs');
			const source = fs.readFileSync(0, 'utf8');
			let observerCallback = null;
			class Element {
				constructor(selector, text = '') {
					this.selector = selector;
					this.textContent = text;
					this.nodeType = 1;
					this.parentElement = null;
					this.attrs = {};
					this.queryResult = null;
				}
				matches(selector) {
					return selector.split(',').some(part => {
						part = part.trim();
						return part === this.selector || (part === '[lang]' && Boolean(this.attrs.lang));
					});
				}
				closest(selector) {
					for (let node = this; node; node = node.parentElement) {
						if (node.matches(selector)) return node;
					}
					return null;
				}
				getAttribute(name) { return this.attrs[name] || ''; }
				querySelector() { return this.queryResult; }
			}
			const root = new Element('html');
			root.attrs.lang = 'id';
			const main = new Element('#main');
			const title = new Element('title', 'Chat A');
			main.queryResult = title;
			const status = new Element('#wa-plus-live-region[role="status"]');
			const log = new Element('#wa-plus-message-log[role="log"]');
			const alert = new Element('#wa-plus-settings-alert');
			const customAlert = new Element('#wa-plus-custom-text-error');
			status.parentElement = root;
			log.parentElement = root;
			alert.parentElement = root;
			customAlert.parentElement = root;
			let language = 'id';
			let privacy = 'false';
			global.localStorage = {
				getItem(key) {
					if (key === 'wa-plus-language') return language;
					if (key === 'wa-plus-privacy') return privacy;
					return null;
				}
			};
			global.crypto = require('node:crypto').webcrypto;
			global.document = {
				documentElement: root,
				querySelector(selector) {
					if (selector === '#main') return main;
					if (selector === '#wa-plus-live-region[role="status"]') return status;
					if (selector === '#wa-plus-settings-alert, #wa-plus-custom-text-error') return alert;
					return null;
				}
			};
			global.MutationObserver = class {
				constructor(callback) { observerCallback = callback; }
				observe() {}
			};
			eval(source);
			const bridge = global.__whatsappWebPlusCompanionBridge;
			if (!bridge || bridge.contractVersion !== 2) throw new Error('missing bridge v2');
			const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
			const startup = bridge.readSince(0, 0);
			if (!uuidPattern.test(startup.sessionToken) || !uuidPattern.test(startup.context)) {
				throw new Error('secure tokens');
			}
			if (startup.sessionToken === startup.context) throw new Error('token collision');
			status.textContent = 'Pesan status';
			observerCallback([{ target: status, addedNodes: [] }]);
			const first = bridge.readSince(0, 1);
			if (first.entries.length !== 1 || first.entries[0].source !== 'status') throw new Error('status');
			if (first.entries[0].language !== 'id' || first.entries[0].privacy !== false) throw new Error('metadata');
			if (first.entries[0].sessionToken !== first.sessionToken || first.entries[0].context !== first.context) {
				throw new Error('entry tokens');
			}
			title.textContent = 'Chat B';
			const chatInvalidated = bridge.readSince(first.latestSequence, first.generation);
			if (!chatInvalidated.invalidated || chatInvalidated.entries.length !== 0) throw new Error('chat invalidation');
			if (chatInvalidated.lastInvalidation !== 'chat-context-changed' ||
				chatInvalidated.context === first.context || chatInvalidated.context.includes('Chat')) {
				throw new Error('chat context token');
			}
			language = 'en';
			const languageInvalidated = bridge.readSince(first.latestSequence, chatInvalidated.generation);
			if (!languageInvalidated.invalidated || languageInvalidated.entries.length !== 0 ||
				languageInvalidated.lastInvalidation !== 'language-changed' ||
				languageInvalidated.context === chatInvalidated.context) {
				throw new Error('language invalidation');
			}
			privacy = 'true';
			const invalidated = bridge.readSince(first.latestSequence, languageInvalidated.generation);
			if (!invalidated.invalidated || invalidated.entries.length !== 0) throw new Error('privacy invalidation');
			if (invalidated.lastInvalidation !== 'privacy-changed' ||
				invalidated.context === languageInvalidated.context) throw new Error('privacy context token');
			alert.textContent = 'Pengaturan tidak dapat disimpan.';
			observerCallback([{ target: alert, addedNodes: [] }]);
			const alertBatch = bridge.readSince(first.latestSequence, invalidated.generation);
			if (alertBatch.entries.length !== 1 || alertBatch.entries[0].source !== 'alert') throw new Error('alert');
			if (alertBatch.entries[0].privacy !== true) throw new Error('privacy metadata');
			customAlert.textContent = 'Kesalahan teks kustom.';
			observerCallback([{ target: customAlert, addedNodes: [] }]);
			const customAlertBatch = bridge.readSince(alertBatch.latestSequence, alertBatch.generation);
			if (customAlertBatch.entries.length !== 1 || customAlertBatch.entries[0].source !== 'alert') throw new Error('custom alert');
			const node = new Element('message', 'x'.repeat(2200));
			node.parentElement = log;
			observerCallback([{ target: log, addedNodes: [node] }]);
			const logBatch = bridge.readSince(customAlertBatch.latestSequence, customAlertBatch.generation);
			if (logBatch.entries.length !== 1 || logBatch.entries[0].source !== 'message-log') throw new Error('log');
			if (logBatch.entries[0].text.length !== 1800) throw new Error('truncate');
			""",
		)
		completed = subprocess.run(
			["node", "-e", harness],
			input=_COMPANION_BRIDGE_SOURCE,
			text=True,
			capture_output=True,
			check=False,
		)
		self.assertEqual(completed.returncode, 0, completed.stderr)
		self.assertNotIn("Math.random", _COMPANION_BRIDGE_SOURCE)

	def test_scoped_invalidation_retains_other_source_from_prior_generation(self) -> None:
		batch = readCompanionAnnouncements(
			AnnouncementSession(
				announcementBatch(
					[
						{
							"sequence": 7,
							"generation": 2,
							"source": "status",
							"language": "id",
							"privacy": False,
							"text": "Status tetap berlaku",
						},
						{
							"sequence": 8,
							"generation": 2,
							"source": "message-log",
							"language": "id",
							"privacy": False,
							"text": "Log lama",
						},
					],
					generation=3,
					context="session-1:3",
					invalidated=True,
					lastInvalidation="message-log-reset",
					invalidatedSource="message-log",
				),
			),
			0,
			2,
		)

		self.assertEqual([entry.text for entry in batch.entries], ["Status tetap berlaku"])
		self.assertEqual(batch.entries[0].generation, 3)
		self.assertEqual(batch.entries[0].context, "session-1:3")
