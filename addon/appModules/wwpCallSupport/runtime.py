"""Runtime for contextual native WhatsApp app-module commands."""

import json
import time
import threading

import addonHandler
from logHandler import log
import ui

from . import CallAction, captureSnapshot, readProperty

addonHandler.initTranslation()


def diagnosticsAllowed():
	try:
		import globalVars
		import NVDAState
		from utils.security import isRunningOnSecureDesktop
		from winAPI.sessionTracking import isLockScreenModeActive

		return (
			not globalVars.appArgs.secure
			and NVDAState.shouldWriteToDisk()
			and not isRunningOnSecureDesktop()
			and not isLockScreenModeActive()
		)
	except Exception:
		return False


_lastAttempt = (0, 0.0)
_lastRestore = 0.0
_restoreCancel = threading.Event()
_restorePending = False
# Set on the GUI thread once the worker has committed to restoring the compact call view.
_restoreRunning = False
_lastRestoreNotice = 0.0
_diagnosticsPending = False
# Do not repeat the restore notice for every auto-repeated key press.
_RESTORE_NOTICE_INTERVAL = 1.5


def cancelRecovery():
	_restoreCancel.set()


def _withCallClient(work):
	"""Create and release every UIA object on this worker's COM apartment."""
	import comtypes
	import UIAHandler

	comtypes.CoInitializeEx(comtypes.COINIT_MULTITHREADED)
	client = None
	try:
		client = comtypes.CoCreateInstance(
			UIAHandler.UIA.CUIAutomation8._reg_clsid_,
			interface=UIAHandler.UIA.CUIAutomation8._com_interfaces_[1],
			clsctx=comtypes.CLSCTX_INPROC_SERVER,
		)
		client.ConnectionTimeout = 1000
		client.TransactionTimeout = 1000
		return work(client, UIAHandler)
	except Exception:
		return "failed"
	finally:
		client = None
		comtypes.CoUninitialize()


def _callOnMain(function):
	import wx

	wx.CallAfter(function)


def _announceRestoring():
	global _lastRestoreNotice
	_lastRestoreNotice = time.monotonic()
	# Translators: The helper is restoring the compact call view and needs the shortcut keys released.
	ui.message(_("Restoring call controls. Release the shortcut keys."))


def _dispatchCallWorker(work, finished):
	import wx

	def run():
		try:
			result = _withCallClient(work)
		except Exception:
			result = "failed"
		wx.CallAfter(finished, result)

	threading.Thread(target=run, name="WhatsAppCallAction", daemon=True).start()


def performCallAction(action, gesture):
	"""Capture GUI context, then discover and invoke on one dedicated worker."""
	import api
	import winUser
	import scriptHandler
	from controlTypes import Role, State

	global _lastAttempt, _restorePending, _restoreCancel

	def passThrough():
		if gesture is not None:
			gesture.send()

	try:
		foreground = api.getForegroundObject()
		pid = readProperty(foreground, "processID")
		hwnd = readProperty(foreground, "windowHandle")
		if (
			readProperty(readProperty(foreground, "appModule"), "appName")
			not in {"whatsapp.root", "whatsapp"}
			or readProperty(foreground, "windowClassName") != "WinUIDesktopWin32WindowClass"
			or type(pid) is not int
			or pid <= 0
			or type(hwnd) is not int
			or hwnd <= 0
			or winUser.getForegroundWindow() != hwnd
			or not diagnosticsAllowed()
		):
			passThrough()
			return
		focus = api.getFocusObject()
		if (
			readProperty(focus, "role") == Role.EDITABLETEXT
			or State.EDITABLE in (readProperty(focus, "states", ()) or ())
			or winUser.getKeyState(winUser.VK_RMENU) & 0x8000
		):
			passThrough()
			return
		if _restorePending:
			# Say why the shortcut did nothing while the call view is being restored.
			if _restoreRunning and time.monotonic() - _lastRestoreNotice >= _RESTORE_NOTICE_INTERVAL:
				_announceRestoring()
			return
		if _lastRestore and scriptHandler.getLastScriptRepeatCount() > 0:
			return
		if _lastAttempt[0] == (hwnd, action) and (
			time.monotonic() - _lastAttempt[1] < 1.0 or scriptHandler.getLastScriptRepeatCount() > 0
		):
			return
	except Exception:
		passThrough()
		return

	focusHost = readProperty(focus, "windowHandle")
	_lastAttempt = ((hwnd, action), time.monotonic())
	_restorePending = True
	_restoreCancel = threading.Event()
	cancel = _restoreCancel
	deadline = time.monotonic() + 3.0

	def contextValid():
		try:
			return (
				not cancel.is_set()
				and diagnosticsAllowed()
				and winUser.getForegroundWindow() == hwnd
				and winUser.getWindowThreadProcessID(hwnd)[0] == pid
			)
		except Exception:
			return False

	def restoring():
		global _restoreRunning
		if cancel.is_set() or not _restorePending:
			return
		_restoreRunning = True
		if contextValid():
			_announceRestoring()

	def work(client, uia):
		return _performCallWork(
			action,
			pid,
			hwnd,
			focusHost,
			client,
			uia,
			cancel,
			deadline,
			contextValid,
			onRestore=lambda: _callOnMain(restoring),
		)

	def finished(result):
		global _restorePending, _restoreRunning, _lastAttempt, _lastRestore
		_restorePending = False
		_restoreRunning = False
		if not contextValid():
			return
		if result == "passthrough":
			_lastAttempt = (0, 0.0)
			if api.getFocusObject() is focus and time.monotonic() < deadline:
				passThrough()
		elif result in {"restored", "restore-failed"}:
			_lastRestore = time.monotonic()
			ui.message(
				_("Call controls restored. Press the shortcut again.")
				if result == "restored"
				else _("Couldn't restore call controls. Go to the call window and try again."),
			)
		elif result == "failed":
			ui.message(_("Couldn't confirm that it worked. Check the WhatsApp call window."))

	try:
		_dispatchCallWorker(work, finished)
	except Exception:
		finished("failed")


def _performCallWork(
	action,
	pid,
	hwnd,
	focusHost,
	client,
	uia,
	cancel,
	deadline,
	contextValid,
	onRestore=lambda: None,
):
	from .actions import findActiveControls, findIncomingPair, invokePair
	from .discoveryCache import cachedTraversal
	from .compact import findCompact, kind
	import winUser

	def timely():
		return time.monotonic() < deadline and contextValid()

	if not timely():
		return "failed"
	try:
		root = client.ElementFromHandle(hwnd)
		if root.currentProcessId != pid or not timely():
			return "failed"
		searchRoot, searchWalker = cachedTraversal(client, root, uia)
		if action in {CallAction.ANSWER, CallAction.DECLINE}:
			pair = findIncomingPair(searchRoot, searchWalker, pid, uia.UIA_ButtonControlTypeId)
		else:
			pair = findActiveControls(searchRoot, searchWalker, pid, uia.UIA_ButtonControlTypeId, action)
		candidate = None
		if pair is None:
			focus = client.GetFocusedElement()
			if kind(focus, pid, allowHiddenMute=True) != "mute":
				return "passthrough"
			candidate = findCompact(root, client.RawViewWalker, pid)
	except Exception:
		# No usable call controls (no call, or a large or slow tree). WhatsApp receives the key;
		# only a failure after a control was found is reported.
		return "passthrough"
	if not timely():
		return "failed"
	if pair is None:
		if candidate is None or candidate[2] != focusHost:
			return "passthrough"
		if not timely():
			return "failed"
		from globalPlugins.whatsappWebPlusCompanion.callAvailability import restoreCallView

		onRestore()
		# The helper rechecks foreground, focus, desktop and target before its one click.
		return "restored" if restoreCallView(pid, hwnd, cancel) else "restore-failed"

	def getInvoke(element):
		pattern = element.GetCurrentPattern(uia.UIA_InvokePatternId)
		return pattern.QueryInterface(uia.IUIAutomationInvokePattern) if pattern else None

	def getToggle(element):
		pattern = element.GetCurrentPattern(uia.UIA_TogglePatternId)
		return pattern.QueryInterface(uia.IUIAutomationTogglePattern) if pattern else None

	completed = invokePair(
		pair,
		action,
		pid,
		uia.UIA_ButtonControlTypeId,
		contextValid=timely,
		belongsToWindow=lambda host: winUser.isDescendantWindow(hwnd, host),
		getInvoke=getInvoke,
		getToggle=getToggle,
	)
	return "done" if completed else "failed"


def captureDiagnostics():
	"""Read NVDA objects here, then walk the call window's UIA tree on the call worker."""
	import api

	global _diagnosticsPending

	if not diagnosticsAllowed():
		# Translators: Diagnostic capture is unavailable on secure/locked/no-write sessions.
		ui.message(_("Call diagnostics are unavailable in this NVDA session."))
		return
	if _diagnosticsPending:
		return
	try:
		foreground = api.getForegroundObject()
		processId = readProperty(foreground, "processID")
		hwnd = readProperty(foreground, "windowHandle")
		appName = readProperty(readProperty(foreground, "appModule"), "appName")
		if appName not in {"whatsapp.root", "whatsapp"} or type(processId) is not int or processId <= 0:
			# Translators: Capture only the WhatsApp window belonging to this app module.
			ui.message(_("Go to the WhatsApp call window first."))
			return
		snapshot = captureSnapshot(processId, foreground, api.getFocusObject(), api.getNavigatorObject())
		snapshot["appName"] = appName
	except Exception:
		# Translators: No exception details are logged, to avoid private provider data.
		ui.message(_("Couldn't save call diagnostics."))
		return

	def work(client, uia):
		return captureControlInventory(hwnd, processId, client, uia)

	def finished(controls):
		global _diagnosticsPending
		_diagnosticsPending = False
		# Recheck before retaining any provider data if Windows changed desktop.
		if not diagnosticsAllowed():
			return
		snapshot["controls"] = (
			controls if isinstance(controls, dict) else {"status": "unavailable-or-incomplete"}
		)
		try:
			log.info("WWP-CALL-SNAPSHOT %s", json.dumps(snapshot, ensure_ascii=True, separators=(",", ":")))
		except Exception:
			ui.message(_("Couldn't save call diagnostics."))
			return
		# Translators: Confirmation after writing one explicitly requested snapshot.
		ui.message(_("Call diagnostics saved to the NVDA log. No call buttons were pressed."))

	_diagnosticsPending = True
	try:
		_dispatchCallWorker(work, finished)
	except Exception:
		finished("failed")


def captureControlInventory(hwnd, processId, client, uia):
	"""Read-only inventory, including controls that have no action mapping. Runs on the call worker."""
	try:
		from .diagnostics import collectInventory
		from .discoveryCache import CachedElement, cachedTraversal

		root = client.ElementFromHandle(hwnd)
		root, walker = cachedTraversal(client, root, uia)
		result = collectInventory(
			root,
			walker,
			processId,
			uia.UIA_ButtonControlTypeId,
			uia.UIA_InvokePatternId,
			uia.UIA_TogglePatternId,
		)
		result["propertyCache"] = isinstance(root, CachedElement)
		return result
	except Exception:
		return {"status": "unavailable-or-incomplete"}
