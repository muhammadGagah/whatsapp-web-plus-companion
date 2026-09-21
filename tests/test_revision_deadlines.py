"""D04: real loopback sockets, slow peers and cancellation, no WhatsApp required."""

import base64
import hashlib
import socket
import threading
import time
import unittest
from unittest.mock import MagicMock, patch
from _path import installPackagePath

installPackagePath()
from globalPlugins.whatsappWebPlusCompanion import http, websocket, ioDeadline, cdp
from globalPlugins.whatsappWebPlusCompanion.models import LoaderError
from globalPlugins.whatsappWebPlusCompanion.controller import Controller


class Peer:
	def __init__(self, handler):
		self.listener = socket.socket()
		self.listener.bind(("127.0.0.1", 0))
		self.listener.listen(1)
		self.listener.settimeout(1)
		self.port = self.listener.getsockname()[1]
		self.connected = threading.Event()
		self.stop = threading.Event()

		def serve():
			try:
				connection, _ = self.listener.accept()
				with connection:
					connection.settimeout(0.5)
					self.connected.set()
					handler(connection, self.stop)
			except (OSError, ValueError):
				pass

		self.thread = threading.Thread(target=serve, daemon=True)

	def __enter__(self):
		self.thread.start()
		return self

	def __exit__(self, *a):
		self.stop.set()
		self.listener.close()
		self.thread.join(1)


def handshake(connection):
	request = b""
	while b"\r\n\r\n" not in request:
		request += connection.recv(4096)
	key = next(
		x.split(b":", 1)[1].strip()
		for x in request.split(b"\r\n")
		if x.lower().startswith(b"sec-websocket-key:")
	)
	accept = base64.b64encode(hashlib.sha1(key + websocket._GUID.encode(), usedforsecurity=False).digest())
	connection.sendall(
		b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: "
		+ accept
		+ b"\r\n\r\n"
	)


def frame(opcode, payload=b"", final=True):
	assert len(payload) < 126
	return bytes([(128 if final else 0) | opcode, len(payload)]) + payload


class DeadlineTests(unittest.TestCase):
	def assertBounded(self, function, maxSeconds=0.8):
		started = time.monotonic()
		with self.assertRaises((LoaderError, TimeoutError)):
			function()
		self.assertLess(time.monotonic() - started, maxSeconds)

	def test_http_drip_headers_have_whole_operation_deadline(self):
		def drip(conn, stop):
			conn.recv(4096)
			for b in b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\n{}":
				if stop.wait(0.03):
					break
				conn.sendall(bytes([b]))

		with Peer(drip) as peer:
			self.assertBounded(lambda: http.httpGetJson(peer.port, "/json/list", 0.12))

	def test_http_body_does_not_reset_header_deadline(self):
		def drip(conn, stop):
			conn.recv(4096)
			conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 20\r\n\r\n")
			for _ in range(20):
				if stop.wait(0.025):
					break
				conn.sendall(b" ")

		with Peer(drip) as peer:
			self.assertBounded(lambda: http.httpGetJson(peer.port, "/json/list", 0.12))

	def test_websocket_drip_handshake_has_absolute_deadline(self):
		def drip(conn, stop):
			conn.recv(4096)
			for b in b"HTTP/1.1 101 Switching Protocols\r\n":
				if stop.wait(0.03):
					break
				conn.sendall(bytes([b]))

		with Peer(drip) as peer:
			self.assertBounded(
				lambda: websocket.WebSocket.connect(f"ws://127.0.0.1:{peer.port}/devtools/page/p", 0.12)
			)

	def test_fragmented_message_cannot_renew_deadline(self):
		def drip(conn, stop):
			handshake(conn)
			conn.sendall(frame(1, b"a", False))
			while not stop.wait(0.03):
				conn.sendall(frame(0, b"a", False))

		with Peer(drip) as peer:
			ws = websocket.WebSocket.connect(f"ws://127.0.0.1:{peer.port}/devtools/page/p", 1)
			try:
				self.assertBounded(lambda: ws.receiveText(budget=ioDeadline.Deadline.after(0.12)))
			finally:
				ws.close()

	def test_ping_storm_has_control_frame_count_limit(self):
		def pings(conn, stop):
			handshake(conn)
			conn.sendall(frame(9) * 20)
			stop.wait(0.5)

		with Peer(pings) as peer, patch.object(websocket, "_MAX_MESSAGE_FRAMES", 8):
			ws = websocket.WebSocket.connect(f"ws://127.0.0.1:{peer.port}/devtools/page/p", 1)
			try:
				with self.assertRaisesRegex(LoaderError, "websocket.tooManyFrames"):
					ws.receiveText()
			finally:
				ws.close()

	def test_cdp_unsolicited_events_cannot_extend_request_deadline(self):
		def events(conn, stop):
			handshake(conn)
			conn.recv(4096)
			while not stop.wait(0.02):
				conn.sendall(frame(1, b'{"method":"Runtime.consoleAPICalled"}'))

		with Peer(events) as peer:
			session = cdp.CdpSession(
				websocket.WebSocket.connect(f"ws://127.0.0.1:{peer.port}/devtools/page/p", 1)
			)
			try:
				self.assertBounded(lambda: session.request("Runtime.enable", {}, deadline=0.12))
			finally:
				session.close()

	def test_cancellation_interrupts_registered_socket_during_handshake(self):
		cancel = threading.Event()
		closers = []
		outcome = []

		def register(fn):
			closers.append(fn)
			return lambda: closers.remove(fn)

		with Peer(lambda conn, stop: stop.wait(1)) as peer:

			def run():
				try:
					websocket.WebSocket.connect(
						f"ws://127.0.0.1:{peer.port}/devtools/page/p",
						5,
						cancelEvent=cancel,
						registerCloser=register,
					)
				except Exception as error:
					outcome.append(error)

			worker = threading.Thread(target=run)
			worker.start()
			self.assertTrue(peer.connected.wait(0.5))
			started = time.monotonic()
			cancel.set()
			for close in tuple(closers):
				close()
			worker.join(0.5)
			self.assertFalse(worker.is_alive())
			self.assertLess(time.monotonic() - started, 0.5)
			self.assertEqual(outcome[0].code, "operation.cancelled")
			self.assertFalse(closers)

	def test_cancellation_before_connect_does_not_create_socket(self):
		cancel = threading.Event()
		cancel.set()
		with patch.object(ioDeadline.socket, "socket") as create:
			with self.assertRaisesRegex(LoaderError, "operation.cancelled"):
				ioDeadline.connectLoopback(49223, ioDeadline.Deadline.after(1, cancel))
			create.assert_not_called()

	def test_send_stall_is_deadline_bounded(self):
		sock = MagicMock()

		def stalled(data):
			time.sleep(0.01)
			raise socket.timeout()

		sock.send.side_effect = stalled
		self.assertBounded(lambda: ioDeadline.sendAll(sock, b"request", ioDeadline.Deadline.after(0.08)))

	def test_late_closer_registration_after_stop_closes_immediately(self):
		controller = Controller(lambda *a: None, lambda r: None)
		controller.stop()
		close = MagicMock()
		controller.registerCloser(close)
		close.assert_called_once()
