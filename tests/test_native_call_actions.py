import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch

from _path import installPackagePath

installPackagePath()
from appModules.wwpCallSupport import CallAction, actions, diagnostics


def element(name="", cls="Pane", host=0, children=(), **overrides):
	return types.SimpleNamespace(
		**{
			"currentName": name,
			"currentClassName": cls,
			"currentProcessId": 10,
			"currentControlType": 50000 if cls == "Button" else 50033,
			"currentFrameworkId": "XAML",
			"currentIsEnabled": True,
			"currentIsOffscreen": False,
			"currentNativeWindowHandle": host,
			"children": list(children),
			**overrides,
		},
	)


class Walker:
	def __init__(self, root):
		self.next = {}

		def index(obj):
			for i, child in enumerate(obj.children):
				self.next[id(child)] = obj.children[i + 1] if i + 1 < len(obj.children) else None
				index(child)

		index(root)

	def GetFirstChildElement(self, obj):
		return obj.children[0] if obj.children else None

	def GetNextSiblingElement(self, obj):
		return self.next[id(obj)]


def tree():
	answer = element("Accept call", "Button")
	decline = element("Decline\u00a0call", "Button")
	host = element(cls="InputSiteWindowClass", host=200, children=[answer, decline])
	root = element(cls="WinUIDesktopWin32WindowClass", host=100, children=[host])
	return root, host, answer, decline


class NativeActionTests(unittest.TestCase):
	def setUp(self):
		self.root, self.host, self.answer, self.decline = tree()

	def find(self):
		return actions.findIncomingPair(self.root, Walker(self.root), 10, 50000)

	def test_observed_pair_and_child_host_invoke_once(self):
		pair = self.find()
		self.assertEqual([b.host for b in pair], [200, 200])
		for action in (CallAction.ANSWER, CallAction.DECLINE):
			pattern = Mock()
			self.assertTrue(
				actions.invokePair(
					pair,
					action,
					10,
					50000,
					contextValid=lambda: True,
					belongsToWindow=lambda h: h == 200,
					getInvoke=lambda el: pattern,
				),
			)
			pattern.Invoke.assert_called_once_with()

	def test_active_controls_require_end_call_same_host_and_invoke_only_requested(self):
		labels = {
			CallAction.CAMERA: "Toggle camera",
			CallAction.MUTE: "Toggle mute",
			CallAction.REACTIONS: "Reactions",
			CallAction.HAND: "Raise hand",
			CallAction.SHARE: "Screen share",
			CallAction.END: "End call",
		}
		for action, label in labels.items():
			with self.subTest(action=action):
				target = element(label, "Button")
				end = element("End call", "Button")
				self.host.children = [target] if action == CallAction.END else [end, target]
				pair = actions.findActiveControls(self.root, Walker(self.root), 10, 50000, action)
				self.assertIsNotNone(pair)
				pattern = Mock()
				getInvoke = Mock(return_value=pattern)
				self.assertTrue(
					actions.invokePair(
						pair,
						action,
						10,
						50000,
						contextValid=lambda: True,
						belongsToWindow=lambda h: h == 200,
						getInvoke=getInvoke,
					),
				)
				getInvoke.assert_called_once_with(target)
				pattern.Invoke.assert_called_once_with()

	def test_active_controls_reject_missing_anchor_duplicates_and_incoming_call(self):
		target = element("Toggle mute", "Button")
		end = element("End call", "Button")
		for children in (
			[target],
			[end, target, element("Toggle mute", "Button")],
			[end, target, self.answer],
			[end, element("Toggle mute Alice", "Button")],
		):
			self.host.children = children
			self.assertIsNone(
				actions.findActiveControls(self.root, Walker(self.root), 10, 50000, CallAction.MUTE),
			)
		self.host.children = [end]
		self.root.children.append(element(cls="InputSiteWindowClass", host=300, children=[target]))
		self.assertIsNone(
			actions.findActiveControls(self.root, Walker(self.root), 10, 50000, CallAction.MUTE),
		)

	def test_active_control_state_change_aborts_invocation(self):
		target = element("Mute", "ToggleButton", currentControlType=50000)
		self.host.children = [element("End call", "Button"), target]
		pair = actions.findActiveControls(self.root, Walker(self.root), 10, 50000, CallAction.MUTE)
		self.assertIsNotNone(pair)
		target.currentIsEnabled = False
		getInvoke = Mock()
		self.assertFalse(
			actions.invokePair(
				pair,
				CallAction.MUTE,
				10,
				50000,
				contextValid=lambda: True,
				belongsToWindow=lambda h: True,
				getInvoke=getInvoke,
			),
		)
		getInvoke.assert_not_called()

	def test_no_ambiguous_cross_host_disabled_foreign_or_end_call_pair(self):
		for attr, value in (
			("currentName", "End call"),
			("currentName", "Decline call Alice"),
			("currentIsEnabled", False),
			("currentIsOffscreen", True),
			("currentProcessId", 20),
			("currentFrameworkId", "Chrome"),
			("currentControlType", 50033),
		):
			with self.subTest(attr=attr, value=value):
				with patch.object(self.decline, attr, value):
					self.assertIsNone(self.find())
		self.host.children.append(element("Accept call", "Button"))
		self.assertIsNone(self.find())
		self.host.children = [self.answer]
		self.root.children.append(element(cls="InputSiteWindowClass", host=300, children=[self.decline]))
		self.assertIsNone(self.find())

	def test_search_limits_reject_partial_tree_even_when_pair_found(self):
		with patch.object(actions, "MAX_NODES", 2):
			with self.assertRaises(actions.IncompleteSearch):
				self.find()
		with self.assertRaises(actions.IncompleteSearch):
			actions.findIncomingPair(self.root, Walker(self.root), 10, 50000, clock=Mock(side_effect=[0, 1]))

	def test_changed_context_or_pair_never_invokes(self):
		pair = self.find()
		pattern = Mock()
		kwargs = dict(contextValid=lambda: True, belongsToWindow=lambda h: True, getInvoke=lambda el: pattern)
		for overrides in (
			{"contextValid": lambda: False},
			{"belongsToWindow": lambda h: False},
			{"getInvoke": lambda el: None},
			{"contextValid": Mock(side_effect=[True, False])},
		):
			self.assertFalse(actions.invokePair(pair, CallAction.ANSWER, 10, 50000, **(kwargs | overrides)))
		self.decline.currentName = "End call"
		self.assertFalse(actions.invokePair(pair, CallAction.ANSWER, 10, 50000, **kwargs))
		pattern.Invoke.assert_not_called()

	def test_foreground_changes_in_final_provider_getter(self):
		pair = self.find()
		pattern = Mock()
		original = actions.buttonAction
		context = {"valid": True, "reads": 0}

		def changingButtonAction(*args):
			context["reads"] += 1
			if context["reads"] == 3:
				context["valid"] = False
			return original(*args)

		with patch.object(actions, "buttonAction", side_effect=changingButtonAction):
			self.assertFalse(
				actions.invokePair(
					pair,
					CallAction.ANSWER,
					10,
					50000,
					contextValid=lambda: context["valid"],
					belongsToWindow=lambda h: True,
					getInvoke=lambda el: pattern,
				),
			)
		pattern.Invoke.assert_not_called()

	def test_invoke_exception_never_retried(self):
		pattern = Mock()
		with self.subTest("foreground changes during final provider reads"):
			self.assertFalse(
				actions.invokePair(
					self.find(),
					CallAction.ANSWER,
					10,
					50000,
					contextValid=Mock(side_effect=[True, True, False]),
					belongsToWindow=lambda host: True,
					getInvoke=lambda el: pattern,
				),
			)
			pattern.Invoke.assert_not_called()
		pattern = Mock()
		pattern.Invoke.side_effect = RuntimeError()
		with self.assertRaises(RuntimeError):
			actions.invokePair(
				self.find(),
				CallAction.DECLINE,
				10,
				50000,
				contextValid=lambda: True,
				belongsToWindow=lambda h: True,
				getInvoke=lambda el: pattern,
			)
		pattern.Invoke.assert_called_once_with()


class NativeActionRuntimeTests(unittest.TestCase):
	def setUp(self):
		self.root, self.host, self.answer, self.decline = tree()
		self.pattern = Mock()
		for button in (self.answer, self.decline):
			button.GetCurrentPattern = Mock(
				return_value=types.SimpleNamespace(QueryInterface=lambda _: self.pattern),
			)
		self.foreground = types.SimpleNamespace(
			processID=10,
			windowHandle=100,
			windowClassName="WinUIDesktopWin32WindowClass",
			appModule=types.SimpleNamespace(appName="whatsapp.root"),
		)
		self.api = types.SimpleNamespace(
			getForegroundObject=Mock(return_value=self.foreground),
			getFocusObject=Mock(return_value=types.SimpleNamespace(role="BUTTON", states=set())),
		)
		self.win = types.SimpleNamespace(
			getForegroundWindow=Mock(return_value=100),
			getKeyState=Mock(return_value=0),
			getWindowThreadProcessID=Mock(return_value=(10, 1)),
			VK_RMENU=165,
			isDescendantWindow=lambda root, host: (root, host) == (100, 200),
		)
		client = types.SimpleNamespace(
			ElementFromHandle=lambda hwnd: self.root,
			GetFocusedElement=lambda: getattr(self.api.getFocusObject(), "UIAElement", element()),
			RawViewWalker=Walker(self.root),
		)
		self.ui = types.SimpleNamespace(message=Mock())
		self.modules = {
			"api": self.api,
			"winUser": self.win,
			"ui": self.ui,
			"controlTypes": types.SimpleNamespace(
				Role=types.SimpleNamespace(EDITABLETEXT="EDIT"),
				State=types.SimpleNamespace(EDITABLE="EDITABLE"),
			),
			"scriptHandler": types.SimpleNamespace(getLastScriptRepeatCount=lambda: 0),
			"UIAHandler": types.SimpleNamespace(
				handler=types.SimpleNamespace(clientObject=client),
				UIA_ButtonControlTypeId=50000,
				UIA_InvokePatternId=10000,
				UIA_TogglePatternId=10015,
				IUIAutomationInvokePattern=object,
				IUIAutomationTogglePattern=object,
				UIA_LegacyIAccessiblePatternId=10018,
				IUIAutomationLegacyIAccessiblePattern=object,
			),
			"addonHandler": types.SimpleNamespace(initTranslation=lambda: None),
			"logHandler": types.SimpleNamespace(log=Mock()),
		}
		p = patch.dict(sys.modules, self.modules)
		p.start()
		self.addCleanup(p.stop)
		p = patch("builtins._", lambda t: t, create=True)
		p.start()
		self.addCleanup(p.stop)
		path = Path(__file__).parents[1] / "addon/appModules/wwpCallSupport/runtime.py"
		spec = importlib.util.spec_from_file_location("appModules.wwpCallSupport.runtime", path)
		self.runtime = importlib.util.module_from_spec(spec)
		spec.loader.exec_module(self.runtime)
		self.runtime.diagnosticsAllowed = lambda: True
		self.client = client
		self.realWithClient = self.runtime._withCallClient
		self.runtime._withCallClient = lambda work: work(client, self.modules["UIAHandler"])

		def immediate(work, finished):
			try:
				result = self.runtime._withCallClient(work)
			except Exception:
				result = "failed"
			finished(result)

		self.realDispatch = self.runtime._dispatchCallWorker
		self.runtime._dispatchCallWorker = immediate
		self.runtime._callOnMain = lambda function: function()
		self.gesture = Mock()

	def inventory(self):
		return self.runtime.captureControlInventory(100, 10, self.client, self.modules["UIAHandler"])

	def test_worker_owns_com_client_and_uninitializes_on_failure(self):
		calls = []
		owned = types.SimpleNamespace()
		com = types.SimpleNamespace(
			COINIT_MULTITHREADED=0,
			CLSCTX_INPROC_SERVER=1,
			CoInitializeEx=lambda flags: calls.append(("init", flags)),
			CoCreateInstance=Mock(return_value=owned),
			CoUninitialize=lambda: calls.append(("uninit",)),
		)
		uia = self.modules["UIAHandler"]
		with (
			patch.dict(sys.modules, {"comtypes": com}),
			patch.object(
				uia,
				"UIA",
				types.SimpleNamespace(
					CUIAutomation8=types.SimpleNamespace(
						_reg_clsid_="clsid",
						_com_interfaces_=[None, "interface"],
					),
				),
				create=True,
			),
		):

			def work(client, constants):
				self.assertIs(client, owned)
				self.assertIsNot(client, self.client)
				self.assertEqual(client.ConnectionTimeout, 1000)
				self.assertEqual(client.TransactionTimeout, 1000)
				raise RuntimeError("provider failed")

			self.assertEqual(self.realWithClient(work), "failed")
		self.assertEqual(calls, [("init", 0), ("uninit",)])

	def test_slow_provider_does_not_block_gui_or_spawn_more_workers(self):
		import threading

		entered = threading.Event()
		release = threading.Event()
		completed = threading.Event()
		callbacks = []
		threads = []

		def slowRoot(hwnd):
			threads.append(threading.get_ident())
			entered.set()
			release.wait(2)
			return self.root

		def dispatch(fn, *args):
			callbacks.append(lambda: fn(*args))
			completed.set()

		self.client.ElementFromHandle = slowRoot
		self.runtime._dispatchCallWorker = self.realDispatch
		with patch.dict(sys.modules, {"wx": types.SimpleNamespace(CallAfter=dispatch)}):
			try:
				self.runtime.performCallAction(CallAction.ANSWER, self.gesture)
				self.assertTrue(entered.wait(1))
				self.assertNotEqual(threads[0], threading.get_ident())
				self.assertFalse(completed.is_set())
				self.runtime.performCallAction(CallAction.DECLINE, self.gesture)
				self.assertEqual(len(threads), 1)
				self.runtime.cancelRecovery()
			finally:
				release.set()
			self.assertTrue(completed.wait(2))
			for callback in callbacks:
				callback()
		self.pattern.Invoke.assert_not_called()
		self.gesture.send.assert_not_called()
		self.ui.message.assert_not_called()
		self.assertFalse(self.runtime._restorePending)

	def test_expired_or_replaced_window_never_invokes(self):
		for expired in (True, False):
			with self.subTest(expired=expired):
				self.runtime._lastAttempt = (0, 0.0)
				pending = []
				with patch.object(
					self.runtime,
					"_dispatchCallWorker",
					side_effect=lambda w, f: pending.append((w, f)),
				):
					self.runtime.performCallAction(CallAction.ANSWER, self.gesture)
				work, finished = pending.pop()
				if expired:
					with patch.object(self.runtime.time, "monotonic", return_value=10**12):
						finished(self.runtime._withCallClient(work))
				else:
					self.win.getWindowThreadProcessID.return_value = (99, 1)
					finished(self.runtime._withCallClient(work))
		self.pattern.Invoke.assert_not_called()
		self.gesture.send.assert_not_called()

	def prepareCompact(self):
		self.answer.currentName = "Mute microphone"
		self.answer.currentClassName = "CheckBox"
		self.answer.currentControlType = 50002
		self.decline.currentName = "WhatsApp.PeerStreamVm"
		self.decline.currentClassName = "ListViewItem"
		self.decline.currentControlType = 50007
		self.pattern.CurrentDefaultAction = "Click"
		self.api.getFocusObject.return_value = types.SimpleNamespace(
			role="CHECKBOX",
			states=set(),
			UIAElement=self.answer,
			windowHandle=200,
		)

	def runRecovery(self, result=True, cancel=False, moved=False, restore=None):
		self.restore = restore or Mock(return_value=result)
		self.worker = None

		def schedule(work, finished):
			self.worker = lambda: finished(self.runtime._withCallClient(work))

		with (
			patch.dict(
				sys.modules,
				{
					"globalPlugins.whatsappWebPlusCompanion.callAvailability": types.SimpleNamespace(
						restoreCallView=self.restore,
					),
				},
			),
			patch.object(self.runtime, "_dispatchCallWorker", side_effect=schedule),
		):
			self.runtime.performCallAction(CallAction.END, self.gesture)
			self.runtime.performCallAction(CallAction.END, self.gesture)
			self.assertIsNotNone(self.worker)
			if cancel:
				self.runtime.cancelRecovery()
			if moved:
				self.win.getForegroundWindow.return_value = 999
			self.worker()

	def test_compact_hidden_mute_with_exact_id_can_restore(self):
		self.prepareCompact()
		self.answer.currentIsOffscreen = True
		self.answer.currentAutomationId = "MicMuteButton"
		self.runRecovery()
		self.restore.assert_called_once()

	def test_hidden_mute_without_exact_id_does_not_restore(self):
		from appModules.wwpCallSupport.compact import kind

		self.prepareCompact()
		self.answer.currentIsOffscreen = True
		self.answer.currentAutomationId = "other"
		self.assertIsNone(kind(self.answer, 10, allowHiddenMute=True))

	def test_compact_restore_once_no_call_action_or_replay(self):
		self.prepareCompact()
		self.runRecovery()
		self.restore.assert_called_once()
		self.pattern.DoDefaultAction.assert_not_called()
		self.pattern.Invoke.assert_not_called()
		self.pattern.Toggle.assert_not_called()
		self.gesture.send.assert_not_called()
		self.assertIn("Press the shortcut again", self.ui.message.call_args.args[0])

	def test_restore_is_announced_and_suppressed_shortcuts_explain_why(self):
		notice = "Restoring call controls. Release the shortcut keys."
		self.prepareCompact()
		spoken = []

		def pressDuringRestore(pid, hwnd, cancel):
			spoken.append([call.args[0] for call in self.ui.message.call_args_list])
			# Auto-repeat right after the notice stays quiet; a later press hears it again.
			self.runtime.performCallAction(CallAction.END, self.gesture)
			spoken.append(self.ui.message.call_count)
			self.runtime._lastRestoreNotice -= 10
			self.runtime.performCallAction(CallAction.END, self.gesture)
			spoken.append(self.ui.message.call_args.args[0])
			return True

		self.runRecovery(restore=Mock(side_effect=pressDuringRestore))
		self.restore.assert_called_once()
		self.assertEqual(spoken, [[notice], 1, notice])
		self.assertEqual(
			self.ui.message.call_args.args[0],
			"Call controls restored. Press the shortcut again.",
		)
		self.gesture.send.assert_not_called()
		self.assertFalse(self.runtime._restoreRunning)

	def test_pending_ordinary_action_suppresses_repeat_silently(self):
		pending = []
		with patch.object(self.runtime, "_dispatchCallWorker", side_effect=lambda w, f: pending.append(f)):
			self.runtime.performCallAction(CallAction.ANSWER, self.gesture)
			self.runtime.performCallAction(CallAction.DECLINE, self.gesture)
		self.assertEqual(len(pending), 1)
		self.ui.message.assert_not_called()
		self.gesture.send.assert_not_called()

	def test_compact_failure_never_replays_or_retries(self):
		self.prepareCompact()
		self.runRecovery(result=False)
		self.restore.assert_called_once()
		self.gesture.send.assert_not_called()
		self.pattern.Invoke.assert_not_called()
		self.assertIn("Could not restore", self.ui.message.call_args.args[0])

	def test_cancelled_restore_has_no_late_success(self):
		self.prepareCompact()
		self.runRecovery(cancel=True)
		self.ui.message.assert_not_called()
		self.restore.assert_not_called()
		self.assertFalse(self.runtime._restorePending)

	def test_focus_move_suppresses_late_restore_announcement(self):
		self.prepareCompact()
		self.runRecovery(moved=True)
		self.ui.message.assert_not_called()
		self.restore.assert_not_called()

	def test_compact_held_repeat_after_throttle_expires_still_does_not_restore(self):
		self.prepareCompact()
		self.runRecovery()
		with patch.object(self.runtime.time, "monotonic", return_value=self.runtime._lastRestore + 10):
			with patch.object(self.modules["scriptHandler"], "getLastScriptRepeatCount", return_value=1):
				self.runtime.performCallAction(CallAction.END, self.gesture)
		self.restore.assert_called_once()

	def test_compact_requires_unique_peer_same_host_and_complete_scan(self):
		from appModules.wwpCallSupport.compact import findCompact

		self.prepareCompact()
		self.host.children.append(element("WhatsApp.PeerStreamVm", "ListViewItem", currentControlType=50007))
		self.assertIsNone(findCompact(self.root, Walker(self.root), 10))
		self.host.children = [self.answer]
		self.root.children.append(element(cls="InputSiteWindowClass", host=300, children=[self.decline]))
		self.assertIsNone(findCompact(self.root, Walker(self.root), 10))
		self.assertIsNone(findCompact(self.root, Walker(self.root), 10, clock=Mock(side_effect=[0, 1])))

	def test_compact_hold_does_not_activate_expanded_window_but_new_press_does(self):
		self.prepareCompact()
		self.runtime.performCallAction(CallAction.END, self.gesture)
		self.answer.currentName = "Mute microphone"
		self.answer.currentClassName = "Button"
		self.answer.currentControlType = 50000
		self.decline.currentName = "End call"
		self.decline.currentClassName = "Button"
		self.decline.currentControlType = 50000
		# Expansion may replace the top-level window; held keys still must not activate it.
		self.foreground.windowHandle = 300
		self.win.getForegroundWindow.return_value = 300
		self.win.isDescendantWindow = lambda root, host: (root, host) == (300, 200)
		with patch.object(self.modules["scriptHandler"], "getLastScriptRepeatCount", return_value=1):
			self.runtime.performCallAction(CallAction.END, self.gesture)
		self.pattern.Invoke.assert_not_called()
		self.runtime.performCallAction(CallAction.END, self.gesture)
		self.pattern.Invoke.assert_called_once_with()

	def test_screen_share_start_stop_toggle_once_and_end_remains_invoke(self):
		for label in ("Start screen sharing", "Stop screen sharing"):
			self.runtime._lastAttempt = (0, 0.0)
			self.pattern.reset_mock()
			self.answer.currentName = label
			self.answer.currentClassName = "CheckBox"
			self.answer.currentControlType = 50002
			self.answer.currentAutomationId = "NewScreenShareButton"
			self.decline.currentName = "End call"
			self.runtime.performCallAction(CallAction.SHARE, self.gesture)
			self.pattern.Toggle.assert_called_once_with()
			self.pattern.Invoke.assert_not_called()
			self.runtime.performCallAction(CallAction.END, self.gesture)
			self.pattern.Invoke.assert_called_once_with()
			item = next(x for x in self.inventory()["recognized"] if x["action"] == "share")
			self.assertEqual(item["label"], label.casefold())
		self.ui.message.assert_not_called()
		self.gesture.send.assert_not_called()

	def test_screen_share_rejects_other_checkbox_id_class_or_name(self):
		self.answer.currentName = "Start screen sharing"
		self.answer.currentClassName = "CheckBox"
		self.answer.currentControlType = 50002
		self.answer.currentAutomationId = "NewScreenShareButton"
		self.decline.currentName = "End call"
		for attr, value in (
			("currentAutomationId", "StopSharingButton"),
			("currentAutomationId", "AudioSharingSwitch"),
			("currentClassName", "ToggleSwitch"),
			("currentName", "Start screen sharing Alice"),
			("currentIsEnabled", False),
		):
			with patch.object(self.answer, attr, value):
				self.runtime.performCallAction(CallAction.SHARE, self.gesture)
		self.pattern.Toggle.assert_not_called()
		self.pattern.Invoke.assert_not_called()

	def prepareReact(self):
		self.answer.currentName = "React"
		self.answer.currentClassName = "CheckBox"
		self.answer.currentControlType = 50002
		self.answer.currentAutomationId = "NewReactionButton"
		self.decline.currentName = "End call"

	def test_react_checkbox_toggles_once_without_invoking_end_or_moving_focus(self):
		self.prepareReact()
		self.runtime.performCallAction(CallAction.REACTIONS, self.gesture)
		self.runtime.performCallAction(CallAction.REACTIONS, self.gesture)
		self.pattern.Toggle.assert_called_once_with()
		self.pattern.Invoke.assert_not_called()
		self.answer.GetCurrentPattern.assert_called_once_with(10015)
		self.decline.GetCurrentPattern.assert_not_called()
		self.gesture.send.assert_not_called()
		self.ui.message.assert_not_called()

	def test_react_rejects_wrong_identity_disabled_or_offscreen(self):
		self.prepareReact()
		for attr, value in (
			("currentName", "React Alice"),
			("currentAutomationId", "OtherCheckbox"),
			("currentClassName", "Button"),
			("currentControlType", 50000),
			("currentIsEnabled", False),
			("currentIsOffscreen", True),
		):
			with patch.object(self.answer, attr, value):
				self.runtime.performCallAction(CallAction.REACTIONS, self.gesture)
		self.pattern.Toggle.assert_not_called()
		self.pattern.Invoke.assert_not_called()
		self.assertEqual(self.gesture.send.call_count, 6)

	def test_react_missing_or_failing_toggle_never_falls_back(self):
		self.prepareReact()
		self.answer.GetCurrentPattern.return_value = None
		self.runtime.performCallAction(CallAction.REACTIONS, self.gesture)
		self.pattern.Toggle.assert_not_called()
		self.runtime._lastAttempt = (0, 0.0)
		self.answer.GetCurrentPattern.return_value = types.SimpleNamespace(
			QueryInterface=lambda _: self.pattern,
		)
		self.pattern.Toggle.side_effect = RuntimeError("uncertain")
		self.runtime.performCallAction(CallAction.REACTIONS, self.gesture)
		self.pattern.Toggle.assert_called_once_with()
		self.pattern.Invoke.assert_not_called()
		self.gesture.send.assert_not_called()
		self.assertEqual(self.ui.message.call_count, 2)

	def test_react_identity_change_during_pattern_acquisition_aborts(self):
		self.prepareReact()

		def changed(patternId):
			self.answer.currentAutomationId = "OtherCheckbox"
			return types.SimpleNamespace(QueryInterface=lambda _: self.pattern)

		self.answer.GetCurrentPattern.side_effect = changed
		self.runtime.performCallAction(CallAction.REACTIONS, self.gesture)
		self.pattern.Toggle.assert_not_called()
		self.pattern.Invoke.assert_not_called()

	def test_react_inventory_includes_checkbox_without_activation(self):
		self.prepareReact()
		result = self.inventory()
		item = next(x for x in result["recognized"] if x["action"] == "reactions")
		self.assertEqual(item["uiaClass"], "CheckBox")
		self.assertEqual(item["automationId"], "NewReactionButton")
		self.pattern.Toggle.assert_not_called()
		self.pattern.Invoke.assert_not_called()

	def test_camera_word_order_labels_invoke_camera_not_end_call(self):
		for label in ("Turn on camera", "Turn off camera", "Turn\u00a0on camera"):
			with self.subTest(label=label):
				self.runtime._lastAttempt = (0, 0.0)
				self.pattern.reset_mock()
				self.answer.GetCurrentPattern.reset_mock()
				self.decline.GetCurrentPattern.reset_mock()
				self.answer.currentName = label
				self.answer.currentAutomationId = "NewVideoMuteButton"
				self.decline.currentName = "End call"
				self.runtime.performCallAction(CallAction.CAMERA, self.gesture)
				self.pattern.Invoke.assert_called_once_with()
				self.answer.GetCurrentPattern.assert_called_once()
				self.decline.GetCurrentPattern.assert_not_called()
				inventory = self.inventory()
				self.assertIn("camera", [item["action"] for item in inventory["recognized"]])
		self.gesture.send.assert_not_called()

	def test_active_runtime_invokes_mute_only(self):
		self.answer.currentName = "Toggle mute"
		self.decline.currentName = "End call"
		self.runtime.performCallAction(CallAction.MUTE, self.gesture)
		self.pattern.Invoke.assert_called_once_with()
		self.answer.GetCurrentPattern.assert_called_once()
		self.decline.GetCurrentPattern.assert_not_called()
		self.gesture.send.assert_not_called()

	def test_distinct_call_actions_are_not_suppressed_as_key_repeat(self):
		self.answer.currentName = "Toggle mute"
		self.decline.currentName = "End call"
		self.runtime.performCallAction(CallAction.MUTE, self.gesture)
		self.runtime.performCallAction(CallAction.END, self.gesture)
		self.assertEqual(self.pattern.Invoke.call_count, 2)

	def test_control_inventory_is_read_only_and_omits_unknown_names(self):
		self.answer.currentName = "Private caller Alice"
		self.decline.currentName = "End call"
		result = self.inventory()
		self.assertEqual(result["status"], "complete")
		self.assertEqual([x["action"] for x in result["recognized"]], ["end-call"])
		self.assertNotIn("Alice", str(result))
		self.pattern.Invoke.assert_not_called()
		self.answer.GetCurrentPattern.assert_called()

	def test_control_inventory_reports_incomplete_search(self):
		with patch.object(diagnostics, "MAX_NODES", 1):
			result = self.inventory()
		self.assertEqual(result["status"], "partial")
		self.pattern.Invoke.assert_not_called()

	def test_unmapped_camera_is_reported_but_never_authorizes_an_action(self):
		self.answer.currentName = "Private unknown label"
		self.answer.currentAutomationId = "NewVideoMuteButton"
		self.answer.currentIsEnabled = False
		self.answer.currentIsOffscreen = True
		self.decline.currentName = "End call"
		result = self.inventory()
		self.assertEqual(result["status"], "complete")
		unknown = result["unmapped"][0]
		self.assertEqual(unknown["automationId"], "NewVideoMuteButton")
		self.assertEqual(unknown["label"], "unmapped")
		self.assertFalse(unknown["enabled"])
		self.assertTrue(unknown["offscreen"])
		self.assertTrue(unknown["invoke"])
		self.assertNotIn("Private", str(result))
		self.runtime.performCallAction(CallAction.CAMERA, self.gesture)
		self.pattern.Invoke.assert_not_called()
		self.gesture.send.assert_called_once_with()

	def test_inventory_pattern_errors_are_independent(self):
		self.answer.GetCurrentPattern.side_effect = [RuntimeError("private"), object()]
		result = self.inventory()
		item = next(x for x in result["recognized"] if x["action"] == "answer")
		self.assertEqual(item["invoke"], "unavailable")
		self.assertTrue(item["toggle"])
		self.assertNotIn("private", str(result))

	def test_inventory_skips_foreign_process_and_obeys_time_budget(self):
		self.answer.currentProcessId = 99
		result = self.inventory()
		self.assertEqual(len(result["recognized"]), 1)
		self.answer.GetCurrentPattern.assert_not_called()
		result = diagnostics.collectInventory(
			self.root,
			Walker(self.root),
			10,
			50000,
			10000,
			10015,
			clock=Mock(side_effect=[0, 1]),
		)
		self.assertEqual(result["status"], "partial")
		self.assertEqual(result["recognized"], [])

	def test_success_preserves_focus_and_debounces(self):
		self.runtime.performCallAction(CallAction.ANSWER, self.gesture)
		self.runtime.performCallAction(CallAction.ANSWER, self.gesture)
		self.pattern.Invoke.assert_called_once_with()
		self.gesture.send.assert_not_called()
		self.ui.message.assert_not_called()

	def test_outside_whatsapp_editable_altgr_or_locked_passes_through(self):
		cases = [
			(self.foreground.appModule, "appName", "notepad"),
			(self.foreground, "windowClassName", "Chrome_WidgetWin_1"),
			(self.win, "getKeyState", lambda vk: 0x8000),
			(self.runtime, "diagnosticsAllowed", lambda: False),
			(self.api, "getFocusObject", lambda: types.SimpleNamespace(role="EDIT", states=set())),
		]
		for obj, name, value in cases:
			with patch.object(obj, name, value):
				self.runtime.performCallAction(CallAction.DECLINE, self.gesture)
		self.assertEqual(self.gesture.send.call_count, len(cases))
		self.pattern.Invoke.assert_not_called()

	def test_missing_pair_passes_through_and_failed_invoke_does_not(self):
		self.decline.currentName = "End call"
		self.runtime.performCallAction(CallAction.DECLINE, self.gesture)
		self.gesture.send.assert_called_once_with()
		self.gesture.reset_mock()
		self.decline.currentName = "Decline call"
		self.pattern.Invoke.side_effect = RuntimeError()
		self.runtime.performCallAction(CallAction.DECLINE, self.gesture)
		self.gesture.send.assert_not_called()
		self.ui.message.assert_called_once()

	def test_foreground_change_during_discovery_aborts(self):
		self.win.getForegroundWindow.side_effect = [100, 999]
		self.runtime.performCallAction(CallAction.ANSWER, self.gesture)
		self.pattern.Invoke.assert_not_called()
		self.gesture.send.assert_not_called()


class CachedDiscoveryTests(unittest.TestCase):
	def setUp(self):
		from appModules.wwpCallSupport import discoveryCache

		self.cache = discoveryCache
		self.root, self.host, self.answer, self.end = tree()
		self.end.currentName = "End call"
		self.answer.currentName = "Stop screen sharing"
		self.answer.currentControlType = 50002
		self.answer.currentClassName = "CheckBox"
		self.answer.currentAutomationId = "NewScreenShareButton"
		self.request = types.SimpleNamespace(AddProperty=Mock())
		self.uia = types.SimpleNamespace(
			TreeScope_Element=1,
			AutomationElementMode_Full=0,
			**{"UIA_" + name + "PropertyId": i for i, name in enumerate(discoveryCache.PROPERTIES)},
		)

		def snapshot(el):
			if el is None:
				return None
			for name in discoveryCache.PROPERTIES:
				setattr(el, "cached" + name, getattr(el, "current" + name, ""))
			return el

		walker = Walker(self.root)
		walker.GetFirstChildElementBuildCache = lambda el, req: snapshot(walker.GetFirstChildElement(el))
		walker.GetNextSiblingElementBuildCache = lambda el, req: snapshot(walker.GetNextSiblingElement(el))
		self.root.BuildUpdatedCache = lambda req: snapshot(self.root)
		self.client = types.SimpleNamespace(CreateCacheRequest=lambda: self.request, RawViewWalker=walker)

	def test_cache_keeps_full_tree_and_returns_live_controls_for_final_validation(self):
		root, walker = self.cache.cachedTraversal(self.client, self.root, self.uia)
		pair = actions.findActiveControls(root, walker, 10, 50000, CallAction.SHARE)
		self.assertIs(pair[1].element, self.answer)
		self.assertEqual(self.request.TreeScope, 1)
		self.assertEqual(self.request.AutomationElementMode, 0)
		self.assertEqual(self.request.AddProperty.call_count, 9)
		self.answer.currentIsEnabled = False
		pattern = Mock()
		self.assertFalse(
			actions.invokePair(
				pair,
				CallAction.SHARE,
				10,
				50000,
				contextValid=lambda: True,
				belongsToWindow=lambda h: True,
				getInvoke=lambda el: pattern,
				getToggle=lambda el: pattern,
			),
		)
		pattern.Toggle.assert_not_called()

	def test_cached_discovery_rejects_partial_results_and_setup_falls_back(self):
		root, walker = self.cache.cachedTraversal(self.client, self.root, self.uia)
		with patch.object(actions, "MAX_NODES", 2):
			with self.assertRaises(actions.IncompleteSearch):
				actions.findActiveControls(root, walker, 10, 50000, CallAction.END)
		self.client.CreateCacheRequest = Mock(side_effect=RuntimeError())
		root, walker = self.cache.cachedTraversal(self.client, self.root, self.uia)
		self.assertIs(root, self.root)
		self.assertIs(walker, self.client.RawViewWalker)

	def test_cached_properties_do_not_fall_back_to_live_reads(self):
		class Provider:
			cachedName = "End call"

			@property
			def currentName(self):
				raise AssertionError("Discovery must use prefetched properties")

		self.assertEqual(self.cache.CachedElement(Provider()).currentName, "End call")
