import addonHandler
import braille
from collections.abc import Callable
import config
import globalVars
import globalPluginHandler
import gui
from logHandler import log
import NVDAState
import re
import speech
import threading
import ui
import wx
from scriptHandler import script
from speech.commands import LangChangeCommand
from typing import Protocol

from .announcements import BrailleMessageQueue, ScheduledCall
from .cleanup import forceCloseOperation
from .controller import Controller
from .dialogs import MessageDialog
from .launcher import launchOperation
from .menu import CompanionMenu, MenuSpec
from .models import Channel, LoaderError, OperationResult
from .packages import findPackage, findRunningPackageProcesses, runPowerShellCancellable
from .policy import CHANNELS
from .registry import WinRegistry, releaseRegistryMutex
from .registryRepair import (
	RegistryPermissionStatus,
	RepairIdentity,
	captureRequestIdentity,
	diagnoseRegistryPermissions,
	runRegistryRepair,
	tryAcquireRegistryMutex,
)
from .security import buildSecurityProbe
from .updater import UpdateCheckResult, UpdateStatus, checkForUpdate

addonHandler.initTranslation()

_DELIVERY_TIMEOUT = 2.0
# After a menu command, NVDA announces the window that regains focus (for
# example "Desktop list, OpenCode 52 of 60") and that announcement cuts off
# speech emitted synchronously from the menu handler. Defer add-on
# announcements long enough for the focus announcement to complete.
_ANNOUNCEMENT_DELAY_MS = 350
_BRAILLE_ANNOUNCEMENT_DWELL_FALLBACK_MS = 4000
_BRAILLE_MAX_PENDING_MESSAGES = 50
_VALID_ANNOUNCEMENT_SOURCES = frozenset({"status", "message-log", "alert"})
_LANGUAGE_PATTERN = re.compile(r"^[a-z]{2,3}(?:-[a-z0-9]{2,8})*$", re.IGNORECASE)


class _Dialog(Protocol):
	def Bind(self, eventType: object, handler: Callable[..., object]) -> object: ...

	def Show(self) -> object: ...

	def Close(self) -> object: ...


def _scheduleBrailleMessage(delay: int, callback: Callable[[], None]) -> ScheduledCall:
	return wx.CallLater(delay, callback)


def _brailleMessageDwellMilliseconds() -> int | None:
	try:
		brailleConfig = config.conf["braille"]
		showMessages = brailleConfig["showMessages"]
		seconds = brailleConfig["messageTimeout"]
	except (KeyError, TypeError):
		return _BRAILLE_ANNOUNCEMENT_DWELL_FALLBACK_MS
	try:
		from config.configFlags import ShowMessages

		useTimeout = ShowMessages.USE_TIMEOUT
	except ImportError:
		# ShowMessages.USE_TIMEOUT has value 1 throughout supported NVDA releases.
		useTimeout = 1
	if showMessages != useTimeout:
		return None
	if isinstance(seconds, bool) or not isinstance(seconds, (int, float)):
		return _BRAILLE_ANNOUNCEMENT_DWELL_FALLBACK_MS
	return max(1000, int(seconds * 1000))


def _brailleMessagesEnabled() -> bool:
	try:
		brailleConfig = config.conf["braille"]
		showMessages = brailleConfig["showMessages"]
		mode = brailleConfig.get("mode", "followCursors")
	except (AttributeError, KeyError, TypeError):
		return True
	try:
		from config.configFlags import BrailleMode, ShowMessages

		disabled = ShowMessages.DISABLED
		speechOutput = BrailleMode.SPEECH_OUTPUT
	except ImportError:
		disabled = 0
		speechOutput = "speechOutput"
	return showMessages != disabled and mode != speechOutput


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	# Translators: Category name shown in NVDA's Input Gestures dialog.
	scriptCategory = _("WhatsApp Companion")

	def __init__(self) -> None:
		super().__init__()
		self._disposed = False
		self._generation = 0
		self.lastResult: OperationResult | None = None
		self.selectedChannel = Channel.STABLE
		self._updateCheckPending = False
		self._updateCancel = threading.Event()
		self._updateLock = threading.Lock()
		self._updateWorker: threading.Thread | None = None
		self._updateDuplicateAnnounced = False
		self._updateOperationToken = 0
		self._updateTerminalPending = False
		self._registryDiagnosisPending = False
		self._registryDiagnosisResumeGeneration: int | None = None
		self._registryDiagnosisCancel = threading.Event()
		self._registryDiagnosisWorker: threading.Thread | None = None
		self._dialog: _Dialog | None = None
		self._menu: CompanionMenu | None = None
		self._companionSession = ""
		self._companionGeneration = 0
		self._companionContext = ""
		self._companionLastSequence = 0
		self._brailleMessages = BrailleMessageQueue(
			braille.handler.message,
			_scheduleBrailleMessage,
			dwellMilliseconds=_brailleMessageDwellMilliseconds,
			maxPendingMessages=_BRAILLE_MAX_PENDING_MESSAGES,
			overflowMessage=lambda count: _(
				"Skipped WhatsApp Web Plus braille announcements: {count}.",
			).format(count=count),
			clearedMessage=lambda: _("WhatsApp Web Plus announcement cleared."),
			enabled=_brailleMessagesEnabled,
		)
		self.controller = Controller(
			launchOperation,
			self._queueReport,
			forceCloseOperation,
			self._queueLaunchReport,
		)
		if not globalVars.appArgs.secure and NVDAState.shouldWriteToDisk():
			self._menu = self._createMenu()

	def _createMenu(self) -> CompanionMenu:
		return CompanionMenu(
			# Translators: Submenu label shown under NVDA's Tools menu.
			_("&WhatsApp Companion"),
			# Translators: Help text for the add-on submenu under NVDA's Tools menu.
			_(
				"Launch or force close Microsoft Store WhatsApp, and manage WhatsApp Web Plus userscript updates.",
			),
			(
				# Launch WhatsApp.
				(
					MenuSpec(
						# Translators: Tools submenu command. The ampersand marks the mnemonic.
						_("Launch WhatsApp &Stable with WhatsApp Companion"),
						_("Launch WhatsApp Stable with WhatsApp Companion"),
						self._onLaunchStableMenu,
					),
					MenuSpec(
						# Translators: Tools submenu command. The ampersand marks the mnemonic.
						_("Launch WhatsApp &Beta with WhatsApp Companion"),
						_("Launch WhatsApp Beta with WhatsApp Companion"),
						self._onLaunchBetaMenu,
					),
					MenuSpec(
						# Translators: Tools submenu command. The ampersand marks the mnemonic.
						_("Launch the &last selected WhatsApp channel with WhatsApp Companion"),
						_("Launch the last selected WhatsApp channel with WhatsApp Companion"),
						self._onLaunchSelectedMenu,
					),
				),
				# Stop or fix problems with WhatsApp.
				(
					MenuSpec(
						# Translators: Destructive Tools submenu command. The ampersand marks the mnemonic.
						_("Force close &all Microsoft Store WhatsApp processes..."),
						_("Force close all running Microsoft Store WhatsApp Stable and Beta processes"),
						self._onForceCloseMenu,
					),
					MenuSpec(
						# Translators: Tools submenu command. The ellipsis is required because activation may show a confirmation dialog.
						_("Diagnose and repair WebView2 &policy permissions..."),
						_(
							"Check the per-user WebView2 policy permissions and offer a repair when the Companion cannot use them",
						),
						self._onDiagnoseRepairMenu,
					),
				),
				# Status and updates.
				(
					MenuSpec(
						# Translators: Tools submenu command. The ampersand marks the mnemonic.
						_("&Report the last WhatsApp Companion result"),
						_("Report the last WhatsApp Companion result"),
						self._onReportLastResultMenu,
					),
					MenuSpec(
						# Translators: Tools submenu command. The ampersand marks the mnemonic.
						_("&Check for WhatsApp Web Plus userscript updates"),
						_(
							"Check for WhatsApp Web Plus userscript updates and automatically install a newer or changed official version in the Companion",
						),
						self._onCheckForScriptUpdatesMenu,
					),
				),
			),
		)

	def _onLaunchStableMenu(self, event: wx.CommandEvent) -> None:
		event.Skip()
		self._launch(Channel.STABLE)

	def _onLaunchBetaMenu(self, event: wx.CommandEvent) -> None:
		event.Skip()
		self._launch(Channel.BETA)

	def _onLaunchSelectedMenu(self, event: wx.CommandEvent) -> None:
		event.Skip()
		self._launch(self.selectedChannel)

	def _onForceCloseMenu(self, event: wx.CommandEvent) -> None:
		event.Skip()
		self._reviewForceClose()

	def _onReportLastResultMenu(self, event: wx.CommandEvent) -> None:
		event.Skip()
		self._showLastResultDialog()

	def _onCheckForScriptUpdatesMenu(self, event: wx.CommandEvent) -> None:
		event.Skip()
		self._startUpdateCheck()

	def _onDiagnoseRepairMenu(self, event: wx.CommandEvent) -> None:
		event.Skip()
		self._startRegistryDiagnosis()

	def _queueLaunchReport(self, result: OperationResult, token: int) -> bool:
		return self._queueReport(result, launchToken=token)

	def _queueReport(self, result: OperationResult, *, launchToken: int | None = None) -> bool:
		if self._disposed:
			return False
		generation = self._generation
		if threading.current_thread() is threading.main_thread():
			if launchToken is not None and not self.controller.launchTokenIsActive(launchToken):
				return False
			return self._reportIfCurrent(generation, result)
		completed = threading.Event()
		lock = threading.Lock()
		state = {"cancelled": False, "started": False, "delivered": False}

		def deliver() -> None:
			with lock:
				if state["cancelled"]:
					completed.set()
					return
				state["started"] = True
			try:
				if launchToken is not None and not self.controller.launchTokenIsActive(launchToken):
					return
				state["delivered"] = self._reportIfCurrent(generation, result)
			except Exception:
				log.exception("Unexpected WhatsApp Companion announcement delivery failure")
			finally:
				completed.set()

		try:
			wx.CallAfter(deliver)
		except RuntimeError:
			return False
		if not completed.wait(_DELIVERY_TIMEOUT):
			with lock:
				if not state["started"]:
					state["cancelled"] = True
					return False
			completed.wait()
		return state["delivered"]

	def _reportIfCurrent(self, generation: int, result: OperationResult) -> bool:
		if self._disposed or generation != self._generation:
			return False
		if result.messageKey == "companion.invalidate":
			return self._applyCompanionInvalidation(result)
		if result.messageKey == "companion.overflow":
			if not self._isCurrentCompanionResult(result):
				return False
			# Translators: Spoken and brailled if the bounded bridge queue overflowed during a disconnect.
			self._speakAndQueueBraille(
				_("Some WhatsApp Web Plus announcements were skipped while reconnecting."),
			)
			return True
		if result.messageKey == "companion.announcement":
			return self._deliverCompanionAnnouncement(result)
		if result.messageKey == "package.closed":
			# Closing WhatsApp already moves focus to another application. Store the
			# outcome for the on-demand report command without interrupting that focus announcement.
			self.lastResult = result
			self._resetCompanionDeliveryState()
			return True
		self._report(result)
		return True

	def _resetCompanionDeliveryState(self) -> None:
		self._brailleMessages.clearPending()
		self._companionSession = ""
		self._companionGeneration = 0
		self._companionContext = ""
		self._companionLastSequence = 0

	def _applyCompanionInvalidation(self, result: OperationResult) -> bool:
		session = result.values.get("session")
		generation = result.values.get("generation")
		context = result.values.get("context")
		if (
			not isinstance(session, str)
			or not session
			or isinstance(generation, bool)
			or not isinstance(generation, int)
			or generation <= 0
			or not isinstance(context, str)
			or not context
		):
			return False
		sessionChanged = session != self._companionSession
		if sessionChanged:
			self._companionLastSequence = 0
		invalidatedSource = result.values.get("source")
		if sessionChanged:
			self._brailleMessages.clearPending()
		elif invalidatedSource in _VALID_ANNOUNCEMENT_SOURCES:
			self._brailleMessages.discardPending(invalidatedSource)
		else:
			self._brailleMessages.clearPending()
		self._companionSession = session
		self._companionGeneration = generation
		self._companionContext = context
		return True

	def _isCurrentCompanionResult(self, result: OperationResult) -> bool:
		return (
			result.values.get("session") == self._companionSession
			and result.values.get("generation") == self._companionGeneration
			and result.values.get("context") == self._companionContext
		)

	def _deliverCompanionAnnouncement(self, result: OperationResult) -> bool:
		if not self._isCurrentCompanionResult(result):
			return False
		sequence = result.values.get("sequence")
		source = result.values.get("source")
		language = result.values.get("language", "")
		privacy = result.values.get("privacy")
		text = result.values.get("text")
		if (
			isinstance(sequence, bool)
			or not isinstance(sequence, int)
			or sequence <= self._companionLastSequence
			or source not in _VALID_ANNOUNCEMENT_SOURCES
			or not isinstance(privacy, bool)
			or not isinstance(text, str)
			or not text
			or not isinstance(language, str)
			or (language and not _LANGUAGE_PATTERN.fullmatch(language))
		):
			return False
		if language:
			self._speakAndQueueBraille(text, language, source)
		else:
			self._speakAndQueueBraille(text, source=source)
		self._companionLastSequence = sequence
		return True

	def _speakAndQueueBraille(self, text: str, language: str = "", source: str = "") -> None:
		if language:
			speech.speak(
				[
					LangChangeCommand(language.replace("-", "_")),
					text,
					LangChangeCommand(None),
				],
			)
		else:
			speech.speak([text])
		self._brailleMessages.enqueue(text, source)

	def _announce(self, message: str) -> None:
		"""Speak after the closing menu's focus announcement."""

		def speak() -> None:
			if self._disposed:
				return
			ui.message(message)

		try:
			wx.CallLater(_ANNOUNCEMENT_DELAY_MS, speak)
		except (RuntimeError, TypeError):
			speak()

	def _report(self, result: OperationResult, *, defer: bool = False) -> None:
		hadActiveResult = self.lastResult is not None and self.lastResult.ok
		if result.messageKey != "operation.busy":
			self.lastResult = result
		message = self._messageForResult(result, hadActiveResult=hadActiveResult)
		if defer:
			self._announce(message)
		else:
			ui.message(message)

	def _messageForResult(self, result: OperationResult, *, hadActiveResult: bool = False) -> str:
		channel = self._channelLabel(result.values.get("channel"))
		remainingChannels = self._channelListLabel(result.values.get("remainingChannels"))
		# Translators: Spoken and brailled when another Registry operation is still active.
		registryBusyMessage = _(
			"The Companion is still cleaning up after the previous launch. Wait a moment and try again. If the problem continues, restart NVDA.",
		)
		messages = {
			# Translators: Spoken and brailled after the companion has loaded successfully.
			"active": _("WhatsApp {channel} is running with WhatsApp Companion.").format(
				channel=channel,
			),
			# Translators: Spoken and brailled while WhatsApp is still starting or loading.
			"operation.loading": _(
				"WhatsApp {channel} is still loading with WhatsApp Companion. Please wait.",
			).format(channel=channel),
			# Translators: Spoken and brailled when a launch command is invoked while a session is active.
			"operation.busy": _("WhatsApp Companion is already running. Close WhatsApp first."),
			# Translators: Spoken and brailled when the user closes WhatsApp normally.
			"package.closed": _("WhatsApp {channel} was closed. WhatsApp Companion stopped.").format(
				channel=channel,
			),
			# Translators: Recovery message when WhatsApp was already open before the companion started.
			"package.running": _("WhatsApp is already running. Close it normally and try again."),
			# Translators: Spoken and brailled when NVDA stops an in-progress launch.
			"operation.cancelled": _("WhatsApp Companion launch was cancelled."),
			# Translators: Status when another force-close request is made while one is running.
			"processes.busy": _("WhatsApp is already being force closed. Wait for the result."),
			# Translators: Result when neither Microsoft Store WhatsApp channel has a running process.
			"processes.none": _(
				"Neither WhatsApp Stable nor WhatsApp Beta from Microsoft Store was running.",
			),
			# Translators: Result after every discovered Microsoft Store WhatsApp process was closed.
			"processes.closed": _(
				"The Companion force closed every running Microsoft Store WhatsApp Stable and Beta process. It closed {closedCount} in total.",
			).format(closedCount=result.values.get("closedCount", 0)),
			# Translators: Result when some Microsoft Store WhatsApp processes remain after a force-close attempt.
			"processes.partial": _(
				"The Companion force closed {closedCount} Microsoft Store WhatsApp processes, but WhatsApp {remainingChannels} may still be running. Restart Windows before launching the Companion again.",
			).format(
				remainingChannels=remainingChannels,
				closedCount=result.values.get("closedCount", 0),
			),
			# Translators: Result when no Microsoft Store WhatsApp process could be force closed or verified.
			"processes.failed": _(
				"The Companion could not force close WhatsApp {remainingChannels} from Microsoft Store or confirm that it had closed. Restart Windows before launching the Companion again.",
			).format(remainingChannels=remainingChannels),
			# Translators: Recovery message when force close is unavailable in the current NVDA context.
			"processes.context": _(
				"The Companion cannot force close WhatsApp in this NVDA session. Unlock Windows and run NVDA normally, not as administrator.",
			),
			# Translators: Recovery message after renderer reconnection has failed.
			"cdp.reconnect": _("The companion connection was lost. Close WhatsApp, then launch it again."),
			# Translators: Recovery message for locked, secure, read-only, or elevated NVDA contexts.
			"security": _("Unlock Windows and run a normal, non-administrator copy of NVDA, then try again."),
			# Translators: Recovery message when the selected Microsoft Store WhatsApp channel is unavailable.
			"package": _("Install the selected WhatsApp channel from Microsoft Store, then try again."),
			# Translators: Recovery message while an earlier Companion launch is still releasing its registry lease.
			"registry.busy": registryBusyMessage,
			# Translators: Recovery message when the named Registry mutex cannot be created.
			"registry.mutex.createFailed": _(
				"The Companion could not safely access the Windows Registry. Restart NVDA and try again. If the problem continues, report the error.",
			),
			# Translators: Recovery message when Windows fails while checking Registry mutex ownership.
			"registry.mutex.waitFailed": _(
				"Windows could not confirm whether another Companion operation was using the Registry. Restart NVDA and try again. If the problem continues, report the error.",
			),
			# Translators: Recovery message while another Companion Registry operation owns the mutex.
			"registry.mutex.busy": registryBusyMessage,
			# Translators: Recovery message when machine-wide WebView2 policy cannot be read.
			"registry.machine.readAccessDenied": _(
				"Windows blocked access to the computer-wide WebView2 policy setting. Contact your administrator.",
			),
			# Translators: Recovery message for an unexpected machine-wide WebView2 policy read failure.
			"registry.machine.readFailed": _(
				"The computer-wide WebView2 policy setting could not be checked. Contact your administrator or report the error.",
			),
			# Translators: Recovery message when this exact WhatsApp channel is controlled by machine policy.
			"registry.machine.policyAumid": _(
				"A Windows policy controls the WebView2 launch settings for this WhatsApp channel. The Companion cannot override the policy, so it left the settings unchanged. Contact your administrator for help.",
			),
			# Translators: Recovery message when a wildcard WebView2 argument is controlled by machine policy.
			"registry.machine.policyWildcard": _(
				"A Windows policy controls the WebView2 launch settings for all applications. The Companion cannot override the policy, so it left the settings unchanged. Contact your administrator for help.",
			),
			# Translators: Recovery message when the per-user WebView2 policy value cannot be read.
			"registry.user.readAccessDenied": _(
				"Windows blocked access to the per-user WebView2 policy setting required by the Companion. In NVDA Tools, open WhatsApp Companion and choose Diagnose and repair WebView2 policy permissions, then try again.",
			),
			# Translators: Recovery message for an unexpected per-user WebView2 policy read failure.
			"registry.user.readFailed": _(
				"The per-user WebView2 policy setting could not be read. Close WhatsApp and try again. If this continues, report the error.",
			),
			# Translators: Recovery message when an existing WebView2 value has an unsupported data type.
			"registry.user.invalidValueType": _(
				"An existing per-user WebView2 launch setting has an unsupported data type. The Companion did not change it. Review the setting manually.",
			),
			# Translators: Recovery message when a pre-existing debugging argument is not owned by the Companion.
			"registry.user.debugArgumentPresent": _(
				"A remote-debugging launch argument already exists for this WhatsApp channel. The Companion did not overwrite it. Permission repair does not remove settings the Companion cannot prove it owns.",
			),
			# Translators: Recovery message when the per-user WebView2 policy leaf cannot be created or opened.
			"registry.user.openCreateAccessDenied": _(
				"Windows did not allow the Companion to create or update its temporary per-user WebView2 launch setting. WhatsApp was not launched. Run Diagnose and repair WebView2 policy permissions from the Companion submenu, then try again.",
			),
			# Translators: Recovery message for an unexpected leaf open/create failure.
			"registry.user.openCreateFailed": _(
				"The temporary per-user WebView2 launch setting could not be created or updated. WhatsApp was not launched. Close WhatsApp and try again. If this continues, report the error.",
			),
			# Translators: Recovery message when the temporary value cannot be set.
			"registry.user.setAccessDenied": _(
				"Windows did not allow the Companion to create or update its temporary per-user WebView2 launch setting. WhatsApp was not launched. Run Diagnose and repair WebView2 policy permissions from the Companion submenu, then try again.",
			),
			# Translators: Recovery message for an unexpected temporary value write failure.
			"registry.user.setFailed": _(
				"The temporary per-user WebView2 launch setting could not be written. WhatsApp was not launched. Close WhatsApp and try again. If this continues, report the error.",
			),
			# Translators: Recovery message when the temporary value read-back does not match.
			"registry.user.verifyMismatch": _(
				"The temporary WebView2 launch setting could not be verified after it was written. Close WhatsApp and try again.",
			),
			# Translators: Urgent recovery message when the per-user WebView2 setting cannot be opened during restore.
			"registry.restore.openAccessDenied": _(
				"The Companion could not restore the previous per-user WebView2 setting. Close WhatsApp now, then run Diagnose and repair WebView2 policy permissions. The Companion will retry the saved restoration before another launch.",
			),
			# Translators: Recovery message for an unexpected restore-open failure.
			"registry.restore.openFailed": _(
				"The previous per-user WebView2 setting could not be opened for restoration. Close WhatsApp and report the error.",
			),
			# Translators: Urgent recovery message when the owned temporary value cannot be deleted.
			"registry.restore.deleteAccessDenied": _(
				"The Companion could not remove its temporary per-user WebView2 setting. Close WhatsApp now, then run Diagnose and repair WebView2 policy permissions. The Companion will retry the saved restoration before another launch.",
			),
			# Translators: Recovery message for an unexpected temporary value deletion failure.
			"registry.restore.deleteFailed": _(
				"The temporary per-user WebView2 setting could not be removed. Close WhatsApp and report the error.",
			),
			# Translators: Urgent recovery message when the previous value cannot be written back.
			"registry.restore.setAccessDenied": _(
				"The Companion could not restore the previous per-user WebView2 setting. Close WhatsApp now, then run Diagnose and repair WebView2 policy permissions. The Companion will retry the saved restoration before another launch.",
			),
			# Translators: Recovery message for an unexpected restore write-back failure.
			"registry.restore.setFailed": _(
				"The previous per-user WebView2 setting could not be written back. Close WhatsApp and report the error.",
			),
			# Translators: Recovery message when the live value changed outside the Companion.
			"registry.restore.conflict": _(
				"The per-user WebView2 setting changed outside the Companion while it was active. The Companion did not overwrite it. Review the per-user WebView2 policy setting manually.",
			),
			# Translators: Recovery message when restored state cannot be verified.
			"registry.restore.verifyMismatch": _(
				"The restored per-user WebView2 setting could not be verified. Close WhatsApp and review the per-user WebView2 policy setting manually.",
			),
			# Translators: Recovery message when a saved restoration record cannot be verified for this account.
			"registry.recovery.unreadable": _(
				"A saved WebView2 restoration record could not be verified for this Windows account. The Companion did not change it. Contact your administrator or restore the per-user WebView2 policy setting manually.",
			),
			# Translators: Status when the required WebView2 policy permissions already exist.
			"registry.repair.notNeeded": _(
				"The required WebView2 policy permissions are already available. No changes were made.",
			),
			# Translators: Status when diagnosis is refused while WhatsApp is running.
			"registry.repair.whatsappRunning": _(
				"Close WhatsApp before diagnosing WebView2 policy permissions.",
			),
			# Translators: Status when diagnosis or repair requires a normal NVDA context.
			"registry.repair.context": _(
				"Diagnose and repair requires a normal, non-administrator NVDA session with Windows unlocked.",
			),
			# Translators: Status when the diagnosis cannot determine the condition.
			"registry.repair.diagnosisFailed": _(
				"The WebView2 policy permissions could not be diagnosed. Close WhatsApp and try again. If this continues, contact your administrator.",
			),
			# Translators: Status stored while the repair confirmation dialog is open.
			"registry.repair.confirmationRequired": _(
				"A permission repair is available. Review the confirmation dialog to continue or keep the current permissions.",
			),
			# Translators: Status when the user cancels the Windows permission request.
			"registry.repair.uacCancelled": _("No permission change was made."),
			# Translators: Status when the packaged repair helper is absent.
			"registry.repair.helperMissing": _("The repair helper is missing. Reinstall the add-on."),
			# Translators: Status when the packaged repair helper fails integrity verification.
			"registry.repair.helperUntrusted": _(
				"The repair helper could not be verified. Reinstall the add-on from a trusted source.",
			),
			# Translators: Status when Windows or application control blocks the helper.
			"registry.repair.helperBlocked": _(
				"Windows blocked the permission repair. Contact your administrator.",
			),
			# Translators: Status when the elevated helper exceeds its transaction deadline.
			"registry.repair.helperTimeout": _(
				"The permission repair did not finish. Run the diagnosis again before trying again.",
			),
			# Translators: Status when no compatible helper exists for the platform.
			"registry.repair.unsupportedPlatform": _(
				"No compatible repair helper is available for this computer.",
			),
			# Translators: Status when the helper cannot verify the requesting NVDA session.
			"registry.repair.parentIdentityMismatch": _(
				"The permission repair could not verify this NVDA session. No change was made.",
			),
			# Translators: Status when the requesting user's hive is not loaded.
			"registry.repair.userHiveUnavailable": _(
				"Your Windows user profile is not available. Stay logged in and try again.",
			),
			# Translators: Status when an explicit deny rule blocks effective access.
			"registry.repair.managedDeny": _(
				"An administrator deny rule still blocks the WebView2 policy key. The repair did not remove or weaken that rule. Contact your administrator.",
			),
			# Translators: Status when the elevated helper cannot change the DACL.
			"registry.repair.insufficientAdminRights": _(
				"The permission repair could not change the Registry permissions. Contact your administrator.",
			),
			# Translators: Status when the DACL change failed before completion.
			"registry.repair.applyFailed": _(
				"The permission repair could not be applied. No Registry values were changed.",
			),
			# Translators: Status when the post-apply check failed and the original DACL was restored.
			"registry.repair.verificationFailedRolledBack": _(
				"The permission repair could not be verified and the original permissions were restored. Contact your administrator.",
			),
			# Translators: Critical status when the original DACL could not be restored.
			"registry.repair.rollbackFailed": _(
				"The permission repair could not restore the original Registry permissions after an error. Do not launch WhatsApp through the Companion until an administrator reviews the per-user WebView2 policy key.",
			),
			# Translators: Success status after the permission repair.
			"registry.repair.repaired": _(
				"WebView2 policy permissions were repaired for your Windows account. No Registry values were changed. Try launching WhatsApp through the Companion again.",
			),
			# Translators: Status when the helper reports success but normal access is still blocked.
			"registry.repair.postVerifyFailed": _(
				"The permission repair reported success but access is still blocked. Do not launch WhatsApp through the Companion. Contact your administrator.",
			),
			# Translators: Status when a saved WebView2 value was restored after the repair.
			"registry.repair.recoveryRestored": _(
				"A saved WebView2 setting was restored after the repair. You can launch WhatsApp through the Companion again.",
			),
			# Translators: Status when a saved WebView2 value changed outside the Companion.
			"registry.repair.recoveryConflict": _(
				"A saved WebView2 setting changed outside the Companion. The Companion did not overwrite it. Review the per-user WebView2 policy setting manually.",
			),
			# Translators: Recovery message for temporary WebView2 policy failures.
			"registry": _(
				"The temporary WebView2 setting could not be restored. Restart NVDA before trying again.",
			),
			# Translators: Recovery message for local accessibility connection failures.
			"transport": _(
				"WhatsApp opened, but the companion could not connect. Close WhatsApp and try again.",
			),
			# Translators: Recovery message when the bundled userscript does not initialize.
			"bundle": _(
				"The bundled WhatsApp Web Plus userscript did not start. Close WhatsApp and try again.",
			),
			# Translators: Recovery after a downloaded userscript fails its launch health checks.
			"bundle.updateQuarantined": _(
				"The downloaded WhatsApp Web Plus userscript did not start and was disabled. Close WhatsApp, then launch it again through the Companion to use the packaged fallback.",
			),
			# Translators: Update result after a newer userscript bundle was selected.
			"update.updated": _(
				"WhatsApp Web Plus userscript was updated from version {currentVersion} to {latestVersion}. The new version will be used the next time WhatsApp is launched through the Companion.",
			).format(
				latestVersion=result.values.get("latestVersion", ""),
				currentVersion=result.values.get("currentVersion", ""),
			),
			# Translators: Update result when official content changed without a version number change.
			"update.refreshed": _(
				"WhatsApp Web Plus userscript was refreshed at version {currentVersion} because the official script differed from the Companion bundle. The refreshed version will be used the next time WhatsApp is launched through the Companion.",
			).format(currentVersion=result.values.get("currentVersion", "")),
			# Translators: Update status when the bundled userscript version is current.
			"update.current": _(
				"The WhatsApp Web Plus userscript is up to date at version {currentVersion}.",
			).format(currentVersion=result.values.get("currentVersion", "")),
			# Translators: Recovery message when the userscript update cannot be downloaded.
			"update.error.network": _(
				"The WhatsApp Web Plus userscript update could not be downloaded. Check your internet connection and try again. The existing Companion bundle was not changed.",
			),
			# Translators: Recovery message when a downloaded userscript fails validation.
			"update.error.validation": _(
				"The downloaded WhatsApp Web Plus userscript update could not be verified. The existing Companion bundle was not changed.",
			),
			# Translators: Recovery message when the verified userscript cannot be saved.
			"update.error.save": _(
				"The verified WhatsApp Web Plus userscript update could not be installed. The existing Companion bundle was not changed.",
			),
			# Translators: Recovery message for an unexpected userscript update failure.
			"update.error": _(
				"The WhatsApp Web Plus userscript could not be updated. The existing Companion bundle was not changed.",
			),
			# Translators: Status when updating is unavailable in a restricted NVDA context.
			"update.context": _(
				"The userscript bundle cannot be updated in this NVDA context. Use a normal NVDA session.",
			),
		}
		message = messages.get(result.messageKey)
		if message is None:
			prefix = result.code.split(".", 1)[0]
			message = messages.get(
				{
					"security": "security",
					"package": "package",
					"registry": "registry",
					"http": "transport",
					"websocket": "transport",
					"listener": "transport",
					"target": "transport",
					"endpoint": "transport",
					"cdp": "cdp.reconnect" if hadActiveResult else "transport",
					"bundle": "bundle",
				}.get(prefix, ""),
			)
		# Translators: Fallback launch failure with a safe recovery action.
		return message or _("WhatsApp Companion could not start. Close WhatsApp and try again.")

	def _channelLabel(self, value: object) -> str:
		if value == Channel.BETA.value:
			# Translators: Microsoft Store WhatsApp release channel name.
			return _("Beta")
		# Translators: Microsoft Store WhatsApp release channel name.
		return _("Stable")

	def _channelListLabel(self, value: object) -> str:
		channels = set(value) if isinstance(value, (tuple, list, set, frozenset)) else set()
		if not channels or (Channel.STABLE.value in channels and Channel.BETA.value in channels):
			# Translators: Combined Microsoft Store WhatsApp release channels in a force-close result.
			return _("Stable and Beta")
		if Channel.BETA.value in channels:
			return self._channelLabel(Channel.BETA.value)
		return self._channelLabel(Channel.STABLE.value)

	def _launch(self, channel: Channel) -> None:
		if self.controller.forceClosing:
			self._report(OperationResult(False, "processes.busy", "processes.busy", {}), defer=True)
			return
		if self.controller.repairing or self._registryDiagnosisActive:
			self._report(OperationResult(False, "registry.mutex.busy", "registry.mutex.busy", {}), defer=True)
			return
		if not self.controller.start(channel):
			self._report(OperationResult(False, "operation.busy", "operation.busy", {}), defer=True)
			return
		self._resetCompanionDeliveryState()
		self.selectedChannel = channel
		# Translators: Immediate launch progress spoken and brailled after a user command.
		self._report(
			OperationResult(
				False,
				"operation.loading",
				"operation.loading",
				{"channel": channel.value},
			),
			defer=True,
		)

	def _startRegistryDiagnosis(self) -> None:
		if self._disposed:
			return
		if (
			self._registryDiagnosisActive
			or self.controller.repairing
			or self.controller.forceClosing
			or (self.controller.worker is not None and self.controller.worker.is_alive())
		):
			self._report(OperationResult(False, "registry.mutex.busy", "registry.mutex.busy", {}), defer=True)
			return
		if self._focusExistingDialog():
			return
		if globalVars.appArgs.secure or not NVDAState.shouldWriteToDisk():
			self._report(
				OperationResult(False, "registry.repair.context", "registry.repair.context", {}),
				defer=True,
			)
			return
		# Translators: Immediate progress after the user starts the permission diagnosis.
		self._announce(_("Checking WebView2 policy permissions."))
		generation = self._generation
		cancelEvent = threading.Event()
		self._registryDiagnosisCancel = cancelEvent
		self._registryDiagnosisPending = True
		worker = threading.Thread(
			target=self._runRegistryDiagnosis,
			args=(generation, cancelEvent),
			name="WhatsAppWebPlusRegistryDiagnosis",
			daemon=True,
		)
		self._registryDiagnosisWorker = worker
		worker.start()

	@property
	def _registryDiagnosisActive(self) -> bool:
		return self._registryDiagnosisPending or self._registryDiagnosisResumeGeneration is not None

	def _runRegistryDiagnosis(self, generation: int, cancelEvent: threading.Event) -> None:
		try:
			status = diagnoseRegistryPermissions(
				WinRegistry(),
				buildSecurityProbe(),
				tryAcquireMutex=tryAcquireRegistryMutex,
				releaseMutex=releaseRegistryMutex,
				whatsappRunning=lambda: self._whatsappRunning(cancelEvent),
				isCancelled=cancelEvent.is_set,
			)
		except LoaderError as error:
			if error.code == "operation.cancelled" or cancelEvent.is_set():
				return
			log.warning(
				"WhatsApp Companion permission diagnosis: code=%s detail=%s",
				error.code,
				error.safeDetail,
			)
			self._queueDiagnosisLoaderError(generation, error.code, dict(error.values))
			return
		except Exception:
			log.exception("Unexpected WhatsApp Companion permission diagnosis failure")
			status = RegistryPermissionStatus.MANAGED_OR_UNKNOWN
		if self._disposed or generation != self._generation:
			return
		try:
			wx.CallAfter(self._finishRegistryDiagnosis, generation, status)
		except RuntimeError:
			if not self._disposed and generation == self._generation:
				self._registryDiagnosisPending = False
			return

	def _whatsappRunning(self, cancelEvent: threading.Event | None = None) -> bool:
		cancelEvent = cancelEvent or threading.Event()

		def runner(script: str) -> str:
			return runPowerShellCancellable(script, cancelEvent)

		for policy in CHANNELS.values():
			if cancelEvent.is_set():
				raise LoaderError("operation.cancelled")
			try:
				package = findPackage(policy, runner)
			except LoaderError as error:
				if error.code == "operation.cancelled":
					raise
				log.warning(
					"WhatsApp Companion package probe failed for %s: code=%s",
					policy.id.value,
					error.code,
				)
				continue
			except Exception:
				log.warning(
					"WhatsApp Companion package probe failed for %s",
					policy.id.value,
					exc_info=True,
				)
				continue
			if package is not None:
				try:
					if findRunningPackageProcesses(package, runner):
						return True
				except LoaderError as error:
					if error.code == "operation.cancelled":
						raise
					log.warning(
						"WhatsApp Companion process probe failed for %s: code=%s",
						policy.id.value,
						error.code,
					)
				except Exception:
					log.warning(
						"WhatsApp Companion process probe failed for %s",
						policy.id.value,
						exc_info=True,
					)
		return False

	def _queueDiagnosisLoaderError(
		self,
		generation: int,
		code: str,
		values: dict,
	) -> None:
		if self._disposed or generation != self._generation:
			return

		def deliver() -> None:
			if self._disposed or generation != self._generation:
				return
			self._registryDiagnosisPending = False
			self._registryDiagnosisWorker = None
			self._report(OperationResult(False, code, code, values))

		try:
			wx.CallAfter(deliver)
		except RuntimeError:
			if not self._disposed and generation == self._generation:
				self._registryDiagnosisPending = False
			return

	def _finishRegistryDiagnosis(
		self,
		generation: int,
		status: RegistryPermissionStatus,
	) -> None:
		if self._disposed or generation != self._generation:
			return
		self._registryDiagnosisPending = False
		self._registryDiagnosisWorker = None
		if status is RegistryPermissionStatus.REPAIRABLE_ACCESS_DENIED:
			self._confirmRegistryRepair()
			return
		if status is RegistryPermissionStatus.WHATSAPP_RUNNING:
			self._confirmForceCloseForRegistryDiagnosis()
			return
		result = {
			RegistryPermissionStatus.USABLE: OperationResult(
				True,
				"registry.repair.notNeeded",
				"registry.repair.notNeeded",
				{},
			),
			RegistryPermissionStatus.MACHINE_POLICY: OperationResult(
				False,
				"registry.repair.machinePolicy",
				"registry.machine.policyAumid",
				{},
			),
			RegistryPermissionStatus.BUSY: OperationResult(
				False,
				"registry.mutex.busy",
				"registry.mutex.busy",
				{},
			),
			RegistryPermissionStatus.UNSUPPORTED: OperationResult(
				False,
				"registry.repair.context",
				"registry.repair.context",
				{},
			),
			RegistryPermissionStatus.MANAGED_OR_UNKNOWN: OperationResult(
				False,
				"registry.repair.diagnosisFailed",
				"registry.repair.diagnosisFailed",
				{},
			),
		}[status]
		self._report(result)

	def _confirmForceCloseForRegistryDiagnosis(self) -> None:
		if self._focusExistingDialog():
			return
		self.lastResult = OperationResult(
			False,
			"registry.repair.whatsappRunning",
			"registry.repair.whatsappRunning",
			{},
		)
		try:
			self._showDialog(
				MessageDialog(
					gui.mainFrame,
					_(
						"WhatsApp is currently running. The Companion must force close all Microsoft Store WhatsApp Stable and Beta processes before it can diagnose WebView2 policy permissions. Active calls and file transfers will be interrupted, and text you have not sent may be lost. Do you want to force close WhatsApp and continue the diagnosis? If a repair is needed, you will review a separate confirmation before Windows asks for administrator approval.",
					),
					# Translators: Title of the confirmation shown when permission diagnosis requires closing WhatsApp.
					_("Close WhatsApp to continue diagnosis?"),
					buttons=None,
				)
				.addNoButton(
					# Translators: Safe default button that cancels permission diagnosis without closing WhatsApp.
					label=_("&Keep WhatsApp open"),
					defaultFocus=True,
					fallbackAction=True,
				)
				.addYesButton(
					# Translators: Destructive button that closes WhatsApp and resumes permission diagnosis.
					label=_("&Force close WhatsApp and continue"),
					callback=self._startForceCloseForRegistryDiagnosis,
				),
			)
		except Exception:
			log.exception("Unexpected WhatsApp Companion diagnosis close confirmation failure")
			self._report(
				OperationResult(
					False,
					"registry.repair.diagnosisFailed",
					"registry.repair.diagnosisFailed",
					{},
				),
				defer=True,
			)

	def _startForceCloseForRegistryDiagnosis(self, _payload: object) -> None:
		if self._disposed:
			return
		generation = self._generation
		if not self.controller.forceClose(
			lambda result: self._resumeRegistryDiagnosisAfterForceClose(generation, result),
		):
			self._report(OperationResult(False, "processes.busy", "processes.busy", {}), defer=True)
			return
		# Translators: Progress after the user chooses to close WhatsApp and continue permission diagnosis.
		self._announce(
			_(
				"Force closing Microsoft Store WhatsApp Stable and Beta processes before continuing diagnosis.",
			),
		)

	def _resumeRegistryDiagnosisAfterForceClose(
		self,
		generation: int,
		result: OperationResult,
	) -> None:
		if (
			self._disposed
			or generation != self._generation
			or not result.ok
			or result.messageKey not in {"processes.closed", "processes.none"}
		):
			return
		self._registryDiagnosisResumeGeneration = generation
		try:
			wx.CallAfter(self._continueRegistryDiagnosisAfterForceClose, generation)
		except RuntimeError:
			self._registryDiagnosisResumeGeneration = None
			return

	def _continueRegistryDiagnosisAfterForceClose(self, generation: int) -> None:
		if self._disposed or generation != self._generation:
			self._registryDiagnosisResumeGeneration = None
			return
		if self._dialog is not None and self._focusExistingDialog():
			return
		self._registryDiagnosisResumeGeneration = None
		self._startRegistryDiagnosis()

	def _confirmRegistryRepair(self) -> None:
		if self._focusExistingDialog():
			return
		self.lastResult = OperationResult(
			True,
			"registry.repair.confirmationRequired",
			"registry.repair.confirmationRequired",
			{},
		)
		try:
			self._showDialog(
				MessageDialog(
					gui.mainFrame,
					_(
						"WhatsApp Companion needs a temporary WebView2 launch setting before starting WhatsApp. Windows is blocking the per-user Registry key that stores this setting. This repair gives your Windows account permission to read, create, change, and delete values inside that one WebView2 policy key. Windows protects the whole key rather than individual values, so other programs running as your account could also change values in that key. The repair will not change any Registry value, any machine-wide policy, any administrator deny rule, your WhatsApp data, or your chat content. Only a small repair helper runs as administrator, while NVDA and WhatsApp stay unelevated. The permission stays in place after you restart Windows or remove the add-on. Do you want to continue to the Windows permission request?",
					),
					# Translators: Title of the WebView2 policy permission repair confirmation dialog.
					_("Repair per-user WebView2 policy permissions?"),
					buttons=None,
				)
				.addNoButton(
					# Translators: Safe default button that cancels the permission repair.
					label=_("&Keep current permissions"),
					defaultFocus=True,
					fallbackAction=True,
				)
				.addYesButton(
					# Translators: Affirmative button that continues to the Windows permission request.
					label=_("&Continue to User Account Control"),
					callback=self._startRegistryRepair,
				),
			)
		except Exception:
			log.exception("Unexpected WhatsApp Companion repair confirmation failure")
			self._report(
				OperationResult(
					False,
					"registry.repair.diagnosisFailed",
					"registry.repair.diagnosisFailed",
					{},
				),
				defer=True,
			)

	def _startRegistryRepair(self, _payload: object) -> None:
		if self._disposed:
			return
		if self.controller.forceClosing or self.controller.repairing:
			self._report(OperationResult(False, "registry.mutex.busy", "registry.mutex.busy", {}), defer=True)
			return
		if globalVars.appArgs.secure or not NVDAState.shouldWriteToDisk():
			self._report(
				OperationResult(False, "registry.repair.context", "registry.repair.context", {}),
				defer=True,
			)
			return
		# Translators: Progress before the Windows permission request appears.
		self._announce(
			_(
				"Opening the Windows permission request. NVDA will keep running without administrator privileges.",
			),
		)
		try:
			identity = captureRequestIdentity()
		except LoaderError as error:
			log.warning(
				"WhatsApp Companion repair identity capture failed: code=%s detail=%s",
				error.code,
				error.safeDetail,
			)
			self._report(OperationResult(False, error.code, error.code, dict(error.values)), defer=True)
			return
		hwnd = gui.mainFrame.Handle
		if not self.controller.startRegistryRepair(lambda: self._runRegistryRepair(identity, hwnd)):
			self._report(OperationResult(False, "registry.mutex.busy", "registry.mutex.busy", {}), defer=True)

	def _runRegistryRepair(self, identity: RepairIdentity, hwnd: int) -> OperationResult:
		outcome = runRegistryRepair(identity, hwnd=hwnd)
		return OperationResult(outcome.ok, outcome.code, outcome.code, dict(outcome.values))

	def _reviewForceClose(self) -> None:
		if self.controller.forceClosing:
			self._report(OperationResult(False, "processes.busy", "processes.busy", {}), defer=True)
			return
		if self.controller.repairing or self._registryDiagnosisActive:
			self._report(OperationResult(False, "registry.mutex.busy", "registry.mutex.busy", {}), defer=True)
			return
		if self._focusExistingDialog():
			return
		self._showDialog(
			MessageDialog(
				gui.mainFrame,
				_(
					# Translators: Warning shown before force closing all supported Microsoft Store WhatsApp processes.
					"This will immediately close every running Microsoft Store WhatsApp app, including Stable and Beta. Active calls and file transfers will be interrupted. Text you have not sent may be lost. Do you want to continue?",
				),
				# Translators: Title of the Microsoft Store WhatsApp force-close confirmation dialog.
				_("Force close WhatsApp applications?"),
				buttons=None,
			)
			.addNoButton(
				# Translators: Safe default button that cancels force closing WhatsApp.
				label=_("&Keep WhatsApp open"),
				defaultFocus=True,
				fallbackAction=True,
			)
			.addYesButton(
				# Translators: Destructive confirmation button that closes all supported WhatsApp processes.
				label=_("&Force close"),
				callback=self._startForceClose,
			),
		)

	def _startForceClose(self, _payload: object) -> None:
		if self._disposed:
			return
		if not self.controller.forceClose():
			self._report(OperationResult(False, "processes.busy", "processes.busy", {}), defer=True)
			return
		# Translators: Immediate progress after the user confirms force closing both WhatsApp channels.
		self._announce(_("Closing all running WhatsApp Stable and Beta apps from Microsoft Store."))

	def _startUpdateCheck(self) -> None:
		if self._disposed:
			return
		if self._updateCheckPending or self._updateTerminalPending:
			if not self._updateDuplicateAnnounced:
				self._updateDuplicateAnnounced = True
				# Translators: Status when a second update request is made while one is still running.
				self._announceUpdateWhilePending(
					_("A WhatsApp Web Plus userscript update check is already in progress."),
				)
			return
		self._updateOperationToken += 1
		updateToken = self._updateOperationToken
		if globalVars.appArgs.secure or not NVDAState.shouldWriteToDisk():
			# Translators: Recovery message when bundle updating is unavailable in the current NVDA context.
			self._report(
				OperationResult(False, "update.context", "update.context", {}),
				defer=True,
			)
			return
		self._updateCheckPending = True
		self._updateTerminalPending = False
		self._updateDuplicateAnnounced = False
		self._updateCancel.clear()
		generation = self._generation
		# Translators: Progress after the user requests an update check that automatically installs a newer bundle.
		self._announceUpdateWhilePending(
			_(
				"Checking for WhatsApp Web Plus userscript updates. If the official userscript has a newer version or different content, the Companion will download and install it automatically.",
			),
			updateToken,
		)
		worker = threading.Thread(
			target=self._runUpdateCheck,
			args=(generation, updateToken, self._updateCancel),
			name="WhatsAppWebPlusUpdateCheck",
			daemon=True,
		)
		self._updateWorker = worker
		worker.start()

	def _announceUpdateWhilePending(self, message: str, updateToken: int | None = None) -> None:
		generation = self._generation
		token = self._updateOperationToken if updateToken is None else updateToken

		def speak() -> None:
			if (
				self._disposed
				or generation != self._generation
				or token != self._updateOperationToken
				or not self._updateCheckPending
			):
				return
			ui.message(message)

		try:
			wx.CallLater(_ANNOUNCEMENT_DELAY_MS, speak)
		except (RuntimeError, TypeError):
			speak()

	def _runUpdateCheck(
		self,
		generation: int,
		updateToken: int,
		cancelEvent: threading.Event,
	) -> None:
		if cancelEvent.is_set():
			return
		try:
			result = checkForUpdate(cancelEvent)
		except Exception:
			log.exception("Unexpected WhatsApp Web Plus userscript update check failure")
			result = UpdateCheckResult(UpdateStatus.ERROR, "")
		with self._updateLock:
			if (
				cancelEvent.is_set()
				or self._disposed
				or generation != self._generation
				or updateToken != self._updateOperationToken
			):
				return
			try:
				wx.CallAfter(
					self._finishUpdateCheck,
					generation,
					updateToken,
					result,
					threading.current_thread(),
				)
			except RuntimeError:
				return

	def _finishUpdateCheck(
		self,
		generation: int,
		updateToken: int,
		result: UpdateCheckResult,
		worker: threading.Thread,
	) -> None:
		with self._updateLock:
			if (
				self._disposed
				or generation != self._generation
				or updateToken != self._updateOperationToken
				or self._updateCancel.is_set()
				or worker is not self._updateWorker
			):
				return
			self._updateWorker = None
		self._updateCheckPending = False
		self._updateTerminalPending = True
		if result.status == UpdateStatus.UPDATED:
			messageKey = "update.refreshed" if result.contentChanged else "update.updated"
			operationResult = OperationResult(
				True,
				messageKey,
				messageKey,
				{
					"currentVersion": result.currentVersion,
					"latestVersion": result.latestVersion,
				},
			)
		elif result.status == UpdateStatus.CURRENT:
			operationResult = OperationResult(
				True,
				"update.current",
				"update.current",
				{"currentVersion": result.currentVersion},
			)
		else:
			errorKey = (
				f"update.error.{result.errorCode}"
				if result.errorCode in {"network", "validation", "save"}
				else "update.error"
			)
			operationResult = OperationResult(False, errorKey, errorKey, {})
		self._reportUpdateResult(operationResult, generation, updateToken)

	def _reportUpdateResult(
		self,
		result: OperationResult,
		generation: int,
		updateToken: int,
	) -> None:
		hadActiveResult = self.lastResult is not None and self.lastResult.ok
		self.lastResult = result
		message = self._messageForResult(result, hadActiveResult=hadActiveResult)

		def speak() -> None:
			if self._disposed or generation != self._generation or updateToken != self._updateOperationToken:
				return
			ui.message(message)
			self._updateTerminalPending = False
			self._updateDuplicateAnnounced = False

		try:
			wx.CallLater(_ANNOUNCEMENT_DELAY_MS, speak)
		except (RuntimeError, TypeError):
			speak()

	def _focusExistingDialog(self) -> bool:
		dialog = self._dialog
		if dialog is None:
			return False
		try:
			destroyed = getattr(dialog, "IsDestroyed", None)
			if callable(destroyed) and destroyed():
				self._dialog = None
				return False
			dialog.Raise()
			dialog.SetFocus()
		except RuntimeError:
			# wxPython Phoenix raises RuntimeError ("wrapped C/C++ object has
			# been deleted") for a dialog whose native window is gone; it has no
			# wx.PyDeadObjectError. EVT_WINDOW_DESTROY may be missed for dialogs
			# deleted during event dispatch, so heal the stale reference here.
			self._dialog = None
			return False
		except AttributeError:
			# A transient child-focus failure must not lose the live singleton
			# reference; EVT_WINDOW_DESTROY clears it when the dialog really dies.
			return True
		return True

	def _showDialog(self, dialog: _Dialog) -> None:
		self._dialog = dialog
		dialog.Bind(wx.EVT_WINDOW_DESTROY, self._onDialogDestroyed)
		try:
			dialog.Show()
		except Exception:
			log.exception("WhatsApp Companion dialog could not be shown")
			if self._dialog is dialog:
				self._dialog = None
			raise

	def _onDialogDestroyed(self, event: wx.WindowDestroyEvent) -> None:
		if event.GetEventObject() is self._dialog:
			self._dialog = None
			resumeGeneration = self._registryDiagnosisResumeGeneration
			if resumeGeneration is not None:
				try:
					wx.CallAfter(self._continueRegistryDiagnosisAfterForceClose, resumeGeneration)
				except RuntimeError:
					self._registryDiagnosisResumeGeneration = None
		event.Skip()

	def _showLastResultDialog(self) -> None:
		if self._focusExistingDialog():
			return
		if self.lastResult is None:
			# Translators: Spoken and brailled when no companion operation has completed yet.
			message = _("No WhatsApp Companion result is available yet.")
		else:
			message = self._messageForResult(self.lastResult)
		self._showDialog(
			MessageDialog(
				gui.mainFrame,
				message,
				# Translators: Title for a dialog that shows the most recent companion or update result.
				_("WhatsApp Companion last result"),
			),
		)

	# Translators: Command description in NVDA's Input Gestures dialog.
	@script(description=_("Launch WhatsApp Stable with WhatsApp Companion"), speakOnDemand=True)
	def script_launchStable(self, gesture) -> None:
		self._launch(Channel.STABLE)

	# Translators: Command description in NVDA's Input Gestures dialog.
	@script(description=_("Launch WhatsApp Beta with WhatsApp Companion"), speakOnDemand=True)
	def script_launchBeta(self, gesture) -> None:
		self._launch(Channel.BETA)

	# Translators: Command description in NVDA's Input Gestures dialog.
	@script(
		description=_("Launch the last selected WhatsApp channel with WhatsApp Companion"),
		speakOnDemand=True,
	)
	def script_launchSelected(self, gesture) -> None:
		self._launch(self.selectedChannel)

	# Translators: Command description in NVDA's Input Gestures dialog.
	@script(
		description=_("Force close all running Microsoft Store WhatsApp Stable and Beta processes"),
		speakOnDemand=True,
	)
	def script_forceCloseWhatsApp(self, gesture) -> None:
		self._reviewForceClose()

	# Translators: Command description in NVDA's Input Gestures dialog.
	@script(description=_("Report the last WhatsApp Companion result"), speakOnDemand=True)
	def script_reportLastResult(self, gesture) -> None:
		if self.lastResult is None:
			# Translators: Spoken and brailled when no companion operation has completed yet.
			ui.message(_("No WhatsApp Companion result is available yet."))
			return
		self._report(self.lastResult)

	# Translators: Command description in NVDA's Input Gestures dialog.
	@script(
		description=_("Check for and install WhatsApp Web Plus userscript updates"),
		speakOnDemand=True,
	)
	def script_checkForScriptUpdates(self, gesture) -> None:
		self._startUpdateCheck()

	# Translators: Command description in NVDA's Input Gestures dialog.
	@script(description=_("Diagnose and repair WebView2 policy permissions"), speakOnDemand=True)
	def script_diagnoseAndRepairPermissions(self, gesture) -> None:
		self._startRegistryDiagnosis()

	def terminate(self) -> None:
		with self._updateLock:
			self._disposed = True
			self._generation += 1
			self._updateCancel.set()
			self._updateWorker = None
			self._updateCheckPending = False
			self._updateTerminalPending = False
		self._registryDiagnosisCancel.set()
		self._registryDiagnosisPending = False
		self._registryDiagnosisWorker = None
		self._registryDiagnosisResumeGeneration = None
		self._brailleMessages.terminate()
		if self._dialog is not None:
			try:
				self._dialog.Close()
			except (AttributeError, RuntimeError):
				pass
			self._dialog = None
		if self._menu is not None:
			self._menu.terminate()
			self._menu = None
		self.controller.stop()
		super().terminate()
