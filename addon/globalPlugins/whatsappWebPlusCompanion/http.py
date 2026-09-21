import json

from .models import LoaderError
from .ioDeadline import Deadline, connectLoopback, noopRegister, sendAll, receive
from .policy import (
	ALLOWED_HTTP_PATHS,
	LOOPBACK_HOST,
	MAX_HTTP_BYTES,
	MAX_HTTP_HEADER_BYTES,
	REQUEST_DEADLINE,
)


def _parseHeaders(headerBytes: bytes) -> tuple[str, dict[str, str]]:
	try:
		lines = headerBytes.decode("ascii", "strict").split("\r\n")
	except UnicodeDecodeError as error:
		raise LoaderError("http.headers", "encoding") from error
	if not lines:
		raise LoaderError("http.status")
	statusParts = lines[0].split(" ", 2)
	if len(statusParts) < 2 or statusParts[0] != "HTTP/1.1" or statusParts[1] != "200":
		raise LoaderError("http.status")
	headers: dict[str, str] = {}
	for line in lines[1:]:
		if ":" not in line:
			raise LoaderError("http.headers", "syntax")
		name, value = line.split(":", 1)
		name = name.strip().lower()
		if not name or name in headers:
			raise LoaderError("http.headers", "duplicate")
		headers[name] = value.strip()
	return lines[0], headers


def _contentLength(headers: dict[str, str]) -> int:
	if "transfer-encoding" in headers or "location" in headers:
		raise LoaderError("http.headers", "unsupported")
	try:
		contentLength = int(headers["content-length"])
	except (KeyError, ValueError) as error:
		raise LoaderError("http.length") from error
	if contentLength < 0 or contentLength > MAX_HTTP_BYTES:
		raise LoaderError("http.length")
	return contentLength


def httpGetJson(
	port: int,
	path: str,
	timeout: float = REQUEST_DEADLINE,
	*,
	cancelEvent=None,
	registerCloser=noopRegister,
	deadline: float | None = None,
) -> object:
	if path not in ALLOWED_HTTP_PATHS or not 1024 <= port <= 65535:
		raise LoaderError("http.request")
	request = (
		f"GET {path} HTTP/1.1\r\n"
		f"Host: {LOOPBACK_HOST}:{port}\r\n"
		"Accept: application/json\r\n"
		"Connection: close\r\n\r\n"
	).encode("ascii")
	budget = Deadline.after(timeout, cancelEvent, deadline)
	sock = None

	def unregister():
		return None

	data = bytearray()
	headerEnd = -1
	expectedLength: int | None = None
	try:
		sock, unregister = connectLoopback(port, budget, registerCloser)
		sendAll(sock, request, budget)
		while True:
			chunk = receive(sock, 65536, budget)
			if not chunk:
				break
			data.extend(chunk)
			if len(data) > MAX_HTTP_HEADER_BYTES + 4 + MAX_HTTP_BYTES:
				raise LoaderError("http.tooLarge")
			if headerEnd < 0:
				headerEnd = data.find(b"\r\n\r\n")
				# Keep up to three delimiter bytes when it spans recv() calls.
				if headerEnd < 0 and len(data) > MAX_HTTP_HEADER_BYTES + 3:
					raise LoaderError("http.headers")
				if headerEnd > MAX_HTTP_HEADER_BYTES:
					raise LoaderError("http.headers")
				if headerEnd >= 0:
					_headerStatus, headers = _parseHeaders(bytes(data[:headerEnd]))
					expectedLength = headerEnd + 4 + _contentLength(headers)
			if expectedLength is not None:
				if len(data) > expectedLength:
					raise LoaderError("http.length")
				if len(data) == expectedLength:
					break
	except LoaderError:
		raise
	except (OSError, TimeoutError) as error:
		if cancelEvent is not None and cancelEvent.is_set():
			raise LoaderError("operation.cancelled") from error
		raise LoaderError("http.transport", type(error).__name__) from error
	finally:
		if sock is not None:
			sock.close()
		unregister()

	headerEnd = data.find(b"\r\n\r\n")
	if headerEnd < 0 or headerEnd > MAX_HTTP_HEADER_BYTES:
		raise LoaderError("http.headers")
	headerBytes = bytes(data[:headerEnd])
	body = bytes(data[headerEnd + 4 :])
	_status, headers = _parseHeaders(headerBytes)
	contentLength = _contentLength(headers)
	if len(body) != contentLength:
		raise LoaderError("http.length")
	contentType = headers.get("content-type", "").split(";", 1)[0].strip().lower()
	if contentType and contentType not in ("application/json", "text/json"):
		raise LoaderError("http.contentType")
	try:
		return json.loads(body.decode("utf-8", "strict"))
	except (UnicodeDecodeError, ValueError) as error:
		raise LoaderError("http.json", type(error).__name__) from error


def endpointResponds(port: int, **kwargs) -> bool:
	try:
		value = httpGetJson(port, "/json/version", timeout=0.5, **kwargs)
		return isinstance(value, dict)
	except LoaderError as error:
		if error.code == "operation.cancelled":
			raise
		return False
