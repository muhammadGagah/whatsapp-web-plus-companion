"""Bounded UIA diagnostics. This module never authorizes or performs actions."""

import time

from . import CallAction, identifier
from .actions import _LABELS, UIA_CHECKBOX_CONTROL_TYPE

MAX_NODES = 160
MAX_DEPTH = 16
SECONDS = 0.35


class BudgetReached(Exception):
	pass


def collectInventory(root, walker, processId, buttonType, invokeId, toggleId, *, clock=time.monotonic):
	"""Report native button and checkbox candidates, including unmapped/disabled controls.

	Complete refers to traversal, not mapping coverage. No raw provider names,
	values, descriptions or exception strings are retained. A COM call itself
	cannot be interrupted by this between-call budget.
	"""
	result = {"status": "complete", "recognized": [], "unmapped": [], "visited": 0}
	deadline = clock() + SECONDS

	def read(getter):
		if clock() >= deadline:
			raise BudgetReached()
		return getter()

	def optional(getter):
		try:
			return read(getter)
		except BudgetReached:
			raise
		except Exception:
			return "unavailable"

	stack = [(root, 0, 0)]
	try:
		while stack:
			if result["visited"] >= MAX_NODES:
				raise BudgetReached()
			el, depth, host = stack.pop()
			result["visited"] += 1
			if read(lambda: el.currentProcessId) != processId:
				continue
			cls = read(lambda: el.currentClassName)
			if cls == "InputSiteWindowClass":
				host = read(lambda: el.currentNativeWindowHandle)
			if host and read(lambda: el.currentControlType) in {buttonType, UIA_CHECKBOX_CONTROL_TYPE}:
				name = optional(lambda: el.currentName)
				label = " ".join(name.split()).casefold() if isinstance(name, str) else ""
				action = _LABELS.get(label)
				if label == "react":
					action = CallAction.REACTIONS
				if label in {"start screen sharing", "stop screen sharing"}:
					action = CallAction.SHARE
				item = {
					"action": action.value if action else "unmapped",
					"label": label if action else "unmapped",
					"host": host if type(host) is int else None,
					"uiaClass": identifier(cls),
					"automationId": identifier(optional(lambda: el.currentAutomationId)),
					"framework": identifier(optional(lambda: el.currentFrameworkId)),
					"enabled": optional(lambda: bool(el.currentIsEnabled)),
					"offscreen": optional(lambda: bool(el.currentIsOffscreen)),
					"invoke": optional(lambda: bool(el.GetCurrentPattern(invokeId))),
					"toggle": optional(lambda: bool(el.GetCurrentPattern(toggleId))),
				}
				result["recognized" if action else "unmapped"].append(item)
			child = read(lambda: walker.GetFirstChildElement(el))
			if child and depth >= MAX_DEPTH:
				raise BudgetReached()
			while child:
				if result["visited"] + len(stack) >= MAX_NODES:
					raise BudgetReached()
				stack.append((child, depth + 1, host))
				child = read(lambda: walker.GetNextSiblingElement(child))
	except BudgetReached:
		result["status"] = "partial"
	except Exception:
		result["status"] = "unavailable-or-incomplete"
	return result
