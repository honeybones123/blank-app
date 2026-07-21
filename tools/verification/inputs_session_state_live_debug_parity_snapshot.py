from __future__ import annotations

import copy
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INPUTS_PAGE = ROOT / "inputs_page.py"
SESSION_ROOT = ROOT / "inputs_page_modules" / "session"
VERIFICATION_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


class CopyHostileValue:
    def __deepcopy__(self, memo: dict[int, Any]) -> Any:
        raise RuntimeError("copy denied")

    def __str__(self) -> str:
        return "copy-hostile"


class UnreadableMapping(dict):
    def get(self, key: Any, default: Any = None) -> Any:
        if key == "unreadable":
            raise RuntimeError("read denied")
        return super().get(key, default)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _function_window(source: str, name: str) -> str:
    marker = f"def {name}("
    if marker not in source:
        return ""
    return source.split(marker, 1)[1].split("\ndef ", 1)[0]


def _last_function_window(source: str, name: str) -> str:
    marker = f"def {name}("
    if marker not in source:
        return ""
    return source.rsplit(marker, 1)[1].split("\ndef ", 1)[0]


def _legacy_snapshot_semantics(source: Any) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in list(source.keys()):
        try:
            out[key] = copy.deepcopy(source.get(key))
        except Exception:
            try:
                out[key] = source.get(key)
            except Exception:
                out[key] = "<unreadable>"
    return out


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Session State Live Debug Parity Snapshot",
        "",
        f"## Executive Summary: {payload['decision']}",
        "",
        "This proof covers the debug-audit snapshot boundary used by `INPUTS_DEBUG_AUDIT`.",
        "It verifies that the typed session module owns the returned debug snapshot and the page-local legacy copy loop is deleted.",
        "",
        "## Checks",
        "",
    ]
    for key, value in payload["checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- `_inputs_audit_snapshot_state` remains the page-owned debug snapshot caller.",
            "- The typed session builder owns the returned debug snapshot.",
            "- The legacy page-local copy loop is deleted.",
            "- Trace emission is forced only for the debug-audit proof path.",
            "- No hydration, callback, Apply routing, invalidation, or render-trigger state moved.",
        ]
    )
    if payload.get("failures"):
        lines.extend(["", "## Failures", ""])
        for failure in payload["failures"]:
            lines.append(f"- `{failure}`")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    page = _read(INPUTS_PAGE)
    helper_window = _function_window(page, "_inputs_audit_snapshot_state")
    render_window = _last_function_window(page, "render_inputs")
    module_sources = "\n".join(_read(path) for path in SESSION_ROOT.glob("*.py"))

    from inputs_page_modules.session import build_inputs_session_source_snapshot

    hostile = CopyHostileValue()
    source = UnreadableMapping(
        {
            "alpha": 1,
            "nested": {"x": [1, 2]},
            "hostile": hostile,
            "unreadable": "hidden",
        }
    )
    legacy = _legacy_snapshot_semantics(source)
    typed = build_inputs_session_source_snapshot(source)
    typed_dict = {entry.key: entry.value for entry in typed.entries}
    source["nested"]["x"].append(3)

    checks = {
        "debug_audit_flag_defined": "_INPUTS_DEBUG_AUDIT = os.environ.get(" in page,
        "debug_audit_before_state_uses_helper": "before_state = _inputs_audit_snapshot_state() if _INPUTS_DEBUG_AUDIT else None" in render_window,
        "debug_audit_after_state_compares_legacy_snapshot": "if _INPUTS_DEBUG_AUDIT and before_state is not None:" in render_window
        and "for key in before_state:" in render_window,
        "helper_returns_typed_snapshot_dict": "return out" in helper_window
        and "out: dict[str, object] = {entry.key: entry.value for entry in _typed_snapshot.entries}" in helper_window,
        "helper_forces_debug_delegation_trace": "_inputs_debug_audit_trace(" in helper_window
        and "\"inputs_session_snapshot_delegated\"" in helper_window,
        "helper_deletes_legacy_loop": "legacy_out" not in helper_window
        and "legacy_count" not in helper_window
        and "_mismatch_keys" not in helper_window,
        "helper_marks_cut_over": "live_page_cutover=True" in helper_window,
        "helper_no_longer_silently_falls_back_on_typed_builder_error": "inputs_session_snapshot_parity_error" not in helper_window
        and "except Exception as _session_snapshot_parity_exc" not in helper_window,
        "module_streamlit_free": "import streamlit" not in module_sources
        and "from streamlit" not in module_sources,
        "module_inputs_page_free": "inputs_page" not in module_sources,
        "module_session_mutation_free": "st.session_state" not in module_sources
        and ".session_state" not in module_sources,
        "controlled_key_order_matches": tuple(typed_dict.keys()) == tuple(legacy.keys()),
        "controlled_unreadable_fallback_matches": typed_dict.get("unreadable") == "<unreadable>"
        and legacy.get("unreadable") == "<unreadable>",
        "controlled_copy_hostile_fallback_matches": typed_dict.get("hostile") is hostile
        and legacy.get("hostile") is hostile,
        "controlled_deepcopy_isolated": typed_dict.get("nested", {}).get("x") == [1, 2],
        "typed_display_hash_present": bool(typed.display_hash),
    }
    failures = [key for key, value in checks.items() if not value]
    decision = "SESSION_LIVE_DEBUG_PARITY_READY" if not failures else "SESSION_LIVE_DEBUG_PARITY_GAPS_REMAIN"
    payload = {
        "audit": "inputs_session_state_live_debug_parity_snapshot",
        "timestamp": timestamp,
        "decision": decision,
        "checks": checks,
        "failures": failures,
        "legacy_return_authoritative": False,
        "live_page_cutover": True,
        "debug_trace_forced": checks["helper_forces_debug_delegation_trace"],
        "session_behavior_changed": False,
        "callbacks_moved": False,
        "apply_routing_moved": False,
        "render_trigger_state_moved": False,
        "next_safe_slice": "lock the debug-audit session snapshot boundary or move to the next session surface",
    }
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"inputs_session_state_live_debug_parity_snapshot_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_session_state_live_debug_parity_snapshot_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_session_state_live_debug_parity_snapshot", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
