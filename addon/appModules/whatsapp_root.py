"""Contextual native WhatsApp call commands."""

import addonHandler
import appModuleHandler
from scriptHandler import script

from .wwpCallSupport import CallAction, runtime

try:
	from nvdaBuiltin.appModules.whatsapp_root import AppModule as _WhatsAppBase
except ModuleNotFoundError as error:
	# NVDA before 2026.2 has no built-in WebView2 WhatsApp module.
	# Do not hide a broken dependency inside an existing built-in module.
	if error.name != "nvdaBuiltin.appModules.whatsapp_root":
		raise
	_WhatsAppBase = appModuleHandler.AppModule

addonHandler.initTranslation()


class AppModule(_WhatsAppBase):
	scriptCategory = _("WhatsApp Companion")

	@script(description=_("Answer native WhatsApp call"), gesture="kb:control+alt+a", speakOnDemand=True)
	def script_answerNativeCall(self, gesture):
		runtime.performCallAction(CallAction.ANSWER, gesture)

	@script(description=_("Decline native WhatsApp call"), gesture="kb:control+alt+d", speakOnDemand=True)
	def script_declineNativeCall(self, gesture):
		runtime.performCallAction(CallAction.DECLINE, gesture)

	@script(
		description=_("Toggle native WhatsApp call camera"),
		gesture="kb:control+alt+v",
		speakOnDemand=True,
	)
	def script_toggleNativeCallCamera(self, gesture):
		runtime.performCallAction(CallAction.CAMERA, gesture)

	@script(description=_("Toggle native WhatsApp call mute"), gesture="kb:control+alt+m", speakOnDemand=True)
	def script_toggleNativeCallMute(self, gesture):
		runtime.performCallAction(CallAction.MUTE, gesture)

	@script(
		description=_("Open native WhatsApp call reactions"),
		gesture="kb:control+alt+r",
		speakOnDemand=True,
	)
	def script_nativeCallReactions(self, gesture):
		runtime.performCallAction(CallAction.REACTIONS, gesture)

	@script(
		description=_("Raise or lower hand in native WhatsApp call"),
		gesture="kb:control+alt+h",
		speakOnDemand=True,
	)
	def script_raiseNativeCallHand(self, gesture):
		runtime.performCallAction(CallAction.HAND, gesture)

	@script(
		description=_("Start or stop screen sharing in native WhatsApp call"),
		gesture="kb:control+alt+s",
		speakOnDemand=True,
	)
	def script_nativeCallScreenShare(self, gesture):
		runtime.performCallAction(CallAction.SHARE, gesture)

	@script(description=_("End native WhatsApp call"), gesture="kb:control+alt+w", speakOnDemand=True)
	def script_endNativeCall(self, gesture):
		runtime.performCallAction(CallAction.END, gesture)

	@script(description=_("Capture native WhatsApp call diagnostics"), speakOnDemand=True)
	def script_captureNativeCallDiagnostics(self, gesture):
		runtime.captureDiagnostics()
