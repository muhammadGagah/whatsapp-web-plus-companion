import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, TypeVar


T = TypeVar("T")


class CancellationEvent:
	"""Event with an atomic check-and-submit boundary for external side effects."""

	def __init__(self) -> None:
		super().__init__()
		self._event = threading.Event()
		self._submissionLock = threading.Lock()

	def clear(self) -> None:
		with self._submissionLock:
			self._event.clear()

	def set(self) -> None:
		self._event.set()

	def is_set(self) -> bool:
		return self._event.is_set()

	def wait(self, timeout: float | None = None) -> bool:
		return self._event.wait(timeout)

	def submitUnlessSet(self, action: Callable[[], T]) -> tuple[bool, T | None]:
		with self._submissionLock:
			if self._event.is_set():
				return False, None
		return True, action()


class Channel(StrEnum):
	STABLE = "stable"
	BETA = "beta"


class OperationState(StrEnum):
	IDLE = "idle"
	PREPARING_LAUNCH = "preparingLaunch"
	WAITING_FOR_ENDPOINT = "waitingForEndpoint"
	DISCOVERING_TARGET = "discoveringTarget"
	ATTACHING = "attaching"
	INJECTING = "injecting"
	VERIFYING_HEALTH = "verifyingHealth"
	ATTACHED = "attached"
	RECONNECTING = "reconnecting"
	STOPPING = "stopping"
	FAILED = "failed"


@dataclass(frozen=True, slots=True)
class OperationResult:
	ok: bool
	code: str
	messageKey: str
	values: dict[str, Any]


class LoaderError(RuntimeError):
	def __init__(
		self,
		code: str,
		safeDetail: str = "",
		values: Mapping[str, object] | None = None,
	) -> None:
		super().__init__(code)
		self.code = code
		self.safeDetail = safeDetail
		self.values: Mapping[str, object] = dict(values or {})
