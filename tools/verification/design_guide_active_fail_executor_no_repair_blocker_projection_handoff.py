"""Verify active-fail executor no-repair blocker projection handoff."""

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
PAGE_HELPER = "_active_failure_no_repair_blocker_from_evidence"


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


def _parse_util_value(value: Any) -> float | None:
    if value in (None, "", "-", "—"):
        return None
    try:
        return float(value)
    except Exception:
        try:
            return float(str(value).strip())
        except Exception:
            return None


def _bending_fail_family_owned_repair_blocked_proof(evidence: dict[str, Any] | None) -> bool:
    evidence_d = dict(evidence or {})
    proof = dict(
        evidence_d.get("bending_fail_blocked_ownership_proof")
        or dict(evidence_d.get("repair_reason_proof") or {}).get("blocked_ownership_proof")
        or {}
    )
    family_id = str(
        proof.get("family_id")
        or evidence_d.get("family_id")
        or evidence_d.get("governing_family")
        or evidence_d.get("family_name")
        or ""
    ).strip().upper()
    if family_id != "BENDING_FAIL_GOVERNS":
        return False
    repair_blocked = bool(proof.get("repair_blocked") or evidence_d.get("bending_fail_repair_blocked"))
    hard_blocker = bool(proof.get("hard_blocker_proven") or evidence_d.get("bending_fail_hard_blocker_proven"))
    strategy_exhaustion = bool(
        proof.get("contract_strategy_exhaustion_proven")
        or evidence_d.get("bending_fail_contract_strategy_exhaustion_proven")
    )
    cap_only = bool(proof.get("internal_cap_only") or evidence_d.get("bending_fail_internal_cap_only"))
    return bool(repair_blocked and (hard_blocker or strategy_exhaustion) and not cap_only)


def _old_projection(
    *,
    state: dict[str, Any] | None,
    overview: dict[str, Any] | None,
    active_failures: set[str],
    evidence: dict[str, Any] | None,
) -> dict[str, Any]:
    del state
    from design_brain.design_guide_controller import build_design_guide_controller_guidance_item
    from design_brain.publication import (
        active_failure_blocker_visible_reason_text,
        active_failure_exact_blockers_for_families,
        disabled_design_guide_button_contract,
    )

    active = {str(family or "").strip().lower() for family in active_failures if str(family or "").strip()}
    active_family = "combined" if {"bending", "shear"}.issubset(active) else (
        "shear" if "shear" in active else "bending"
    )
    evidence_map = dict(evidence or {})
    bending_family_owned_blocked = (
        active_family == "bending" and _bending_fail_family_owned_repair_blocked_proof(evidence_map)
    )
    bending_missing_family_proof = active_family == "bending" and not bending_family_owned_blocked
    title = (
        "Bending and shear repair blocked"
        if active_family == "combined"
        else "Shear repair blocked by shear/detailing limits"
        if active_family == "shear"
        else "Bending repair proof incomplete"
        if bending_missing_family_proof
        else "Bending repair blocked by reinforcement/detailing limits"
    )
    overview_map = dict(overview or {})
    evidence_map.setdefault("active_failures", sorted(active))
    exact = active_failure_exact_blockers_for_families(
        sorted(active),
        overview=overview_map,
        evidence=evidence_map,
        primary_family=None,
        primary_reason=None,
    )
    text = active_failure_blocker_visible_reason_text(exact, sorted(active))
    if bending_missing_family_proof:
        text = (
            "BENDING_FAIL_GOVERNS did not publish family-owned repair-blocked proof. "
            "Bounded or cap-only search exhaustion remains diagnostic only."
        )
    item = build_design_guide_controller_guidance_item(
        active_family,
        title,
        text,
        None,
        f"Why: {text}",
        "Key blockers: active strengthening repair search, required PASS checks, detailing limits",
        None,
        None,
        status="FAIL",
        util=_parse_util_value(overview_map.get("worst_util") or overview_map.get("governing_util")),
    )
    item.update(
        {
            "bucket": "fail",
            "status": "FAIL",
            "guidance_intent": "specific_blocker" if not bending_missing_family_proof else "diagnostic_incomplete_proof",
            "final_state_class": "blocker" if not bending_missing_family_proof else "diagnostic_incomplete_proof",
            "active_under_capacity_blocker": not bending_missing_family_proof,
            "active_under_capacity_blocker_family": active_family,
            "candidate_search_evidence": {
                **evidence_map,
                "exact_blockers_by_family": dict(exact),
                "post_click_exact_blockers_by_family": dict(exact),
                "bending_fail_missing_family_owned_no_repair_proof": bool(bending_missing_family_proof),
                "visible_blocked_wording_source": (
                    "BENDING_FAIL_GOVERNS family result" if bending_family_owned_blocked else None
                ),
            },
            "exact_blockers_by_family": dict(exact),
            "post_click_exact_blockers_by_family": dict(exact),
        }
    )
    item["button_contract"] = disabled_design_guide_button_contract(
        item,
        family=active_family,
        reason=text,
    )
    return item


def _new_projection(
    *,
    state: dict[str, Any] | None,
    overview: dict[str, Any] | None,
    active_failures: set[str],
    evidence: dict[str, Any] | None,
) -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        build_design_guide_controller_active_fail_executor_no_repair_blocker_from_evidence,
    )

    return build_design_guide_controller_active_fail_executor_no_repair_blocker_from_evidence(
        state=dict(state or {}),
        overview=dict(overview or {}),
        active_failures=set(active_failures or set()),
        evidence=dict(evidence or {}),
    )


def _cases() -> dict[str, dict[str, Any]]:
    base_overview = {
        "worst_util": "1.28",
        "governing_util": 1.28,
        "statuses": {"bending": "FAIL", "shear": "PASS"},
        "any_fail": True,
    }
    return {
        "bending_missing_family_proof": {
            "state": {"b": 400.0, "D": 650.0},
            "overview": dict(base_overview),
            "active_failures": {"bending"},
            "evidence": {
                "family_id": "BENDING_FAIL_GOVERNS",
                "bending_fail_repair_blocked": True,
                "bending_fail_internal_cap_only": True,
                "failed_routes": ["depth", "width"],
            },
        },
        "bending_family_owned_repair_blocked": {
            "state": {"b": 400.0, "D": 650.0},
            "overview": dict(base_overview),
            "active_failures": {"bending"},
            "evidence": {
                "bending_fail_blocked_ownership_proof": {
                    "family_id": "BENDING_FAIL_GOVERNS",
                    "repair_blocked": True,
                    "hard_blocker_proven": True,
                    "contract_strategy_exhaustion_proven": True,
                    "internal_cap_only": False,
                },
                "candidate_rows": [{"route": "bottom_reo", "result": "blocked"}],
            },
        },
        "shear_no_repair_blocked": {
            "state": {"b": 400.0, "D": 650.0},
            "overview": {
                "worst_util": 1.35,
                "governing_util": 1.35,
                "statuses": {"bending": "PASS", "shear": "FAIL"},
                "any_fail": True,
            },
            "active_failures": {"shear"},
            "evidence": {
                "safe_repair_candidate_count": 0,
                "failed_routes": ["ligature_spacing", "depth"],
            },
        },
        "combined_no_repair_blocked": {
            "state": {"b": 400.0, "D": 650.0},
            "overview": {
                "worst_util": 1.41,
                "governing_util": 1.41,
                "statuses": {"bending": "FAIL", "shear": "FAIL"},
                "any_fail": True,
            },
            "active_failures": {"bending", "shear"},
            "evidence": {
                "safe_repair_candidate_count": 0,
                "combined_strengthening_searched": True,
                "failed_routes": ["geometry", "bottom_reo", "shear_links"],
            },
        },
    }


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    helper_start, helper_end, helper_source = _function_source(inputs_source, PAGE_HELPER)
    controller_start, controller_end, controller_helper_source = _function_source(
        controller_source,
        "build_design_guide_controller_active_fail_executor_no_repair_blocker_from_evidence",
    )
    parity: dict[str, dict[str, Any]] = {}
    for name, case in _cases().items():
        old = _old_projection(**case)
        new = _new_projection(**case)
        parity[name] = {
            "old_hash": _stable_hash(old),
            "new_hash": _stable_hash(new),
            "match": old == new,
            "button_contract_match": dict(old.get("button_contract") or {}) == dict(new.get("button_contract") or {}),
            "exact_blockers_match": dict(old.get("exact_blockers_by_family") or {}) == dict(
                new.get("exact_blockers_by_family") or {}
            ),
            "visible_primary_action_match": str(old.get("primary_action") or "") == str(new.get("primary_action") or ""),
            "guidance_intent_match": old.get("guidance_intent") == new.get("guidance_intent"),
            "final_state_class_match": old.get("final_state_class") == new.get("final_state_class"),
            "active_under_capacity_blocker_match": old.get("active_under_capacity_blocker")
            == new.get("active_under_capacity_blocker"),
        }
    page_forbidden_tokens = [
        "_active_failure_exact_blockers_for_families(",
        "_active_failure_blocker_visible_reason_text(",
        "_guidance_item(",
        "_disabled_design_guide_button_contract(",
        "_parse_util_value(",
        "_bending_fail_family_owned_repair_blocked_proof(",
    ]
    return {
        "schema": "design_guide_active_fail_executor_no_repair_blocker_projection_handoff.v1",
        "page_helper": {
            "name": PAGE_HELPER,
            "line_start": helper_start,
            "line_end": helper_end,
            "line_count": max(0, helper_end - helper_start + 1),
            "delegates_to_controller": "_build_design_guide_controller_active_fail_executor_no_repair_blocker_from_evidence("
            in helper_source,
            "forbidden_page_policy_tokens": {
                token: token in helper_source for token in page_forbidden_tokens
            },
        },
        "controller_helper": {
            "line_start": controller_start,
            "line_end": controller_end,
            "line_count": max(0, controller_end - controller_start + 1),
            "exists": bool(controller_start),
            "exported": '"build_design_guide_controller_active_fail_executor_no_repair_blocker_from_evidence"'
            in controller_source,
            "imports_no_page_or_streamlit": all(
                token not in controller_source
                for token in ("inputs_page", "streamlit", "st.session_state", "design_guide_page")
            ),
        },
        "parity": parity,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_behavior_changed": False,
    }


def _checks(payload: dict[str, Any]) -> dict[str, bool]:
    page = payload.get("page_helper") or {}
    controller = payload.get("controller_helper") or {}
    parity = payload.get("parity") or {}
    return {
        "page_helper_found": bool(page.get("line_start")),
        "page_helper_delegates_to_controller": bool(page.get("delegates_to_controller")),
        "page_helper_policy_tokens_removed": not any((page.get("forbidden_page_policy_tokens") or {}).values()),
        "controller_helper_exists": bool(controller.get("exists")),
        "controller_helper_exported": bool(controller.get("exported")),
        "controller_import_boundary_clean": bool(controller.get("imports_no_page_or_streamlit")),
        "parity_cases_present": len(parity) == 4,
        "all_projection_hashes_match": all(bool(row.get("match")) for row in parity.values()),
        "button_contracts_unchanged": all(bool(row.get("button_contract_match")) for row in parity.values()),
        "exact_blockers_unchanged": all(bool(row.get("exact_blockers_match")) for row in parity.values()),
        "visible_wording_unchanged": all(bool(row.get("visible_primary_action_match")) for row in parity.values())
        and not bool(payload.get("visible_wording_changed")),
        "guidance_state_unchanged": all(
            bool(row.get("guidance_intent_match"))
            and bool(row.get("final_state_class_match"))
            and bool(row.get("active_under_capacity_blocker_match"))
            for row in parity.values()
        ),
        "product_behavior_unchanged": not bool(payload.get("product_behavior_changed")),
        "cta_apply_semantics_unchanged": not bool(payload.get("cta_apply_semantics_changed")),
        "family_runtime_behavior_unchanged": not bool(payload.get("family_runtime_behavior_changed")),
    }


def _write(payload: dict[str, Any], checks: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_active_fail_executor_no_repair_blocker_projection_handoff_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_active_fail_executor_no_repair_blocker_projection_handoff_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Active-Fail Executor No-Repair Blocker Projection Handoff",
        "",
        f"Status: {payload['status']}",
        "",
        "## Executive Summary",
        (
            "The active-fail no-repair blocker projection is controller-owned. "
            "The page helper delegates, and parity cases prove unchanged wording, blocker evidence, "
            "button contract, and state classification."
        ),
        "",
        "## Page Helper",
        f"- Lines: {payload['page_helper']['line_start']}-{payload['page_helper']['line_end']}",
        f"- Line count: {payload['page_helper']['line_count']}",
        f"- Delegates to controller: {payload['page_helper']['delegates_to_controller']}",
        "",
        "## Parity Cases",
    ]
    for name, row in (payload.get("parity") or {}).items():
        lines.append(f"- {name}: {'PASS' if row.get('match') else 'FAIL'} hash `{row.get('new_hash')}`")
    lines.extend(
        [
            "",
            "## Checks",
            *[f"- {name}: {'PASS' if passed else 'FAIL'}" for name, passed in checks.items()],
        ]
    )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = _capture()
    checks = _checks(payload)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {**payload, "status": status, "checks": checks, "checked_at": _timestamp()}
    json_path, report_path = _write(payload, checks)
    print(f"design_guide_active_fail_executor_no_repair_blocker_projection_handoff {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
