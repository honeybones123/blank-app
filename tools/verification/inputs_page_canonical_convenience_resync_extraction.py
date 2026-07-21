from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs_page_modules.app_bridge import canonical_convenience_resync


BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "app_bridge" / "canonical_convenience_resync.py"
VERIFICATION_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


class FakeStreamlit:
    def __init__(self) -> None:
        self.session_state: dict[str, Any] = {}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _function_source(source: str, name: str) -> str:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return "\n".join(lines[node.lineno - 1 : node.end_lineno])
    return ""


def _valid_pack() -> dict[str, Any]:
    return {
        "bot_rows_resolved": [
            {
                "active": True,
                "mode": "Count",
                "bar_count_resolved": 4,
                "spacing_resolved": 150.0,
            }
        ],
        "top_rows_resolved": [
            {
                "active": True,
                "mode": "Count",
                "bar_count_resolved": 1,
                "spacing_resolved": 200.0,
            }
        ],
        "db_bot": 16.0,
        "db_top": 12.0,
        "Ast_bot": 800.0,
        "Ast_top": 300.0,
    }


def _expected_fields() -> dict[str, Any]:
    return {
        "nb_bot": 4,
        "nb_top": 1,
        "total_bot_bars": 4,
        "total_top_bars": 1,
        "db_bot": 16.0,
        "db_top": 12.0,
        "s_bot": 150.0,
        "s_top": 200.0,
        "bot_entry": 4.0,
        "top_entry": 1.0,
        "Ast_bot": 800.0,
        "Ast_top": 300.0,
    }


def _run_scenario(*, pack: dict[str, Any] | None, snap: dict[str, Any], raises: Exception | None = None) -> dict[str, Any]:
    fake_st = FakeStreamlit()
    writes: list[dict[str, Any]] = []
    logs: list[dict[str, Any]] = []
    meta_key = "__canonical_convenience_meta__"

    def _build_pack(state: dict) -> dict[str, Any]:
        if raises is not None:
            raise raises
        return dict(pack or {})

    canonical_convenience_resync.bind_canonical_convenience_resync_dependencies(
        {
            "_CANONICAL_CONVENIENCE_META_KEY": meta_key,
            "_agent_debug_log": lambda message, payload, **kwargs: logs.append(
                {"message": message, "payload": payload, "kwargs": kwargs}
            ),
            "_build_canonical_design_state_pack": _build_pack,
            "_convenience_scalar_differs": lambda cur, new: abs(float(cur or 0) - float(new or 0)) > 1e-6
            if isinstance(cur, (float, int)) or isinstance(new, (float, int))
            else cur != new,
            "_guidance_state_snapshot": lambda state: dict(state),
            "_shared_state_snapshot": lambda: dict(snap),
            "set_shared": lambda key, val, *, source: writes.append(
                {"key": key, "value": val, "source": source}
            ),
            "st": fake_st,
        }
    )
    result = canonical_convenience_resync._apply_canonical_convenience_resync_to_shared(
        source="unit:canonical_convenience"
    )
    return {
        "result": result,
        "session": dict(fake_st.session_state),
        "writes": writes,
        "logs": logs,
    }


def _case_results() -> list[dict[str, Any]]:
    expected = _expected_fields()
    snap = dict(expected)
    snap["nb_bot"] = 2
    invalid = _run_scenario(pack=None, snap={"nb_bot": 2}, raises=ValueError("canonical_pack_failed"))
    valid = _run_scenario(
        pack=_valid_pack(),
        snap=snap,
    )
    return [
        {
            "name": "invalid_payload_skips_writes_and_logs",
            "passed": invalid["result"]["canonical_convenience_resync_skipped"] is True
            and invalid["result"]["canonical_convenience_resync_skip_reason"] == "canonical_pack_failed"
            and invalid["writes"] == []
            and len(invalid["logs"]) == 1
            and invalid["session"].get("canonical_convenience_resync_applied") is False,
            "scenario": invalid,
        },
        {
            "name": "valid_payload_writes_all_fields_and_tracks_drift",
            "passed": valid["result"]["canonical_convenience_resync_applied"] is True
            and [row["key"] for row in valid["writes"]] == list(expected.keys())
            and valid["result"]["convenience_drift_keys"] == ["nb_bot"]
            and valid["session"].get("convenience_field_drift_detected") is True
            and valid["session"].get("canonical_convenience_fields_updated") == list(expected.keys()),
            "scenario": valid,
        },
    ]


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Page Canonical Convenience Resync Extraction",
        "",
        f"## Decision: {payload['decision']}",
        "",
        "## Checks",
        "",
    ]
    for key, value in payload["checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    if payload["failures"]:
        lines.extend(["", "## Failures", ""])
        for failure in payload["failures"]:
            lines.append(f"- `{failure}`")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    bridge_source = _read(BRIDGE)
    module_source = _read(MODULE)
    bridge_helper = _function_source(bridge_source, "_apply_canonical_convenience_resync_to_shared")
    bridge_fields_helper = _function_source(bridge_source, "_canonical_convenience_fields_from_state")
    bridge_app_helper = _function_source(
        bridge_source,
        "_apply_canonical_convenience_resync_to_shared_for_app_bridge",
    )
    bridge_app_fields_helper = _function_source(
        bridge_source,
        "_canonical_convenience_fields_from_state_for_app_bridge",
    )
    module_helper = _function_source(module_source, "_apply_canonical_convenience_resync_to_shared")
    module_fields_helper = _function_source(module_source, "_canonical_convenience_fields_from_state")
    cases = _case_results()
    checks = {
        "module_exists": MODULE.exists(),
        "bridge_imports_extracted_helper": "_apply_canonical_convenience_resync_to_shared_extracted" in bridge_source,
        "bridge_imports_extracted_field_helper": "_canonical_convenience_fields_from_state_extracted" in bridge_source,
        "bridge_helper_is_thin_delegate": len(bridge_helper.splitlines()) <= 5,
        "bridge_binds_module_dependencies": "_bind_canonical_convenience_resync_dependencies(globals())" in bridge_helper,
        "bridge_delegates_to_extracted": "_apply_canonical_convenience_resync_to_shared_extracted(source=source)" in bridge_helper,
        "bridge_removed_resync_body": "canonical_convenience_resync_skipped" not in bridge_helper,
        "bridge_field_helper_is_thin_delegate": len(bridge_fields_helper.splitlines()) <= 4,
        "bridge_field_helper_binds_dependencies": "_bind_canonical_convenience_resync_dependencies(globals())" in bridge_fields_helper,
        "bridge_field_helper_delegates_to_module": "_canonical_convenience_fields_from_state_extracted(state)" in bridge_fields_helper,
        "bridge_removed_field_builder_body": "bot_rows_resolved" not in bridge_fields_helper,
        "bridge_app_helper_is_thin_delegate": len(bridge_app_helper.splitlines()) <= 17,
        "bridge_app_helper_binds_app_dependencies": all(
            token in bridge_app_helper
            for token in (
                "_bind_canonical_convenience_resync_dependencies(",
                '"_build_canonical_design_state_pack": _build_canonical_design_state_pack_for_app_bridge',
                '"_guidance_state_snapshot": _guidance_state_snapshot_for_summary_bridge',
                '"_shared_state_snapshot": _shared_state_snapshot_for_summary_bridge',
                '"_convenience_scalar_differs": _convenience_scalar_differs_for_app_bridge',
            )
        ),
        "bridge_app_helper_delegates_to_extracted": (
            "_apply_canonical_convenience_resync_to_shared_extracted(source=source)"
            in bridge_app_helper
        ),
        "bridge_app_removed_resync_body": "canonical_convenience_resync_skipped" not in bridge_app_helper,
        "bridge_app_field_helper_is_thin_delegate": len(bridge_app_fields_helper.splitlines()) <= 13,
        "bridge_app_field_helper_binds_app_dependencies": all(
            token in bridge_app_fields_helper
            for token in (
                "_bind_canonical_convenience_resync_dependencies(",
                '"_build_canonical_design_state_pack": _build_canonical_design_state_pack_for_app_bridge',
                '"_guidance_state_snapshot": _guidance_state_snapshot_for_summary_bridge',
            )
        ),
        "bridge_app_field_helper_delegates_to_module": (
            "_canonical_convenience_fields_from_state_extracted(state)"
            in bridge_app_fields_helper
        ),
        "bridge_app_removed_field_builder_body": "bot_rows_resolved" not in bridge_app_fields_helper,
        "module_keeps_field_builder_body": "bot_rows_resolved" in module_fields_helper
        and "_build_canonical_design_state_pack(_guidance_state_snapshot" in module_fields_helper,
        "module_field_builder_is_not_bound_from_bridge": module_source.count('"_canonical_convenience_fields_from_state"') == 1,
        "module_keeps_resync_body": "canonical_convenience_resync_skipped" in module_helper
        and "set_shared(key, val, source=source)" in module_helper,
        "all_cases_pass": all(row["passed"] for row in cases),
    }
    failures = [key for key, value in checks.items() if not value]
    failures.extend(f"case:{row['name']}" for row in cases if not row["passed"])
    decision = "INPUTS_PAGE_CANONICAL_CONVENIENCE_RESYNC_EXTRACTION_LOCKED" if not failures else "GAPS_REMAIN"
    payload = {
        "audit": "inputs_page_canonical_convenience_resync_extraction",
        "timestamp": timestamp,
        "decision": decision,
        "checks": checks,
        "failures": failures,
        "case_results": cases,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_behavior_changed": False,
        "engineering_calculations_changed": False,
    }
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"inputs_page_canonical_convenience_resync_extraction_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_canonical_convenience_resync_extraction_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_page_canonical_convenience_resync_extraction", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
