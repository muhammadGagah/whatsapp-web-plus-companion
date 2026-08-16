import unittest

from _path import installPackagePath

installPackagePath()

from globalPlugins.whatsappWebPlusCompanion.announcements import BrailleMessageQueue


class _Scheduled:
	def __init__(self, callback) -> None:
		self.callback = callback
		self.stopped = False

	def Stop(self) -> None:
		self.stopped = True


class BrailleMessageQueueTests(unittest.TestCase):
	def setUp(self) -> None:
		self.shown: list[str] = []
		self.scheduled: list[tuple[int, _Scheduled]] = []

		def schedule(delay: int, callback):
			call = _Scheduled(callback)
			self.scheduled.append((delay, call))
			return call

		self.queue = BrailleMessageQueue(self.shown.append, schedule, dwellMilliseconds=1000)

	def advance(self) -> None:
		_delay, call = self.scheduled.pop(0)
		call.callback()

	def test_burst_is_aggregated_in_order_after_current_message(self) -> None:
		self.queue.enqueue("one")
		self.queue.enqueue("two")
		self.queue.enqueue("three")

		self.assertEqual(self.shown, ["one"])
		self.assertEqual(self.scheduled[0][0], 1000)
		self.advance()

		self.assertEqual(self.shown, ["one", "two | three"])

	def test_overflow_is_visible_and_passive_log_cannot_evict_critical_output(self) -> None:
		queue = BrailleMessageQueue(
			self.shown.append,
			lambda delay, callback: self._schedule(delay, callback),
			dwellMilliseconds=1000,
			maxPendingMessages=2,
			overflowMessage=lambda count: f"Skipped: {count}",
		)
		queue.enqueue("current")
		queue.enqueue("alert", "alert")
		queue.enqueue("status", "status")
		queue.enqueue("passive", "message-log")
		self.advance()

		self.assertEqual(self.shown, ["current", "Skipped: 1 | alert | status"])

	def test_clear_pending_replaces_current_and_drops_tail(self) -> None:
		self.queue.enqueue("current")
		self.queue.enqueue("stale")
		timer = self.scheduled[0][1]
		self.queue.clearPending()

		self.assertTrue(timer.stopped)
		self.assertEqual(self.shown, ["current", "WhatsApp Web Plus announcement cleared."])

	def test_scoped_discard_replaces_current_and_keeps_other_source(self) -> None:
		self.queue.enqueue("current log", "message-log")
		self.queue.enqueue("status retained", "status")
		self.queue.enqueue("log stale", "message-log")
		self.queue.discardPending("message-log")

		self.assertEqual(
			self.shown,
			["current log", "WhatsApp Web Plus announcement cleared.", "status retained"],
		)

	def test_terminate_stops_timer_and_rejects_new_messages(self) -> None:
		self.queue.enqueue("current")
		timer = self.scheduled[0][1]
		self.queue.terminate()
		self.queue.enqueue("late")

		self.assertTrue(timer.stopped)
		self.assertEqual(self.shown, ["current"])

	def test_display_failure_is_retried_internally_without_rejecting_delivery(self) -> None:
		attempts = 0

		def show(message: str) -> None:
			nonlocal attempts
			attempts += 1
			if attempts == 1:
				raise RuntimeError("display unavailable")
			self.shown.append(message)

		queue = BrailleMessageQueue(show, lambda _delay, _callback: None)
		queue.enqueue("first")
		queue.enqueue("second")

		self.assertEqual(self.shown, ["first | second"])

	def test_timer_driven_display_failure_retries_acknowledged_batch(self) -> None:
		attempts = 0

		def show(message: str) -> None:
			nonlocal attempts
			attempts += 1
			if attempts == 2:
				raise RuntimeError("temporary failure")
			self.shown.append(message)

		queue = BrailleMessageQueue(
			show,
			lambda delay, callback: self._schedule(delay, callback),
			dwellMilliseconds=1000,
		)
		queue.enqueue("one")
		queue.enqueue("two")
		self.advance()
		self.assertEqual(self.scheduled[0][0], 250)
		self.advance()

		self.assertEqual(self.shown, ["one", "two"])

	def test_scheduler_failure_or_none_does_not_strand_queue(self) -> None:
		for scheduler in (
			lambda _delay, _callback: None,
			lambda _delay, _callback: (_ for _ in ()).throw(RuntimeError("unavailable")),
		):
			with self.subTest(scheduler=scheduler):
				shown: list[str] = []
				queue = BrailleMessageQueue(shown.append, scheduler)
				queue.enqueue("one")
				queue.enqueue("two")
				self.assertEqual(shown, ["one", "two"])

	def test_indefinite_mode_keeps_a_pannable_aggregate(self) -> None:
		queue = BrailleMessageQueue(
			self.shown.append,
			lambda _delay, _callback: self.fail("must not schedule"),
			dwellMilliseconds=None,
		)
		queue.enqueue("one")
		queue.enqueue("two")

		self.assertEqual(self.shown, ["one", "one | two"])

	def test_runtime_timeout_and_mode_changes_are_applied(self) -> None:
		dwell: list[int | None] = [1000]
		queue = BrailleMessageQueue(
			self.shown.append,
			lambda delay, callback: self._schedule(delay, callback),
			dwellMilliseconds=lambda: dwell[0],
		)
		queue.enqueue("one")
		queue.enqueue("two")
		firstTimer = self.scheduled[0][1]
		dwell[0] = 2000
		queue.enqueue("three")

		self.assertTrue(firstTimer.stopped)
		self.assertEqual(self.scheduled[-1][0], 2000)
		dwell[0] = None
		queue.enqueue("four")

		self.assertEqual(self.shown[-1], "one | two | three | four")

	def test_large_burst_is_split_into_character_bounded_batches(self) -> None:
		queue = BrailleMessageQueue(
			self.shown.append,
			lambda delay, callback: self._schedule(delay, callback),
			dwellMilliseconds=1000,
			maxBatchCharacters=4000,
		)
		for index in range(50):
			queue.enqueue(f"{index}:" + ("x" * 1790), "message-log")
		while self.scheduled:
			self.advance()

		self.assertTrue(all(len(message) <= 4000 for message in self.shown))
		self.assertEqual(sum(message.count(":") for message in self.shown), 50)

	def test_indefinite_aggregate_is_character_bounded_with_visible_overflow(self) -> None:
		queue = BrailleMessageQueue(
			self.shown.append,
			lambda _delay, _callback: self.fail("must not schedule"),
			dwellMilliseconds=None,
			maxBatchCharacters=4000,
			overflowMessage=lambda count: f"Skipped: {count}",
		)
		for index in range(50):
			queue.enqueue(f"{index}:" + ("x" * 1790), "message-log")

		self.assertLessEqual(len(self.shown[-1]), 4000)
		self.assertIn("Skipped:", self.shown[-1])

	def test_disabled_mode_discards_history_instead_of_replaying_it(self) -> None:
		enabled = [False]
		queue = BrailleMessageQueue(
			self.shown.append,
			lambda _delay, _callback: self.fail("must not schedule"),
			dwellMilliseconds=None,
			enabled=lambda: enabled[0],
		)
		queue.enqueue("suppressed while disabled")
		enabled[0] = True
		queue.enqueue("new after enabling")

		self.assertEqual(self.shown, ["new after enabling"])

	def test_display_retry_uses_bounded_exponential_backoff(self) -> None:
		fail = [True]

		def show(message: str) -> None:
			if fail[0]:
				raise RuntimeError("unavailable")
			self.shown.append(message)

		queue = BrailleMessageQueue(
			show,
			lambda delay, callback: self._schedule(delay, callback),
			dwellMilliseconds=1000,
		)
		queue.enqueue("one")
		self.assertEqual(self.scheduled[-1][0], 250)
		self.advance()
		self.assertEqual(self.scheduled[-1][0], 500)
		self.advance()
		self.assertEqual(self.scheduled[-1][0], 1000)
		self.advance()
		self.assertEqual(self.scheduled, [])
		fail[0] = False
		queue.enqueue("two")

		self.assertEqual(self.shown, ["one | two"])

	def _schedule(self, delay: int, callback) -> _Scheduled:
		call = _Scheduled(callback)
		self.scheduled.append((delay, call))
		return call


if __name__ == "__main__":
	unittest.main()
