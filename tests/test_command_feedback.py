import sys
import types
import unittest
from enum import IntEnum
from unittest.mock import Mock, patch

from _path import installPackagePath

installPackagePath()
from globalPlugins.whatsappWebPlusCompanion import commandFeedback


class FeedbackTests(unittest.TestCase):
	def setUp(self):
		class Modes(IntEnum):
			off = 0
			beeps = 1
			talk = 2
			onDemand = 3

		self.modes = Modes
		self.state = types.SimpleNamespace(speechMode=Modes.onDemand)
		self.speech = types.SimpleNamespace(
			SpeechMode=Modes,
			getState=lambda: self.state,
			setSpeechMode=Mock(side_effect=lambda mode: setattr(self.state, "speechMode", mode)),
		)
		self.delivered = []
		self.ui = types.SimpleNamespace(
			message=Mock(side_effect=lambda text: self.delivered.append((text, self.state.speechMode))),
		)

	def test_late_command_result_uses_talk_only_during_message(self):
		with patch.dict(sys.modules, {"speech": self.speech, "ui": self.ui}):
			commandFeedback.message("operation finished")
		self.assertEqual(self.delivered, [("operation finished", self.modes.talk)])
		self.assertEqual(self.state.speechMode, self.modes.onDemand)
		self.ui.message.assert_called_once()

	def test_restores_on_demand_after_message_failure(self):
		self.ui.message.side_effect = RuntimeError("provider failed")
		with patch.dict(sys.modules, {"speech": self.speech, "ui": self.ui}):
			with self.assertRaises(RuntimeError):
				commandFeedback.message("result")
		self.assertEqual(self.state.speechMode, self.modes.onDemand)

	def test_off_beeps_and_talk_are_unchanged(self):
		for mode in (self.modes.off, self.modes.beeps, self.modes.talk):
			self.state.speechMode = mode
			with patch.dict(sys.modules, {"speech": self.speech, "ui": self.ui}):
				commandFeedback.message("result")
			self.assertEqual(self.state.speechMode, mode)
		self.speech.setSpeechMode.assert_not_called()
