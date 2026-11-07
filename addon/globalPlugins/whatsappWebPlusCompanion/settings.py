"""WhatsApp Companion settings kept in NVDA's configuration profile."""

try:
	import config
except ImportError:  # Unit tests without NVDA.
	config = None

_SECTION = "whatsappCompanion"
_SPEC = {"autoConnect": "boolean(default=False)"}


def register() -> None:
	try:
		config.conf.spec[_SECTION] = dict(_SPEC)
	except (AttributeError, KeyError, TypeError):
		pass


def autoConnect() -> bool:
	try:
		return bool(config.conf[_SECTION]["autoConnect"])
	except (AttributeError, KeyError, TypeError, ValueError):
		return False


def setAutoConnect(enabled: bool) -> bool:
	try:
		config.conf[_SECTION]["autoConnect"] = bool(enabled)
	except (AttributeError, KeyError, TypeError, ValueError):
		return False
	return True
