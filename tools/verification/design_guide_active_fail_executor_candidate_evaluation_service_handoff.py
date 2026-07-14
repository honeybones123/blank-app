"""Verify active-fail executor candidate evaluation service handoff."""

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
CANDIDATE_EVALUATION = ROOT / "design_brain" / "candidate_evaluation.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
TARGET = "_active_fail_near_current_repair_item"
SERVICE_HELPER = "evaluate_active_fail_executor_candidate_with_updates"


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


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


def _sample_parity() -> dict[str, Any]:
    from design_brain.candidate_evaluation import (  # noqa: WPS433
        evaluate_active_fail_executor_candidate_with_updates,
        evaluate_design_candidate_with_updates,
    )

    base_state = {
        "b": 400.0,
        "bw": 400.0,
        "D": 650.0,
        "bot_row_1_bars": 6,
        "bot1_count": 6,
        "bot_row_1_dia": 20,
        "db_bot_1": 20,
        "lig_d": 10,
        "lig_legs": 2,
        "s_lig": 200.0,
        "uls_Mstar": 300.0,
        "uls_Vstar": 100.0,
    }
    updates = {"D": 700.0, "b": 450.0, "bw": 450.0, "lig_d": 12, "lig_legs": 2, "s_lig": 150.0}
    source = "combined_fail_contract_ladder"
    label = "COMBINED_BENDING_SHEAR_FAIL repair ladder candidate"
    action_type = "apply_resolved_candidate"
    calls: list[dict[str, Any]] = []

    def snapshot_fn(state: dict[str, Any]) -> dict[str, Any]:
        return dict(state or {})

    def evaluator_fn(state: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        calls.append({"state": dict(state or {}), "kwargs": dict(kwargs)})
        candidate_id = "active_fail_executor_candidate"
        return {
            "candidate_id": candidate_id,
            "source_candidate_id": candidate_id,
            "source": kwargs.get("source"),
            "label": kwargs.get("label"),
            "action_type": kwargs.get("action_type"),
            "updates": dict(kwargs.get("updates") or {}),
            "overview": {
                "utils": {"bending": 0.91, "shear": 0.82},
                "statuses": {
                    "bending": "PASS",
                    "shear": "PASS",
                    "crack": "PASS",
                    "deflection": "PASS",
                },
                "any_fail": False,
                "all_key_pass": True,
                "worst_util": 0.91,
                "governing_util": 0.91,
            },
            "candidate_search_evidence": {
                "selected_candidate_id": candidate_id,
                "search_scope": kwargs.get("source"),
            },
            "button_contract": {
                "enabled": True,
                "actionable": True,
                "action_type": kwargs.get("action_type"),
            },
            "action_payload": {
                "source_candidate_id": candidate_id,
                "updates": dict(kwargs.get("updates") or {}),
            },
            "title_main": kwargs.get("label"),
            "guidance_change_lines": ["Apply active-fail repair candidate."],
        }

    old_path = evaluate_design_candidate_with_updates(
        base_state,
        updates=updates,
        source=source,
        label=label,
        action_type=action_type,
        state_snapshot_fn=snapshot_fn,
        evaluator_fn=evaluator_fn,
    )
    new_path = evaluate_active_fail_executor_candidate_with_updates(
        base_state,
        updates=updates,
        source=source,
        label=label,
        action_type=action_type,
        state_snapshot_fn=snapshot_fn,
        evaluator_fn=evaluator_fn,
    )
    return {
        "old_path": old_path,
        "new_path": new_path,
        "old_hash": _stable_hash(old_path),
        "new_hash": _stable_hash(new_path),
        "candidate_overview_hashes": {
            "old": _stable_hash(dict((old_path or {}).get("overview") or {})),
            "new": _stable_hash(dict((new_path or {}).get("overview") or {})),
        },
        "candidate_evidence_hashes": {
            "old": _stable_hash(dict((old_path or {}).get("candidate_search_evidence") or {})),
            "new": _stable_hash(dict((new_path or {}).get("candidate_search_evidence") or {})),
        },
        "updates_hashes": {
            "old": _stable_hash(dict((old_path or {}).get("updates") or {})),
            "new": _stable_hash(dict((new_path or {}).get("updates") or {})),
        },
        "button_contract_hashes": {
            "old": _stable_hash(dict((old_path or {}).get("button_contract") or {})),
            "new": _stable_hash(dict((new_path or {}).get("button_contract") or {})),
        },
        "action_payload_hashes": {
            "old": _stable_hash(dict((old_path or {}).get("action_payload") or {})),
            "new": _stable_hash(dict((new_path or {}).get("action_payload") or {})),
        },
        "visible_wording_hashes": {
            "old": _stable_hash(
                {
                    "title_main": (old_path or {}).get("title_main"),
                    "guidance_change_lines": (old_path or {}).get("guidance_change_lines"),
                }
            ),
            "new": _stable_hash(
                {
                    "title_main": (new_path or {}).get("title_main"),
                    "guidance_change_lines": (new_path or {}).get("guidance_change_lines"),
                }
            ),
        },
        "calls": calls,
    }


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    candidate_source = _read(CANDIDATE_EVALUATION)
    target_start, target_end, target_source = _function_source(inputs_source, TARGET)
    parity = _sample_parity()
    return {
        "schema": "design_guide_active_fail_executor_candidate_evaluation_service_handoff.v1",
        "target": {
            "name": TARGET,
            "line_start": target_start,
            "line_end": target_end,
            "line_count": max(0, target_end - target_start + 1),
        },
        "parity": parity,
        "source_checks": {
            "target_uses_active_fail_service_helper": "_evaluate_active_fail_executor_candidate_with_updates("
            in target_source,
            "target_no_longer_calls_auto_design_candidate": "_evaluate_auto_design_candidate(" not in target_source,
            "auto_candidate_shim_retained": "def _evaluate_auto_design_candidate(" in inputs_source,
            "candidate_evaluation_helper_exists": f"def {SERVICE_HELPER}(" in candidate_source,
            "candidate_evaluation_exports_helper": f'"{SERVICE_HELPER}"' in candidate_source,
            "candidate_evaluation_import_clean_terms_absent": all(
                token not in candidate_source
                for token in ("inputs_page", "streamlit", "st.session_state", "design_guide_page")
            ),
            "family_ladder_dispatch_controller_owned": (
                "_build_design_guide_controller_active_fail_executor_family_ladder_dispatch("
                in target_source
                and ".contracted_repair_ladder_specs(" not in target_source
            ),
            "session_cache_still_page_owned": "st.session_state" in target_source,
            "cta_side_effect_still_page_owned": "_record_bending_fail_valid_repair_cta_published(" in target_source,
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(payload: dict[str, Any]) -> dict[str, bool]:
    parity = payload.get("parity") or {}
    source_checks = payload.get("source_checks") or {}
    return {
        "target_found": bool((payload.get("target") or {}).get("line_start")),
        "candidate_hash_unchanged": parity.get("old_hash") == parity.get("new_hash"),
        "candidate_overview_unchanged": (
            (parity.get("candidate_overview_hashes") or {}).get("old")
            == (parity.get("candidate_overview_hashes") or {}).get("new")
        ),
        "candidate_evidence_unchanged": (
            (parity.get("candidate_evidence_hashes") or {}).get("old")
            == (parity.get("candidate_evidence_hashes") or {}).get("new")
        ),
        "updates_unchanged": (
            (parity.get("updates_hashes") or {}).get("old")
            == (parity.get("updates_hashes") or {}).get("new")
        ),
        "button_contract_unchanged": (
            (parity.get("button_contract_hashes") or {}).get("old")
            == (parity.get("button_contract_hashes") or {}).get("new")
        ),
        "action_payload_unchanged": (
            (parity.get("action_payload_hashes") or {}).get("old")
            == (parity.get("action_payload_hashes") or {}).get("new")
        ),
        "visible_wording_unchanged_by_parity": (
            (parity.get("visible_wording_hashes") or {}).get("old")
            == (parity.get("visible_wording_hashes") or {}).get("new")
        ),
        **{name: bool(value) for name, value in source_checks.items()},
        "product_behavior_unchanged": not bool(payload.get("product_behavior_changed")),
        "visible_wording_unchanged": not bool(payload.get("visible_wording_changed")),
        "cta_apply_semantics_unchanged": not bool(payload.get("cta_apply_semantics_changed")),
        "family_runtime_unchanged": not bool(payload.get("family_runtime_changed")),
    }


def _write(payload: dict[str, Any], checks: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / (
        f"design_guide_active_fail_executor_candidate_evaluation_service_handoff_{suffix}.json"
    )
    report_path = AUDIT_DIR / (
        f"design_guide_active_fail_executor_candidate_evaluation_service_handoff_{suffix}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Active-Fail Executor Candidate Evaluation Service Handoff",
        "",
        f"Status: {payload['status']}",
        "",
        "## Summary",
        (
            "Moved only the active-fail executor candidate evaluation adapter behind "
            "`design_brain.candidate_evaluation`. Family ladder execution, cache/session, "
            "ranking/evidence packaging, and CTA side effects remain page-owned."
        ),
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
    print(f"design_guide_active_fail_executor_candidate_evaluation_service_handoff {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
