"""Resource-boundary regressions added during the September 2026 audit."""

import base64
import hashlib
import io
import unittest
from unittest.mock import patch

from _path import installPackagePath

installPackagePath()

from globalPlugins.whatsappWebPlusCompanion import http, websocket
from globalPlugins.whatsappWebPlusCompanion.models import LoaderError


def frame(opcode, payload, final=True):
	length = len(payload)
	prefix = bytes([(0x80 if final else 0) | opcode])
	if length < 126:
		return prefix + bytes([length]) + payload
	if length <= 65535:
		return prefix + b"\x7e" + length.to_bytes(2, "big") + payload
	return prefix + b"\x7f" + length.to_bytes(8, "big") + payload


class TrackingStream(io.BytesIO):
	def __init__(self, payload):
		super().__init__(payload)
		self.writeCalls = 0
		self.readCalls = 0

	def write(self, payload):
		# Raw socket streams may short-write. Do not overwrite the incoming response.
		self.writeCalls += 1
		return 1

	def readline(self, size=-1):
		self.readCalls += 1
		return super().readline(size)


class SocketStub:
	def __init__(self, stream=None, chunks=()):
		self.stream = stream
		self.chunks = iter(chunks)
		self.closed = False
		self.sent = []
		self.recvCalls = 0

	def makefile(self, *args, **kwargs):
		return self.stream

	def send(self, data):
		# Exercise short writes instead of assuming send completes the request.
		chunk = bytes(data[:17])
		self.sent.append(chunk)
		return len(chunk)

	def shutdown(self, how):
		pass

	def recv(self, size):
		self.recvCalls += 1
		return self.stream.read(size) if self.stream is not None else next(self.chunks, b"")

	def settimeout(self, timeout):
		pass

	def close(self):
		self.closed = True

	def __enter__(self):
		return self

	def __exit__(self, *args):
		self.close()


class TransportAuditTests(unittest.TestCase):
	def test_fragmented_message_total_is_bounded(self):
		stream = io.BytesIO(frame(1, b"a" * 20, False) + frame(0, b"b" * 20))
		with patch.object(websocket, "MAX_FRAME_BYTES", 32):
			with self.assertRaisesRegex(LoaderError, "websocket.messageTooLarge"):
				websocket.WebSocket(SocketStub(), stream).receiveText()

	def test_fragmented_utf8_with_interleaved_ping_remains_valid(self):
		encoded = "A\U0001f600B".encode("utf-8")
		stream = io.BytesIO(frame(1, encoded[:3], False) + frame(9, b"ping") + frame(0, encoded[3:]))
		sock = SocketStub()
		self.assertEqual(websocket.WebSocket(sock, stream).receiveText(), "A\U0001f600B")
		self.assertEqual(sock.sent[0][0], 0x8A)

	def test_message_exactly_at_limit_is_accepted(self):
		stream = io.BytesIO(frame(1, b"a" * 16, False) + frame(0, b"b" * 16))
		with patch.object(websocket, "MAX_FRAME_BYTES", 32):
			self.assertEqual(websocket.WebSocket(SocketStub(), stream).receiveText(), "a" * 16 + "b" * 16)

	def test_failed_handshake_closes_the_only_socket_resource(self):
		for response in (b"HTTP/1.1 200 OK\r\n\r\n", b"HTTP/1.1 101 OK\r\nbad header\r\n"):
			with self.subTest(response=response):
				stream = TrackingStream(response)
				sock = SocketStub(stream)
				with patch.object(websocket, "connectLoopback", return_value=(sock, lambda: None)):
					with self.assertRaisesRegex(LoaderError, "websocket.handshake"):
						websocket.WebSocket.connect("ws://127.0.0.1:12345/devtools/page/test", 1)
				self.assertTrue(sock.closed)
				self.assertFalse(stream.closed)  # Adapter never duplicates the socket via makefile().

	def test_handshake_request_uses_complete_send(self):
		key = base64.b64encode(b"a" * 16)
		accept = base64.b64encode(
			hashlib.sha1(key + websocket._GUID.encode(), usedforsecurity=False).digest(),
		)
		stream = TrackingStream(
			b"HTTP/1.1 101 OK\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: "
			+ accept
			+ b"\r\n\r\n",
		)
		sock = SocketStub(stream)
		with (
			patch.object(websocket, "connectLoopback", return_value=(sock, lambda: None)),
			patch.object(websocket.os, "urandom", return_value=b"a" * 16),
		):
			connection = websocket.WebSocket.connect("ws://127.0.0.1:12345/devtools/page/test", 1)
		self.assertIs(connection.stream.sock, sock)
		self.assertEqual(stream.writeCalls, 0)
		self.assertGreater(len(sock.sent), 1)
		self.assertTrue(b"".join(sock.sent).endswith(b"\r\n\r\n"))
		connection.close()
		self.assertTrue(sock.closed)

	def test_unterminated_http_headers_are_rejected_early(self):
		sock = SocketStub(chunks=[b"x" * 68, b"x" * 68, b""])
		with (
			patch.object(http, "MAX_HTTP_HEADER_BYTES", 64),
			patch.object(http, "connectLoopback", return_value=(sock, lambda: None)),
		):
			with self.assertRaisesRegex(LoaderError, "http.headers"):
				http.httpGetJson(12345, "/json/list")
		self.assertEqual(sock.recvCalls, 1)

	def test_http_delimiter_may_cross_header_limit_boundary(self):
		body = b"{}"
		header = b"HTTP/1.1 200 OK\r\nContent-Length: 2"
		sock = SocketStub(chunks=[header + b"\r\n\r", b"\n" + body])
		with (
			patch.object(http, "MAX_HTTP_HEADER_BYTES", len(header)),
			patch.object(http, "connectLoopback", return_value=(sock, lambda: None)),
		):
			self.assertEqual(http.httpGetJson(12345, "/json/list"), {})

	def test_http_maximum_header_and_body_allow_delimiter(self):
		body = b"{}"
		header = b"HTTP/1.1 200 OK\r\nContent-Length: 2"
		sock = SocketStub(chunks=[header + b"\r\n\r\n" + body])
		with (
			patch.object(http, "MAX_HTTP_HEADER_BYTES", len(header)),
			patch.object(http, "MAX_HTTP_BYTES", len(body)),
			patch.object(http, "connectLoopback", return_value=(sock, lambda: None)),
		):
			self.assertEqual(http.httpGetJson(12345, "/json/list"), {})

	def test_websocket_handshake_total_headers_are_bounded(self):
		response = (
			b"HTTP/1.1 101 OK\r\n" + b"".join(f"X-{i}: test\r\n".encode() for i in range(500)) + b"\r\n"
		)
		stream = TrackingStream(response)
		sock = SocketStub(stream)
		# Default lets this test run against the original module as well.
		with (
			patch.object(websocket, "MAX_HTTP_HEADER_BYTES", 128, create=True),
			patch.object(websocket, "connectLoopback", return_value=(sock, lambda: None)),
		):
			with self.assertRaisesRegex(LoaderError, "websocket.handshake"):
				websocket.WebSocket.connect("ws://127.0.0.1:12345/devtools/page/test", 1)
		self.assertLessEqual(sock.recvCalls, 144)

	def test_invalid_websocket_ports_raise_domain_error_before_connect(self):
		for port in ("invalid", "65536", "0", "80"):
			with self.subTest(port=port), patch.object(websocket, "connectLoopback") as connect:
				with self.assertRaisesRegex(LoaderError, "websocket.url"):
					websocket.WebSocket.connect(f"ws://127.0.0.1:{port}/devtools/page/test", 1)
				connect.assert_not_called()
