import json
import pathlib
from dataclasses import dataclass

from .models import LoaderError
from .packages import PowerShellCommand, PowerShellRunner, runPowerShell
from .policy import LOOPBACK_HOST


@dataclass(frozen=True, slots=True)
class Listener:
	address: str
	port: int
	pid: int


def _reachesPackage(pid: int, parents: dict[int, int], packagePids: set[int]) -> bool:
	seen: set[int] = set()
	while pid and pid not in seen:
		if pid in packagePids:
			return True
		seen.add(pid)
		pid = parents.get(pid, 0)
	return False


def validateListener(
	port: int,
	listeners: list[Listener],
	parents: dict[int, int],
	packagePids: set[int],
) -> int:
	selected = [row for row in listeners if row.port == port]
	if not selected or any(row.address != LOOPBACK_HOST for row in selected):
		raise LoaderError("listener.exposure")
	pids = {row.pid for row in selected}
	if len(pids) != 1 or not all(_reachesPackage(pid, parents, packagePids) for pid in pids):
		raise LoaderError("listener.ancestry", f"matches={len(pids)}")
	return pids.pop()


def collectProcessTopology(
	port: int,
	runner: PowerShellRunner = runPowerShell,
) -> tuple[list[Listener], dict[int, int]]:
	script = (
		f"$listeners = Get-NetTCPConnection -State Listen -LocalPort {int(port)} -ErrorAction SilentlyContinue "
		"| Select-Object LocalAddress,LocalPort,OwningProcess; "
		"$processes = Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId; "
		"@{Listeners=@($listeners);Processes=@($processes)} | ConvertTo-Json -Compress -Depth 4"
	)
	try:
		data = json.loads(runner(PowerShellCommand(script, "listener.topology")) or "{}")
	except (TypeError, ValueError) as error:
		raise LoaderError("processes.json", type(error).__name__) from error
	listeners = [
		Listener(
			str(row.get("LocalAddress", "")),
			int(row.get("LocalPort") or 0),
			int(row.get("OwningProcess") or 0),
		)
		for row in data.get("Listeners", [])
		if isinstance(row, dict)
	]
	parents = {
		int(row.get("ProcessId") or 0): int(row.get("ParentProcessId") or 0)
		for row in data.get("Processes", [])
		if isinstance(row, dict) and row.get("ProcessId")
	}
	return listeners, parents


@dataclass(frozen=True, slots=True)
class EndpointIdentity:
	port: int
	pid: int
	packageFullName: str
	packageFamily: str
	# Include creation times: a recycled PID/parent PID is not the same process.
	ancestry: tuple[tuple[int, int, str], ...]


def captureEndpointIdentity(
	port: int,
	package,
	runner: PowerShellRunner = runPowerShell,
	*,
	clientPort: int | None = None,
) -> EndpointIdentity:
	if isinstance(port, bool) or not isinstance(port, int) or not 1024 <= port <= 65535:
		raise LoaderError("listener.port")
	if clientPort is not None and (
		isinstance(clientPort, bool) or not isinstance(clientPort, int) or not 1 <= clientPort <= 65535
	):
		raise LoaderError("listener.port")
	connectionQuery = (
		f"$connections = @(Get-NetTCPConnection -State Established -LocalPort {port} "
		f"-RemotePort {clientPort} -ErrorAction SilentlyContinue "
		"| Select-Object LocalAddress,RemoteAddress,LocalPort,RemotePort,OwningProcess); "
		if clientPort is not None
		else "$connections = @(); "
	)
	script = (
		f"$listeners = @(Get-NetTCPConnection -State Listen -LocalPort {port} -ErrorAction SilentlyContinue "
		"| Select-Object LocalAddress,LocalPort,OwningProcess); "
		"$processes = @(Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId,ExecutablePath,"
		"@{Name='Created';Expression={if ($_.CreationDate) {$_.CreationDate.ToFileTimeUtc()} else {0}}}); "
		+ connectionQuery
		+ "@{Listeners=$listeners;Processes=$processes;Connections=$connections} | ConvertTo-Json -Compress -Depth 4"
	)
	try:
		data = json.loads(runner(PowerShellCommand(script, "listener.identity")) or "{}")
		if (
			not isinstance(data, dict)
			or not isinstance(data.get("Listeners"), list)
			or not isinstance(data.get("Processes"), list)
		):
			raise ValueError("snapshot")
		selected = [
			row for row in data["Listeners"] if isinstance(row, dict) and row.get("LocalPort") == port
		]
		if not selected or any(row.get("LocalAddress") != LOOPBACK_HOST for row in selected):
			raise LoaderError("listener.exposure")
		pids = {int(row.get("OwningProcess") or 0) for row in selected}
		if len(pids) != 1 or 0 in pids:
			raise LoaderError("listener.ancestry")
		pid = next(iter(pids))
		if clientPort is not None:
			connections = data.get("Connections")
			if not isinstance(connections, list) or not connections:
				raise LoaderError("listener.connection", "missingEstablishedSocket")
			if any(
				not isinstance(row, dict)
				or row.get("LocalAddress") != LOOPBACK_HOST
				or row.get("RemoteAddress") != LOOPBACK_HOST
				or row.get("LocalPort") != port
				or row.get("RemotePort") != clientPort
				or row.get("OwningProcess") != pid
				for row in connections
			):
				raise LoaderError("listener.connection", "ownerMismatch")
		rows = {}
		for row in data["Processes"]:
			if not isinstance(row, dict):
				raise ValueError("process")
			processId = int(row.get("ProcessId") or 0)
			if processId in rows:
				raise LoaderError("listener.identity", "duplicatePid")
			rows[processId] = row
		root = pathlib.PureWindowsPath(package.installLocation)
		if not root.is_absolute() or ".." in root.parts:
			raise LoaderError("listener.identity", "packagePath")
		chain = []
		seen = set()
		current = pid
		childCreated = None
		while current and current not in seen:
			seen.add(current)
			row = rows.get(current)
			if row is None:
				raise LoaderError("listener.identity", "missingProcess")
			created = int(row.get("Created") or 0)
			if created <= 0 or (childCreated is not None and created > childCreated):
				raise LoaderError("listener.identity", "creationTime")
			path = str(row.get("ExecutablePath") or "")
			chain.append((current, created, path.casefold()))
			if path:
				try:
					pathlib.PureWindowsPath(path).relative_to(root)
				except ValueError:
					pass
				else:
					return EndpointIdentity(port, pid, package.fullName, package.familyName, tuple(chain))
			childCreated = created
			current = int(row.get("ParentProcessId") or 0)
		raise LoaderError("listener.ancestry")
	except (ValueError, TypeError, KeyError, OverflowError) as error:
		raise LoaderError("listener.identity", "snapshot") from error
