"""
Proof-only audit for ACTION-vs-BLOCKED family visual expectation rows.

Audits bending_fail_action and combined_fail_action against the active family
contracts and latest browser/live visual consistency artifact.

No product behaviour, visible wording, CTA/apply semantics, family runtime,
solver maths, target bands, widget keys, or render ownership are changed.
"""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
TARGET_SCENARIOS = ("bending_fail_action", "combined_fail_action")


def _datetime_stamp() -> str:
    return datetime.now().replace(microsecond=0).isoformat().replace(":", "-")


def _latest_visual_snapshot() -> Path:
    candidates = sorted(
        ARTIFACT_DIR.glob("design_guide_family_browser_live_visual_consistency_*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for candidate in candidates:
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except Exception:
            continue
        if payload.get("schema") == "design_guide_family_browser_live_visual_consistency_snapshot.v1":
            return candidate
    raise SystemExit("No family browser/live visual consistency artifact found.")


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _normalise_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    return None


def _normalise_int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(float(str(value).strip()))
    except Exception:
        return None


def _walk(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _first_value(source: Any, *keys: str) -> Any:
    for node in _walk(source):
        for key in keys:
            value = node.get(key)
            if value not in (None, "", [], {}):
                return value
    return None


def _first_dict_with(source: Any, *keys: str) -> dict[str, Any]:
    for node in _walk(source):
        if all(key in node for key in keys):
            return dict(node)
    return {}


def _contract_summary(contract_path: Path) -> dict[str, Any]:
    payload = json.loads(contract_path.read_text(encoding="utf-8"))
    allowed = []
    for row in payload.get("allowed_outcomes") or []:
        if isinstance(row, dict):
            allowed.append(row.get("outcome"))
    return {
        "path": str(contract_path),
        "family_id": _as_dict(payload.get("family_identity")).get("family_id"),
        "selection_requirements": list(payload.get("selection_requirements") or []),
        "allowed_outcomes": allowed,
        "forbidden_outcomes": list(payload.get("forbidden_outcomes") or []),
    }


def _scenario_diagnostics(scenario: dict[str, Any]) -> dict[str, Any]:
    state = _as_dict(scenario.get("browser_state"))
    classification = _as_dict(scenario.get("classification"))
    checks = _as_dict(scenario.get("checks"))
    cta = _as_dict(checks.get("cta"))
    text = str(_as_dict(scenario.get("design_guide")).get("text_sample") or "")

    executable_count = _normalise_int(
        _first_value(
            state,
            "executable_repair_candidate_count",
            "executable_candidate_count",
        )
    )
    safe_count = _normalise_int(_first_value(state, "safe_repair_candidate_count", "safe_candidate_count"))
    selected_candidate_id = _first_value(state, "selected_candidate_id")
    selected_updates = _first_value(state, "selected_candidate_updates", "button_contract_updates")
    candidate_search_ran = _normalise_bool(_first_value(state, "repair_search_ran", "candidate_search_ran"))
    candidate_search_exhaustive = _normalise_bool(
        _first_value(state, "repair_search_exhaustive", "candidate_search_exhaustive")
    )
    repair_blocked = _normalise_bool(_first_value(state, "repair_blocked", "bending_fail_repair_blocked"))
    proof_source = _first_value(state, "proof_source", "blocked_reason_source")
    blocked_reason = _first_value(state, "blocked_reason", "bending_fail_blocked_reason")
    raw_flags = _first_dict_with(state, "locked_repair_blocked", "legal_repair_exists")
    exact_blockers = _first_value(state, "exact_blockers_by_family")
    repair_variables_available = _first_value(state, "repair_variables_available")

    return {
        "scenario_id": scenario.get("scenario_id"),
        "recipe": scenario.get("recipe"),
        "expected_visual_state": scenario.get("expected_visual_state"),
        "selected_family_id": classification.get("selected_family_id"),
        "observed_statuses": list(classification.get("observed_statuses") or []),
        "action_button_count": len(cta.get("action_buttons") or []),
        "enabled_action_button_count": len(cta.get("enabled_action_buttons") or []),
        "candidate_search_ran": candidate_search_ran,
        "candidate_search_exhaustive": candidate_search_exhaustive,
        "executable_repair_candidate_count": executable_count,
        "safe_repair_candidate_count": safe_count,
        "selected_candidate_id": selected_candidate_id,
        "selected_candidate_updates_present": bool(selected_updates),
        "repair_blocked": repair_blocked,
        "blocked_reason": str(blocked_reason or "")[:700],
        "proof_source": proof_source,
        "raw_state_flags": raw_flags,
        "repair_variables_available": repair_variables_available,
        "exact_blockers_by_family_present": isinstance(exact_blockers, dict) and bool(exact_blockers),
        "design_guide_text_sample": text[:1000],
    }


def _decision_for_scenario(diag: dict[str, Any]) -> dict[str, Any]:
    sid = str(diag.get("scenario_id") or "")
    has_action = int(diag.get("enabled_action_button_count") or 0) > 0
    executable_count = diag.get("executable_repair_candidate_count")
    search_exhaustive = diag.get("candidate_search_exhaustive") is True
    selected_family = str(diag.get("selected_family_id") or "")
    raw_flags = _as_dict(diag.get("raw_state_flags"))
    locked_no_repair = selected_family == "LOCKED_NO_REPAIR"
    legal_repair_exists = _normalise_bool(raw_flags.get("legal_repair_exists"))
    locked_repair_blocked = _normalise_bool(raw_flags.get("locked_repair_blocked"))

    if sid == "bending_fail_action":
        if not has_action and executable_count == 0 and search_exhaustive and diag.get("repair_blocked") is True:
            return {
                "contract_decision": "EXPECTATION_STALE_ACCEPT_BLOCKED",
                "repair_candidate_available": False,
                "ladder_exhausted_correctly": True,
                "blocker_proof_complete": True,
                "final_publication_cta_should_be_disabled": True,
                "reason": (
                    "BENDING_FAIL_GOVERNS allows EXHAUSTED_REPAIR_SEARCH_WITH_PROOF. "
                    "The live evidence shows exhaustive search, zero executable candidates, "
                    "family-owned repair-blocked proof, and no enabled Design Guide action CTA."
                ),
            }
    if sid == "combined_fail_action":
        if not has_action and locked_no_repair and executable_count == 0 and search_exhaustive:
            return {
                "contract_decision": "EXPECTATION_STALE_ACCEPT_BLOCKED_WITH_LOCKED_NO_REPAIR_EVIDENCE",
                "repair_candidate_available": False,
                "ladder_exhausted_correctly": True,
                "blocker_proof_complete": bool(
                    diag.get("exact_blockers_by_family_present")
                    or legal_repair_exists is False
                    or locked_repair_blocked is True
                ),
                "final_publication_cta_should_be_disabled": True,
                "reason": (
                    "The live state selected LOCKED_NO_REPAIR, exposes no enabled Design Guide action CTA, "
                    "and debug evidence shows no executor-backed combined repair candidate. "
                    "Because LOCKED_NO_REPAIR has priority when repair variables are blocked/unavailable, "
                    "the visual representative expectation should not require ACTION for this recipe unless "
                    "a separate contract proves a legal combined repair candidate exists."
                ),
            }
    return {
        "contract_decision": "PRODUCT_CONTRACT_GAP_NEEDS_FAMILY_FIX",
        "repair_candidate_available": None,
        "ladder_exhausted_correctly": None,
        "blocker_proof_complete": False,
        "final_publication_cta_should_be_disabled": None,
        "reason": "The artifact does not prove legal no-repair; keep ACTION expectation and audit family candidate publication.",
    }


def _build_report(payload: dict[str, Any]) -> str:
    lines = [
        "# Design Guide ACTION vs BLOCKED Family Contract Audit",
        "",
        "## Executive Summary",
        "",
        f"Status: `{payload.get('status')}`",
        f"Source snapshot: `{payload.get('source_snapshot')}`",
        f"Rows audited: `{len(payload.get('rows') or [])}`",
        "",
        "## Decisions",
        "",
    ]
    for row in payload.get("rows") or []:
        lines.extend(
            [
                f"### {row.get('scenario_id')}",
                "",
                f"- Selected family: `{row.get('selected_family_id')}`",
                f"- Observed statuses: `{', '.join(row.get('observed_statuses') or [])}`",
                f"- Contract decision: `{row.get('contract_decision')}`",
                f"- Repair candidate available: `{row.get('repair_candidate_available')}`",
                f"- Ladder/search exhausted correctly: `{row.get('ladder_exhausted_correctly')}`",
                f"- Blocker proof complete: `{row.get('blocker_proof_complete')}`",
                f"- CTA should be disabled: `{row.get('final_publication_cta_should_be_disabled')}`",
                f"- Reason: {row.get('reason')}",
                "",
            ]
        )
    lines.extend(
        [
            "## Contract Sources",
            "",
            "- `artifacts/contracts/families/bending_fail_governs.json`",
            "- `artifacts/contracts/families/combined_bending_shear_fail.json`",
            "- `artifacts/contracts/families/underdesign_repair_invariant.json`",
            "- `artifacts/contracts/families/family_selection_contract.json`",
            "",
            "## Next Safe Step",
            "",
            "Update only the representative browser visual expectations for rows whose decision is "
            "`EXPECTATION_STALE_ACCEPT_BLOCKED...`, then rerun the family browser visual and trace-gap "
            "classification snapshots. Do not change family runtime or CTA/apply semantics for these rows.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    source = _latest_visual_snapshot()
    visual = json.loads(source.read_text(encoding="utf-8"))
    scenarios = {
        str(row.get("scenario_id")): row
        for row in visual.get("scenarios") or []
        if row.get("scenario_id") in TARGET_SCENARIOS
    }
    rows = []
    for scenario_id in TARGET_SCENARIOS:
        diag = _scenario_diagnostics(scenarios.get(scenario_id, {"scenario_id": scenario_id}))
        rows.append({**diag, **_decision_for_scenario(diag)})

    status = "PASS" if all(
        row.get("contract_decision") != "PRODUCT_CONTRACT_GAP_NEEDS_FAMILY_FIX" for row in rows
    ) else "PARTIAL"
    stamp = _datetime_stamp()
    payload = {
        "schema": "design_guide_action_vs_blocked_family_contract_audit.v1",
        "status": status,
        "created_at": stamp,
        "source_snapshot": str(source),
        "contracts": {
            "bending_fail": _contract_summary(ROOT / "artifacts/contracts/families/bending_fail_governs.json"),
            "combined_bending_shear_fail": _contract_summary(
                ROOT / "artifacts/contracts/families/combined_bending_shear_fail.json"
            ),
            "underdesign_repair_invariant": _contract_summary(
                ROOT / "artifacts/contracts/families/underdesign_repair_invariant.json"
            ),
        },
        "rows": rows,
        "product_behaviour_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtimes_changed": False,
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_DIR / f"design_guide_action_vs_blocked_family_contract_audit_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_action_vs_blocked_family_contract_audit_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(_build_report(payload), encoding="utf-8")
    print("design_guide_action_vs_blocked_family_contract_audit", status)
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
