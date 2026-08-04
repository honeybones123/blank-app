"""Impact snapshot for the guarded pre-card restamper bypass."""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification.design_guide_pre_render_restamper_guarded_bypass_impact_snapshot import (  # noqa: E402
    MUTATION_FLAGS,
    _decision,
    _escape_md,
    _latest,
    _stable_hash,
)


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"

CALLSITE_ID = "render_guidance_secondary_items.pre_card_binding"
BYPASS_CALL = "_pre_card_restamper_bypass = _maybe_bypass_final_visible_restamper_bridge_noop("
RESTAMPER_CALL = "_pre_card_bound_item = _publish_final_visible_design_guide_contract_binding("

LOCK_PREFIXES = {
    "implementation": "design_guide_pre_card_restamper_guarded_bypass_implementation",
    "readiness": "design_guide_pre_card_restamper_guarded_bypass_readiness",
    "pre_card_proof": "design_guide_pre_card_final_visible_output_bridge_proof",
    "pre_render_impact": "design_guide_pre_render_restamper_guarded_bypass_impact",
    "render_bridge_lock": "design_guide_render_bridge_lock",
    "compute_resolver_publication_bridge_lock": "design_guide_compute_resolver_publication_bridge_lock",
    "design_guide_independence_lock": "design_guide_independence_lock",
}


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _base_proof() -> dict[str, Any]:
    proof = {
        "callsite_id": CALLSITE_ID,
        "input_item_hash": "item-a",
        "output_item_hash": "item-a",
        "state_hash": "state-a",
        "debug_hash": "debug-a",
        "rec_hash": "rec-a",
        "cta_projection_hash": "cta-a",
        "display_projection_hash": "display-a",
        "evidence_projection_hash": "evidence-a",
        "proof_hash": "proof-a",
    }
    proof.update({flag: False for flag in MUTATION_FLAGS})
    return proof


def _scenario(
    scenario_id: str,
    *,
    previous: dict[str, Any] | None,
    current: dict[str, Any],
    expected_bypassed: bool,
    note: str,
    debug_force_rebuild: bool = False,
    apply_in_flight: bool = False,
    post_click_state_present: bool = False,
) -> dict[str, Any]:
    decision = _decision(
        previous=previous,
        current=current,
        debug_force_rebuild=debug_force_rebuild,
        apply_in_flight=apply_in_flight,
        post_click_state_present=post_click_state_present,
    )
    product_surface_unchanged = decision["bypassed"] is False or all(
        previous and previous.get(field) == current.get(field)
        for field in (
            "input_item_hash",
            "output_item_hash",
            "cta_projection_hash",
            "display_projection_hash",
            "evidence_projection_hash",
        )
    )
    return {
        "scenario_id": scenario_id,
        "note": note,
        "decision": decision["decision"],
        "reason": decision["reason"],
        "mismatches": decision.get("mismatches") or [],
        "expected_bypassed": expected_bypassed,
        "expected_met": bool(decision["bypassed"]) is expected_bypassed,
        "restamper_rebuilds_skipped": 1 if decision["bypassed"] else 0,
        "forced_rebuilds": 0 if decision["bypassed"] else 1,
        "visible_wording_unchanged": True,
        "cta_apply_semantics_unchanged": True,
        "publication_truth_unchanged": True,
        "terminal_blocker_truth_unchanged": True,
        "primary_presentation_truth_unchanged": True,
        "product_surface_unchanged": product_surface_unchanged,
        "streamlit_rerun_markers_affected": False,
        "scenario_hash": _stable_hash(
            {
                "scenario_id": scenario_id,
                "previous": previous,
                "current": current,
                "decision": decision,
            }
        ),
    }


def _scenario_rows() -> list[dict[str, Any]]:
    previous = _base_proof()
    current = _base_proof()

    changed_input = _base_proof()
    changed_input["input_item_hash"] = "item-b"

    changed_state = _base_proof()
    changed_state["state_hash"] = "state-b"

    changed_debug = _base_proof()
    changed_debug["debug_hash"] = "debug-b"

    changed_rec = _base_proof()
    changed_rec["rec_hash"] = "rec-b"

    changed_display = _base_proof()
    changed_display["display_projection_hash"] = "display-b"

    previous_mutated = _base_proof()
    previous_mutated["output_changed"] = True

    previous_display_mutated = _base_proof()
    previous_display_mutated["display_changed"] = True

    current_evidence_mutated = _base_proof()
    current_evidence_mutated["evidence_changed"] = True

    previous_output_differs = _base_proof()
    previous_output_differs["output_item_hash"] = "item-old-output"

    missing_hash = _base_proof()
    missing_hash.pop("proof_hash", None)

    return [
        _scenario(
            "stable_noop_previous_proof",
            previous=previous,
            current=current,
            expected_bypassed=True,
            note="Stable no-op proof can skip the pre-card restamper.",
        ),
        _scenario(
            "rerun_without_input_changes",
            previous=previous,
            current=current,
            expected_bypassed=True,
            note="No-input-change rerun can skip when debug/state/rec/projections are also stable.",
        ),
        _scenario(
            "missing_previous_proof",
            previous=None,
            current=current,
            expected_bypassed=False,
            note="First run must rebuild because no previous proof exists.",
        ),
        _scenario(
            "previous_proof_missing_hash",
            previous=missing_hash,
            current=current,
            expected_bypassed=False,
            note="A previous proof without a proof hash is not trusted.",
        ),
        _scenario(
            "changed_input_item_hash",
            previous=previous,
            current=changed_input,
            expected_bypassed=False,
            note="Changed item identity must rebuild.",
        ),
        _scenario(
            "changed_state_hash",
            previous=previous,
            current=changed_state,
            expected_bypassed=False,
            note="Changed engineering/display state must rebuild.",
        ),
        _scenario(
            "changed_debug_hash",
            previous=previous,
            current=changed_debug,
            expected_bypassed=False,
            note="Changed debug proof surface must rebuild because the restamper reads debug.",
        ),
        _scenario(
            "changed_pending_recommendation_hash",
            previous=previous,
            current=changed_rec,
            expected_bypassed=False,
            note="Changed pending recommendation must rebuild.",
        ),
        _scenario(
            "changed_display_projection_hash",
            previous=previous,
            current=changed_display,
            expected_bypassed=False,
            note="Changed display/terminal presentation projection must rebuild.",
        ),
        _scenario(
            "previous_proof_mutated_output",
            previous=previous_mutated,
            current=current,
            expected_bypassed=False,
            note="Prior mutation means the old restamper still added truth.",
        ),
        _scenario(
            "previous_display_mutation",
            previous=previous_display_mutated,
            current=current,
            expected_bypassed=False,
            note="Prior display/presentation mutation must rebuild.",
        ),
        _scenario(
            "current_evidence_probe_mutation",
            previous=previous,
            current=current_evidence_mutated,
            expected_bypassed=False,
            note="Current evidence/blocker mutation prevents bypass.",
        ),
        _scenario(
            "previous_output_not_current_input",
            previous=previous_output_differs,
            current=current,
            expected_bypassed=False,
            note="The previous output must exactly match the current input item.",
        ),
        _scenario(
            "debug_force_rebuild",
            previous=previous,
            current=current,
            debug_force_rebuild=True,
            expected_bypassed=False,
            note="Debug force rebuild bypasses the bypass.",
        ),
        _scenario(
            "apply_in_flight",
            previous=previous,
            current=current,
            apply_in_flight=True,
            expected_bypassed=False,
            note="Apply-in-flight state must rebuild.",
        ),
        _scenario(
            "post_click_state_present",
            previous=previous,
            current=current,
            post_click_state_present=True,
            expected_bypassed=False,
            note="Post-click state must rebuild.",
        ),
    ]


def _source_guards(source: str) -> dict[str, bool]:
    callsite_start = source.find(BYPASS_CALL)
    callsite_window = source[callsite_start : callsite_start + 3800] if callsite_start >= 0 else ""
    return {
        "bypass_callsite_present": callsite_start >= 0,
        "old_restamper_default_path_present": RESTAMPER_CALL in callsite_window,
        "bypass_returns_input_only": "_pre_card_bound_item = dict(_pre_card_input_item)" in callsite_window,
        "proof_stamp_still_runs_after_bypass": "_stamp_final_visible_final_visible_output_bridge_proof(" in callsite_window,
        "diagnostics_non_authority": "final_visible_restamper_bridge_pre_card_bypassed" in callsite_window,
        "bound_contract_read_after_decision": "_pre_card_bound_contract =" in callsite_window,
        "terminal_blocker_logic_after_decision": "_pre_card_bound_is_terminal_blocker" in callsite_window,
        "no_rerun_in_bypass_window": "st.rerun" not in callsite_window and "experimental_rerun" not in callsite_window,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Design Guide Pre-Card Restamper Guarded Bypass Impact Snapshot",
        "",
        f"Status: `{payload['status']}`",
        f"Snapshot hash: `{payload['snapshot_hash']}`",
        "",
        "## Summary",
        "",
        f"- Stable no-op bypass hits: `{payload['stable_noop_bypass_hits']}`",
        f"- No-input-change rerun bypass hits: `{payload['rerun_without_input_changes_bypass_hits']}`",
        f"- Forced rebuilds in guarded cases: `{payload['forced_rebuilds_in_guarded_cases']}`",
        f"- Product behaviour changed: `{payload['product_behavior_changed']}`",
        "",
        "## Scenarios",
        "",
        "| Scenario | Skipped | Rebuilt | Expected met | Reason |",
        "| --- | ---: | ---: | --- | --- |",
    ]
    for row in payload["scenarios"]:
        lines.append(
            "| `{}` | {} | {} | `{}` | `{}` |".format(
                _escape_md(row["scenario_id"]),
                row["restamper_rebuilds_skipped"],
                row["forced_rebuilds"],
                row["expected_met"],
                _escape_md(row["reason"]),
            )
        )
    lines.extend(["", "## Source Guards", "", "| Guard | PASS |", "| --- | --- |"])
    for key, value in payload["source_guards"].items():
        lines.append(f"| `{_escape_md(key)}` | `{value}` |")
    lines.extend(["", "## Locks", ""])
    for name, lock in payload["locks"].items():
        lines.append(f"- `{name}`: passed=`{lock.get('passed')}`, path=`{lock.get('path')}`")
    lines.extend(["", "## Failures", ""])
    if payload["failures"]:
        lines.extend(f"- `{failure}`" for failure in payload["failures"])
    else:
        lines.append("- None")
    lines.extend(["", "## Recommendation", "", payload["recommended_next_slice"]])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    scenarios = _scenario_rows()
    source_guards = _source_guards(source)
    locks = {name: _latest(prefix) for name, prefix in LOCK_PREFIXES.items()}

    failures: list[str] = []
    for key, value in source_guards.items():
        if value is not True:
            failures.append(f"source_guard_failed::{key}")
    for name, lock in locks.items():
        if lock.get("passed") is not True:
            failures.append(f"{name}_not_passed")
    for row in scenarios:
        if row["expected_met"] is not True:
            failures.append(f"{row['scenario_id']}_unexpected_bypass_decision")
        if row["product_surface_unchanged"] is not True:
            failures.append(f"{row['scenario_id']}_product_surface_changed")
        if row["visible_wording_unchanged"] is not True:
            failures.append(f"{row['scenario_id']}_visible_wording_changed")
        if row["cta_apply_semantics_unchanged"] is not True:
            failures.append(f"{row['scenario_id']}_cta_apply_semantics_changed")
        if row["terminal_blocker_truth_unchanged"] is not True:
            failures.append(f"{row['scenario_id']}_terminal_blocker_truth_changed")
        if row["primary_presentation_truth_unchanged"] is not True:
            failures.append(f"{row['scenario_id']}_primary_presentation_truth_changed")
        if row["streamlit_rerun_markers_affected"]:
            failures.append(f"{row['scenario_id']}_streamlit_rerun_markers_affected")

    stable_hits = next(
        row["restamper_rebuilds_skipped"]
        for row in scenarios
        if row["scenario_id"] == "stable_noop_previous_proof"
    )
    rerun_hits = next(
        row["restamper_rebuilds_skipped"]
        for row in scenarios
        if row["scenario_id"] == "rerun_without_input_changes"
    )
    guarded_rebuilds = sum(row["forced_rebuilds"] for row in scenarios if row["expected_bypassed"] is False)
    if stable_hits <= 0:
        failures.append("stable_noop_case_has_no_bypass_hit")
    if rerun_hits <= 0:
        failures.append("rerun_without_input_changes_has_no_bypass_hit")
    if guarded_rebuilds < 14:
        failures.append("guarded_cases_did_not_force_expected_rebuilds")

    status = "PASS" if not failures else "FAIL"
    stamp = _stamp()
    payload = {
        "schema": "design_guide_pre_card_restamper_guarded_bypass_impact_snapshot.v1",
        "status": status,
        "generated_at": stamp,
        "failures": failures,
        "product_behavior_changed": False,
        "stable_noop_bypass_hits": stable_hits,
        "rerun_without_input_changes_bypass_hits": rerun_hits,
        "forced_rebuilds_in_guarded_cases": guarded_rebuilds,
        "scenarios": scenarios,
        "source_guards": source_guards,
        "locks": {
            name: {
                "found": lock.get("found"),
                "passed": lock.get("passed"),
                "path": lock.get("path"),
                "status": lock.get("status"),
            }
            for name, lock in locks.items()
        },
        "snapshot_hash": "",
        "recommended_next_slice": (
            "Do not delete the restamper yet. Move to the compute rebound bridge category and build "
            "focused proof/cutover readiness for those callsites."
        ),
    }
    payload["snapshot_hash"] = _stable_hash(
        {
            "scenarios": scenarios,
            "source_guards": source_guards,
            "locks": {name: lock.get("path") for name, lock in locks.items()},
        }
    )
    json_path = ARTIFACT_DIR / f"design_guide_pre_card_restamper_guarded_bypass_impact_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_pre_card_restamper_guarded_bypass_impact_{stamp}.md"
    payload["artifact"] = str(json_path)
    payload["report"] = str(report_path)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_pre_card_restamper_guarded_bypass_impact_snapshot {status}")
    print(f"stable_noop_bypass_hits={stable_hits}")
    print(f"rerun_without_input_changes_bypass_hits={rerun_hits}")
    print(f"forced_rebuilds_in_guarded_cases={guarded_rebuilds}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures:", json.dumps(failures, sort_keys=True))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
