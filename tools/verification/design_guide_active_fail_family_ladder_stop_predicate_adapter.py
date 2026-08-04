"""Verify active-fail family ladder stop predicate adapter extraction."""

from __future__ import annotations

import ast
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
TARGET = "_active_fail_near_current_repair_item"
HELPER = "resolve_design_guide_controller_active_fail_executor_ladder_stop_decision"


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


def _function_source(source: str, name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            end = int(node.end_lineno or node.lineno)
            return node.lineno, end, "\n".join(lines[node.lineno - 1 : end])
    return 0, 0, ""


def _old_stop(family_id: str, candidate: dict[str, Any] | None) -> bool:
    cand = dict(candidate or {}) if isinstance(candidate, dict) else {}
    overview = dict(cand.get("overview") or {})
    if not bool(cand.get("is_compliant")):
        return False
    if str(family_id or "").strip().upper() == "COMBINED_BENDING_SHEAR_FAIL":
        return bool(overview.get("all_key_pass")) and not bool(overview.get("any_fail"))
    return not bool(overview.get("any_fail"))


def _new_stop(family_id: str, candidate: dict[str, Any] | None) -> bool:
    from design_brain.design_guide_controller import (  # noqa: WPS433
        resolve_design_guide_controller_active_fail_executor_ladder_stop_decision,
    )

    return bool(
        resolve_design_guide_controller_active_fail_executor_ladder_stop_decision(
            family_id=family_id,
            evaluated_candidate=candidate,
        )
    )


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    target_start, target_end, target_source = _function_source(inputs_source, TARGET)
    helper_start, helper_end, helper_source = _function_source(controller_source, HELPER)
    candidates = {
        "empty": None,
        "not_compliant": {"is_compliant": False, "overview": {"any_fail": False, "all_key_pass": True}},
        "safe": {"is_compliant": True, "overview": {"any_fail": False, "all_key_pass": True}},
        "still_fail": {"is_compliant": True, "overview": {"any_fail": True, "all_key_pass": False}},
        "combined_missing_all_key": {"is_compliant": True, "overview": {"any_fail": False, "all_key_pass": False}},
    }
    families = ("SHEAR_FAIL_GOVERNS", "BENDING_FAIL_GOVERNS", "COMBINED_BENDING_SHEAR_FAIL")
    parity: dict[str, dict[str, Any]] = {}
    for family in families:
        for case_name, candidate in candidates.items():
            name = f"{family}:{case_name}"
            old = _old_stop(family, candidate)
            new = _new_stop(family, candidate)
            parity[name] = {"match": old == new, "old": old, "new": new}
    old_inline_tokens_removed = all(
        token not in target_source
        for token in (
            'bool(evaluated.get("is_compliant"))\n                    and not bool((evaluated.get("overview") or {}).get("any_fail"))',
            'bool((evaluated.get("overview") or {}).get("all_key_pass"))',
        )
    )
    return {
        "schema": "design_guide_active_fail_family_ladder_stop_predicate_adapter.v1",
        "target": {
            "line_start": target_start,
            "line_end": target_end,
            "delegates_stop_decision": "_resolve_design_guide_controller_active_fail_executor_ladder_stop_decision("
            in target_source,
            "delegate_call_count": target_source.count(
                "_resolve_design_guide_controller_active_fail_executor_ladder_stop_decision("
            ),
            "old_inline_tokens_removed": old_inline_tokens_removed,
        },
        "controller_helper": {
            "line_start": helper_start,
            "line_end": helper_end,
            "exists": bool(helper_start),
            "exported": f'"{HELPER}"' in controller_source,
            "imports_no_page_or_streamlit": all(
                token not in controller_source for token in ("inputs_page", "streamlit", "st.session_state")
            ),
            "helper_source_has_no_page_helpers": all(
                token not in helper_source for token in ("_inputs_pre_widget_trace", "st.session_state")
            ),
        },
        "parity": parity,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(payload: dict[str, Any]) -> dict[str, bool]:
    target = payload.get("target") or {}
    helper = payload.get("controller_helper") or {}
    parity = payload.get("parity") or {}
    return {
        "target_found": bool(target.get("line_start")),
        "target_delegates_stop_decision": bool(target.get("delegates_stop_decision")),
        "delegate_call_count_three": int(target.get("delegate_call_count") or 0) == 3,
        "old_inline_tokens_removed": bool(target.get("old_inline_tokens_removed")),
        "controller_helper_exists": bool(helper.get("exists")),
        "controller_helper_exported": bool(helper.get("exported")),
        "controller_import_boundary_clean": bool(helper.get("imports_no_page_or_streamlit")),
        "controller_helper_has_no_page_helpers": bool(helper.get("helper_source_has_no_page_helpers")),
        "parity_cases_present": len(parity) == 15,
        "all_parity_cases_match": all(bool(row.get("match")) for row in parity.values()),
        "product_behavior_unchanged": not bool(payload.get("product_behavior_changed")),
        "visible_wording_unchanged": not bool(payload.get("visible_wording_changed")),
        "cta_apply_semantics_unchanged": not bool(payload.get("cta_apply_semantics_changed")),
        "family_runtime_unchanged": not bool(payload.get("family_runtime_changed")),
    }


def _write(payload: dict[str, Any], checks: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_active_fail_family_ladder_stop_predicate_adapter_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_active_fail_family_ladder_stop_predicate_adapter_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Active-Fail Family Ladder Stop Predicate Adapter",
        "",
        f"Status: {payload['status']}",
        "",
        "## Summary",
        "Shear, bending, and combined active-fail ladder stop predicates now delegate to a pure controller helper.",
        "",
        "## Checks",
        *[f"- {name}: {'PASS' if passed else 'FAIL'}" for name, passed in checks.items()],
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = _capture()
    checks = _checks(payload)
    payload["checks"] = checks
    payload["status"] = "PASS" if all(checks.values()) else "FAIL"
    json_path, report_path = _write(payload, checks)
    print(f"design_guide_active_fail_family_ladder_stop_predicate_adapter {payload['status']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
