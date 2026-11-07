import unittest
from unittest import mock

from _path import installPackagePath

installPackagePath()

from globalPlugins.whatsappWebPlusCompanion.callAvailability import CallAvailability, ConnectedCall
from globalPlugins.whatsappWebPlusCompanion.models import Channel


class CallAvailabilityTests(unittest.TestCase):
	def setUp(self):
		self.now = 0
		self.changed = mock.Mock()
		self.cache = CallAvailability(mock.Mock(), self.changed, clock=lambda: self.now)
		self.call = ConnectedCall(Channel.BETA, 10, 20)

	def test_channel_specific_evidence_expires(self):
		self.cache._finish(0, {Channel.BETA: self.call})
		self.assertNotIn(Channel.STABLE, self.cache.current())
		self.assertEqual(self.cache.current()[Channel.BETA], self.call)
		self.now = self.cache.TTL
		self.assertEqual(self.cache.current(), {})

	def test_invalidation_completes_pending_dialog_and_rejects_late_result(self):
		completed = mock.Mock()
		self.cache._pending = True
		self.cache.request(force=True, callback=completed)
		self.cache.invalidate()
		completed.assert_called_once_with({})
		self.cache._finish(0, {Channel.BETA: self.call})
		completed.assert_called_once_with({})
		self.assertEqual(self.cache.current(), {})
		self.assertFalse(self.cache._pending)
		self.changed.assert_not_called()

	def test_repeated_requests_share_one_worker(self):
		with mock.patch("threading.Thread") as thread:
			self.cache.request(force=True)
			self.cache.request(force=True)
			thread.assert_called_once()
			thread.return_value.start.assert_called_once()

	def test_refresh_preserves_unexpired_call_evidence(self):
		self.cache._finish(0, {Channel.BETA: self.call})
		self.now = self.cache.TTL / 2
		with mock.patch("threading.Thread") as thread:
			self.cache.request()
			thread.return_value.start.assert_called_once()
			self.assertEqual(self.cache.current()[Channel.BETA], self.call)

	def test_request_after_invalidation_gets_fresh_worker_result(self):
		old, fresh = mock.Mock(), mock.Mock()
		with mock.patch("threading.Thread") as thread:
			self.cache.request(force=True, callback=old)
			self.cache.invalidate()
			self.cache.request(force=True, callback=fresh)
			self.cache._finish(0, {Channel.BETA: self.call})
			fresh.assert_not_called()
			self.assertEqual(thread.call_count, 2)
			self.cache._finish(1, {Channel.BETA: self.call})
		old.assert_called_once_with({})
		fresh.assert_called_once_with({Channel.BETA: self.call})

	def test_probe_failure_is_unknown_not_a_definitive_no_call(self):
		completed = mock.Mock()
		self.cache._probe = mock.Mock(side_effect=TimeoutError)
		self.cache._dispatch = lambda function, *args: function(*args)
		with mock.patch("threading.Thread") as thread:
			self.cache.request(force=True, callback=completed)
			thread.call_args.kwargs["target"]()
		completed.assert_called_once_with(None)
		self.assertFalse(self.cache._pending)
		self.assertIsNone(self.cache.available(Channel.BETA))
		self.assertIsNone(self.cache.available())

	def test_failed_refresh_keeps_previous_evidence_until_it_expires(self):
		self.cache._finish(0, {Channel.BETA: self.call})
		self.now = self.cache.REFRESH
		self.cache._finish(0, None)
		self.assertTrue(self.cache.available(Channel.BETA))
		self.assertFalse(self.cache.available(Channel.STABLE))
		self.now = self.cache.TTL
		self.assertIsNone(self.cache.available(Channel.BETA))
		self.assertEqual(self.cache.current(), {})

	def test_passive_refreshes_reuse_recent_evidence_and_never_overlap(self):
		with mock.patch("threading.Thread") as thread:
			self.cache.request()
			self.assertEqual(thread.call_count, 1)
			# The menu and dialog tick every 2 seconds while a probe is still running.
			for _tick in range(5):
				self.cache.request()
				self.cache.request(force=True)
			self.assertEqual(thread.call_count, 1)
			self.cache._finish(0, {})
			self.assertFalse(self.cache.available())
			for self.now in (2, 4, self.cache.REFRESH - 1):
				self.cache.request()
			self.assertEqual(thread.call_count, 1)
			self.now = self.cache.REFRESH
			self.cache.request()
			self.assertEqual(thread.call_count, 2)

	def test_forced_request_probes_despite_recent_evidence(self):
		self.cache._finish(0, {})
		completed = mock.Mock()
		with mock.patch("threading.Thread") as thread:
			self.cache.request(force=True, callback=completed)
			thread.assert_called_once()
		completed.assert_not_called()
		self.cache._finish(0, {Channel.BETA: self.call})
		completed.assert_called_once_with({Channel.BETA: self.call})

	def test_recent_passive_callback_reports_unknown_after_failure(self):
		self.cache._finish(0, None)
		completed = mock.Mock()
		with mock.patch("threading.Thread") as thread:
			self.cache.request(callback=completed)
			thread.assert_not_called()
		completed.assert_called_once_with(None)

	def test_probe_timeout_allows_for_powershell_compile(self):
		from globalPlugins.whatsappWebPlusCompanion import callAvailability

		self.assertGreaterEqual(callAvailability.PROBE_TIMEOUT, 20)
		self.assertGreaterEqual(self.cache.TTL, self.cache.REFRESH + callAvailability.PROBE_TIMEOUT)


if __name__ == "__main__":
	unittest.main()
