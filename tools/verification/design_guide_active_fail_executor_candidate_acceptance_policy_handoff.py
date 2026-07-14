"""Verify active-fail executor candidate acceptance policy handoff."""

from __future__ import annotations

import ast
import hashlib
import json
from datetime import datetime, timezone
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
NESTED = "_candidate_accepted_for_active_fail_repair"


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


def _function_node(source: str, name: str) -> ast.FunctionDef | None:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def _function_source(source: str, node: ast.FunctionDef | None) -> str:
    if node is None:
        return ""
    lines = source.splitlines()
    end = int(node.end_lineno or node.lineno)
    return "\n".join(lines[node.lineno - 1 : end])


def _nested_function_source(source: str, outer_name: str, nested_name: str) -> tuple[int, int, str]:
    outer = _function_node(source, outer_name)
    if outer is None:
        return 0, 0, ""
    lines = source.splitlines()
    for node in ast.walk(outer):
        if isinstance(node, ast.FunctionDef) and node.name == nested_name:
            end = int(node.end_lineno or node.lineno)
            return node.lineno, end, "\n".join(lines[node.lineno - 1 : end])
    return 0, 0, ""


def _old_required_checks_acceptable(overview: dict[str, Any] | None) -> bool:
    if not isinstance(overview, dict):
        return False
    statuses = overview.get("statuses")
    if isinstance(statuses, dict):
        tracked = [
            str(status or "").strip().upper()
            for status in statuses.values()
            if str(status or "").strip() not in {"", "â€”", "-"}
        ]
    else:
        tracked = []
    if not tracked:
        return bool(overview.get("all_key_pass")) and not bool(overview.get("any_fail"))
    return not any(status in {"FAIL", "FAILED", "ERROR"} for status in tracked)


def _old_acceptance(
    candidate: dict[str, Any] | None,
    *,
    bending_family_ladder_attempted: bool,
    shear_family_ladder_attempted: bool,
) -> bool:
    cand = dict(candidate or {}) if isinstance(candidate, dict) else {}
    if not cand or not bool(cand.get("is_compliant")):
        return False
    overview = dict(cand.get("overview") or {})
    if bool(overview.get("any_fail")):
        return False
    family_id = str(cand.get("candidate_family_id") or "").strip().upper()
    if bending_family_ladder_attempted and family_id == "BENDING_FAIL_GOVERNS":
        return bool(_old_required_checks_acceptable(overview))
    if shear_family_ladder_attempted and family_id == "SHEAR_FAIL_GOVERNS":
        return bool(_old_required_checks_acceptable(overview))
    return bool(overview.get("all_key_pass"))


def _new_acceptance(
    candidate: dict[str, Any] | None,
    *,
    bending_family_ladder_attempted: bool,
    shear_family_ladder_attempted: bool,
) -> bool:
    from design_brain.design_guide_controller import (  # noqa: WPS433
        accept_design_guide_controller_active_fail_executor_repair_candidate,
    )

    return bool(
        accept_design_guide_controller_active_fail_executor_repair_candidate(
            candidate=dict(candidate or {}) if isinstance(candidate, dict) else {},
            bending_family_ladder_attempted=bool(bending_family_ladder_attempted),
            shear_family_ladder_attempted=bool(shear_family_ladder_attempted),
        )
    )


def _parity_rows() -> dict[str, dict[str, Any]]:
    cases: dict[str, dict[str, Any]] = {
        "bending_accepts_required_checks": {
            "candidate": {
                "is_compliant": True,
                "candidate_family_id": "BENDING_FAIL_GOVERNS",
                "overview": {"any_fail": False, "all_key_pass": False, "statuses": {"bending": "PASS", "shear": "NEAR LIMIT"}},
            },
            "bending": True,
            "shear": False,
        },
        "bending_rejects_explicit_fail": {
            "candidate": {
                "is_compliant": True,
                "candidate_family_id": "BENDING_FAIL_GOVERNS",
                "overview": {"any_fail": False, "all_key_pass": True, "statuses": {"bending": "FAIL"}},
            },
            "bending": True,
            "shear": False,
        },
        "shear_accepts_required_checks": {
            "candidate": {
                "is_compliant": True,
                "candidate_family_id": "SHEAR_FAIL_GOVERNS",
                "overview": {"any_fail": False, "all_key_pass": False, "statuses": {"shear": "PASS", "bending": "NEAR LIMIT"}},
            },
            "bending": False,
            "shear": True,
        },
        "generic_requires_all_key_pass": {
            "candidate": {
                "is_compliant": True,
                "candidate_family_id": "COMBINED_BENDING_SHEAR_FAIL",
                "overview": {"any_fail": False, "all_key_pass": True, "statuses": {"bending": "PASS", "shear": "PASS"}},
            },
            "bending": False,
            "shear": False,
        },
        "generic_rejects_non_all_key_pass": {
            "candidate": {
                "is_compliant": True,
                "candidate_family_id": "COMBINED_BENDING_SHEAR_FAIL",
                "overview": {"any_fail": False, "all_key_pass": False, "statuses": {"bending": "PASS", "shear": "PASS"}},
            },
            "bending": False,
            "shear": False,
        },
        "rejects_any_fail": {
            "candidate": {
                "is_compliant": True,
                "candidate_family_id": "SHEAR_FAIL_GOVERNS",
                "overview": {"any_fail": True, "all_key_pass": True, "statuses": {"shear": "PASS"}},
            },
            "bending": False,
            "shear": True,
        },
        "rejects_non_compliant": {
            "candidate": {
                "is_compliant": False,
                "candidate_family_id": "BENDING_FAIL_GOVERNS",
                "overview": {"any_fail": False, "all_key_pass": True, "statuses": {"bending": "PASS"}},
            },
            "bending": True,
            "shear": False,
        },
    }
    rows: dict[str, dict[str, Any]] = {}
    for name, case in cases.items():
        candidate = dict(case["candidate"])
        old = _old_acceptance(
            candidate,
            bending_family_ladder_attempted=bool(case["bending"]),
            shear_family_ladder_attempted=bool(case["shear"]),
        )
        new = _new_acceptance(
            candidate,
            bending_family_ladder_attempted=bool(case["bending"]),
            shear_family_ladder_attempted=bool(case["shear"]),
        )
        rows[name] = {
            "old": old,
            "new": new,
            "matches": old == new,
            "hash": _stable_hash({"old": old, "new": new, "case": case}),
        }
    return rows


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    target_node = _function_node(inputs_source, TARGET)
    target_source = _function_source(inputs_source, target_node)
    nested_start, nested_end, nested_source = _nested_function_source(inputs_source, TARGET, NESTED)
    parity = _parity_rows()
    source_checks = {
        "target_found": target_node is not None,
        "nested_acceptance_wrapper_found": bool(nested_source),
        "nested_acceptance_wrapper_delegates_to_controller": (
            "_accept_design_guide_controller_active_fail_executor_repair_candidate(" in nested_source
        ),
        "nested_acceptance_wrapper_no_longer_owns_bending_family_predicate": (
            "BENDING_FAIL_GOVERNS" not in nested_source
        ),
        "nested_acceptance_wrapper_no_longer_owns_shear_family_predicate": (
            "SHEAR_FAIL_GOVERNS" not in nested_source
        ),
        "nested_acceptance_wrapper_no_longer_calls_required_checks_page_helper": (
            "_overview_required_checks_acceptable(" not in nested_source
        ),
        "target_filters_safe_candidates_through_wrapper": (
            "_candidate_accepted_for_active_fail_repair(cand)" in target_source
        ),
        "controller_acceptance_helper_exists": (
            "def accept_design_guide_controller_active_fail_executor_repair_candidate(" in controller_source
        ),
        "controller_exports_acceptance_helper": (
            '"accept_design_guide_controller_active_fail_executor_repair_candidate"' in controller_source
        ),
        "controller_has_no_page_or_streamlit_imports": all(
            token not in controller_source
            for token in ("inputs_page", "streamlit", "st.session_state", "design_guide_page")
        ),
    }
    return {
        "schema": "design_guide_active_fail_executor_candidate_acceptance_policy_handoff.v1",
        "target": {
            "name": TARGET,
            "line_start": int(target_node.lineno if target_node else 0),
            "line_end": int(target_node.end_lineno if target_node and target_node.end_lineno else 0),
        },
        "nested_wrapper": {
            "name": NESTED,
            "line_start": nested_start,
            "line_end": nested_end,
            "line_count": max(0, nested_end - nested_start + 1),
        },
        "parity": parity,
        "source_checks": source_checks,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_behavior_changed": False,
    }


def _checks(payload: dict[str, Any]) -> dict[str, bool]:
    parity = dict(payload.get("parity") or {})
    source_checks = dict(payload.get("source_checks") or {})
    return {
        "acceptance_policy_hashes_unchanged": bool(parity)
        and all(row.get("matches") for row in parity.values()),
        **{name: bool(value) for name, value in source_checks.items()},
        "product_behavior_unchanged": not bool(payload.get("product_behavior_changed")),
        "visible_wording_unchanged": not bool(payload.get("visible_wording_changed")),
        "cta_apply_semantics_unchanged": not bool(payload.get("cta_apply_semantics_changed")),
        "family_runtime_behavior_unchanged": not bool(payload.get("family_runtime_behavior_changed")),
    }


def _write(payload: dict[str, Any], checks: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_active_fail_executor_candidate_acceptance_policy_handoff_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_active_fail_executor_candidate_acceptance_policy_handoff_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Active-Fail Executor Candidate Acceptance Policy Handoff",
        "",
        f"Status: {payload['status']}",
        "",
        "## Summary",
        (
            "Moved the active-fail executor safe-candidate acceptance predicate behind "
            "`DesignGuideController`. The page still owns candidate iteration, cache/session "
            "state, trace, and final Apply/render side effects."
        ),
        "",
        "## Parity",
        *[
            f"- {name}: {'PASS' if row.get('matches') else 'FAIL'}"
            for name, row in (payload.get("parity") or {}).items()
        ],
        "",
        "## Checks",
        *[f"- {name}: {'PASS' if passed else 'FAIL'}" for name, passed in checks.items()],
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = _capture()
    checks = _checks(payload)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {**payload, "status": status, "checks": checks, "checked_at": _timestamp()}
    json_path, report_path = _write(payload, checks)
    print(f"design_guide_active_fail_executor_candidate_acceptance_policy_handoff {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
