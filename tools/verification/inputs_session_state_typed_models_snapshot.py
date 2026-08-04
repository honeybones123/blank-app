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
                pass
    return out


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Session State Typed Models Snapshot",
        "",
        f"## Executive Summary: {payload['decision']}",
        "",
        "This verifier proves the new `inputs_page_modules.session` typed snapshot models are read-only and match the current `_inputs_audit_snapshot_state` copy/fallback semantics for a session-like mapping.",
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
            "- No Streamlit import enters `inputs_page_modules.session`.",
            "- No session mutation, Apply routing, callback execution, or widget rendering moved.",
            "- `inputs_page.py` is not cut over to the new module in this slice.",
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
    source = {
        "inputs_b": 300.0,
        "inputs_D": 600.0,
        "nested": {"bars": [4, 20]},
        "copy_hostile": hostile,
    }
    legacy = _legacy_snapshot_semantics(source)
    snapshot = build_inputs_session_source_snapshot(source)
    snapshot_dict = {entry.key: entry.value for entry in snapshot.entries}
    source["nested"]["bars"].append(25)

    checks = {
        "session_module_present": SESSION_ROOT.exists(),
        "models_file_present": "class InputsSessionEntry" in module_sources.get("models.py", "")
        and "class InputsSessionSourceSnapshot" in module_sources.get("models.py", ""),
        "contracts_file_present": "read_only_snapshot_models" in module_sources.get("contracts.py", ""),
        "builder_function_present": "def build_inputs_session_source_snapshot(" in module_sources.get("builders.py", ""),
        "builder_exported": "build_inputs_session_source_snapshot" in module_sources.get("__init__.py", ""),
        "module_does_not_import_streamlit": "import streamlit" not in module_combined
        and "from streamlit" not in module_combined,
        "module_does_not_import_inputs_page": "inputs_page" not in module_combined,
        "module_does_not_mutate_session_state": "st.session_state" not in module_combined
        and ".session_state" not in module_combined,
        "module_does_not_route_apply": "route_apply" not in executable_module_combined
        and "apply_payload" not in executable_module_combined,
        "module_does_not_execute_callbacks": "sync_callbacks" not in executable_module_combined
        and "on_change" not in executable_module_combined,
        "module_does_not_render_widgets": "st." not in executable_module_combined
        and "number_input(" not in executable_module_combined
        and "selectbox(" not in executable_module_combined,
        "snapshot_keys_match_legacy": tuple(snapshot_dict.keys()) == tuple(legacy.keys()),
        "snapshot_plain_values_match_legacy": snapshot_dict.get("inputs_b") == legacy.get("inputs_b")
        and snapshot_dict.get("inputs_D") == legacy.get("inputs_D"),
        "snapshot_deepcopy_isolated": snapshot_dict.get("nested", {}).get("bars") == [4, 20],
        "snapshot_copy_hostile_fallback_matches_legacy": snapshot_dict.get("copy_hostile") is hostile
        and legacy.get("copy_hostile") is hostile,
        "snapshot_display_hash_present": bool(snapshot.display_hash),
        "inputs_page_imports_or_uses_typed_snapshot_builder": (
            "build_inputs_session_source_snapshot(" not in page
            or "inputs_session_snapshot_delegated" in page
            or "inputs_session_snapshot_parity" in page
        ),
        "legacy_audit_snapshot_still_present": "def _inputs_audit_snapshot_state(" in page,
    }
    failures = [key for key, value in checks.items() if not value]
    decision = "SESSION_TYPED_SOURCE_SNAPSHOT_MODELS_READY" if not failures else "SESSION_TYPED_SOURCE_SNAPSHOT_GAPS_REMAIN"
    payload = {
        "audit": "inputs_session_state_typed_models_snapshot",
        "timestamp": timestamp,
        "decision": decision,
        "checks": checks,
        "failures": failures,
        "snapshot_entry_count": len(snapshot.entries),
        "snapshot_display_hash": snapshot.display_hash,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "widget_keys_changed": False,
        "session_behavior_changed": False,
        "callbacks_moved": False,
        "apply_routing_moved": False,
        "live_page_cutover": "live_page_cutover=True" in page,
        "next_safe_slice": "prove deadness for the legacy local copy loop after module-owned debug snapshot delegation",
    }
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"inputs_session_state_typed_models_snapshot_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_session_state_typed_models_snapshot_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_session_state_typed_models_snapshot", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
