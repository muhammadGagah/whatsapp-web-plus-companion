"""D03: ownership snapshots and attachment checks (simulated Windows topology)."""

import copy
import json
import threading
import unittest
from unittest.mock import MagicMock, patch
from _path import installPackagePath

installPackagePath()
from globalPlugins.whatsappWebPlusCompanion import launcher, processes
from globalPlugins.whatsappWebPlusCompanion.cdp import Target
from globalPlugins.whatsappWebPlusCompanion.models import LoaderError
from globalPlugins.whatsappWebPlusCompanion.packages import PackageInfo


class EndpointTests(unittest.TestCase):
	def setUp(self):
		self.package = PackageInfo("package-1", "family", r"C:\Apps\WA")
		self.data = {
			"Listeners": [{"LocalAddress": "127.0.0.1", "LocalPort": 49223, "OwningProcess": 30}],
			"Processes": [
				{
					"ProcessId": 30,
					"ParentProcessId": 20,
					"Created": 300,
					"ExecutablePath": r"C:\WebView\webview.exe",
				},
				{
					"ProcessId": 20,
					"ParentProcessId": 1,
					"Created": 200,
					"ExecutablePath": r"C:\Apps\WA\WhatsApp.exe",
				},
			],
		}

	def capture(self):
		return processes.captureEndpointIdentity(49223, self.package, lambda s: json.dumps(self.data))

	def test_snapshot_binds_port_package_ancestry_pid_creation_and_path(self):
		identity = self.capture()
		self.assertEqual(identity.pid, 30)
		self.assertEqual(identity.port, 49223)
		self.assertEqual(identity.packageFullName, "package-1")
		self.assertEqual(identity.ancestry[0][:2], (30, 300))
		self.assertEqual(identity.ancestry[1][:2], (20, 200))

	def test_same_pid_with_new_creation_time_is_different_identity(self):
		first = self.capture()
		self.data["Processes"][0]["Created"] = 301
		self.assertNotEqual(first, self.capture())

	def test_recycled_parent_newer_than_child_is_rejected(self):
		self.data["Processes"][1]["Created"] = 400
		with self.assertRaisesRegex(LoaderError, "listener.identity"):
			self.capture()

	def test_missing_creation_time_or_process_is_rejected(self):
		original = copy.deepcopy(self.data)
		for key in ("Created", "ProcessId"):
			self.data = copy.deepcopy(original)
			self.data["Processes"][0].pop(key)
			with self.subTest(key=key), self.assertRaises(LoaderError):
				self.capture()

	def test_foreign_listener_and_wildcard_are_rejected(self):
		original = copy.deepcopy(self.data)
		for address, pid in [("0.0.0.0", 30), ("::1", 30), ("127.0.0.1", 99)]:
			self.data = copy.deepcopy(original)
			self.data["Listeners"].append({"LocalAddress": address, "LocalPort": 49223, "OwningProcess": pid})
			with self.subTest(address=address, pid=pid), self.assertRaises(LoaderError):
				self.capture()

	def test_package_prefix_collision_is_rejected(self):
		self.data["Processes"][1]["ExecutablePath"] = r"C:\Apps\WA-malicious\WhatsApp.exe"
		with self.assertRaises(LoaderError):
			self.capture()

	def test_legacy_topology_also_rejects_mixed_foreign_listener(self):
		with self.assertRaisesRegex(LoaderError, "listener.ancestry"):
			processes.validateListener(
				49223,
				[processes.Listener("127.0.0.1", 49223, 30), processes.Listener("127.0.0.1", 49223, 99)],
				{30: 20},
				{20},
			)

	def test_changed_identity_before_connection_prevents_socket_and_injection(self):
		target = Target("p", "https://web.whatsapp.com/", "ws://127.0.0.1:49223/devtools/page/p", "old")
		with (
			patch.object(launcher.WebSocket, "connect") as connect,
			patch.object(launcher, "installAndVerify") as install,
		):
			with self.assertRaisesRegex(LoaderError, "listener.changed"):
				launcher._connectAndInstall(
					target, "source", "1", "hash", threading.Event(), validator=lambda **kwargs: "new"
				)
			connect.assert_not_called()
			install.assert_not_called()

	def test_changed_identity_after_handshake_prevents_injection_and_closes(self):
		target = Target("p", "https://web.whatsapp.com/", "ws://127.0.0.1:49223/devtools/page/p", "owner")
		ws = MagicMock()
		with (
			patch.object(launcher.WebSocket, "connect", return_value=ws),
			patch.object(launcher, "installAndVerify") as install,
		):
			with self.assertRaisesRegex(LoaderError, "listener.changed"):
				launcher._connectAndInstall(
					target,
					"source",
					"1",
					"hash",
					threading.Event(),
					validator=MagicMock(side_effect=["owner", "new"]),
				)
			install.assert_not_called()
			ws.close.assert_called_once()

	def test_every_attachment_revalidates_before_and_after_handshake(self):
		target = Target("p", "https://web.whatsapp.com/", "ws://127.0.0.1:49223/devtools/page/p", "owner")
		validate = MagicMock(return_value="owner")
		with (
			patch.object(launcher.WebSocket, "connect", side_effect=lambda *a, **k: MagicMock()),
			patch.object(launcher, "installAndVerify", return_value=({}, "id")) as install,
		):
			for _ in range(2):
				session, health, unregister = launcher._connectAndInstall(
					target, "source", "1", "hash", threading.Event(), validator=validate
				)
				session.close()
				unregister()
			self.assertEqual(validate.call_count, 4)
			self.assertEqual(install.call_count, 2)

	def test_established_connection_must_have_the_validated_listener_owner(self):
		self.data["Connections"] = [
			{
				"LocalAddress": "127.0.0.1",
				"RemoteAddress": "127.0.0.1",
				"LocalPort": 49223,
				"RemotePort": 50000,
				"OwningProcess": 30,
			}
		]
		identity = processes.captureEndpointIdentity(
			49223, self.package, lambda _: json.dumps(self.data), clientPort=50000
		)
		self.assertEqual(identity.pid, 30)
		self.data["Connections"][0]["OwningProcess"] = 99
		with self.assertRaisesRegex(LoaderError, "listener.connection"):
			processes.captureEndpointIdentity(
				49223, self.package, lambda _: json.dumps(self.data), clientPort=50000
			)

	def test_missing_established_connection_is_rejected(self):
		with self.assertRaisesRegex(LoaderError, "listener.connection"):
			processes.captureEndpointIdentity(
				49223, self.package, lambda _: json.dumps(self.data), clientPort=50000
			)
