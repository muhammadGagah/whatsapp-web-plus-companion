"""Absolute I/O budgets. No DNS, per-read timeout renewal, or uncancellable connect."""

import contextlib
import errno
import select
import socket
import time
from dataclasses import dataclass
from collections.abc import Callable

from .models import LoaderError
from .policy import LOOPBACK_HOST


@dataclass(frozen=True)
class Deadline:
	end: float
	cancelEvent: object | None = None

	@classmethod
	def after(cls, seconds: float, cancelEvent=None, absolute: float | None = None):
		end = time.monotonic() + max(0.0, seconds)
		return cls(min(end, absolute) if absolute is not None else end, cancelEvent)

	def remaining(self) -> float:
		if self.cancelEvent is not None and self.cancelEvent.is_set():
			raise LoaderError("operation.cancelled")
		remaining = self.end - time.monotonic()
		if remaining <= 0:
			raise TimeoutError("operation deadline exceeded")
		return remaining

	def prepare(self, sock) -> None:
		# Raw recv/send are retryable after timeout; SocketIO.makefile is not.
		sock.settimeout(min(0.1, self.remaining()))


def noopRegister(closer: Callable[[], None]) -> Callable[[], None]:
	return lambda: None


def interruptSocket(sock) -> None:
	with contextlib.suppress(OSError):
		sock.shutdown(socket.SHUT_RDWR)
	with contextlib.suppress(OSError):
		sock.close()


def connectLoopback(port: int, budget: Deadline, registerCloser=noopRegister):
	budget.remaining()
	sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

	def unregister():
		return None

	try:
		# Register before connect, not after the HTTP/WebSocket handshake.
		unregister = registerCloser(lambda: interruptSocket(sock))
		budget.remaining()
		sock.setblocking(False)
		status = sock.connect_ex((LOOPBACK_HOST, port))
		pending = {errno.EINPROGRESS, errno.EWOULDBLOCK, errno.EALREADY, 10035, 10036, 10037}
		if status not in pending and status not in (0, errno.EISCONN):
			raise OSError(status, "loopback connect failed")
		while status not in (0, errno.EISCONN):
			remaining = budget.remaining()
			_, writable, exceptional = select.select([], [sock], [sock], min(0.1, remaining))
			if not writable and not exceptional:
				continue
			status = sock.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
			if status:
				raise OSError(status, "loopback connect failed")
		budget.prepare(sock)
		return sock, unregister
	except BaseException:
		interruptSocket(sock)
		unregister()
		if budget.cancelEvent is not None and budget.cancelEvent.is_set():
			raise LoaderError("operation.cancelled")
		raise


def sendAll(sock, data: bytes, budget: Deadline) -> None:
	view = memoryview(data)
	while view:
		budget.prepare(sock)
		try:
			sent = sock.send(view)
		except socket.timeout:
			budget.remaining()
			continue
		if sent <= 0:
			raise OSError("socket closed during send")
		view = view[sent:]
	budget.remaining()


def receive(sock, length: int, budget: Deadline) -> bytes:
	while True:
		budget.prepare(sock)
		try:
			data = sock.recv(length)
		except socket.timeout:
			budget.remaining()
			continue
		budget.remaining()
		return data
