"""Custom call aliases must preserve the native call authorization gates."""

import copy
import sys
import types
import unittest
from unittest.mock import Mock, patch

from _path import installPackagePath

installPackagePath()
from appModules.wwpCallSupport import CallAction, actions, compact, labels
from test_native_call_actions import Walker, element, tree


class Config(dict):
	def __init__(self):
		super().__init__({labels.SECTION: {action.value: "" for action in CallAction}})
		self.spec = {}
		self.profiles = [self]
		self.saved = None
		self.save = Mock(side_effect=self._persist)

	def _persist(self):
		self.saved = copy.deepcopy(dict(self))


class CallLabelTests(unittest.TestCase):
	def setUp(self):
		self.conf = Config()
		self.state = types.SimpleNamespace(shouldWriteToDisk=Mock(return_value=True))
		self.modules = {
			"config": types.SimpleNamespace(conf=self.conf),
			"NVDAState": self.state,
		}
		self.patcher = patch.dict(sys.modules, self.modules)
		self.patcher.start()
		self.addCleanup(self.patcher.stop)
		labels._compiled.cache_clear()
		self.addCleanup(labels._compiled.cache_clear)

	def save(self, **overrides):
		labels.saveOverrides(overrides)

	def test_defaults_and_multiline_round_trip_survive_runtime_reload(self):
		self.assertEqual(labels.loadOverrides(), {action.value: "" for action in CallAction})
		self.assertIn("react", labels.defaultLabels(CallAction.REACTIONS))
		self.save(answer="  Responder llamada  \nRESPONDER LLAMADA\nAccepter l’appel", mute="Silenciar")
		self.assertEqual(labels.loadOverrides()["answer"], "Responder llamada\nAccepter l’appel")
		self.assertIn(labels.SECTION, self.conf.spec)
		self.conf.save.assert_called_once_with()
		self.conf[labels.SECTION] = copy.deepcopy(self.conf.saved[labels.SECTION])
		labels._compiled.cache_clear()
		self.assertEqual(labels.buttonAction("RESPONDER\u00a0LLAMADA"), CallAction.ANSWER)
		self.assertEqual(labels.buttonAction("Accept call"), CallAction.ANSWER)
		self.assertIsNone(labels.buttonAction("Responder llamada Alice"))

	def test_all_actions_get_exact_custom_aliases_and_reset_preserves_defaults(self):
		labels.saveOverrides({action.value: f"custom {action.value}" for action in CallAction})
		for action in CallAction:
			self.assertEqual(labels.buttonAction(f"CUSTOM {action.value}"), action)
		self.save()
		for action in CallAction:
			self.assertIsNone(labels.buttonAction(f"custom {action.value}"))
		self.assertEqual(labels.buttonAction("End call"), CallAction.END)

	def test_conflicts_limits_and_bad_types_do_not_mutate_or_save(self):
		for draft in (
			{"answer": "Decline\u00a0CALL"},
			{"answer": "Duplicated", "decline": "duplicated"},
			{"answer": "React"},
			{"mute": "Start screen sharing"},
			{"answer": "x" * 129},
			{"answer": "\n".join(str(n) for n in range(21))},
			{"answer": "a\x00b"},
			{"answer": 7},
			{"unknown": "new label"},
		):
			with self.subTest(draft=draft), self.assertRaises(labels.ValidationError):
				labels.saveOverrides(draft)
		self.conf.save.assert_not_called()
		self.assertTrue(all(value == "" for value in labels.loadOverrides().values()))

	def test_save_failure_rolls_back_memory_and_matching(self):
		self.save(answer="Responder")
		self.assertEqual(labels.buttonAction("Responder"), CallAction.ANSWER)
		before = labels.loadOverrides()
		self.conf.save.side_effect = OSError("disk full")
		with self.assertRaises(OSError):
			self.save(answer="Accepter")
		self.assertEqual(labels.loadOverrides(), before)
		self.assertEqual(labels.buttonAction("Responder"), CallAction.ANSWER)
		self.assertIsNone(labels.buttonAction("Accepter"))

	def test_secure_session_refuses_writes_before_mutation(self):
		self.state.shouldWriteToDisk.return_value = False
		with self.assertRaises(PermissionError):
			self.save(answer="Responder")
		self.conf.save.assert_not_called()
		self.assertTrue(all(value == "" for value in labels.loadOverrides().values()))

	def test_corrupt_settings_report_load_failure_and_runtime_uses_defaults(self):
		self.conf[labels.SECTION]["answer"] = "End call"
		with self.assertRaises(labels.ValidationError):
			labels.loadOverrides()
		with self.assertRaises(labels.ValidationError):
			self.save(answer="Responder")
		self.conf.save.assert_not_called()
		self.assertEqual(self.conf[labels.SECTION]["answer"], "End call")
		self.assertEqual(labels.buttonAction("End call"), CallAction.END)
		self.assertIsNone(labels.buttonAction("Responder"))
		self.conf[labels.SECTION]["answer"] = ["unhashable"]
		self.assertIsNone(labels.buttonAction("Responder"))

	def test_profile_switch_does_not_redirect_labels_and_reset_uses_current_memory(self):
		self.save(answer="Responder")
		self.assertEqual(labels.buttonAction("Responder"), CallAction.ANSWER)
		triggered = {labels.SECTION: {"answer": "Accepter"}}
		self.conf.profiles.append(triggered)
		self.assertEqual(labels.buttonAction("Responder"), CallAction.ANSWER)
		self.assertIsNone(labels.buttonAction("Accepter"))
		self.save(answer="Answer custom")
		self.assertEqual(triggered[labels.SECTION]["answer"], "Accepter")
		self.conf.profiles.pop()
		self.assertEqual(labels.buttonAction("Answer custom"), CallAction.ANSWER)
		self.conf[labels.SECTION]["answer"] = ""
		self.assertIsNone(labels.buttonAction("Answer custom"))
		self.assertEqual(self.conf.save.call_count, 2)

	def test_incoming_custom_pair_preserves_process_host_and_control_gates(self):
		self.save(answer="Responder", decline="Rechazar")
		root, host, answer, decline = tree()
		answer.currentName, decline.currentName = "RESPONDER", "Rechazar"
		self.assertIsNotNone(actions.findIncomingPair(root, Walker(root), 10, 50000))
		for attr, value in (
			("currentProcessId", 20),
			("currentFrameworkId", "Chrome"),
			("currentClassName", "Text"),
			("currentControlType", 50002),
			("currentIsEnabled", False),
			("currentIsOffscreen", True),
		):
			with self.subTest(attr=attr), patch.object(answer, attr, value):
				self.assertIsNone(actions.findIncomingPair(root, Walker(root), 10, 50000))
		host.children.remove(decline)
		root.children.append(element(cls="InputSiteWindowClass", host=300, children=[decline]))
		self.assertIsNone(actions.findIncomingPair(root, Walker(root), 10, 50000))

	def test_active_custom_controls_and_checkbox_ids_remain_required(self):
		self.save(**{"reactions": "Reaccionar", "share": "Compartir", "end-call": "Terminar"})
		root, host, _answer, _decline = tree()
		end = element("Terminar", "Button")
		for action, name, automationId in (
			(CallAction.REACTIONS, "Reaccionar", "NewReactionButton"),
			(CallAction.SHARE, "Compartir", "NewScreenShareButton"),
		):
			target = element(name, "CheckBox", currentControlType=50002, currentAutomationId=automationId)
			host.children = [end, target]
			pair = actions.findActiveControls(root, Walker(root), 10, 50000, action)
			self.assertIsNotNone(pair)
			pattern = Mock()
			getInvoke = Mock()
			self.assertTrue(
				actions.invokePair(
					pair,
					action,
					10,
					50000,
					contextValid=lambda: True,
					belongsToWindow=lambda h: h == 200,
					getInvoke=getInvoke,
					getToggle=lambda el: pattern,
				)
			)
			pattern.Toggle.assert_called_once_with()
			getInvoke.assert_not_called()
			target.currentAutomationId = "OtherCheckbox"
			self.assertIsNone(actions.findActiveControls(root, Walker(root), 10, 50000, action))
			host.children = [target]
			self.assertIsNone(actions.findActiveControls(root, Walker(root), 10, 50000, action))

	def test_changed_alias_during_pattern_acquisition_aborts_invocation(self):
		self.save(answer="Responder", decline="Rechazar")
		root, _host, answer, decline = tree()
		answer.currentName, decline.currentName = "Responder", "Rechazar"
		pair = actions.findIncomingPair(root, Walker(root), 10, 50000)
		pattern = Mock()

		def getInvoke(el):
			self.save()
			return pattern

		self.assertFalse(
			actions.invokePair(
				pair,
				CallAction.ANSWER,
				10,
				50000,
				contextValid=lambda: True,
				belongsToWindow=lambda h: h == 200,
				getInvoke=getInvoke,
			)
		)
		pattern.Invoke.assert_not_called()

	def test_custom_compact_mute_requires_technical_peer_and_rejects_expanded_alias(self):
		self.save(mute="Silenciar", **{"end-call": "Terminar"})
		root, host, _answer, _decline = tree()
		peer = element(compact.PEER_NAME, "ListViewItem", currentControlType=50007)
		mute = element("Silenciar", "CheckBox", currentControlType=50002)
		host.children = [peer, mute]
		candidate = compact.findCompact(root, Walker(root), 10)
		self.assertIsNotNone(candidate)
		pattern = Mock(CurrentDefaultAction="Click")
		self.assertTrue(
			compact.restore(
				candidate,
				10,
				contextValid=lambda: True,
				belongsToWindow=lambda h: h == 200,
				getLegacy=lambda el: pattern,
			)
		)
		pattern.DoDefaultAction.assert_called_once_with()
		with patch.object(peer, "currentName", "Silenciar"):
			self.assertIsNone(compact.findCompact(root, Walker(root), 10))
		host.children.append(element("Terminar", "Button"))
		self.assertIsNone(compact.findCompact(root, Walker(root), 10))

	def test_reentering_builtins_does_not_broaden_observed_control_types(self):
		self.save(reactions="React", mute="Mute", share="Start screen sharing")
		self.assertIsNone(actions.buttonAction(element("React", "Button"), 10, 50000))
		self.assertIsNone(compact.kind(element("Mute", "CheckBox", currentControlType=50002), 10))
		self.assertIsNone(actions.buttonAction(element("Start screen sharing", "Button"), 10, 50000))
