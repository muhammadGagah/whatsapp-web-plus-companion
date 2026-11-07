import addonHandler
import braille
from collections.abc import Callable
import config
import globalVars
import globalPluginHandler
import gui
from logHandler import log
import NVDAState
import os
import re
import speech
import sys
import threading
import time
from dataclasses import dataclass, replace
from functools import partial
import ui
import wx
from scriptHandler import script
from speech.commands import LangChangeCommand
from typing import Protocol

from . import commandFeedback, nativeProbes, settings
from .recording import Recording, foregroundWindow, listMicrophones, supported as recordingSupported
from .callAvailability import CallAvailability
from .announcements import BrailleMessageQueue, ScheduledCall
from .cleanup import forceCloseOperation
from .controller import Controller
from .dialogs import MessageDialog
from .launcher import launchOperation, recoverPendingRegistryStateAtStartup
from .menu import CompanionMenu, MenuSpec
from .models import Channel, LoaderError, OperationResult
from .messageReader import isReaderForeground, showReader, validateReader
from .packages import findPackage, findRunningPackageProcesses, runPowerShellCancellable
from .policy import CHANNELS, channelForExecutable
from .registry import WinRegistry, releaseRegistryMutex
from .registryRepair import (
	RegistryPermissionStatus,
	RepairIdentity,
	captureRequestIdentity,
	diagnoseRegistryPermissions,
	runRegistryRepair,
	tryAcquireRegistryMutex,
)
from .security import buildSecurityProbe, AnnouncementGuard
from .updater import UpdateCheckResult, UpdateStatus, checkForUpdate

addonHandler.initTranslation()

_DELIVERY_TIMEOUT = 2.0
# After a menu command, NVDA announces the window that regains focus (for
# example "Desktop list, OpenCode 52 of 60") and that announcement cuts off
# speech emitted synchronously from the menu handler. Defer add-on
# announcements long enough for the focus announcement to complete.
_ANNOUNCEMENT_DELAY_MS = 350
# The input desktop can lag NVDA's unlock notification; retry a held recording outcome briefly.
_HELD_REPORT_RETRY_MS = 1000
_HELD_REPORT_ATTEMPTS = 5
# Recording outcomes the user must hear even when they arrive while Windows is locked.
_TERMINAL_RECORDING_STATES = frozenset(
	{"saved", "limit", "call-ended", "cancelled", "failed", "unavailable", "focus-changed"},
)
# The closing setup dialog can keep NVDA in the foreground for a moment. Wait for WhatsApp instead.
_FOREGROUND_RETRY_MS = 100
_FOREGROUND_ATTEMPTS = 15
_BRAILLE_ANNOUNCEMENT_DWELL_FALLBACK_MS = 4000
_BRAILLE_MAX_PENDING_MESSAGES = 50
_VALID_ANNOUNCEMENT_SOURCES = frozenset({"status", "message-log", "alert"})
_LANGUAGE_PATTERN = re.compile(r"^[a-z]{2,3}(?:-[a-z0-9]{2,8})*$", re.IGNORECASE)
# Automatic connection only reopens a WhatsApp window that started this recently.
_AUTO_CONNECT_WINDOW = 30.0
# Results of an automatic connection that stay silent: WhatsApp was already open before.
_AUTO_CONNECT_QUIET = frozenset({"autoConnect.tooLate", "operation.cancelled"})


@dataclass
class _CompanionDelivery:
	"""Announcement order for one WhatsApp channel's userscript session."""

	session: str = ""
	generation: int = 0
	context: str = ""
	lastSequence: int = 0


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
		self._recordingSetupPending = False
		self._recordingSetupToken = 0
		self._heldRecordingReport: tuple[str, str] | None = None
		self._callAvailability = CallAvailability(wx.CallAfter, self._refreshRecordingAvailability)
		self._recording = Recording(self._queueRecordingReport)
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
		self._announcementGuard = AnnouncementGuard()
		self._securitySubscriptions = []
		self._companionOutputActive = False
		self._lastCompanionBraille = ""
		# Keyed by channel value; None holds results that name no channel.
		self._companionDeliveries: dict[str | None, _CompanionDelivery] = {}
		self._autoConnectSeen: set[int] = set()
		self._autoConnectTokens: dict[int, Channel] = {}
		self._autoConnectBlocked: set[Channel] = set()
		settings.register()
		self._brailleMessages = BrailleMessageQueue(
			self._showCompanionBraille,
			_scheduleBrailleMessage,
			dwellMilliseconds=_brailleMessageDwellMilliseconds,
			maxPendingMessages=_BRAILLE_MAX_PENDING_MESSAGES,
			overflowMessage=lambda count: _(
				"{count} braille announcements skipped.",
			).format(count=count),
			clearedMessage=lambda: _("WhatsApp Web Plus announcement cleared."),
			enabled=_brailleMessagesEnabled,
			outputAllowed=self._allowCompanionOutput,
		)
		self.controller = Controller(
			partial(launchOperation, announcementGuard=self._announcementGuard),
			self._queueReport,
			forceCloseOperation,
			self._queueLaunchReport,
		)
		self._subscribeAnnouncementSecurity()
		if not globalVars.appArgs.secure and NVDAState.shouldWriteToDisk():
			self._menu = self._createMenu()
			# NVDA may have exited during a launch. Restore its temporary WebView2 setting now, off the
			# GUI thread, so a WhatsApp started by hand never keeps the debugging port enabled.
			threading.Thread(
				target=recoverPendingRegistryStateAtStartup,
				name="WhatsAppCompanionRegistryRecovery",
				daemon=True,
			).start()

	def _subscribeAnnouncementSecurity(self) -> None:
		try:
			from utils.security import post_sessionLockStateChanged
			from winAPI.secureDesktop import post_secureDesktopStateChange

			for event, callback in (
				(post_sessionLockStateChanged, self._onSessionLockChanged),
				(post_secureDesktopStateChange, self._onSecureDesktopChanged),
			):
				event.register(callback)
				self._securitySubscriptions.append((event, callback))
		except (ImportError, AttributeError, RuntimeError):
			# Do not silently run without transition invalidation on unsupported NVDA.
			self._announcementGuard.setBlocked("missing-hooks", True)
			log.warning("WhatsApp Companion announcements disabled: security hooks unavailable")

	def _onSessionLockChanged(self, isNowLocked: bool) -> None:
		self._announcementGuard.setBlocked("lock", bool(isNowLocked))
		if isNowLocked:
			self._callAvailability.invalidate()
			self._recordingSetupToken += 1
			self._recordingSetupPending = False
			self._cancelCallRecovery()
			self._recording.stop()
			self._suspendCompanionOutput()
		else:
			self._scheduleHeldRecordingReport()

	def _onSecureDesktopChanged(self, isSecureDesktop: bool) -> None:
		self._announcementGuard.setBlocked("secure-desktop", bool(isSecureDesktop))
		if isSecureDesktop:
			self._callAvailability.invalidate()
			self._recordingSetupToken += 1
			self._recordingSetupPending = False
			self._cancelCallRecovery()
			self._recording.stop()
			# NVDA already cancels speech before announcing the secure desktop.
			self._suspendCompanionOutput(cancelSpeech=False)
		else:
			self._scheduleHeldRecordingReport()

	@staticmethod
	def _cancelCallRecovery():
		module = sys.modules.get("appModules.wwpCallSupport.runtime")
		if module is not None:
			module.cancelRecovery()

	def _suspendCompanionOutput(self, *, cancelSpeech: bool = True) -> None:
		self._brailleMessages.clearPending(silent=True)
		if self._companionOutputActive and cancelSpeech:
			try:
				speech.cancelSpeech()
			except (AttributeError, RuntimeError):
				pass
		# Clear only our last message, never a newer lock-screen/NVDA message.
		try:
			handler = braille.handler
			messageBuffer = handler.messageBuffer
			if self._lastCompanionBraille and messageBuffer.rawText == self._lastCompanionBraille:
				messageBuffer.clear()
				messageBuffer.update()
				if handler.buffer is messageBuffer:
					handler.update()
		except (AttributeError, RuntimeError):
			pass
		self._companionOutputActive = False
		self._lastCompanionBraille = ""
		self._companionDeliveries.clear()

	def _delivery(self, channel: object = None) -> _CompanionDelivery:
		key = channel if isinstance(channel, str) and channel else None
		return self._companionDeliveries.setdefault(key, _CompanionDelivery())

	# Single-channel views of the delivery state, used where a result names no channel.
	@property
	def _companionSession(self) -> str:
		return self._delivery().session

	@_companionSession.setter
	def _companionSession(self, value: str) -> None:
		self._delivery().session = value

	@property
	def _companionGeneration(self) -> int:
		return self._delivery().generation

	@_companionGeneration.setter
	def _companionGeneration(self, value: int) -> None:
		self._delivery().generation = value

	@property
	def _companionContext(self) -> str:
		return self._delivery().context

	@_companionContext.setter
	def _companionContext(self, value: str) -> None:
		self._delivery().context = value

	@property
	def _companionLastSequence(self) -> int:
		return self._delivery().lastSequence

	@_companionLastSequence.setter
	def _companionLastSequence(self, value: int) -> None:
		self._delivery().lastSequence = value

	def _allowCompanionOutput(self) -> bool:
		return not self._disposed and self._announcementGuard.permits()

	def _showCompanionBraille(self, text: str) -> None:
		if not self._allowCompanionOutput():
			self._suspendCompanionOutput()
			return
		braille.handler.message(text)
		self._lastCompanionBraille = text
		self._companionOutputActive = True

	def _createMenu(self) -> CompanionMenu:
		return CompanionMenu(
			# Translators: Submenu label shown under NVDA's Tools menu.
			_("&WhatsApp Companion"),
			# Translators: Help text for the add-on submenu under NVDA's Tools menu.
			_(
				"Open WhatsApp with WhatsApp Companion and manage its settings.",
			),
			(
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
					MenuSpec(
						# Translators: Checkable Tools submenu command. The ampersand marks the mnemonic.
						_("Connect &automatically when WhatsApp is opened"),
						_(
							"Reopen WhatsApp with WhatsApp Companion when you open it from the Start menu, taskbar or desktop",
						),
						self._onAutoConnectMenu,
						isChecked=settings.autoConnect,
					),
				),
				(
					MenuSpec(
						# Translators: Destructive Tools submenu command. The ampersand marks the mnemonic.
						_("&Force close Microsoft Store WhatsApp processes..."),
						_(
							"Close WhatsApp Stable, Beta or both when they won't close normally",
						),
						self._onForceCloseMenu,
					),
					MenuSpec(
						# Translators: Tools submenu command. The ellipsis is required because activation may show a confirmation dialog.
						_("Diagnose and repair WebView2 &policy permissions..."),
						_(
							"Check the WebView2 permissions WhatsApp Companion needs, and fix them if needed",
						),
						self._onDiagnoseRepairMenu,
					),
				),
				(
					MenuSpec(
						_("Call control lab&els..."),
						_("Customize call control labels for the language used by WhatsApp"),
						self._onCallLabelsMenu,
					),
					MenuSpec(
						_("Start call &recording..."),
						_("Record the call and your microphone to a WAV file"),
						self._onStartRecordingMenu,
						self._recordingMenuEnabled,
					),
					MenuSpec(
						_("Sto&p recording"),
						_("Stop recording and save the WAV file"),
						self._onStopRecordingMenu,
						lambda: self._recording.active or self._recordingSetupPending,
					),
				),
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
							"Check for and install the latest official WhatsApp Web Plus",
						),
						self._onCheckForScriptUpdatesMenu,
					),
				),
			),
			refresh=self._requestCallAvailability,
		)

	def _onStartRecordingMenu(self, event: wx.CommandEvent) -> None:
		event.Skip()
		wx.CallAfter(self._prepareRecording)

	def _onStopRecordingMenu(self, event: wx.CommandEvent) -> None:
		event.Skip()
		self._stopRecording()

	def _recordingAllowed(self) -> bool:
		return (
			not self._disposed
			and self._announcementGuard.permits()
			and not globalVars.appArgs.secure
			and NVDAState.shouldWriteToDisk()
		)

	def _prepareRecording(self) -> None:
		if not self._recordingAllowed():
			return
		self._deliverHeldRecordingReport()
		if self._recording.active or self._recordingSetupPending:
			self._announceRecording(_("A recording is already running or starting."))
			return
		if not recordingSupported():
			self._announceRecording(_("Call recording requires Windows build 20348 or later."))
			return
		self._recordingSetupPending = True
		self._recordingSetupToken += 1
		token = self._recordingSetupToken
		self._announceRecording(_("Checking for a WhatsApp call. Please wait."))
		self._callAvailability.request(
			force=True,
			callback=lambda calls: self._recordingCallReady(calls, token),
		)

	def _recordingMenuEnabled(self) -> bool:
		if not self._recordingAllowed() or self._recording.active or self._recordingSetupPending:
			return False
		if not recordingSupported():
			return False
		# Unknown stays enabled: Start always runs its own fresh probe before anything is recorded.
		return self._callAvailability.available() is not False

	def _requestCallAvailability(self) -> None:
		"""Passive refresh for the open menu; CallAvailability throttles and never overlaps probes."""
		if self._recordingAllowed() and not self._recording.active and recordingSupported():
			self._callAvailability.request()

	def _recordingCallAvailable(self, channel) -> bool | None:
		if not self._recordingAllowed() or self._recording.active:
			return False
		self._callAvailability.request()
		return self._callAvailability.available(channel)

	def _announceCallCheckFailed(self) -> None:
		self._announceRecording(
			# Translators: The call state check failed or timed out, so no call can be confirmed or ruled out.
			_("Couldn't check for a WhatsApp call. Try again."),
		)

	def _refreshRecordingAvailability(self) -> None:
		if not self._disposed and self._menu is not None:
			self._menu.refreshEnabled()

	def _recordingCallReady(self, calls, token) -> None:
		if token != self._recordingSetupToken:
			return
		if not self._recordingAllowed():
			self._recordingSetupPending = False
			return
		if calls is None:
			self._recordingSetupPending = False
			self._announceCallCheckFailed()
			return
		if not calls:
			self._recordingSetupPending = False
			self._announceRecording(
				_("No WhatsApp call found. Open the full call window and try again."),
			)
			return
		if self._focusExistingDialog():
			self._recordingSetupPending = False
			return
		self._announceRecording(_("Loading microphones. Please wait."))

		def load():
			try:
				devices = listMicrophones()
			except Exception:
				devices = []
			wx.CallAfter(self._checkRecordingAfterDevices, devices, token)

		threading.Thread(target=load, name="WhatsAppRecordingDevices", daemon=True).start()

	def _checkRecordingAfterDevices(self, devices, token) -> None:
		if token != self._recordingSetupToken:
			return
		if not self._recordingAllowed():
			self._recordingSetupPending = False
			return
		self._callAvailability.request(
			force=True,
			callback=lambda calls: self._showRecordingDialog(devices, token, calls),
		)

	def _showRecordingDialog(self, devices, token, calls) -> None:
		if token != self._recordingSetupToken:
			return
		self._recordingSetupPending = False
		if not self._recordingAllowed():
			return
		if calls is None:
			self._announceCallCheckFailed()
			return
		if not calls:
			self._announceRecording(
				_("No WhatsApp call found. Open the full call window and try again."),
			)
			return
		if not devices:
			self._announceRecording(
				_("Couldn't load microphones. Check microphone access in Windows settings and try again."),
			)
			return
		if self._focusExistingDialog():
			return
		from .recordingDialog import RecordingDialog

		dialog = RecordingDialog(
			gui.mainFrame,
			devices=devices,
			channel=self.selectedChannel if self.selectedChannel in calls else next(iter(calls)),
			allowed=self._recordingAllowed,
			callAvailable=self._recordingCallAvailable,
			onStatus=self._announceRecording,
			onStart=self._startRecording,
		)
		gui.mainFrame.prePopup()
		try:
			self._showDialog(dialog)
		finally:
			gui.mainFrame.postPopup()

	def _startRecording(
		self,
		channel,
		microphone,
		directory,
		completed=lambda started: None,
		stillOpen=lambda: True,
	) -> None:
		if not self._recordingAllowed():
			completed(False)
			return
		self._recordingSetupToken += 1
		token = self._recordingSetupToken
		self._recordingSetupPending = True
		self._announceRecording(_("Checking for a WhatsApp call. Please wait."))

		def checked(calls):
			if token != self._recordingSetupToken or not self._recordingAllowed() or not stillOpen():
				if token == self._recordingSetupToken:
					self._recordingSetupPending = False
				completed(False)
				return
			if calls is None:
				self._recordingSetupPending = False
				self._announceCallCheckFailed()
				completed(False)
				return
			if channel not in calls:
				self._recordingSetupPending = False
				self._announceRecording(
					_("No WhatsApp call found. Open the full call window and try again."),
				)
				completed(False)
				return
			self._announceRecording(_("Opening the call window to check the call before recording."))
			completed(True)

			wx.CallAfter(
				self._beginRecordingWhenForegroundSettles,
				channel,
				microphone,
				directory,
				token,
				_FOREGROUND_ATTEMPTS,
			)

		self._callAvailability.request(force=True, callback=checked)

	def _beginRecordingWhenForegroundSettles(self, channel, microphone, directory, token, attempts) -> None:
		"""Start capture with the window that is in front once NVDA's setup dialog has gone.

		The helper refuses to act if that window changes, so it must not be NVDA's own dialog.
		"""
		if token != self._recordingSetupToken:
			return
		if not self._recordingAllowed():
			self._recordingSetupPending = False
			self._refreshRecordingAvailability()
			return
		try:
			window, processId = foregroundWindow()
		except (OSError, AttributeError, ValueError):
			# Unknown foreground: start anyway; the helper then reports a focus change instead of hanging.
			window, processId = 0, 0
		if attempts > 0 and (not window or processId == os.getpid()):
			try:
				wx.CallLater(
					_FOREGROUND_RETRY_MS,
					self._beginRecordingWhenForegroundSettles,
					channel,
					microphone,
					directory,
					token,
					attempts - 1,
				)
				return
			except (RuntimeError, TypeError):
				pass
		self._recordingSetupPending = False
		if self._recording.start(channel, microphone, directory, foreground=window):
			self._announceRecording(_("Starting call recording. Please wait."))
		self._refreshRecordingAvailability()

	def _stopRecording(self) -> None:
		self._deliverHeldRecordingReport()
		pending = self._recordingSetupPending
		self._recordingSetupToken += 1
		self._recordingSetupPending = False
		self._callAvailability.invalidate()
		if self._recording.active and self._recording.captureStarted:
			self._recording.stop()
			self._announceRecording(_("Stopping recording and saving the file."))
		elif self._recording.active:
			self._recording.stop()
			# Translators: Stop was pressed before capture started; nothing is saved.
			self._announceRecording(_("Cancelling the recording."))
		elif pending:
			self._announceRecording(_("Recording cancelled before it started."))
		else:
			self._announceRecording(_("No call recording is running."))

	def _announceRecording(self, message):
		self._announce(message, protected=True)

	def _queueRecordingReport(self, state, path):
		"""Runs on the recording worker."""
		allowed, epoch = self._announcementGuard.snapshot()
		if allowed:
			wx.CallAfter(self._deliverRecordingReport, state, path, epoch)
		elif state in _TERMINAL_RECORDING_STATES:
			wx.CallAfter(self._holdRecordingReport, state, path)

	def _deliverRecordingReport(self, state, path, epoch):
		if self._announcementGuard.permits(epoch):
			self._recordingReport(state, path)
		elif state in _TERMINAL_RECORDING_STATES:
			self._holdRecordingReport(state, path)

	def _holdRecordingReport(self, state, path) -> None:
		# Kept in memory only and never spoken on the lock screen or secure desktop. The latest outcome
		# wins, so after unlock the user still hears that recording stopped and where it was saved.
		if not self._disposed:
			self._heldRecordingReport = (state, path)
			# Unlock may already have happened; delivery still waits until output is permitted.
			self._scheduleHeldRecordingReport()

	def _scheduleHeldRecordingReport(self) -> None:
		if self._heldRecordingReport is None or self._disposed:
			return
		try:
			wx.CallLater(_HELD_REPORT_RETRY_MS, self._deliverHeldRecordingReport, _HELD_REPORT_ATTEMPTS)
		except (RuntimeError, TypeError):
			pass

	def _deliverHeldRecordingReport(self, attempts: int = 0) -> None:
		if self._heldRecordingReport is None or self._disposed:
			return
		if not self._recordingAllowed():
			if attempts > 1:
				try:
					wx.CallLater(_HELD_REPORT_RETRY_MS, self._deliverHeldRecordingReport, attempts - 1)
				except (RuntimeError, TypeError):
					pass
			return
		state, path = self._heldRecordingReport
		self._heldRecordingReport = None
		self._recordingReport(state, path)

	def _recordingReport(self, state, path) -> None:
		if not self._recordingAllowed():
			return
		if state in _TERMINAL_RECORDING_STATES:
			# If a lock arrives during the speech delay, keep the outcome for unlock instead of losing it.
			announce = partial(
				self._announce,
				protected=True,
				onBlocked=lambda: self._holdRecordingReport(state, path),
			)
		else:
			announce = partial(self._announce, protected=True)
		self._refreshRecordingAvailability()
		if state == "unavailable" and self._recording.cancel.is_set():
			state = "cancelled"
		if state == "unavailable":
			self._callAvailability.invalidate()
			announce(
				_("No WhatsApp call found. Open the full call window and try again."),
			)
			return
		if state == "started":
			if not self._recording.cancel.is_set():
				announce(_("Call recording started."))
		elif state == "saved":
			announce(_("Recording saved: {path}").format(path=path))
		elif state == "call-ended":
			self._callAvailability.invalidate()
			announce(
				# Translators: The recorder stopped by itself after the WhatsApp call window closed.
				_("The call ended. Recording saved: {path}").format(path=path),
			)
		elif state == "limit":
			announce(
				# Translators: The recorder stopped by itself at its maximum length.
				_("Recording reached the 4-hour limit. Saved: {path}").format(path=path),
			)
		elif state == "cancelled":
			announce(_("Recording cancelled."))
		elif state == "focus-changed":
			announce(
				# Translators: Recording did not start because another window took the foreground.
				_(
					"Recording didn't start because you left the call window. Stay in the call window and try again.",
				),
			)
		elif path:
			announce(
				_("Recording stopped because of an error. Part of it may be saved at: {path}").format(
					path=path,
				),
			)
		else:
			announce(
				_(
					"Couldn't record the call. Check that the selected WhatsApp is open, the microphone is free and you can save to the folder. No other computer audio was recorded.",
				),
			)

	def _onCallLabelsMenu(self, event: wx.CommandEvent) -> None:
		event.Skip()
		wx.CallAfter(self._showCallLabelsDialog)

	def _showCallLabelsDialog(self) -> None:
		if self._disposed or not self._announcementGuard.permits():
			return
		if globalVars.appArgs.secure or not NVDAState.shouldWriteToDisk():
			return
		if self._focusExistingDialog():
			return
		from .callLabelsDialog import CallLabelsDialog

		try:
			dialog = CallLabelsDialog(
				gui.mainFrame,
				onSaved=lambda: self._announce(_("Call control labels saved.")),
				allowed=lambda: not self._disposed and self._announcementGuard.permits(),
			)
		except Exception:
			log.warning("WhatsApp Companion call labels could not be loaded")
			self._announce(_("Couldn't load call control labels. Your saved labels weren't changed."))
			return
		gui.mainFrame.prePopup()
		try:
			self._showDialog(dialog)
		finally:
			gui.mainFrame.postPopup()

	def _onLaunchStableMenu(self, event: wx.CommandEvent) -> None:
		event.Skip()
		self._launch(Channel.STABLE)

	def _onLaunchBetaMenu(self, event: wx.CommandEvent) -> None:
		event.Skip()
		self._launch(Channel.BETA)

	def _onLaunchSelectedMenu(self, event: wx.CommandEvent) -> None:
		event.Skip()
		self._launch(self.selectedChannel)

	def _onAutoConnectMenu(self, event: wx.CommandEvent) -> None:
		event.Skip()
		self._toggleAutoConnect()

	def _toggleAutoConnect(self) -> None:
		if self._disposed:
			return
		enabled = not settings.autoConnect()
		if not settings.setAutoConnect(enabled):
			# Translators: Spoken when the automatic connection setting cannot be saved.
			self._announce(_("Couldn't change automatic connection."))
			return
		if enabled:
			# Opening WhatsApp again after this choice should connect, even if it failed before.
			self._autoConnectBlocked.clear()
			self._announce(
				# Translators: Spoken after turning on automatic connection.
				_(
					"Automatic connection on. When you open WhatsApp, it will reopen with WhatsApp Companion.",
				),
			)
		else:
			# Translators: Spoken after turning off automatic connection.
			self._announce(_("Automatic connection off."))

	def event_foreground(self, obj, nextHandler) -> None:
		try:
			self._maybeAutoConnect(obj)
		except Exception:
			log.exception("Unexpected WhatsApp Companion automatic connection failure")
		nextHandler()

	def _maybeAutoConnect(self, obj) -> None:
		"""Reopen a WhatsApp that the user has just opened, so WhatsApp Companion can connect.

		This runs on NVDA's GUI thread, so it only reads cached app details and one process time.
		The launch worker checks again before closing anything.
		"""
		if self._disposed or not settings.autoConnect() or not self._recordingAllowed():
			return
		appModule = getattr(obj, "appModule", None)
		appName = getattr(appModule, "appName", "")
		if not isinstance(appName, str) or not appName.casefold().startswith("whatsapp"):
			return
		pid = getattr(obj, "processID", 0)
		if type(pid) is not int or pid <= 0 or pid in self._autoConnectSeen:
			return
		if len(self._autoConnectSeen) > 256:
			self._autoConnectSeen.clear()
		self._autoConnectSeen.add(pid)
		channel = channelForExecutable(getattr(appModule, "appPath", None))
		if (
			channel is None
			or channel in self._autoConnectBlocked
			or self.controller.channelActive(channel)
			or self.controller.forceClosing
			or self.controller.repairing
			or self._registryDiagnosisActive
		):
			return
		try:
			age = nativeProbes.processAgeSeconds(pid)
		except nativeProbes.NativeProbeUnavailable:
			return
		if age is None or age > _AUTO_CONNECT_WINDOW:
			return
		if not self.controller.start(channel, replaceRecent=True):
			return
		self._autoConnectTokens[self.controller.operationToken] = channel
		self._resetCompanionDeliveryState(channel.value)
		self.selectedChannel = channel
		self._report(
			OperationResult(
				False,
				"autoConnect.starting",
				"autoConnect.starting",
				{"channel": channel.value},
			),
			defer=True,
		)

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
		channel = self.controller.channelForToken(token)
		if channel is not None and "channel" not in result.values:
			result = replace(result, values={**result.values, "channel": channel.value})
		autoChannel = self._autoConnectTokens.get(token)
		if autoChannel is not None and not result.messageKey.startswith(("companion.", "cdp.")):
			if result.messageKey == "active":
				self._autoConnectBlocked.discard(autoChannel)
			elif not result.ok:
				self._autoConnectTokens.pop(token, None)
				# Do not reopen this channel by itself again until a launch succeeds.
				self._autoConnectBlocked.add(autoChannel)
				if result.code in _AUTO_CONNECT_QUIET:
					log.info("WhatsApp Companion did not connect automatically: code=%s", result.code)
					return True
		return self._queueReport(result, launchToken=token)

	def _queueReport(self, result: OperationResult, *, launchToken: int | None = None) -> bool:
		if self._disposed:
			return False
		generation = self._generation
		securityEpoch = self._announcementGuard.snapshot()[1]
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
				if result.messageKey.startswith("companion.") and not self._announcementGuard.permits(
					securityEpoch,
				):
					if not self._allowCompanionOutput():
						self._suspendCompanionOutput()
					state["delivered"] = True
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
		end = time.monotonic() + _DELIVERY_TIMEOUT
		while not completed.wait(min(0.05, max(0.0, end - time.monotonic()))):
			stale = (
				self._disposed
				or generation != self._generation
				or (launchToken is not None and not self.controller.launchTokenIsActive(launchToken))
			)
			if stale or time.monotonic() >= end:
				with lock:
					state["cancelled"] = True
					# A callback already executing owns this report. Consume it rather
					# than retrying and duplicating speech; never wait without a bound.
					return state["started"] and not stale
		return state["delivered"]

	def _reportIfCurrent(self, generation: int, result: OperationResult) -> bool:
		if self._disposed or generation != self._generation:
			return False
		if result.messageKey.startswith("companion.") and not self._announcementGuard.permits(
			result.values.get("securityEpoch"),
		):
			if not self._allowCompanionOutput():
				self._suspendCompanionOutput()
			return True
		if result.messageKey == "companion.invalidate":
			return self._applyCompanionInvalidation(result)
		if result.messageKey == "companion.overflow":
			if not self._isCurrentCompanionResult(result):
				return False
			# Translators: Spoken and brailled if the bounded bridge queue overflowed during a disconnect.
			self._speakAndQueueBraille(
				_("Some announcements were missed while reconnecting."),
			)
			return True
		if result.messageKey == "companion.announcement":
			return self._deliverCompanionAnnouncement(result)
		if result.messageKey == "companion.reader":
			return self._deliverCompanionReader(result)
		if result.messageKey == "package.closed":
			# Closing WhatsApp already moves focus to another application. Store the
			# outcome for the on-demand report command without interrupting that focus announcement.
			self.lastResult = result
			self._resetCompanionDeliveryState(result.values.get("channel"))
			if result.values.get("recoveryReported"):
				commandFeedback.message(self._messageForResult(result))
			return True
		if result.messageKey == "cdp.recovering":
			# Progress must not replace the last completed operation result.
			# Translators: Spoken while retrying a temporarily unavailable connection.
			commandFeedback.message(_("Reconnecting WhatsApp Companion. Please wait."))
			return True
		self._report(result)
		return True

	def _resetCompanionDeliveryState(self, channel: object = None) -> None:
		self._brailleMessages.clearPending()
		if isinstance(channel, str) and channel:
			self._companionDeliveries.pop(channel, None)
			self._companionDeliveries.pop(None, None)
		else:
			self._companionDeliveries.clear()

	@staticmethod
	def _foregroundChannel() -> Channel | None:
		try:
			import api

			return channelForExecutable(api.getForegroundObject().appModule.appPath)
		except (ImportError, AttributeError, RuntimeError, OSError):
			return None

	def _otherWhatsAppInFront(self, channel: object) -> bool:
		"""While one WhatsApp is in front, the other one's announcements are not spoken."""
		if not isinstance(channel, str) or not channel:
			return False
		foreground = self._foregroundChannel()
		return foreground is not None and foreground.value != channel

	def _applyCompanionInvalidation(self, result: OperationResult) -> bool:
		delivery = self._delivery(result.values.get("channel"))
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
		sessionChanged = session != delivery.session
		if sessionChanged:
			delivery.lastSequence = 0
		invalidatedSource = result.values.get("source")
		if sessionChanged:
			self._brailleMessages.clearPending()
		elif invalidatedSource in _VALID_ANNOUNCEMENT_SOURCES:
			self._brailleMessages.discardPending(invalidatedSource)
		else:
			self._brailleMessages.clearPending()
		delivery.session = session
		delivery.generation = generation
		delivery.context = context
		return True

	def _isCurrentCompanionResult(self, result: OperationResult) -> bool:
		delivery = self._delivery(result.values.get("channel"))
		return (
			result.values.get("session") == delivery.session
			and result.values.get("generation") == delivery.generation
			and result.values.get("context") == delivery.context
		)

	def _deliverCompanionAnnouncement(self, result: OperationResult) -> bool:
		if not self._announcementGuard.permits(result.values.get("securityEpoch")):
			if not self._allowCompanionOutput():
				self._suspendCompanionOutput()
			return True
		if not self._isCurrentCompanionResult(result):
			return False
		delivery = self._delivery(result.values.get("channel"))
		sequence = result.values.get("sequence")
		source = result.values.get("source")
		language = result.values.get("language", "")
		privacy = result.values.get("privacy")
		text = result.values.get("text")
		if (
			isinstance(sequence, bool)
			or not isinstance(sequence, int)
			or sequence <= delivery.lastSequence
			or source not in _VALID_ANNOUNCEMENT_SOURCES
			or not isinstance(privacy, bool)
			or not isinstance(text, str)
			or not text
			or not isinstance(language, str)
			or (language and not _LANGUAGE_PATTERN.fullmatch(language))
		):
			return False
		if self._otherWhatsAppInFront(result.values.get("channel")):
			delivery.lastSequence = sequence
			return True
		if language:
			self._speakAndQueueBraille(text, language, source)
		else:
			self._speakAndQueueBraille(text, source=source)
		delivery.lastSequence = sequence
		return True

	def _deliverCompanionReader(self, result: OperationResult) -> bool:
		if not self._announcementGuard.permits(result.values.get("securityEpoch")):
			return True
		if not self._isCurrentCompanionResult(result):
			return True
		delivery = self._delivery(result.values.get("channel"))
		sequence = result.values.get("sequence")
		if type(sequence) is not int or sequence <= 0:
			return True
		if sequence <= delivery.lastSequence:
			return True
		# The GUI operation is not idempotent and returns None even on success.
		# Claim the sequence before opening so delivery retries cannot reopen it.
		delivery.lastSequence = sequence
		reader = validateReader(result.values.get("reader"))
		expiresAt = result.values.get("readerExpiresAt")
		if type(expiresAt) is not int or expiresAt <= time.time() * 1000:
			return True
		language = result.values.get("language", "")
		if (
			reader is None
			or not isinstance(language, str)
			or not isReaderForeground(result.values.get("readerProcessIds"))
		):
			return True
		self._brailleMessages.clearPending(silent=True)
		try:
			showReader(reader, language)
		except Exception:
			log.exception("WhatsApp Companion message reader could not be opened")
		return True

	def _speakAndQueueBraille(self, text: str, language: str = "", source: str = "") -> None:
		if not self._allowCompanionOutput():
			self._suspendCompanionOutput()
			return
		self._companionOutputActive = True
		if language:
			speech.speech.speak(
				[
					LangChangeCommand(language.replace("-", "_")),
					text,
					LangChangeCommand(None),
				],
			)
		else:
			speech.speech.speak([text])
		self._brailleMessages.enqueue(text, source)

	def _announce(
		self,
		message: str,
		*,
		protected: bool = False,
		onBlocked: Callable[[], None] | None = None,
	) -> None:
		"""Speak after the closing menu's focus announcement."""
		epoch = self._announcementGuard.snapshot()[1] if protected else None

		def speak() -> None:
			if self._disposed:
				return
			if protected and not self._announcementGuard.permits(epoch):
				if onBlocked is not None:
					onBlocked()
				return
			commandFeedback.message(message)

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
			commandFeedback.message(message)

	def _messageForResult(
		self,
		result: OperationResult,
		*,
		hadActiveResult: bool = False,
		includeDiagnosticCode: bool = False,
	) -> str:
		channel = self._channelLabel(result.values.get("channel"))
		remainingChannels = self._channelListLabel(result.values.get("remainingChannels"))
		# Translators: Spoken and brailled when another Registry operation is still active.
		registryBusyMessage = _(
			"The previous launch is still finishing. Wait a moment and try again. If this keeps happening, restart NVDA.",
		)
		messages = {
			# Translators: Spoken and brailled after connection recovery and health verification succeed.
			"cdp.restored": _("WhatsApp Companion is connected again."),
			# Translators: Spoken and brailled after the companion has loaded successfully.
			"active": _("WhatsApp {channel} is ready with WhatsApp Companion.").format(
				channel=channel,
			),
			# Translators: Spoken and brailled while WhatsApp is still starting or loading.
			"operation.loading": _(
				"Opening WhatsApp {channel} with WhatsApp Companion. Please wait.",
			).format(channel=channel),
			# Translators: Spoken and brailled when a launch command is invoked while a session is active.
			"operation.busy": _("WhatsApp Companion is already running. Close WhatsApp first."),
			# Translators: Spoken and brailled when this WhatsApp channel already runs with the Companion.
			"operation.channelBusy": _(
				"WhatsApp {channel} is already running with WhatsApp Companion.",
			).format(
				channel=channel,
			),
			# Translators: Spoken when a WhatsApp the user just opened is reopened with the Companion.
			"autoConnect.starting": _(
				"Reopening WhatsApp {channel} with WhatsApp Companion. Please wait.",
			).format(channel=channel),
			# Translators: Spoken when a WhatsApp the user just opened could not be closed to reopen it.
			"autoConnect.closeFailed": _(
				"Couldn't reopen WhatsApp {channel}. Close it, then launch it from the WhatsApp Companion menu.",
			).format(channel=channel),
			# Translators: Spoken and brailled when the user closes WhatsApp normally.
			"package.closed": _("WhatsApp {channel} was closed. WhatsApp Companion stopped.").format(
				channel=channel,
			),
			# Translators: Recovery message when WhatsApp was already open before the companion started.
			"package.running": _("WhatsApp is already open. Close it, then try again."),
			# Translators: Diagnosis stops because a package/process probe failed.
			"registry.repair.processUnknown": _(
				"Couldn't tell whether WhatsApp is open, so the check stopped. Try again.",
			),
			# Translators: Spoken and brailled when NVDA stops an in-progress launch.
			"operation.cancelled": _("Launch cancelled."),
			# Translators: Status when another force-close request is made while one is running.
			"processes.busy": _("WhatsApp is already being closed. Please wait."),
			# Translators: Result when neither Microsoft Store WhatsApp channel has a running process.
			"processes.none": _(
				"WhatsApp Stable and Beta weren't running.",
			),
			# Translators: Result when the selected Microsoft Store WhatsApp channel was not running.
			"processes.none.one": _("WhatsApp {channel} wasn't running.").format(
				channel=channel,
			),
			# Translators: Result after every process of the selected Microsoft Store WhatsApp channel was closed.
			"processes.closed.one": _(
				"WhatsApp {channel} was closed ({closedCount} processes).",
			).format(channel=channel, closedCount=result.values.get("closedCount", 0)),
			# Translators: Result after every discovered Microsoft Store WhatsApp process was closed.
			"processes.closed": _(
				"WhatsApp Stable and Beta were closed ({closedCount} processes).",
			).format(closedCount=result.values.get("closedCount", 0)),
			# Translators: Result when some Microsoft Store WhatsApp processes remain after a force-close attempt.
			"processes.partial": _(
				"Closed {closedCount} WhatsApp processes, but WhatsApp {remainingChannels} may still be running. Restart Windows before launching again.",
			).format(
				remainingChannels=remainingChannels,
				closedCount=result.values.get("closedCount", 0),
			),
			# Translators: Result when no Microsoft Store WhatsApp process could be force closed or verified.
			"processes.failed": _(
				"Couldn't close WhatsApp {remainingChannels}, or couldn't confirm that it closed. Restart Windows before launching again.",
			).format(remainingChannels=remainingChannels),
			# Translators: Recovery message when force close is unavailable in the current NVDA context.
			"processes.context": _(
				"Can't close WhatsApp from this NVDA session. Unlock Windows and run NVDA normally, not as administrator.",
			),
			# Translators: Recovery message after renderer reconnection has failed.
			"cdp.reconnect": _(
				"Couldn't reconnect WhatsApp Companion. Close WhatsApp, then launch it again.",
			),
			# Translators: Recovery message for locked, secure, read-only, or elevated NVDA contexts.
			"security": _("Unlock Windows and run NVDA normally, not as administrator, then try again."),
			# Translators: Recovery message when the selected Microsoft Store WhatsApp channel is unavailable.
			"package": _("Install this WhatsApp from Microsoft Store, then try again."),
			# Translators: Recovery message while an earlier Companion launch is still releasing its registry lease.
			"registry.busy": registryBusyMessage,
			# Translators: Recovery message when the named Registry mutex cannot be created.
			"registry.mutex.createFailed": _(
				"Couldn't safely use the Windows Registry. Restart NVDA and try again. If this keeps happening, report it.",
			),
			# Translators: Recovery message when Windows fails while checking Registry mutex ownership.
			"registry.mutex.waitFailed": _(
				"Another WhatsApp Companion task may still be using the Registry. Restart NVDA and try again. If this keeps happening, report it.",
			),
			# Translators: Recovery message while another Companion Registry operation owns the mutex.
			"registry.mutex.busy": registryBusyMessage,
			# Translators: Recovery message when machine-wide WebView2 policy cannot be read.
			"registry.machine.readAccessDenied": _(
				"Windows blocked the computer-wide WebView2 setting. Ask your administrator for help.",
			),
			# Translators: Recovery message for an unexpected machine-wide WebView2 policy read failure.
			"registry.machine.readFailed": _(
				"Couldn't check the computer-wide WebView2 setting. Ask your administrator, or report it.",
			),
			# Translators: Recovery message when this exact WhatsApp channel is controlled by machine policy.
			"registry.machine.policyAumid": _(
				"A Windows policy controls WebView2 for this WhatsApp, and WhatsApp Companion can't override it. Nothing was changed. Ask your administrator for help.",
			),
			# Translators: Recovery message when a wildcard WebView2 argument is controlled by machine policy.
			"registry.machine.policyWildcard": _(
				"A Windows policy controls WebView2 for all apps, and WhatsApp Companion can't override it. Nothing was changed. Ask your administrator for help.",
			),
			# Translators: Recovery message when the per-user WebView2 policy value cannot be read.
			"registry.user.readAccessDenied": _(
				"Windows blocked a WebView2 setting that WhatsApp Companion needs. In the WhatsApp Companion menu, choose Diagnose and repair WebView2 policy permissions, then try again.",
			),
			# Translators: Recovery message for an unexpected per-user WebView2 policy read failure.
			"registry.user.readFailed": _(
				"Couldn't read your WebView2 setting. Close WhatsApp and try again. If this keeps happening, report it.",
			),
			# Translators: Recovery message when an existing WebView2 value has an unsupported data type.
			"registry.user.invalidValueType": _(
				"Your WebView2 launch setting uses a type WhatsApp Companion doesn't support, so it was left unchanged. Check it manually.",
			),
			# Translators: Recovery message when a pre-existing debugging argument is not owned by the Companion.
			"registry.user.debugArgumentPresent": _(
				"This WhatsApp already has a remote debugging setting that WhatsApp Companion didn't create, so it was left unchanged. Remove it yourself if you don't need it.",
			),
			# Translators: Recovery message when the per-user WebView2 policy leaf cannot be created or opened.
			"registry.user.openCreateAccessDenied": _(
				"Windows didn't let WhatsApp Companion save its temporary WebView2 setting, so WhatsApp wasn't launched. In the WhatsApp Companion menu, choose Diagnose and repair WebView2 policy permissions, then try again.",
			),
			# Translators: Recovery message for an unexpected leaf open/create failure.
			"registry.user.openCreateFailed": _(
				"Couldn't save the temporary WebView2 setting, so WhatsApp wasn't launched. Close WhatsApp and try again. If this keeps happening, report it.",
			),
			# Translators: Recovery message when the temporary value cannot be set.
			"registry.user.setAccessDenied": _(
				"Windows didn't let WhatsApp Companion save its temporary WebView2 setting, so WhatsApp wasn't launched. In the WhatsApp Companion menu, choose Diagnose and repair WebView2 policy permissions, then try again.",
			),
			# Translators: Recovery message for an unexpected temporary value write failure.
			"registry.user.setFailed": _(
				"Couldn't write the temporary WebView2 setting, so WhatsApp wasn't launched. Close WhatsApp and try again. If this keeps happening, report it.",
			),
			# Translators: Recovery message when the temporary value read-back does not match.
			"registry.user.verifyMismatch": _(
				"Couldn't confirm the temporary WebView2 setting. Close WhatsApp and try again.",
			),
			# Translators: Urgent recovery message when the per-user WebView2 setting cannot be opened during restore.
			"registry.restore.openAccessDenied": _(
				"Couldn't put your previous WebView2 setting back. Close WhatsApp now, then run Diagnose and repair WebView2 policy permissions. WhatsApp Companion will try again before the next launch.",
			),
			# Translators: Recovery message for an unexpected restore-open failure.
			"registry.restore.openFailed": _(
				"Couldn't open your previous WebView2 setting to put it back. Close WhatsApp and report it.",
			),
			# Translators: Urgent recovery message when the owned temporary value cannot be deleted.
			"registry.restore.deleteAccessDenied": _(
				"Couldn't remove the temporary WebView2 setting. Close WhatsApp now, then run Diagnose and repair WebView2 policy permissions. WhatsApp Companion will try again before the next launch.",
			),
			# Translators: Recovery message for an unexpected temporary value deletion failure.
			"registry.restore.deleteFailed": _(
				"The temporary WebView2 setting couldn't be removed. Close WhatsApp and report it.",
			),
			# Translators: Urgent recovery message when the previous value cannot be written back.
			"registry.restore.setAccessDenied": _(
				"Couldn't put your previous WebView2 setting back. Close WhatsApp now, then run Diagnose and repair WebView2 policy permissions. WhatsApp Companion will try again before the next launch.",
			),
			# Translators: Recovery message for an unexpected restore write-back failure.
			"registry.restore.setFailed": _(
				"Your previous WebView2 setting couldn't be written back. Close WhatsApp and report it.",
			),
			# Translators: Recovery message when the live value changed outside the Companion.
			"registry.restore.conflict": _(
				"Another program changed your WebView2 setting during launch, so it was left as is. Check it manually.",
			),
			# Translators: Recovery message when restored state cannot be verified.
			"registry.restore.verifyMismatch": _(
				"Couldn't confirm that your WebView2 setting was put back. Close WhatsApp and check it manually.",
			),
			# Translators: Recovery message when a saved restoration record cannot be verified for this account.
			"registry.recovery.unreadable": _(
				"A saved WebView2 restore record doesn't match this Windows account, so nothing was changed. Ask your administrator, or restore the setting manually.",
			),
			# Translators: Status when the required WebView2 policy permissions already exist.
			"registry.repair.notNeeded": _(
				"WebView2 permissions are fine. Nothing needs fixing.",
			),
			# Translators: Status when diagnosis is refused while WhatsApp is running.
			"registry.repair.whatsappRunning": _(
				"Close WhatsApp before checking WebView2 permissions.",
			),
			# Translators: Status when diagnosis or repair requires a normal NVDA context.
			"registry.repair.context": _(
				"To check permissions, unlock Windows and run NVDA normally, not as administrator.",
			),
			# Translators: Status when the diagnosis cannot determine the condition.
			"registry.repair.diagnosisFailed": _(
				"Couldn't check WebView2 permissions. Close WhatsApp and try again. If this keeps happening, ask your administrator.",
			),
			# Translators: Status stored while the repair confirmation dialog is open.
			"registry.repair.confirmationRequired": _(
				"A repair is available. Choose in the dialog whether to continue.",
			),
			# Translators: Status when the user cancels the Windows permission request.
			"registry.repair.uacCancelled": _("Permissions were not changed."),
			# Translators: Status when the packaged repair helper is absent.
			"registry.repair.helperMissing": _("The repair helper is missing. Reinstall the add-on."),
			# Translators: Status when the packaged repair helper fails integrity verification.
			"registry.repair.helperUntrusted": _(
				"The repair helper failed its safety check. Reinstall the add-on from a trusted source.",
			),
			# Translators: Status when Windows or application control blocks the helper.
			"registry.repair.helperBlocked": _(
				"Windows blocked the repair. Ask your administrator for help.",
			),
			# Translators: Status when the elevated helper exceeds its transaction deadline.
			"registry.repair.helperTimeout": _(
				"The repair didn't finish. Run the check again.",
			),
			# Translators: Status when no compatible helper exists for the platform.
			"registry.repair.unsupportedPlatform": _(
				"There's no repair helper for this computer.",
			),
			# Translators: Status when the helper cannot verify the requesting NVDA session.
			"registry.repair.parentIdentityMismatch": _(
				"The repair couldn't confirm this NVDA session, so nothing was changed.",
			),
			# Translators: Status when the requesting user's hive is not loaded.
			"registry.repair.userHiveUnavailable": _(
				"Your Windows profile isn't available. Stay signed in and try again.",
			),
			# Translators: Status when an explicit deny rule blocks effective access.
			"registry.repair.managedDeny": _(
				"An administrator rule still blocks the WebView2 setting. The repair never removes such rules. Ask your administrator for help.",
			),
			# Translators: Status when the elevated helper cannot change the DACL.
			"registry.repair.insufficientAdminRights": _(
				"The repair couldn't change the Registry permissions. Ask your administrator for help.",
			),
			# Translators: Status when the DACL change failed before completion.
			"registry.repair.applyFailed": _(
				"The repair couldn't be applied. Nothing was changed.",
			),
			# Translators: Status when the post-apply check failed and the original DACL was restored.
			"registry.repair.verificationFailedRolledBack": _(
				"The repair couldn't be confirmed, so the original permissions were put back. Ask your administrator for help.",
			),
			# Translators: Critical status when the original DACL could not be restored.
			"registry.repair.rollbackFailed": _(
				"After an error, the repair couldn't put the original permissions back. Don't launch WhatsApp with WhatsApp Companion until an administrator checks the WebView2 setting.",
			),
			# Translators: Success status after the permission repair.
			"registry.repair.repaired": _(
				"WebView2 permissions are fixed. You can launch WhatsApp with WhatsApp Companion now.",
			),
			# Translators: Status when the helper reports success but normal access is still blocked.
			"registry.repair.postVerifyFailed": _(
				"The repair finished, but access is still blocked. Don't launch WhatsApp with WhatsApp Companion yet. Ask your administrator for help.",
			),
			# Translators: Status when a saved WebView2 value was restored after the repair.
			"registry.repair.recoveryRestored": _(
				"A saved WebView2 setting was put back. You can launch WhatsApp with WhatsApp Companion again.",
			),
			# Translators: Status when a saved WebView2 value changed outside the Companion.
			"registry.repair.recoveryConflict": _(
				"Another program changed a saved WebView2 setting, so it was left as is. Check it manually.",
			),
			# Translators: Recovery message for temporary WebView2 policy failures.
			"registry": _(
				"Couldn't undo the temporary WebView2 setting. Restart NVDA, then try again.",
			),
			# Translators: Recovery message for local accessibility connection failures.
			"transport": _(
				"WhatsApp opened, but WhatsApp Companion couldn't connect. Close WhatsApp and try again.",
			),
			# Translators: Recovery message when the bundled userscript does not initialize.
			"bundle": _(
				"WhatsApp Web Plus didn't start. Close WhatsApp and try again.",
			),
			# Translators: Recovery after a downloaded userscript fails its launch health checks.
			"bundle.updateQuarantined": _(
				"The downloaded WhatsApp Web Plus update didn't start, so it was turned off. Close WhatsApp and launch it again to use the built-in version.",
			),
			# Translators: Update result after a newer userscript bundle was selected.
			"update.updated": _(
				"WhatsApp Web Plus was updated from {currentVersion} to {latestVersion}. It will be used the next time you launch WhatsApp.",
			).format(
				latestVersion=result.values.get("latestVersion", ""),
				currentVersion=result.values.get("currentVersion", ""),
			),
			# Translators: Update result when official content changed without a version number change.
			"update.refreshed": _(
				"WhatsApp Web Plus {currentVersion} was replaced with the official copy. It will be used the next time you launch WhatsApp.",
			).format(currentVersion=result.values.get("currentVersion", "")),
			# Translators: Update status when the bundled userscript version is current.
			"update.current": _(
				"WhatsApp Web Plus is up to date ({currentVersion}).",
			).format(currentVersion=result.values.get("currentVersion", "")),
			# Translators: Recovery message when the userscript update cannot be downloaded.
			"update.error.network": _(
				"Couldn't download the WhatsApp Web Plus update. Check your internet connection and try again. Your current version was kept.",
			),
			# Translators: Recovery message when a downloaded userscript fails validation.
			"update.error.validation": _(
				"The WhatsApp Web Plus update failed its safety check. Your current version was kept.",
			),
			# Translators: Recovery when a signed update uses a key unknown to this Companion version.
			"update.error.keyUnknown": _(
				"The WhatsApp Web Plus update is signed with a key this version doesn't know. Update WhatsApp Companion, then try again. Your current version was kept.",
			),
			# Translators: Recovery message when the verified userscript cannot be saved.
			"update.error.save": _(
				"Couldn't install the WhatsApp Web Plus update. Your current version was kept.",
			),
			# Translators: Recovery message for an unexpected userscript update failure.
			"update.error": _(
				"Couldn't update WhatsApp Web Plus. Your current version was kept.",
			),
			# Translators: Status when updating is unavailable in a restricted NVDA context.
			"update.context": _(
				"WhatsApp Web Plus can't be updated from this NVDA session. Use NVDA normally.",
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
		message = message or _("WhatsApp Companion could not start. Close WhatsApp and try again.")
		errorCode = result.values.get("errorCode")
		if includeDiagnosticCode and not result.ok and isinstance(errorCode, str) and errorCode:
			# Translators: Appended only when the user explicitly reports a detailed update failure.
			message = f"{message} " + _("Technical error code: {errorCode}.").format(errorCode=errorCode)
		return message

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
		if self.controller.channelActive(channel):
			self._report(
				OperationResult(False, "operation.busy", "operation.channelBusy", {"channel": channel.value}),
				defer=True,
			)
			return
		if not self.controller.start(channel):
			self._report(OperationResult(False, "operation.busy", "operation.busy", {}), defer=True)
			return
		self._autoConnectBlocked.discard(channel)
		self._resetCompanionDeliveryState(channel.value)
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
			or self.controller.launching()
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
		self._announce(_("Checking WebView2 permissions."))
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

		probeFailed = False
		for policy in CHANNELS.values():
			if cancelEvent.is_set():
				raise LoaderError("operation.cancelled")
			try:
				package = findPackage(policy, runner)
				if package is not None and findRunningPackageProcesses(package, runner):
					return True
			except LoaderError as error:
				if error.code == "operation.cancelled":
					raise
				probeFailed = True
				log.warning(
					"WhatsApp Companion process status unavailable for %s: code=%s",
					policy.id.value,
					error.code,
				)
			except Exception:
				probeFailed = True
				log.warning("WhatsApp Companion process status unavailable for %s", policy.id.value)
		if cancelEvent.is_set():
			raise LoaderError("operation.cancelled")
		if probeFailed:
			raise LoaderError("registry.repair.processUnknown")
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
		if status in (
			RegistryPermissionStatus.REPAIRABLE_ACCESS_DENIED,
			RegistryPermissionStatus.MISSING_KEY,
		):
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
						"WhatsApp is open. To check WebView2 permissions, WhatsApp Companion must close WhatsApp Stable and Beta first. Calls and file transfers will stop, and unsent text may be lost. If a repair is needed, you'll be asked again before Windows asks for administrator approval. Close WhatsApp and continue?",
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
				"Closing WhatsApp Stable and Beta before the check.",
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
						"WhatsApp Companion saves a temporary WebView2 setting each time it launches WhatsApp, but Windows is blocking the place where it is stored. This repair creates that WebView2 policy key if it is missing, and lets your Windows account read and change values in it. Other programs running under your account could then change that key too. The repair doesn't change any setting values, computer-wide policies, administrator rules, WhatsApp data or chats. Only a small helper runs as administrator; NVDA and WhatsApp don't. The permission stays after you restart Windows or remove the add-on. Continue to the Windows permission prompt?",
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
				"Opening the Windows permission prompt. NVDA keeps running without administrator rights.",
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
		# Suggest the only WhatsApp connected to the Companion; otherwise suggest both.
		active = self.controller.activeChannels()
		self._showDialog(self._createForceCloseDialog(active[0] if len(active) == 1 else None))

	def _createForceCloseDialog(self, default: Channel | None) -> _Dialog:
		from .forceCloseDialog import ForceCloseDialog

		return ForceCloseDialog(gui.mainFrame, default=default, onConfirm=self._startForceClose)

	def _startForceClose(self, channels: tuple[Channel, ...] | None = None) -> None:
		if self._disposed:
			return
		if channels is not None and set(channels) >= {Channel.STABLE, Channel.BETA}:
			channels = None
		started = (
			self.controller.forceClose()
			if channels is None
			else self.controller.forceClose(channels=channels)
		)
		if not started:
			self._report(OperationResult(False, "processes.busy", "processes.busy", {}), defer=True)
			return
		if channels is None:
			# Translators: Immediate progress after the user confirms force closing both WhatsApp channels.
			self._announce(_("Closing WhatsApp Stable and Beta."))
			return
		self._announce(
			# Translators: Immediate progress after the user confirms force closing one WhatsApp channel.
			_("Closing WhatsApp {channel}.").format(
				channel=self._channelLabel(channels[0].value),
			),
		)

	def _startUpdateCheck(self) -> None:
		if self._disposed:
			return
		if self._updateCheckPending or self._updateTerminalPending:
			if not self._updateDuplicateAnnounced:
				self._updateDuplicateAnnounced = True
				# Translators: Status when a second update request is made while one is still running.
				self._announceUpdateWhilePending(
					_("Already checking for WhatsApp Web Plus updates."),
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
			_("Checking for WhatsApp Web Plus updates."),
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
			commandFeedback.message(message)

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
			if result.errorCode == "network":
				messageKey = "update.error.network"
			elif result.errorCode == "save":
				messageKey = "update.error.save"
			elif result.errorCode == "keyUnknown":
				messageKey = "update.error.keyUnknown"
			else:
				messageKey = "update.error.validation"
			safeErrorCode = result.errorCode or "unexpected"
			operationResult = OperationResult(
				False,
				f"update.{safeErrorCode}",
				messageKey,
				{"errorCode": safeErrorCode},
			)
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
			commandFeedback.message(message)
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
			message = _("Nothing to report yet.")
		else:
			message = self._messageForResult(self.lastResult, includeDiagnosticCode=True)
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
		description=_("Force close Microsoft Store WhatsApp Stable, Beta or both"),
		speakOnDemand=True,
	)
	def script_forceCloseWhatsApp(self, gesture) -> None:
		self._reviewForceClose()

	# Translators: Command description in NVDA's Input Gestures dialog.
	@script(description=_("Report the last WhatsApp Companion result"), speakOnDemand=True)
	def script_reportLastResult(self, gesture) -> None:
		if self.lastResult is None:
			# Translators: Spoken and brailled when no companion operation has completed yet.
			ui.message(_("Nothing to report yet."))
			return
		ui.message(self._messageForResult(self.lastResult, includeDiagnosticCode=True))

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

	@script(description=_("Start WhatsApp call recording"), speakOnDemand=True)
	def script_startCallRecording(self, gesture) -> None:
		self._prepareRecording()

	@script(description=_("Stop WhatsApp call recording"), speakOnDemand=True)
	def script_stopCallRecording(self, gesture) -> None:
		self._stopRecording()

	@script(
		# Translators: Input gesture description for turning automatic connection on or off.
		description=_("Turn automatic WhatsApp Companion connection on or off"),
		speakOnDemand=True,
	)
	def script_toggleAutoConnect(self, gesture) -> None:
		self._toggleAutoConnect()

	def terminate(self) -> None:
		self._announcementGuard.setBlocked("terminated", True)
		self._heldRecordingReport = None
		self._recordingSetupToken += 1
		self._cancelCallRecovery()
		self._callAvailability.invalidate()
		self._recording.stop()
		for event, callback in self._securitySubscriptions:
			try:
				event.unregister(callback)
			except (AttributeError, RuntimeError, ValueError):
				pass
		self._securitySubscriptions.clear()
		self._suspendCompanionOutput()
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
