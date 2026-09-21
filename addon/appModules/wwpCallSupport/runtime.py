"""Runtime for contextual native WhatsApp app-module commands."""

import json
import time

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


def performCallAction(action, gesture):
	"""Contextual bindings pass through outside verified native call controls."""
	import api
	import winUser
	import scriptHandler
	from controlTypes import Role, State
	from .actions import findActiveControls, findIncomingPair, invokePair

	global _lastAttempt

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
		if _lastRestore and scriptHandler.getLastScriptRepeatCount() > 0:
			return
		# Block repeat activation, even if the first invocation has removed a button.
		if _lastAttempt[0] == (hwnd, action) and (
			time.monotonic() - _lastAttempt[1] < 1.0 or scriptHandler.getLastScriptRepeatCount() > 0
		):
			return
		import UIAHandler

		client = UIAHandler.handler.clientObject
		root = client.ElementFromHandle(hwnd)
		from .discoveryCache import cachedTraversal

		searchRoot, searchWalker = cachedTraversal(client, root, UIAHandler)
		if action in {CallAction.ANSWER, CallAction.DECLINE}:
			pair = findIncomingPair(searchRoot, searchWalker, pid, UIAHandler.UIA_ButtonControlTypeId)
		else:
			pair = findActiveControls(
				searchRoot,
				searchWalker,
				pid,
				UIAHandler.UIA_ButtonControlTypeId,
				action,
			)
		if pair is None:
			if tryRestoreCompact(root, client, pid, hwnd, focus):
				return
			passThrough()
			return
	except Exception:
		passThrough()
		return

	def contextValid():
		current = api.getForegroundObject()
		return (
			diagnosticsAllowed()
			and winUser.getForegroundWindow() == hwnd
			and readProperty(current, "windowHandle") == hwnd
			and readProperty(current, "processID") == pid
			and readProperty(readProperty(current, "appModule"), "appName") in {"whatsapp.root", "whatsapp"}
		)

	def getInvoke(element):
		pattern = element.GetCurrentPattern(UIAHandler.UIA_InvokePatternId)
		return pattern.QueryInterface(UIAHandler.IUIAutomationInvokePattern) if pattern else None

	def getToggle(element):
		pattern = element.GetCurrentPattern(UIAHandler.UIA_TogglePatternId)
		return pattern.QueryInterface(UIAHandler.IUIAutomationTogglePattern) if pattern else None

	_lastAttempt = ((hwnd, action), time.monotonic())
	try:
		completed = invokePair(
			pair,
			action,
			pid,
			UIAHandler.UIA_ButtonControlTypeId,
			contextValid=contextValid,
			belongsToWindow=lambda host: winUser.isDescendantWindow(hwnd, host),
			getInvoke=getInvoke,
			getToggle=getToggle,
		)
	except Exception:
		completed = False
	if not completed:
		# No retry: an Invoke exception does not prove the call remained unchanged.
		ui.message(_("The call action could not be confirmed. Check the WhatsApp call window."))


def tryRestoreCompact(root, client, pid, hwnd, focus):
	"""Consume a verified compact-window recovery, never replay a call action."""
	import api
	import UIAHandler
	import winUser
	from .compact import findCompact, kind, restore

	global _lastRestore
	try:
		if kind(readProperty(focus, "UIAElement"), pid) != "mute":
			return False
		candidate = findCompact(root, client.RawViewWalker, pid)
		if candidate is None or readProperty(focus, "windowHandle") != candidate[2]:
			return False
	except Exception:
		return False
	# Shared across all call shortcuts; failed restore attempts are also throttled.
	if time.monotonic() - _lastRestore < 1.0:
		return True
	_lastRestore = time.monotonic()

	def contextValid():
		current = api.getForegroundObject()
		currentFocus = api.getFocusObject()
		return (
			diagnosticsAllowed()
			and winUser.getForegroundWindow() == hwnd
			and readProperty(current, "windowHandle") == hwnd
			and readProperty(current, "processID") == pid
			and readProperty(readProperty(current, "appModule"), "appName") in {"whatsapp.root", "whatsapp"}
			and readProperty(currentFocus, "windowHandle") == candidate[2]
			and kind(readProperty(currentFocus, "UIAElement"), pid) == "mute"
		)

	def getLegacy(el):
		pattern = el.GetCurrentPattern(UIAHandler.UIA_LegacyIAccessiblePatternId)
		return pattern.QueryInterface(UIAHandler.IUIAutomationLegacyIAccessiblePattern) if pattern else None

	try:
		requested = restore(
			candidate,
			pid,
			contextValid=contextValid,
			belongsToWindow=lambda host: winUser.isDescendantWindow(hwnd, host),
			getLegacy=getLegacy,
		)
	except Exception:
		requested = False
	if requested:
		ui.message(
			_(
				"Requested the full call view. Release the keys, check the window, then press the shortcut again.",
			),
		)
	else:
		ui.message(_("Could not confirm call view recovery. Open the full call window manually."))
	return True


def captureDiagnostics():
	import api

	if not diagnosticsAllowed():
		# Translators: Diagnostic capture is unavailable on secure/locked/no-write sessions.
		ui.message(_("Call diagnostics are unavailable in this NVDA session."))
		return
	try:
		foreground = api.getForegroundObject()
		processId = readProperty(foreground, "processID")
		appName = readProperty(readProperty(foreground, "appModule"), "appName")
		if appName not in {"whatsapp.root", "whatsapp"} or type(processId) is not int or processId <= 0:
			# Translators: Capture only the WhatsApp window belonging to this app module.
			ui.message(_("Focus the WhatsApp call window before capturing diagnostics."))
			return
		snapshot = captureSnapshot(processId, foreground, api.getFocusObject(), api.getNavigatorObject())
		snapshot["appName"] = appName
		snapshot["controls"] = captureControlInventory(foreground, processId)
		# Recheck before retaining any provider data if Windows changed desktop.
		if not diagnosticsAllowed():
			return
		log.info("WWP-CALL-SNAPSHOT %s", json.dumps(snapshot, ensure_ascii=True, separators=(",", ":")))
	except Exception:
		# Translators: No exception details are logged, to avoid private provider data.
		ui.message(_("Call diagnostics could not be captured."))
		return
	# Translators: Confirmation after writing one explicitly requested snapshot.
	ui.message(_("Call diagnostics written to the NVDA log. Call controls were not activated."))


def captureControlInventory(foreground, processId):
	"""Read-only inventory, including controls that have no action mapping."""
	try:
		import UIAHandler
		from .diagnostics import collectInventory

		client = UIAHandler.handler.clientObject
		root = client.ElementFromHandle(readProperty(foreground, "windowHandle"))
		from .discoveryCache import CachedElement, cachedTraversal

		root, walker = cachedTraversal(client, root, UIAHandler)
		result = collectInventory(
			root,
			walker,
			processId,
			UIAHandler.UIA_ButtonControlTypeId,
			UIAHandler.UIA_InvokePatternId,
			UIAHandler.UIA_TogglePatternId,
		)
		result["propertyCache"] = isinstance(root, CachedElement)
		return result
	except Exception:
		return {"status": "unavailable-or-incomplete"}
