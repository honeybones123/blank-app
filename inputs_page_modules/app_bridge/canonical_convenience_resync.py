"""Canonical convenience-field resync coordination for app bridge commit paths."""

from __future__ import annotations

from typing import Any


_CANONICAL_CONVENIENCE_RESYNC_DEPENDENCIES: tuple[str, ...] = (
    "_CANONICAL_CONVENIENCE_META_KEY",
    "_agent_debug_log",
    "_build_canonical_design_state_pack",
    "_convenience_scalar_differs",
    "_guidance_state_snapshot",
    "_shared_state_snapshot",
    "set_shared",
    "st",
)


def bind_canonical_convenience_resync_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _CANONICAL_CONVENIENCE_RESYNC_DEPENDENCIES
            if name in namespace
        }
    )


def _canonical_convenience_fields_from_state(state: dict) -> dict:
    """
    Pure summary counters aligned with ``bot_rows_resolved`` / ``top_rows_resolved`` / canonical pack.
    Used to refresh shared convenience fields after canonical commits or beam load.

    Fail-soft: never raises - intermediate/malformed reo states return only metadata under
    ``_CANONICAL_CONVENIENCE_META_KEY`` so callers can skip ``set_shared`` without crashing render/autopersist.
    """

    def _fail(reason: str, detail: str = "") -> dict:
        return {
            _CANONICAL_CONVENIENCE_META_KEY: {
                "canonical_convenience_resync_valid": False,
                "canonical_convenience_resync_reason": str(reason),
                "detail": str(detail)[:400],
            },
        }

    try:
        pack = _build_canonical_design_state_pack(_guidance_state_snapshot(dict(state or {})))
    except AssertionError as exc:
        _msg = str(exc).lower()
        if "no bars resolved" in _msg:
            return _fail("no_bars_resolved", str(exc))
        return _fail("canonical_pack_failed", str(exc))
    except (ValueError, TypeError) as exc:
        return _fail("canonical_pack_failed", str(exc))
    except Exception as exc:
        return _fail("canonical_pack_failed", str(exc))

    try:
        bot_rows = list(pack.get("bot_rows_resolved") or [])
        top_rows = list(pack.get("top_rows_resolved") or [])
        total_bot = int(sum(int((r or {}).get("bar_count_resolved", 0) or 0) for r in bot_rows))
        total_top = int(sum(int((r or {}).get("bar_count_resolved", 0) or 0) for r in top_rows))
        primary_bot = next((r for r in bot_rows if (r or {}).get("active")), None)
        primary_top = next((r for r in top_rows if (r or {}).get("active")), None)

        def _entry_row(row: dict | None) -> float:
            if not row:
                return 0.0
            if str(row.get("mode", "Count") or "Count") == "Count":
                return float(int(row.get("bar_count_resolved", 0) or 0))
            return float(row.get("spacing_resolved", 0.0) or 0.0)

        db_bot = float(pack.get("db_bot", 0.0) or 0.0)
        db_top = float(pack.get("db_top", 0.0) or 0.0)
        s_bot = float((primary_bot or {}).get("spacing_resolved", 0.0) or 0.0)
        s_top = float((primary_top or {}).get("spacing_resolved", 0.0) or 0.0)
        out = {
            "nb_bot": total_bot,
            "nb_top": total_top,
            "total_bot_bars": total_bot,
            "total_top_bars": total_top,
            "db_bot": db_bot,
            "db_top": db_top,
            "s_bot": s_bot,
            "s_top": s_top,
            "bot_entry": _entry_row(primary_bot),
            "top_entry": _entry_row(primary_top),
            "Ast_bot": float(pack.get("Ast_bot", 0.0) or 0.0),
            "Ast_top": float(pack.get("Ast_top", 0.0) or 0.0),
            _CANONICAL_CONVENIENCE_META_KEY: {
                "canonical_convenience_resync_valid": True,
                "canonical_convenience_resync_reason": "ok",
            },
        }
        return out
    except Exception as exc:
        return _fail("canonical_pack_failed", str(exc))


def _apply_canonical_convenience_resync_to_shared(*, source: str) -> dict:
    """
    Rewrite convenience/summary counters from the canonical resolved layout into shared state.
    Safe on write/commit paths only (not for render-only summary).

    Best-effort only: invalid or empty convenience payloads skip all ``set_shared`` writes and never raise.
    """
    snap = _shared_state_snapshot()
    desired = dict(_canonical_convenience_fields_from_state(snap) or {})
    meta = dict(desired.pop(_CANONICAL_CONVENIENCE_META_KEY, {}) or {})
    valid = bool(meta.get("canonical_convenience_resync_valid"))
    reason = str(meta.get("canonical_convenience_resync_reason") or "")

    def _mark_session(**kwargs: object) -> None:
        try:
            for mk, mv in kwargs.items():
                st.session_state[str(mk)] = mv
        except Exception:
            pass

    _mark_session(
        canonical_convenience_resync_source=str(source),
        canonical_convenience_resync_valid=valid,
        canonical_convenience_resync_reason=reason or ("ok" if valid else "unknown"),
    )

    if not valid or not desired:
        skip_reason = reason if not valid else "empty_convenience_fields"
        _mark_session(
            canonical_convenience_resync_skipped=True,
            canonical_convenience_resync_skip_reason=skip_reason,
            canonical_convenience_resync_applied=False,
            canonical_convenience_fields_updated=[],
            convenience_field_drift_detected=False,
        )
        try:
            _agent_debug_log(
                "canonical_convenience_resync_skipped",
                {
                    "source": str(source),
                    "valid": False,
                    "reason": skip_reason,
                    "meta_detail": str(meta.get("detail") or "")[:400],
                },
                location="inputs_page.py:_apply_canonical_convenience_resync_to_shared",
                hypothesis_id="H_CANON_CONVENIENCE_SKIP",
            )
        except Exception:
            pass
        return {
            "canonical_convenience_resync_applied": False,
            "canonical_convenience_resync_skipped": True,
            "canonical_convenience_resync_skip_reason": skip_reason,
            "canonical_convenience_fields_updated": [],
            "convenience_field_drift_detected": False,
            "convenience_drift_keys": [],
        }

    drift_keys: list[str] = []
    updated_keys: list[str] = []
    for key, val in desired.items():
        cur = snap.get(key)
        if _convenience_scalar_differs(cur, val):
            drift_keys.append(str(key))
        set_shared(key, val, source=source)
        updated_keys.append(str(key))
    _mark_session(
        canonical_convenience_resync_skipped=False,
        canonical_convenience_resync_skip_reason="",
        canonical_convenience_resync_applied=True,
        canonical_convenience_fields_updated=list(updated_keys),
        convenience_field_drift_detected=bool(drift_keys),
    )
    return {
        "canonical_convenience_resync_applied": True,
        "canonical_convenience_resync_skipped": False,
        "canonical_convenience_resync_skip_reason": "",
        "canonical_convenience_fields_updated": updated_keys,
        "convenience_field_drift_detected": bool(drift_keys),
        "convenience_drift_keys": drift_keys,
    }


__all__ = [
    "bind_canonical_convenience_resync_dependencies",
    "_canonical_convenience_fields_from_state",
    "_apply_canonical_convenience_resync_to_shared",
]
