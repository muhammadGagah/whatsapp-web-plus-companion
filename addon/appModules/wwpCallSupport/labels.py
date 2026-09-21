"""Global, exact call aliases shared without importing the global plugin.

NVDA owns persistence through config.conf.spec/save. The base profile keeps one
configuration across WhatsApp channels and NVDA's own modeless settings dialog.
Runtime reads only in-memory settings; compiled aliases are cached by content
so configuration resets take effect without any disk access or event hooks.
"""

from functools import lru_cache
from types import MappingProxyType
import unicodedata

from . import CallAction

SECTION = "whatsappCompanionCallLabels"
MAX_LABELS = 20
MAX_LENGTH = 128
BUTTON_LABELS = {
	"accept call": CallAction.ANSWER,
	"answer call": CallAction.ANSWER,
	"jawab panggilan": CallAction.ANSWER,
	"terima panggilan": CallAction.ANSWER,
	"decline call": CallAction.DECLINE,
	"reject call": CallAction.DECLINE,
	"tolak panggilan": CallAction.DECLINE,
	"toggle camera": CallAction.CAMERA,
	"turn camera on": CallAction.CAMERA,
	"turn on camera": CallAction.CAMERA,
	"turn off camera": CallAction.CAMERA,
	"turn camera off": CallAction.CAMERA,
	"toggle mute": CallAction.MUTE,
	"mute": CallAction.MUTE,
	"unmute": CallAction.MUTE,
	"mute microphone": CallAction.MUTE,
	"unmute microphone": CallAction.MUTE,
	"reactions": CallAction.REACTIONS,
	"raise hand": CallAction.HAND,
	"lower hand": CallAction.HAND,
	"screen share": CallAction.SHARE,
	"share screen": CallAction.SHARE,
	"stop sharing": CallAction.SHARE,
	"end call": CallAction.END,
}
CHECKBOX_LABELS = {
	CallAction.REACTIONS: frozenset({"react"}),
	CallAction.SHARE: frozenset({"start screen sharing", "stop screen sharing"}),
}
COMPACT_MUTE_LABELS = frozenset({"mute microphone", "unmute microphone"})


class ValidationError(ValueError):
	def __init__(self, action):
		self.action = action
		# Never include arbitrary user text in exception messages or logs.
		super().__init__("Invalid or conflicting call labels")


def normalize(value):
	return " ".join(value.split()).casefold() if isinstance(value, str) else ""


def defaultLabels(action):
	return tuple(
		dict.fromkeys(
			[label for label, owner in BUTTON_LABELS.items() if owner == action]
			+ sorted(CHECKBOX_LABELS.get(action, ()))
		),
	)


def _section():
	import config

	if SECTION not in config.conf.spec:
		config.conf.spec[SECTION] = {action.value: "string(default='')" for action in CallAction}
	# ConfigManager.save always saves profiles[0]. Read/write the base profile
	# directly so auto-triggered application profiles cannot redirect the editor.
	base = config.conf.profiles[0]
	if SECTION not in base:
		base[SECTION] = {}
	return base[SECTION]


def _rawValues():
	section = _section()
	return tuple(section.get(action.value, "") for action in CallAction)


def _validate(values):
	owners = {label: action for action in CallAction for label in defaultLabels(action)}
	clean = {}
	aliases = {}
	for action, value in zip(CallAction, values, strict=True):
		if not isinstance(value, str) or len(value) > MAX_LABELS * (MAX_LENGTH + 2):
			raise ValidationError(action.value)
		lines = [line.strip() for line in value.splitlines() if line.strip()]
		if len(lines) > MAX_LABELS:
			raise ValidationError(action.value)
		accepted = {}
		for line in lines:
			label = normalize(line)
			if len(line) > MAX_LENGTH or any(unicodedata.category(char) == "Cc" for char in line):
				raise ValidationError(action.value)
			owner = owners.get(label)
			if owner is not None and owner != action:
				raise ValidationError(action.value)
			owners[label] = action
			# Re-entering a built-in must not broaden its observed control type.
			if label not in defaultLabels(action):
				accepted.setdefault(label, line)
		clean[action.value] = "\n".join(accepted.values())
		aliases[action] = frozenset(accepted)
	return clean, MappingProxyType(aliases)


def loadOverrides():
	"""Return editable aliases; propagate corrupt/unreadable settings to the UI."""
	return _validate(_rawValues())[0]


def saveOverrides(overrides):
	"""Persist a validated draft, restoring previous memory settings on failure."""
	import config
	import NVDAState

	if not NVDAState.shouldWriteToDisk():
		raise PermissionError("Call labels cannot be saved in this NVDA session")
	if not isinstance(overrides, dict) or set(overrides) - {action.value for action in CallAction}:
		raise ValidationError("")
	clean, _aliases = _validate(tuple(overrides.get(action.value, "") for action in CallAction))
	# Validate the existing configuration before changing anything: do not erase
	# unknown or corrupt settings just because the dialog has an older draft.
	previous = _rawValues()
	_validate(previous)
	section = _section()
	try:
		for action in CallAction:
			section[action.value] = clean[action.value]
		if not NVDAState.shouldWriteToDisk():
			raise PermissionError("Call labels cannot be saved in this NVDA session")
		config.conf.save()
	except Exception:
		for action, value in zip(CallAction, previous, strict=True):
			section[action.value] = value
		raise
	_compiled.cache_clear()


@lru_cache(maxsize=8)
def _compiled(values):
	return _validate(values)[1]


def _aliases():
	try:
		return _compiled(_rawValues())
	except Exception:
		# Missing NVDA config, corrupt values, or an unavailable profile never
		# authorizes a custom action. The editor reports the actual load failure.
		return {}


def matches(action, label, defaults):
	label = normalize(label)
	return label in defaults or label in _aliases().get(action, ())


def buttonAction(label):
	label = normalize(label)
	default = BUTTON_LABELS.get(label)
	if default is not None:
		return default
	return next((action for action, names in _aliases().items() if label in names), None)
