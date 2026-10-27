"""Bounded, dedicated AI transport; payloads never use the announcement bridge."""

import http.client
import ipaddress
import json
import re
import socket
import ssl
import base64
import threading
import time
from urllib.parse import urlsplit

_ENDPOINTS = {
	"gemini": "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent",
	"groq": "https://api.groq.com/openai/v1/chat/completions",
}


def validateRequest(value):
	if not isinstance(value, dict) or value.get("version") != 1:
		raise ValueError("contract")
	provider = value.get("provider")
	if provider not in ("gemini", "groq", "custom", "cloudflare"):
		raise ValueError("provider")
	identifier = value.get("id")
	if not isinstance(identifier, str) or len(identifier) != 36:
		raise ValueError("id")
	key = value.get("key")
	if not isinstance(key, str) or not key.strip() or len(key) > 8192 or "\r" in key or "\n" in key:
		raise ValueError("key")
	url = urlsplit(value.get("endpoint", ""))
	if url.scheme != "https" or not url.hostname or url.username or url.password or url.query or url.fragment:
		raise ValueError("endpoint")
	if url.port not in (None, 443):
		raise ValueError("port")
	if provider not in ("custom", "cloudflare") and value["endpoint"] != _ENDPOINTS[provider]:
		raise ValueError("endpoint")
	if provider == "custom" and not url.path.endswith("/chat/completions"):
		raise ValueError("path")
	deadline = value.get("expiresAt", 0)
	if (
		not isinstance(deadline, (int, float))
		or not time.time() * 1000 < deadline <= time.time() * 1000 + 60000
	):
		raise ValueError("deadline")
	body = value.get("body")
	if not isinstance(body, dict):
		raise ValueError("body")
	encoded = json.dumps(body, separators=(",", ":")).encode("utf-8")
	if len(encoded) > 8 * 1024 * 1024:
		raise ValueError("size")
	if provider == "cloudflare":
		if not re.fullmatch(
			r"https://api\.cloudflare\.com/client/v4/accounts/[a-f0-9]{32}/ai/run/"
			r"@(cf|hf)/[A-Za-z0-9][A-Za-z0-9_-]*/[A-Za-z0-9][A-Za-z0-9._-]*",
			value["endpoint"],
		):
			raise ValueError("endpoint")
		model = url.path.split("/ai/run/")[1]
		if len(model) > 160:
			raise ValueError("model")
		legacy = model == "@cf/meta/llama-3.2-11b-vision-instruct"
		if value.get("purpose") == "model-agreement":
			if not legacy:
				raise ValueError("agreement")
			if body != {"prompt": "agree"}:
				raise ValueError("agreement")
			return url, b'{"prompt":"agree"}'
		if legacy:
			prompt = body.get("prompt")
			image = body.get("image")
			if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 6000:
				raise ValueError("prompt")
			if not isinstance(image, str) or not image.startswith("data:image/png;base64,"):
				raise ValueError("image")
			if not base64.b64decode(image.split(",", 1)[1], validate=True):
				raise ValueError("image")
			body = {"prompt": prompt, "image": image, "max_tokens": 512, "stream": False}
			return url, json.dumps(body, separators=(",", ":")).encode("utf-8")
	if provider == "gemini":
		parts = body.get("contents", [{}])[0].get("parts")
	else:
		parts = body.get("messages", [{}])[0].get("content")
	if not isinstance(parts, list) or not 2 <= len(parts) <= 7:
		raise ValueError("parts")
	images = 0
	cleanParts = []
	for part in parts:
		if not isinstance(part, dict):
			raise ValueError("part")
		if isinstance(part.get("text"), str):
			if len(part["text"]) > 6000:
				raise ValueError("prompt")
			cleanParts.append(
				{"text": part["text"]} if provider == "gemini" else {"type": "text", "text": part["text"]},
			)
			continue
		if provider == "gemini":
			image = part.get("inlineData", {})
			if image.get("mimeType") != "image/png" or not isinstance(image.get("data"), str):
				raise ValueError("image")
			base64.b64decode(image["data"], validate=True)
			cleanParts.append({"inlineData": {"mimeType": "image/png", "data": image["data"]}})
		else:
			image = part.get("image_url", {}).get("url", "")
			if not isinstance(image, str) or not image.startswith("data:image/png;base64,"):
				raise ValueError("image")
			base64.b64decode(image.split(",", 1)[1], validate=True)
			cleanParts.append({"type": "image_url", "image_url": {"url": image}})
		images += 1
	if not images or provider == "groq" and images > 3:
		raise ValueError("images")
	if provider == "gemini":
		body = {
			"contents": [{"role": "user", "parts": cleanParts}],
			"generationConfig": {"maxOutputTokens": 512},
		}
	else:
		model = body.get("model")
		if provider != "cloudflare" and (not isinstance(model, str) or not model.strip() or len(model) > 160):
			raise ValueError("model")
		body = {
			"model": model,
			"messages": [{"role": "user", "content": cleanParts}],
			"max_completion_tokens": 512,
			"stream": False,
		}
	if provider == "cloudflare":
		del body["model"]
		del body["max_completion_tokens"]
		body["max_tokens"] = 512
	encoded = json.dumps(body, separators=(",", ":")).encode("utf-8")
	return url, encoded


def _connectToCheckedAddress(addresses, cancel):
	"""Try each verified global address in turn, so broken IPv6 routing can fall back to IPv4."""
	lastError = None
	for item in addresses:
		if cancel.is_set():
			break
		try:
			return socket.create_connection((item[4][0], 443), timeout=10)
		except OSError as error:
			lastError = error
	raise lastError or OSError("no address")


class StickerTransport:
	def __init__(self):
		self._lock = threading.Lock()
		self._jobs = {}
		self._results = []

	def close(self):
		with self._lock:
			for job in self._jobs.values():
				job["cancel"].set()
				if job.get("connection"):
					job["connection"].close()
			self._results.clear()

	def _run(self, request, job):
		identifier = request["id"]
		result = {"error": "stickerNetworkError"}
		connection = None
		try:
			url, body = validateRequest(request)
			addresses = socket.getaddrinfo(url.hostname, 443, type=socket.SOCK_STREAM)
			if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
				raise ValueError("address")
			if job["cancel"].is_set():
				return
			connection = http.client.HTTPSConnection(url.hostname, timeout=10)
			job["connection"] = connection
			connection.sock = ssl.create_default_context().wrap_socket(
				_connectToCheckedAddress(addresses, job["cancel"]),
				server_hostname=url.hostname,
			)
			if job["cancel"].is_set() or time.time() * 1000 >= request["expiresAt"]:
				return
			headers = {"Content-Type": "application/json"}
			headers["x-goog-api-key" if request["provider"] == "gemini" else "Authorization"] = (
				request["key"] if request["provider"] == "gemini" else "Bearer " + request["key"]
			)
			# The 10 s limit covers connecting only. A provider may stay silent until its whole answer is
			# ready, so reads may use the rest of the request deadline.
			connection.sock.settimeout(max(0.5, request["expiresAt"] / 1000 - time.time()))
			connection.request("POST", url.path, body=body, headers=headers)
			request["key"] = ""
			response = connection.getresponse()
			if 300 <= response.status < 400:
				raise ValueError("redirect")
			chunks = []
			size = 0
			while True:
				if job["cancel"].is_set() or time.time() * 1000 >= request["expiresAt"]:
					return
				chunk = response.read(4096)
				if not chunk:
					break
				size += len(chunk)
				if size > 65536:
					raise ValueError("response")
				chunks.append(chunk)
			try:
				responseBody = json.loads(b"".join(chunks))
			except (ValueError, UnicodeError):
				responseBody = None
			result = {"result": {"status": response.status, "body": responseBody}}
		except Exception:
			pass  # Provider errors, credentials and image data must not enter NVDA logs.
		finally:
			request["key"] = ""
			if connection:
				connection.close()
			with self._lock:
				self._jobs.pop(identifier, None)
				if not job["cancel"].is_set():
					self._results.append((identifier, result))

	def pump(self, session):
		response = session.request(
			"Runtime.evaluate",
			{
				"expression": "location.origin==='https://web.whatsapp.com' && "
				"globalThis.__waPlusStickerNative?.version===1 ? globalThis.__waPlusStickerNative.poll() : null",
				"returnByValue": True,
			},
			deadline=2.0,
		)
		value = response.get("result", {}).get("value")
		if not isinstance(value, dict) or value.get("version") != 1:
			self.close()
			return
		identifier = value.get("activeId")
		with self._lock:
			for jobId, job in self._jobs.items():
				if jobId != identifier:
					job["cancel"].set()
					if job.get("connection"):
						job["connection"].close()
			results, self._results = self._results, []
		request = value.get("request")
		if request:
			try:
				validateRequest(request)
				with self._lock:
					if len(self._jobs) >= 2 or request["id"] in self._jobs:
						raise ValueError("busy")
					job = {"cancel": threading.Event()}
					self._jobs[request["id"]] = job
				threading.Thread(target=self._run, args=(request, job), daemon=True).start()
			except (ValueError, TypeError, KeyError, IndexError, AttributeError) as error:
				if isinstance(request, dict) and request.get("id") == identifier:
					# Cancelled jobs can still be finishing; that is not a network problem.
					busy = isinstance(error, ValueError) and error.args == ("busy",)
					results.append((identifier, {"error": "stickerBusy" if busy else "stickerNetworkError"}))
		for jobId, result in results:
			if jobId != identifier:
				continue
			session.request(
				"Runtime.evaluate",
				{
					"expression": "globalThis.__waPlusStickerNative?.resolve("
					+ json.dumps(jobId)
					+ ","
					+ json.dumps(result)
					+ ")",
					"returnByValue": True,
				},
				deadline=2.0,
			)
