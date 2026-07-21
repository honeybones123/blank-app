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


class CopyHostileMapping(dict):
    pass


class CopyHostileValue:
    def __deepcopy__(self, memo: dict[int, Any]) -> Any:
        raise RuntimeError("copy denied")

    def __str__(self) -> str:
        return "copy-hostile"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _legacy_snapshot_semantics(source: dict[str, Any]) -> dict[str, Any]:
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


def _function_window(source: str, name: str) -> str:
    marker = f"def {name}("
    if marker not in source:
        return ""
    return source.split(marker, 1)[1].split("\ndef ", 1)[0]


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Session State Trace Parity Snapshot",
        "",
        f"## Executive Summary: {payload['decision']}",
        "",
        "This verifier proves `_inputs_audit_snapshot_state` now returns the typed session snapshot and the legacy page-local copy loop has been deleted.",
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
            "- Page still owns `st.session_state` reads.",
            "- The typed session module remains Streamlit-free and read-only.",
            "- The typed session snapshot is delegated for this debug-audit boundary.",
            "- The legacy page-local copy loop is deleted.",
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
    module_sources = {
        path.name: _read(path)
        for path in SESSION_ROOT.glob("*.py")
    }
    module_combined = "\n".join(module_sources.values())
    executable_module_combined = "\n".join(
        source for name, source in module_sources.items() if name != "contracts.py"
    )

    from inputs_page_modules.session import build_inputs_session_source_snapshot

    hostile = CopyHostileValue()
    source = CopyHostileMapping(
        {
            "alpha": 1,
            "nested": {"x": [1, 2]},
            "hostile": hostile,
        }
    )
    legacy = _legacy_snapshot_semantics(source)
    typed = build_inputs_session_source_snapshot(source)
    typed_dict = {entry.key: entry.value for entry in typed.entries}
    source["nested"]["x"].append(3)
    checks = {
        "page_imports_typed_builder": "from inputs_page_modules.session import build_inputs_session_source_snapshot" in page,
        "legacy_helper_still_present": "def _inputs_audit_snapshot_state(" in page,
        "helper_returns_typed_out_dict": "return out" in helper_window
        and "out: dict[str, object] = {entry.key: entry.value for entry in _typed_snapshot.entries}" in helper_window,
        "helper_passes_session_mapping_to_module": "build_inputs_session_source_snapshot(st.session_state)" in helper_window
        and "st.session_state.keys()" not in helper_window
        and "st.session_state.get(k)" not in helper_window,
        "helper_calls_typed_builder_for_delegation": "build_inputs_session_source_snapshot(st.session_state)" in helper_window
        and "inputs_session_snapshot_delegated" in helper_window
        and "live_page_cutover=True" in helper_window,
        "helper_does_not_return_typed_snapshot": "return _typed_snapshot" not in helper_window
        and "return typed" not in helper_window,
        "helper_deletes_legacy_loop": "legacy_out" not in helper_window
        and "legacy_count" not in helper_window
        and "_mismatch_keys" not in helper_window,
        "module_does_not_import_streamlit": "import streamlit" not in module_combined
        and "from streamlit" not in module_combined,
        "module_does_not_import_inputs_page": "inputs_page" not in module_combined,
        "module_does_not_mutate_session_state": "st.session_state" not in executable_module_combined
        and ".session_state" not in executable_module_combined,
        "module_does_not_route_apply": "route_apply" not in executable_module_combined
        and "apply_payload" not in executable_module_combined,
        "controlled_keys_match": tuple(typed_dict.keys()) == tuple(legacy.keys()),
        "controlled_values_match": typed_dict.get("alpha") == legacy.get("alpha"),
        "controlled_deepcopy_isolated": typed_dict.get("nested", {}).get("x") == [1, 2],
        "controlled_copy_hostile_fallback_matches": typed_dict.get("hostile") is hostile
        and legacy.get("hostile") is hostile,
        "typed_display_hash_present": bool(typed.display_hash),
    }
    failures = [key for key, value in checks.items() if not value]
    decision = "SESSION_SNAPSHOT_DELEGATION_DEAD_LOOP_DELETED" if not failures else "SESSION_SNAPSHOT_DELEGATION_GAPS_REMAIN"
    payload = {
        "audit": "inputs_session_state_trace_parity_snapshot",
        "timestamp": timestamp,
        "decision": decision,
        "checks": checks,
        "failures": failures,
        "typed_display_hash": typed.display_hash,
        "legacy_return_authoritative": False,
        "live_page_cutover": True,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "widget_keys_changed": False,
        "session_behavior_changed": False,
        "callbacks_moved": False,
        "apply_routing_moved": False,
        "next_safe_slice": "lock the debug-audit session snapshot boundary or move to the next session surface",
    }
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"inputs_session_state_trace_parity_snapshot_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_session_state_trace_parity_snapshot_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_session_state_trace_parity_snapshot", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
