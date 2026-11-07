from dataclasses import dataclass
from types import MappingProxyType

from .models import Channel


@dataclass(frozen=True, slots=True)
class ChannelPolicy:
	id: Channel
	aumid: str
	packageFamily: str


CHANNELS = MappingProxyType(
	{
		Channel.STABLE: ChannelPolicy(
			Channel.STABLE,
			"5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App",
			"5319275A.WhatsAppDesktop_cv1g1gvanyjgm",
		),
		Channel.BETA: ChannelPolicy(
			Channel.BETA,
			"5319275A.51895FA4EA97F_cv1g1gvanyjgm!App",
			"5319275A.51895FA4EA97F_cv1g1gvanyjgm",
		),
	},
)

EXPECTED_ORIGIN = "https://web.whatsapp.com"
EXPECTED_HOST = "web.whatsapp.com"
LOOPBACK_HOST = "127.0.0.1"
REGISTRY_PATH = r"Software\Policies\Microsoft\Edge\WebView2\AdditionalBrowserArguments"
# KEY_QUERY_VALUE | KEY_SET_VALUE: the only rights the Companion needs on the
# fixed per-user WebView2 policy leaf, and the only rights repair may grant.
REGISTRY_REQUIRED_RIGHTS = 0x0001 | 0x0002
REGISTRY_HELPER_PROTOCOL_VERSION = 1
ENDPOINT_DEADLINE = 20.0
TARGET_DEADLINE = 15.0
LISTENER_DEADLINE = 60.0
TARGET_IDENTITY_DEADLINE = 45.0
CONNECT_DEADLINE = 5.0
REQUEST_DEADLINE = 5.0
BUNDLE_HEALTH_DEADLINE = 15.0
RECONNECT_DELAYS = (0.25, 0.5, 1.0)
# Process lookup and repeated endpoint identity checks share this bounded budget.
# A single identity probe can take 30 seconds on a busy machine.
RECONNECT_DEADLINE = 90.0
CANCEL_INTERVAL = 0.25
SOCKET_CLOSE_DEADLINE = 2.0
MAX_HTTP_BYTES = 1024 * 1024
MAX_HTTP_HEADER_BYTES = 64 * 1024
MAX_FRAME_BYTES = 1024 * 1024
ALLOWED_HTTP_PATHS = frozenset(("/json/version", "/json/list"))


def channelForExecutable(path: object) -> Channel | None:
	"""The WhatsApp channel whose Microsoft Store package contains this executable.

	Package install folders start with the package name, for example
	``WindowsApps\\5319275A.WhatsAppDesktop_2.2642.101.0_x64__cv1g1gvanyjgm``.
	"""
	if not isinstance(path, str) or not path:
		return None
	folders = [part.casefold() for part in path.replace("/", "\\").split("\\")]
	for channel, policy in CHANNELS.items():
		name = policy.packageFamily.rsplit("_", 1)[0].casefold()
		publisher = policy.packageFamily.rsplit("_", 1)[1].casefold()
		for folder in folders[:-1]:
			if folder.startswith(name + "_") and folder.endswith("__" + publisher):
				return channel
	return None
