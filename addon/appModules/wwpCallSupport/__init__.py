"""Diagnostic support for native WhatsApp call controls.

Activation lives in actions.py; diagnostic hints never authorize an action.
This module deliberately does not import the loader plugin.
"""

from enum import Enum
from itertools import islice
import re
import time


class CallAction(Enum):
	ANSWER = "answer"
	DECLINE = "decline"
	CAMERA = "camera"
	MUTE = "mute"
	REACTIONS = "reactions"
	HAND = "hand"
	SHARE = "share"
	END = "end-call"


MAX_ANCESTORS = 4
SNAPSHOT_BUDGET = 0.25
_IDENTIFIER = re.compile(r"[A-Za-z0-9_.:#-]{1,128}\Z")
# Exact labels only. Never log a caller name, window title, description or value.
# These are diagnostic hints, NOT selectors authorizing an action.
_LABEL_HINTS = {
	"answer": "answer",
	"accept": "answer",
	"answer call": "answer",
	"accept call": "answer",
	"jawab": "answer",
	"jawab panggilan": "answer",
	"terima": "answer",
	"terima panggilan": "answer",
	"decline": "decline",
	"reject": "decline",
	"decline call": "decline",
	"reject call": "decline",
	"tolak": "decline",
	"tolak panggilan": "decline",
	"end call": "end-call",
	"akhiri panggilan": "end-call",
	"toggle camera": "camera",
	"turn camera on": "camera",
	"turn on camera": "camera",
	"turn off camera": "camera",
	"turn camera off": "camera",
	"toggle mute": "mute",
	"mute": "mute",
	"unmute": "mute",
	"mute microphone": "mute",
	"unmute microphone": "mute",
	"reactions": "reactions",
	"react": "reactions",
	"raise hand": "hand",
	"lower hand": "hand",
	"screen share": "share",
	"start screen sharing": "share",
	"stop screen sharing": "share",
	"share screen": "share",
	"stop sharing": "share",
}


def readProperty(obj, name, default=None):
	try:
		return getattr(obj, name, default)
	except Exception:
		# Accessibility providers can disappear while the call window closes.
		# Exception text can contain private provider data; do not log it.
		return default


def identifier(value):
	return value if isinstance(value, str) and _IDENTIFIER.fullmatch(value) else "omitted"


def enumName(value):
	return identifier(readProperty(value, "name"))


def describeObject(obj):
	name = readProperty(obj, "name")
	# Native XAML uses NBSP in "Decline\u00a0call". Normalize whitespace only;
	# retain exact matching so private names and unrelated controls stay unmapped.
	label = " ".join(name.split()).casefold() if isinstance(name, str) else ""
	hint = _LABEL_HINTS.get(label, "unmapped")
	try:
		states = sorted(enumName(state) for state in islice(readProperty(obj, "states", ()) or (), 32))
	except Exception:
		states = ["unavailable"]
	uia = readProperty(obj, "UIAElement")
	hwnd = readProperty(obj, "windowHandle")
	return {
		"backend": identifier(type(obj).__module__),
		"objectClass": identifier(type(obj).__name__),
		"role": enumName(readProperty(obj, "role")),
		"states": states,
		"windowClass": identifier(readProperty(obj, "windowClassName")),
		"windowHandle": hwnd if type(hwnd) is int else None,
		"automationId": identifier(readProperty(uia, "cachedAutomationId")),
		"uiaClass": identifier(readProperty(uia, "cachedClassName")),
		"labelHint": hint,
	}


def captureSnapshot(processId, foreground, focus, navigator, *, clock=time.monotonic):
	"""Bounded object paths only; never enumerate the whole accessibility tree.

	The budget is checked between provider calls. It cannot interrupt a single
	blocked COM getter. No network, process lookup or registry access occurs here.
	"""
	end = clock() + SNAPSHOT_BUDGET
	result = {
		"schemaVersion": 1,
		"mapping": "incoming-observed-active-provisional",
		"paths": [],
		"budgetReached": False,
	}
	for source, obj in (("foreground", foreground), ("focus", focus), ("navigator", navigator)):
		path = {"source": source, "nodes": [], "stop": "depth-limit"}
		result["paths"].append(path)
		seen = set()
		for _depth in range(MAX_ANCESTORS):
			if clock() >= end:
				path["stop"] = "budget"
				result["budgetReached"] = True
				break
			if obj is None:
				path["stop"] = "missing"
				break
			if id(obj) in seen:
				path["stop"] = "cycle"
				break
			seen.add(id(obj))
			if readProperty(obj, "processID") != processId:
				path["stop"] = "other-process"
				break
			path["nodes"].append(describeObject(obj))
			obj = readProperty(obj, "parent")
	return result
