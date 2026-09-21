"""Native call control discovery. Require a same-window call context."""

from dataclasses import dataclass
import time

from . import CallAction, labels

UIA_CHECKBOX_CONTROL_TYPE = 50002

MAX_NODES = 160
MAX_DEPTH = 16
SEARCH_SECONDS = 0.35
# Diagnostics intentionally retain only public built-ins, never custom text.
_LABELS = labels.BUTTON_LABELS


@dataclass
class CallButton:
	element: object
	action: CallAction
	host: int


class IncompleteSearch(Exception):
	pass


def buttonAction(element, processId, buttonType):
	if (
		element.currentProcessId != processId
		or element.currentFrameworkId != "XAML"
		or not element.currentIsEnabled
		or element.currentIsOffscreen
	):
		return None
	label = labels.normalize(element.currentName)
	if element.currentControlType == UIA_CHECKBOX_CONTROL_TYPE:
		if (
			element.currentClassName == "CheckBox"
			and labels.matches(CallAction.REACTIONS, label, labels.CHECKBOX_LABELS[CallAction.REACTIONS])
			and element.currentAutomationId == "NewReactionButton"
		):
			return CallAction.REACTIONS
		if (
			element.currentClassName == "CheckBox"
			and labels.matches(CallAction.SHARE, label, labels.CHECKBOX_LABELS[CallAction.SHARE])
			and element.currentAutomationId == "NewScreenShareButton"
		):
			return CallAction.SHARE
		return None
	if element.currentControlType != buttonType or element.currentClassName not in {"Button", "ToggleButton"}:
		return None
	return labels.buttonAction(label)


def collectControls(root, walker, processId, buttonType, *, clock=time.monotonic):
	"""Bound raw UIA walking, including sibling enumeration; reject partial results.

	The budget bounds calls made, but cannot interrupt an individual COM getter.
	Retain only recognized enabled controls under a native InputSite host.
	"""
	end = clock() + SEARCH_SECONDS
	stack = [(root, 0, 0)]
	buttons = {action: [] for action in CallAction}
	count = 0
	while stack:
		if count >= MAX_NODES or clock() >= end:
			raise IncompleteSearch()
		element, depth, host = stack.pop()
		count += 1
		if element.currentProcessId != processId:
			continue
		if element.currentClassName == "InputSiteWindowClass":
			host = element.currentNativeWindowHandle
		action = buttonAction(element, processId, buttonType)
		if action is not None and host:
			buttons[action].append(CallButton(getattr(element, "liveElement", element), action, host))
		child = walker.GetFirstChildElement(element)
		if child and depth >= MAX_DEPTH:
			raise IncompleteSearch()
		while child:
			if count + len(stack) >= MAX_NODES or clock() >= end:
				raise IncompleteSearch()
			stack.append((child, depth + 1, host))
			child = walker.GetNextSiblingElement(child)
	return buttons


def findIncomingPair(root, walker, processId, buttonType, *, clock=time.monotonic):
	buttons = collectControls(root, walker, processId, buttonType, clock=clock)
	if any(len(buttons[action]) != 1 for action in (CallAction.ANSWER, CallAction.DECLINE)):
		return None
	answer, decline = buttons[CallAction.ANSWER][0], buttons[CallAction.DECLINE][0]
	return (answer, decline) if answer.host == decline.host else None


def findActiveControls(root, walker, processId, buttonType, action):
	buttons = collectControls(root, walker, processId, buttonType)
	if buttons[CallAction.ANSWER] or buttons[CallAction.DECLINE]:
		return None
	if len(buttons[CallAction.END]) != 1 or len(buttons[action]) != 1:
		return None
	end, target = buttons[CallAction.END][0], buttons[action][0]
	if end.host != target.host:
		return None
	return (end,) if action == CallAction.END else (end, target)


def invokePair(
	pair, action, processId, buttonType, *, contextValid, belongsToWindow, getInvoke, getToggle=None
):
	"""Revalidate before one Invoke or the observed checkbox Toggle. Never retry."""
	if not contextValid():
		return False
	for button in pair:
		if (
			not belongsToWindow(button.host)
			or buttonAction(button.element, processId, buttonType) != button.action
		):
			return False
	target = next(button for button in pair if button.action == action)
	targetType = target.element.currentControlType
	useToggle = targetType == UIA_CHECKBOX_CONTROL_TYPE
	if useToggle and getToggle is None:
		return False
	pattern = getToggle(target.element) if useToggle else getInvoke(target.element)
	if not pattern or not contextValid():
		return False
	# Pattern acquisition may run provider code; check the pair once more.
	if any(buttonAction(button.element, processId, buttonType) != button.action for button in pair):
		return False
	if target.element.currentControlType != targetType:
		return False
	if not all(belongsToWindow(button.host) for button in pair) or not contextValid():
		return False
	if useToggle:
		pattern.Toggle()
	else:
		pattern.Invoke()
	return True
