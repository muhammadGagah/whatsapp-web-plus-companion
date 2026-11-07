from collections.abc import Callable

from .models import Channel, LoaderError, OperationResult
from .packages import PackageInfo, PackageProcessCloseResult, findPackage, forceClosePackageProcesses
from .policy import CHANNELS, ChannelPolicy
from .security import SecurityProbe, buildSecurityProbe, checkPreflight

PackageFinder = Callable[[ChannelPolicy], PackageInfo | None]
ProcessCloser = Callable[[PackageInfo], PackageProcessCloseResult]
ProbeBuilder = Callable[[], SecurityProbe]


def forceCloseOperation(
	packageFinder: PackageFinder = findPackage,
	processCloser: ProcessCloser = forceClosePackageProcesses,
	probeBuilder: ProbeBuilder = buildSecurityProbe,
	*,
	channels: tuple[Channel, ...] | None = None,
) -> OperationResult:
	"""Close the selected WhatsApp channels, or both when ``channels`` is None."""
	selected = tuple(
		channel for channel in (Channel.STABLE, Channel.BETA) if channels is None or channel in channels
	)
	checkPreflight(probeBuilder())
	closedCount = 0
	foundCount = 0
	remainingChannels: list[str] = []
	errors: list[str] = []
	for channel in selected:
		try:
			package = packageFinder(CHANNELS[channel])
		except LoaderError as error:
			errors.append(error.code)
			remainingChannels.append(channel.value)
			continue
		if package is None:
			continue
		try:
			result = processCloser(package)
		except LoaderError as error:
			errors.append(error.code)
			remainingChannels.append(channel.value)
			continue
		foundCount += result.foundCount
		closedCount += result.closedCount
		if result.remainingCount:
			remainingChannels.append(channel.value)

	values = {
		"closedCount": closedCount,
		"foundCount": foundCount,
		"remainingChannels": tuple(remainingChannels),
	}
	# One selected channel gets its own wording; the result code stays the same.
	single = ""
	if len(selected) == 1:
		single = ".one"
		values["channel"] = selected[0].value
	if not foundCount and not errors:
		return OperationResult(True, "processes.none", "processes.none" + single, values)
	if foundCount and closedCount == foundCount and not errors:
		return OperationResult(True, "processes.closed", "processes.closed" + single, values)
	if closedCount:
		return OperationResult(False, "processes.partial", "processes.partial", values)
	return OperationResult(False, "processes.failed", "processes.failed", values)
