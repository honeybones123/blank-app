"""Application-owned identity and runtime for post-Apply cleanup acceptance."""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Mapping

from inputs_application.state_projection import build_guidance_state_snapshot
from state_and_helpers import RESULT_KEYS, SHARED_DEFAULTS


class AuditedFingerprintSet(set[tuple]):
    """Shared acceptance history with lightweight audit metadata."""

    def __init__(self) -> None:
        super().__init__()
        self.add_count = 0
        self.clear_count = 0
        self.last_event: dict[str, object] = {}
        self.last_added: tuple | None = None

    @staticmethod
    def _caller() -> str:
        frame = inspect.currentframe()
        caller = frame.f_back.f_back if frame and frame.f_back else None
        if caller is None:
            return ""
        return f"{caller.f_globals.get('__name__', '')}:{caller.f_code.co_name}"

    def add(self, element: tuple) -> None:
        self.add_count += 1
        self.last_added = element
        self.last_event = {"op": "add", "caller": self._caller()}
        super().add(element)

    def clear(self) -> None:
        self.clear_count += 1
        self.last_event = {"op": "clear", "caller": self._caller()}
        super().clear()


DESIGN_GUIDE_POST_CLEANUP_ACCEPTED_FPS = AuditedFingerprintSet()


@dataclass(frozen=True)
class LocalCleanupAcceptanceRuntime:
    expected_fingerprint: Callable[[], Any]
    accepted_fingerprints: Callable[[], set[Any]]


_ACCEPTANCE_KEYS = (
    "b", "D", "bot1_count", "db_bot_1", "bot2_count", "db_bot_2",
    "bot_row_count", "bot_row_1_bars", "bot_row_1_dia", "bot_row_2_bars",
    "bot_row_2_dia", "lig_d", "lig_legs", "s_lig",
)


def _canonical_acceptance_value(value: Any) -> str:
    if isinstance(value, bool) or value is None:
        return str(value)
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return str(value)
    if not number.is_finite():
        return str(value)
    normalized = format(number.normalize(), "f")
    return "0" if normalized in {"-0", ""} else normalized


def build_local_cleanup_acceptance_fingerprint(
    state: Mapping[str, Any] | None,
) -> tuple[tuple[str, str], ...]:
    snapshot = build_guidance_state_snapshot(
        dict(state or {}), result_keys=RESULT_KEYS, shared_defaults=SHARED_DEFAULTS
    )
    try:
        second_row_count = max(
            int(float(snapshot.get("bot2_count") or 0)),
            int(float(snapshot.get("bot_row_2_bars") or 0)),
        )
    except (TypeError, ValueError):
        second_row_count = 0
    if second_row_count <= 0:
        snapshot["db_bot_2"] = 0
        snapshot["bot_row_2_dia"] = 0
    return tuple(
        (key, _canonical_acceptance_value(snapshot.get(key)))
        for key in _ACCEPTANCE_KEYS
    )


def local_cleanup_post_apply_acceptance_matches(
    state: Mapping[str, Any] | None,
    *, expected_fingerprint: Any, accepted_fingerprints: set[Any] | None = None,
) -> bool:
    try:
        current = build_local_cleanup_acceptance_fingerprint(state)
        return bool(
            (expected_fingerprint is not None and expected_fingerprint == current)
            or (accepted_fingerprints is not None and current in accepted_fingerprints)
        )
    except Exception:
        return False


def local_cleanup_post_apply_acceptance_matches_with_runtime(
    state: Mapping[str, Any] | None, *, runtime: LocalCleanupAcceptanceRuntime,
) -> bool:
    return local_cleanup_post_apply_acceptance_matches(
        state,
        expected_fingerprint=runtime.expected_fingerprint(),
        accepted_fingerprints=runtime.accepted_fingerprints(),
    )


__all__ = [
    "AuditedFingerprintSet", "DESIGN_GUIDE_POST_CLEANUP_ACCEPTED_FPS",
    "LocalCleanupAcceptanceRuntime", "build_local_cleanup_acceptance_fingerprint",
    "local_cleanup_post_apply_acceptance_matches",
    "local_cleanup_post_apply_acceptance_matches_with_runtime",
]
