from __future__ import annotations

from collections import deque
from collections.abc import Callable
from typing import Protocol


class ScheduledCall(Protocol):
	def Stop(self) -> None: ...


ScheduleLater = Callable[[int, Callable[[], None]], ScheduledCall | None]
DwellProvider = Callable[[], int | None]
OverflowMessage = Callable[[int], str]
ClearedMessage = Callable[[], str]
EnabledProvider = Callable[[], bool]
_RETRY_DELAY_MS = 250
_MAX_RETRIES = 3
_PASSIVE_SOURCE = "message-log"


def _defaultOverflowMessage(count: int) -> str:
	return f"Skipped WhatsApp Web Plus braille announcements: {count}."


def _defaultClearedMessage() -> str:
	return "WhatsApp Web Plus announcement cleared."


class BrailleMessageQueue:
	"""Deliver bounded, pannable braille batches without overwriting a burst."""

	def __init__(
		self,
		showMessage: Callable[[str], None],
		scheduleLater: ScheduleLater,
		*,
		dwellMilliseconds: int | None | DwellProvider = 2500,
		maxPendingMessages: int = 50,
		maxBatchCharacters: int = 8000,
		overflowMessage: OverflowMessage | None = None,
		clearedMessage: ClearedMessage | None = None,
		enabled: bool | EnabledProvider = True,
	) -> None:
		super().__init__()
		self._showMessage = showMessage
		self._scheduleLater = scheduleLater
		if callable(dwellMilliseconds):
			self._getDwellMilliseconds = dwellMilliseconds
		else:
			self._getDwellMilliseconds = lambda: dwellMilliseconds
		self._maxPendingMessages = max(2, maxPendingMessages)
		self._maxBatchCharacters = max(256, maxBatchCharacters)
		self._overflowMessage: OverflowMessage = overflowMessage or _defaultOverflowMessage
		self._clearedMessage: ClearedMessage = clearedMessage or _defaultClearedMessage
		if callable(enabled):
			self._getEnabled = enabled
		else:
			self._getEnabled = lambda: enabled
		self._pending: deque[tuple[str, str]] = deque()
		self._pendingSkipped = 0
		self._current: list[tuple[str, str]] = []
		self._nativeEntries: deque[tuple[str, str]] = deque()
		self._nativeSkipped = 0
		self._serializing: bool | None = None
		self._activeDwell: int | None = None
		self._timer: ScheduledCall | None = None
		self._waiting = False
		self._retryCount = 0
		self._disposed = False

	def enqueue(self, message: str, source: str = "") -> None:
		if self._disposed or not message:
			return
		if not self._effectiveEnabled():
			self._disable()
			return
		dwell = self._effectiveDwell()
		self._applyMode(dwell)
		entry = (message, source)
		if not self._serializing:
			self._nativeSkipped = self._appendBounded(
				self._nativeEntries,
				entry,
				self._nativeSkipped,
			)
			self._showNativeAggregate()
			return
		self._pendingSkipped = self._appendBounded(self._pending, entry, self._pendingSkipped)
		if not self._waiting:
			self._showPendingBatch()

	def clearPending(self) -> None:
		"""Discard queued and displayed bridge messages across a context boundary."""

		hadOutput = bool(self._current or self._nativeEntries)
		self._stopTimer()
		self._pending.clear()
		self._pendingSkipped = 0
		self._current.clear()
		self._nativeEntries.clear()
		self._nativeSkipped = 0
		self._waiting = False
		if hadOutput:
			_ = self._safeShow(self._clearedMessage())
		self._retryCount = 0

	def discardPending(self, source: str) -> None:
		"""Remove one invalidated source, including its currently displayed text."""

		self._pending = deque(entry for entry in self._pending if entry[1] != source)
		if not self._serializing:
			before = len(self._nativeEntries)
			self._nativeEntries = deque(entry for entry in self._nativeEntries if entry[1] != source)
			if len(self._nativeEntries) != before:
				self._showNativeAggregate()
			return
		retainedCurrent = [entry for entry in self._current if entry[1] != source]
		if len(retainedCurrent) == len(self._current):
			return
		self._stopTimer()
		self._current = retainedCurrent
		if self._current:
			_ = self._safeShow(self._render(self._current, 0))
			self._scheduleAdvance(self._effectiveDwell())
		else:
			_ = self._safeShow(self._clearedMessage())
			self._waiting = False
			self._showPendingBatch()

	def terminate(self) -> None:
		self._disposed = True
		self._stopTimer()
		self._pending.clear()
		self._current.clear()
		self._nativeEntries.clear()
		self._waiting = False
		self._retryCount = 0

	def _effectiveDwell(self) -> int | None:
		try:
			dwell = self._getDwellMilliseconds()
		except (KeyError, TypeError, RuntimeError):
			return 4000
		if dwell is None:
			return None
		if isinstance(dwell, bool):
			return 4000
		return max(1000, int(dwell))

	def _effectiveEnabled(self) -> bool:
		try:
			return bool(self._getEnabled())
		except (KeyError, TypeError, RuntimeError):
			return True

	def _disable(self) -> None:
		self._stopTimer()
		self._pending.clear()
		self._pendingSkipped = 0
		self._current.clear()
		self._nativeEntries.clear()
		self._nativeSkipped = 0
		self._serializing = None
		self._activeDwell = None
		self._waiting = False
		self._retryCount = 0

	def _applyMode(self, dwell: int | None) -> None:
		serializing = dwell is not None
		if self._serializing is None:
			self._serializing = serializing
			self._activeDwell = dwell
			return
		if self._serializing and not serializing:
			entries = [*self._current, *self._pending]
			self._stopTimer()
			self._current.clear()
			self._pending.clear()
			self._nativeEntries.clear()
			self._nativeSkipped = self._pendingSkipped
			self._pendingSkipped = 0
			for entry in entries:
				self._nativeSkipped = self._appendBounded(
					self._nativeEntries,
					entry,
					self._nativeSkipped,
				)
			self._waiting = False
		elif not self._serializing and serializing:
			self._nativeEntries.clear()
			self._nativeSkipped = 0
			self._waiting = False
		elif serializing and self._waiting and dwell != self._activeDwell:
			self._stopTimer()
			self._scheduleAdvance(dwell)
		self._serializing = serializing
		self._activeDwell = dwell

	def _appendBounded(
		self,
		entries: deque[tuple[str, str]],
		entry: tuple[str, str],
		skipped: int,
	) -> int:
		if len(entries) < self._maxPendingMessages:
			entries.append(entry)
			return skipped
		items = list(entries)
		passiveIndex = next((index for index, item in enumerate(items) if item[1] == _PASSIVE_SOURCE), None)
		if entry[1] == _PASSIVE_SOURCE and passiveIndex is None:
			return skipped + 1
		removeIndex = passiveIndex if passiveIndex is not None else 0
		_ = items.pop(removeIndex)
		items.append(entry)
		entries.clear()
		entries.extend(items)
		return skipped + 1

	def _showNativeAggregate(self) -> None:
		if self._disposed:
			return
		self._stopTimer()
		self._trimNativeToCharacterLimit()
		if self._safeShow(self._render(self._nativeEntries, self._nativeSkipped)):
			self._retryCount = 0
		else:
			self._scheduleNativeRetry()

	def _showPendingBatch(self) -> None:
		if self._disposed or not self._pending:
			self._waiting = False
			return
		entries: list[tuple[str, str]] = []
		skipped = self._pendingSkipped
		characterCount = len(self._overflowMessage(skipped)) if skipped else 0
		while self._pending:
			entry = self._pending[0]
			additionalCharacters = len(entry[0]) + (3 if entries else 0)
			if entries and characterCount + additionalCharacters > self._maxBatchCharacters:
				break
			entries.append(self._pending.popleft())
			characterCount += additionalCharacters
		self._pendingSkipped = 0
		if not self._safeShow(self._render(entries, skipped)):
			for entry in reversed(entries):
				self._pending.appendleft(entry)
			self._pendingSkipped += skipped
			self._scheduleRetry()
			return
		self._retryCount = 0
		self._current = entries
		self._scheduleAdvance(self._effectiveDwell())

	def _scheduleAdvance(self, dwell: int | None) -> None:
		if dwell is None:
			self._waiting = False
			return
		self._activeDwell = dwell
		self._waiting = self._schedule(dwell, self._advance)
		if not self._waiting:
			self._current.clear()
			if self._pending:
				self._showPendingBatch()

	def _scheduleRetry(self) -> None:
		if self._retryCount >= _MAX_RETRIES:
			self._waiting = False
			return
		delay = _RETRY_DELAY_MS * (2**self._retryCount)
		self._retryCount += 1
		self._waiting = self._schedule(delay, self._retry)

	def _scheduleNativeRetry(self) -> None:
		if self._retryCount >= _MAX_RETRIES:
			return
		delay = _RETRY_DELAY_MS * (2**self._retryCount)
		self._retryCount += 1
		_ = self._schedule(delay, self._retryNative)

	def _schedule(self, delay: int, callback: Callable[[], None]) -> bool:
		try:
			timer = self._scheduleLater(delay, callback)
		except (RuntimeError, TypeError):
			self._timer = None
			return False
		if timer is None:
			self._timer = None
			return False
		self._timer = timer
		return True

	def _retry(self) -> None:
		self._timer = None
		self._waiting = False
		self._showPendingBatch()

	def _retryNative(self) -> None:
		self._timer = None
		if not self._effectiveEnabled():
			self._disable()
			return
		self._showNativeAggregate()

	def _advance(self) -> None:
		self._timer = None
		self._waiting = False
		self._current.clear()
		self._showPendingBatch()

	def _stopTimer(self) -> None:
		timer = self._timer
		self._timer = None
		if timer is not None:
			try:
				timer.Stop()
			except (AttributeError, RuntimeError):
				pass

	def _safeShow(self, message: str) -> bool:
		try:
			self._showMessage(message)
		except Exception:
			return False
		return True

	def _trimNativeToCharacterLimit(self) -> None:
		while (
			self._nativeEntries
			and len(self._render(self._nativeEntries, self._nativeSkipped)) > self._maxBatchCharacters
		):
			items = list(self._nativeEntries)
			passiveIndex = next(
				(index for index, item in enumerate(items) if item[1] == _PASSIVE_SOURCE),
				None,
			)
			removeIndex = passiveIndex if passiveIndex is not None else 0
			_ = items.pop(removeIndex)
			self._nativeEntries.clear()
			self._nativeEntries.extend(items)
			self._nativeSkipped += 1

	def _render(self, entries: list[tuple[str, str]] | deque[tuple[str, str]], skipped: int) -> str:
		parts: list[str] = []
		if skipped:
			parts.append(self._overflowMessage(skipped))
		parts.extend(message for message, _source in entries)
		return " | ".join(parts)
