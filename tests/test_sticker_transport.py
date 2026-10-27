import threading
import unittest
import time
from _path import installPackagePath

installPackagePath()
from globalPlugins.whatsappWebPlusCompanion.stickerTransport import validateRequest, StickerTransport


class StickerTransportTests(unittest.TestCase):
	def request(self):
		return {
			"version": 1,
			"id": "12345678-1234-4234-8234-123456789012",
			"provider": "groq",
			"endpoint": "https://api.groq.com/openai/v1/chat/completions",
			"key": "test-only",
			"expiresAt": time.time() * 1000 + 45000,
			"body": {
				"model": "qwen/qwen3.8-27b",
				"messages": [
					{
						"role": "user",
						"content": [
							{"type": "text", "text": "Read sticker"},
							{"type": "image_url", "image_url": {"url": "data:image/png;base64,AA=="}},
						],
					},
				],
			},
		}

	def test_cloudflare_request(self):
		import json

		request = self.request()
		request["provider"] = "cloudflare"
		request["endpoint"] = (
			"https://api.cloudflare.com/client/v4/accounts/"
			+ "a" * 32
			+ "/ai/run/@cf/meta/llama-3.2-11b-vision-instruct"
		)
		request["body"] = {
			"prompt": "Describe sticker",
			"image": "data:image/png;base64,AA==",
			"stream": True,
			"max_tokens": 9000,
		}
		url, body = validateRequest(request)
		self.assertEqual(url.hostname, "api.cloudflare.com")
		self.assertEqual(json.loads(body)["max_tokens"], 512)
		self.assertFalse(json.loads(body)["stream"])
		endpoint = request["endpoint"]
		for invalid in (endpoint.replace("api.cloudflare.com", "evil.test"), endpoint + "?key=x"):
			request["endpoint"] = invalid
			with self.assertRaises(ValueError):
				validateRequest(request)
		request["endpoint"] = endpoint
		for invalid in (
			"https://example.test/image.png",
			"data:image/png;base64,",
			"data:image/png;base64,???",
		):
			request["body"]["image"] = invalid
			with self.assertRaises(ValueError):
				validateRequest(request)

	def test_cloudflare_agreement(self):
		request = self.request()
		request["provider"] = "cloudflare"
		request["purpose"] = "model-agreement"
		request["endpoint"] = (
			"https://api.cloudflare.com/client/v4/accounts/"
			+ "a" * 32
			+ "/ai/run/@cf/meta/llama-3.2-11b-vision-instruct"
		)
		request["body"] = {"prompt": "agree"}
		_, body = validateRequest(request)
		self.assertEqual(body, b'{"prompt":"agree"}')
		for invalid in ({"prompt": "no"}, {"prompt": "agree", "image": "AA=="}):
			request["body"] = invalid
			with self.assertRaises(ValueError):
				validateRequest(request)
		request["body"] = {"prompt": "agree"}
		del request["purpose"]
		with self.assertRaises(ValueError):
			validateRequest(request)

	def test_valid_request(self):
		url, body = validateRequest(self.request())
		self.assertEqual(url.hostname, "api.groq.com")
		self.assertNotIn(b"test-only", body)

	def test_cloudflare_selected_model(self):
		import json

		request = self.request()
		request["provider"] = "cloudflare"
		request["endpoint"] = (
			"https://api.cloudflare.com/client/v4/accounts/"
			+ "a" * 32
			+ "/ai/run/@cf/meta/llama-4-scout-17b-16e-instruct"
		)
		_, encoded = validateRequest(request)
		body = json.loads(encoded)
		self.assertEqual(body["max_tokens"], 512)
		self.assertNotIn("model", body)
		self.assertEqual(body["messages"][0]["content"][1]["image_url"]["url"], "data:image/png;base64,AA==")
		endpoint = request["endpoint"]
		for suffix in ("../../evil", "model?key=x", "%2e%2e", ""):
			request["endpoint"] = endpoint.rsplit("/", 1)[0] + "/" + suffix
			with self.assertRaises(ValueError):
				validateRequest(request)
		request["endpoint"] = endpoint
		request["purpose"] = "model-agreement"
		request["body"] = {"prompt": "agree"}
		with self.assertRaises(ValueError):
			validateRequest(request)

	def test_invalid_endpoints(self):
		for endpoint in (
			"http://api.groq.com/openai/v1/chat/completions",
			"https://wrong.example/v1/chat/completions",
			"https://user:secret@api.groq.com/openai/v1/chat/completions",
			"https://api.groq.com/openai/v1/chat/completions?key=x",
		):
			request = self.request()
			request["endpoint"] = endpoint
			with self.assertRaises(ValueError):
				validateRequest(request)

	def test_expiry_and_images(self):
		request = self.request()
		request["expiresAt"] = 0
		with self.assertRaises(ValueError):
			validateRequest(request)
		request = self.request()
		parts = request["body"]["messages"][0]["content"]
		parts.extend([parts[-1]] * 3)
		with self.assertRaises(ValueError):
			validateRequest(request)

	def test_no_bridge_does_no_network(self):
		class Session:
			def request(self, *args, **kwargs):
				return {"result": {"value": None}}

		transport = StickerTransport()
		transport.pump(Session())
		self.assertEqual(transport._jobs, {})

	def test_busy_transport_reports_busy_not_network_error(self):
		request = self.request()
		resolved = []

		class Session:
			def request(self, method, params, **kwargs):
				expression = params["expression"]
				if "resolve(" in expression:
					resolved.append(expression)
					return {"result": {"value": True}}
				return {"result": {"value": {"version": 1, "request": request, "activeId": request["id"]}}}

		transport = StickerTransport()
		# Two cancelled jobs are still finishing, so a new request cannot start.
		transport._jobs = {"a": {"cancel": threading.Event()}, "b": {"cancel": threading.Event()}}
		transport.pump(Session())
		self.assertEqual(len(resolved), 1)
		self.assertIn('"stickerBusy"', resolved[0])
		self.assertNotIn("stickerNetworkError", resolved[0])


class AddressFallbackTests(unittest.TestCase):
	def test_next_verified_address_is_tried_when_the_first_fails(self):
		from unittest import mock

		from globalPlugins.whatsappWebPlusCompanion import stickerTransport

		attempts = []

		def connect(address, timeout):
			attempts.append(address[0])
			if address[0] == "2001:db8::1":
				raise OSError("network unreachable")
			return "socket"

		addresses = [
			(None, None, None, None, ("2001:db8::1", 443)),
			(None, None, None, None, ("192.0.2.1", 443)),
		]
		with mock.patch.object(stickerTransport.socket, "create_connection", side_effect=connect):
			self.assertEqual(
				stickerTransport._connectToCheckedAddress(addresses, threading.Event()),
				"socket",
			)
		self.assertEqual(attempts, ["2001:db8::1", "192.0.2.1"])


if __name__ == "__main__":
	unittest.main()
