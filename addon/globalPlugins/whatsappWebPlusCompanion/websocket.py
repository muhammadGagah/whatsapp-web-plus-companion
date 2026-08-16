import base64
import contextlib
import hashlib
import os
import socket
from urllib.parse import urlsplit

from .models import LoaderError
from .policy import LOOPBACK_HOST, MAX_FRAME_BYTES

_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


def _isSwitchingProtocolsStatus(status: str) -> bool:
	parts = status.split(" ", 2)
	return len(parts) == 3 and parts[0] == "HTTP/1.1" and parts[1] == "101"


def _readExact(stream, length: int) -> bytes:
	result = bytearray()
	while len(result) < length:
		try:
			chunk = stream.read(length - len(result))
		except socket.timeout:
			raise
		except OSError as error:
			raise LoaderError("websocket.receive", type(error).__name__) from error
		if not chunk:
			raise LoaderError("websocket.closed")
		result.extend(chunk)
	return bytes(result)


def encodeClientFrame(opcode: int, payload: bytes) -> bytes:
	if len(payload) > MAX_FRAME_BYTES:
		raise LoaderError("websocket.frameTooLarge")
	mask = os.urandom(4)
	length = len(payload)
	if length < 126:
		header = bytes((0x80 | opcode, 0x80 | length))
	elif length <= 0xFFFF:
		header = bytes((0x80 | opcode, 0x80 | 126)) + length.to_bytes(2, "big")
	else:
		header = bytes((0x80 | opcode, 0x80 | 127)) + length.to_bytes(8, "big")
	masked = bytes(value ^ mask[index % 4] for index, value in enumerate(payload))
	return header + mask + masked


def readServerFrame(stream) -> tuple[int, bytes, bool]:
	first, second = _readExact(stream, 2)
	final = bool(first & 0x80)
	opcode = first & 0x0F
	if first & 0x70 or second & 0x80:
		raise LoaderError("websocket.protocol")
	length = second & 0x7F
	if length == 126:
		length = int.from_bytes(_readExact(stream, 2), "big")
	elif length == 127:
		encoded = _readExact(stream, 8)
		if encoded[0] & 0x80:
			raise LoaderError("websocket.protocol")
		length = int.from_bytes(encoded, "big")
	if length > MAX_FRAME_BYTES:
		raise LoaderError("websocket.frameTooLarge")
	if opcode >= 8 and (not final or length > 125):
		raise LoaderError("websocket.protocol")
	return opcode, _readExact(stream, length), final


class WebSocket:
	def __init__(self, sock: socket.socket, stream) -> None:
		super().__init__()
		self.sock = sock
		self.stream = stream
		self.closed = False

	@classmethod
	def connect(cls, url: str, timeout: float) -> "WebSocket":
		parsed = urlsplit(url)
		if (
			parsed.scheme != "ws"
			or parsed.hostname != LOOPBACK_HOST
			or parsed.port is None
			or parsed.username
			or parsed.password
			or parsed.fragment
			or not parsed.path.startswith("/devtools/")
		):
			raise LoaderError("websocket.url")
		key = base64.b64encode(os.urandom(16)).decode("ascii")
		sock: socket.socket | None = None
		try:
			sock = socket.create_connection((LOOPBACK_HOST, parsed.port), timeout=timeout)
			sock.settimeout(timeout)
			stream = sock.makefile("rwb", buffering=0)
			path = parsed.path or "/"
			if parsed.query:
				path += f"?{parsed.query}"
			request = (
				f"GET {path} HTTP/1.1\r\n"
				f"Host: {LOOPBACK_HOST}:{parsed.port}\r\n"
				"Upgrade: websocket\r\n"
				"Connection: Upgrade\r\n"
				f"Sec-WebSocket-Key: {key}\r\n"
				"Sec-WebSocket-Version: 13\r\n\r\n"
			)
			stream.write(request.encode("ascii"))
			status = stream.readline(4096).decode("ascii", "strict").rstrip("\r\n")
			headers: dict[str, str] = {}
			while True:
				line = stream.readline(4096)
				if line == b"\r\n":
					break
				if not line or len(line) >= 4096:
					raise LoaderError("websocket.handshake")
				name, value = line.decode("ascii", "strict").split(":", 1)
				name = name.lower()
				if name in headers:
					raise LoaderError("websocket.handshake")
				headers[name] = value.strip()
		except LoaderError:
			if sock is not None:
				sock.close()
			raise
		except (OSError, UnicodeError, ValueError) as error:
			if sock is not None:
				sock.close()
			raise LoaderError("websocket.handshake", type(error).__name__) from error
		assert sock is not None
		expected = base64.b64encode(
			hashlib.sha1((key + _GUID).encode("ascii"), usedforsecurity=False).digest(),
		).decode("ascii")
		connectionTokens = {item.strip().lower() for item in headers.get("connection", "").split(",")}
		if (
			not _isSwitchingProtocolsStatus(status)
			or headers.get("upgrade", "").lower() != "websocket"
			or "upgrade" not in connectionTokens
			or headers.get("sec-websocket-accept") != expected
			or "sec-websocket-extensions" in headers
			or "sec-websocket-protocol" in headers
		):
			sock.close()
			raise LoaderError("websocket.handshake")
		return cls(sock, stream)

	def sendText(self, text: str) -> None:
		try:
			self.sock.sendall(encodeClientFrame(1, text.encode("utf-8")))
		except OSError as error:
			raise LoaderError("websocket.send", type(error).__name__) from error

	def receiveText(self) -> str:
		parts: list[bytes] = []
		expectingContinuation = False
		while True:
			opcode, payload, final = readServerFrame(self.stream)
			if opcode == 8:
				raise LoaderError("websocket.closed")
			if opcode == 9:
				self.sock.sendall(encodeClientFrame(10, payload))
				continue
			if opcode == 10:
				continue
			if not expectingContinuation and opcode != 1:
				raise LoaderError("websocket.opcode")
			if expectingContinuation and opcode != 0:
				raise LoaderError("websocket.opcode")
			parts.append(payload)
			expectingContinuation = not final
			if final:
				try:
					return b"".join(parts).decode("utf-8", "strict")
				except UnicodeDecodeError as error:
					raise LoaderError("websocket.utf8") from error

	def close(self) -> None:
		if self.closed:
			return
		self.closed = True
		with contextlib.suppress(OSError):
			self.sock.sendall(encodeClientFrame(8, b"\x03\xe8"))
		self.interrupt()
		with contextlib.suppress(OSError):
			self.stream.close()

	def interrupt(self) -> None:
		with contextlib.suppress(OSError):
			self.sock.shutdown(socket.SHUT_RDWR)
		with contextlib.suppress(OSError):
			self.sock.close()
