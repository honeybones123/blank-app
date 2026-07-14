"""
Proof-only audit for representative family visual-state expectation gaps.

This verifier consumes the latest family browser/live visual consistency and
trace-gap classification artifacts. It does not change product behaviour,
family runtimes, visible wording, CTA/apply semantics, or verifier
expectations. It identifies whether remaining ACTION-vs-BLOCKED rows are
format/parser issues or require a product contract decision.
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

from tools.verification.design_guide_browser_live_visual_consistency_snapshot import _stable_hash  # noqa: E402


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _datetime_stamp() -> str:
    return datetime.now().replace(microsecond=0).isoformat().replace(":", "-")


def _latest_artifact(prefix: str, schema: str) -> Path:
    candidates = sorted(
        ARTIFACT_DIR.glob(f"{prefix}_*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for candidate in candidates:
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except Exception:
            continue
        if payload.get("schema") == schema:
            return candidate
    raise SystemExit(f"No artifact found for {prefix} / {schema}")


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _coherent_blocked_card(scenario: dict[str, Any]) -> bool:
    design_text = str(_as_dict(scenario.get("design_guide")).get("text_sample") or "")
    statuses = {
        str(value).upper()
        for value in _as_dict(scenario.get("classification")).get("observed_statuses") or []
    }
    return bool(
        "BLOCKED" in statuses
        and (
            "blocked" in design_text.lower()
            or "repair required" in design_text.lower()
            or "repair blocked" in design_text.lower()
        )
    )


def _has_final_publication_hash(scenario: dict[str, Any]) -> bool:
    probe = _as_dict(_as_dict(scenario.get("classification")).get("recipe_probe"))
    hashes = _as_dict(probe.get("publication_hashes"))
    state = _as_dict(scenario.get("browser_state"))
    state_hashes = _as_dict(state.get("final_publication_hashes"))
    return bool(
        hashes.get("publication_hash")
        or hashes.get("authority_hash")
        or state_hashes.get("publication_hash")
        or state_hashes.get("authority_hash")
    )


def _row_for_gap(gap: dict[str, Any], scenario: dict[str, Any]) -> dict[str, Any]:
    classification = _as_dict(scenario.get("classification"))
    recipe_probe = _as_dict(classification.get("recipe_probe"))
    design_text = str(_as_dict(scenario.get("design_guide")).get("text_sample") or "")
    expected_visual_state = str(scenario.get("expected_visual_state") or "")
    observed_statuses = [
        str(value).upper()
        for value in classification.get("observed_statuses") or []
    ]
    selected_family_id = str(classification.get("selected_family_id") or "")
    coherent_blocked = _coherent_blocked_card(scenario)
    has_hash = _has_final_publication_hash(scenario)
    action_buttons = list(_as_dict(_as_dict(scenario.get("checks")).get("cta")).get("action_buttons") or [])
    requested_recipe = recipe_probe.get("requested_recipe") or scenario.get("recipe")
    applied_recipe = recipe_probe.get("applied_recipe")
    applied_recipe_exposed = bool(applied_recipe)

    if coherent_blocked and has_hash and not action_buttons:
        decision = "CONTRACT_DECISION_REQUIRED"
        reason = (
            "Final card is a coherent BLOCKED publication with publication hash and no action CTA; "
            "decide whether the representative recipe should expect BLOCKED or whether the family "
            "contract requires an executor-backed repair CTA."
        )
    else:
        decision = "UNRESOLVED_VISUAL_OR_TRACE_GAP"
        reason = "The remaining expectation gap is not proven to be a coherent final BLOCKED publication."

    return {
        "scenario_id": scenario.get("scenario_id"),
        "recipe": scenario.get("recipe"),
        "requested_recipe": requested_recipe,
        "applied_recipe": applied_recipe,
        "applied_recipe_exposed": applied_recipe_exposed,
        "selected_family_id": selected_family_id,
        "expected_visual_state": expected_visual_state,
        "observed_statuses": sorted(set(observed_statuses)),
        "action_button_count": len(action_buttons),
        "has_final_publication_hash": has_hash,
        "coherent_blocked_card": coherent_blocked,
        "gap_observation": gap.get("observation"),
        "decision": decision,
        "reason": reason,
        "design_guide_text_hash": _stable_hash(design_text) if design_text else None,
        "design_guide_text_sample": design_text[:900],
        "product_behaviour_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtimes_changed": False,
    }


def _build_report(payload: dict[str, Any]) -> str:
    lines = [
        "# Design Guide Family Visual Expectation Contract Audit",
        "",
        "## Executive Summary",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{payload.get('decision')}`",
        f"Rows audited: `{len(payload.get('rows') or [])}`",
        f"Source visual snapshot: `{payload.get('source_visual_snapshot')}`",
        f"Source classification snapshot: `{payload.get('source_classification_snapshot')}`",
        "",
        "## Rows",
        "",
    ]
    for row in payload.get("rows") or []:
        lines.extend(
            [
                f"### {row.get('scenario_id')}",
                "",
                f"- Recipe: `{row.get('recipe')}`",
                f"- Selected family: `{row.get('selected_family_id')}`",
                f"- Expected visual state: `{row.get('expected_visual_state')}`",
                f"- Observed statuses: `{', '.join(row.get('observed_statuses') or [])}`",
                f"- Action button count: `{row.get('action_button_count')}`",
                f"- Final publication hash exposed: `{row.get('has_final_publication_hash')}`",
                f"- Coherent blocked card: `{row.get('coherent_blocked_card')}`",
                f"- Applied recipe exposed: `{row.get('applied_recipe_exposed')}`",
                f"- Decision: `{row.get('decision')}`",
                f"- Reason: {row.get('reason')}",
                "",
            ]
        )
    lines.extend(
        [
            "## Next Safe Step",
            "",
            "Do not update representative expectations or product logic from this audit alone. "
            "For each row, compare the observed BLOCKED publication against the family lock/contract: "
            "if blocked is the intended terminal result, update the representative visual expectation; "
            "if an executor-backed repair should exist, fix the family candidate/CTA contract.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    visual_path = _latest_artifact(
        "design_guide_family_browser_live_visual_consistency",
        "design_guide_family_browser_live_visual_consistency_snapshot.v1",
    )
    classification_path = _latest_artifact(
        "design_guide_family_browser_trace_gap_classification",
        "design_guide_family_browser_trace_gap_classification_snapshot.v1",
    )
    visual_payload = json.loads(visual_path.read_text(encoding="utf-8"))
    classification_payload = json.loads(classification_path.read_text(encoding="utf-8"))

    scenarios = {
        str(row.get("scenario_id")): row
        for row in visual_payload.get("scenarios") or []
        if row.get("scenario_id")
    }
    rows: list[dict[str, Any]] = []
    for gap in classification_payload.get("classified_gaps") or []:
        if gap.get("bucket") != "SCENARIO_EXPECTATION_OR_PRODUCT_CONTRACT_CHECK":
            continue
        scenario = scenarios.get(str(gap.get("scenario_id")))
        if scenario:
            rows.append(_row_for_gap(gap, scenario))

    unresolved = [row for row in rows if row.get("decision") != "CONTRACT_DECISION_REQUIRED"]
    status = "PASS" if rows and not unresolved else ("PARTIAL" if rows else "PASS")
    decision = "CONTRACT_DECISION_REQUIRED" if rows and not unresolved else "NO_CONTRACT_ROWS_FOUND"
    stamp = _datetime_stamp()
    payload = {
        "schema": "design_guide_family_visual_expectation_contract_audit.v1",
        "status": status,
        "decision": decision,
        "created_at": stamp,
        "source_visual_snapshot": str(visual_path),
        "source_classification_snapshot": str(classification_path),
        "rows": rows,
        "product_behaviour_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtimes_changed": False,
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_DIR / f"design_guide_family_visual_expectation_contract_audit_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_family_visual_expectation_contract_audit_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(_build_report(payload), encoding="utf-8")
    print("design_guide_family_visual_expectation_contract_audit", status)
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status in {"PASS", "PARTIAL"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
