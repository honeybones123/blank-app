"""Composed Design Brain family process and churn lock verifier.

This verifier answers the high-level architecture question:

family contract -> chooser -> runtime/ladder -> publication -> CTA/apply

is consistently proven for every tracked governing family, while the known
Design Guide churn-reduction gates remain active and product-safe.

It intentionally composes latest artifacts instead of recursively rerunning the
full browser suite. Use the underlying focused verifiers to refresh evidence
when a gate is stale or failing.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
PROGRESS_DIR = ROOT / "artifacts" / "progress"

TRACKED_FAMILY_COUNT = 9

REQUIRED_GATES: tuple[dict[str, str], ...] = (
    {
        "id": "family_architecture_end_to_end",
        "prefix": "family_architecture_end_to_end_audit",
        "label": "Family architecture end-to-end audit",
    },
    {
        "id": "locked_family_live_wiring",
        "prefix": "locked_family_live_wiring_snapshot",
        "label": "Locked family live wiring snapshot",
    },
    {
        "id": "family_classification_contract",
        "prefix": "family_classification_contract_check",
        "label": "Family classification contract check",
    },
    {
        "id": "family_chooser_regression",
        "prefix": "family_chooser_classification_regression",
        "label": "Family chooser classification regression",
    },
    {
        "id": "family_classification_lock",
        "prefix": "family_classification_lock_verifier",
        "label": "Family classification lock verifier",
    },
    {
        "id": "cta_button_contract",
        "prefix": "cta_button_contract_check",
        "label": "CTA button contract check",
    },
    {
        "id": "design_guide_independence_lock",
        "prefix": "design_guide_independence_lock",
        "label": "Design Guide independence lock",
    },
    {
        "id": "design_guide_render_bridge_lock",
        "prefix": "design_guide_render_bridge_lock",
        "label": "Design Guide render bridge lock",
    },
    {
        "id": "design_guide_compute_resolver_publication_bridge_lock",
        "prefix": "design_guide_compute_resolver_publication_bridge_lock",
        "label": "Design Guide compute resolver/publication bridge lock",
    },
    {
        "id": "design_guide_apply_current_state_safety",
        "prefix": "design_guide_apply_current_state_safety",
        "label": "Design Guide apply current-state safety",
    },
    {
        "id": "duplicate_publication_stamp_bypass_live_impact",
        "prefix": "design_guide_duplicate_publication_stamp_bypass_live_impact",
        "label": "Duplicate publication stamp bypass live impact",
    },
    {
        "id": "card_render_model_bypass_live_impact",
        "prefix": "design_guide_card_render_model_bypass_live_impact",
        "label": "Card render-model bypass live impact",
    },
    {
        "id": "no_input_candidate_search_reuse_live_impact",
        "prefix": "design_guide_no_input_candidate_search_reuse_live_impact",
        "label": "No-input candidate-search reuse live impact",
    },
)


def _status(payload: dict[str, Any]) -> str:
    for key in ("status", "result", "lock_status"):
        value = payload.get(key)
        if not isinstance(value, str):
            continue
        upper = value.upper()
        if "PASS" in upper or "COMPLETE" in upper or "LOCKED" in upper:
            return "PASS"
        if "PARTIAL" in upper:
            return "PARTIAL"
        if "FAIL" in upper or "INCOMPLETE" in upper or "BLOCKED" in upper:
            return "FAIL"
        return value
    if payload.get("passed") is True:
        return "PASS"
    if payload.get("passed") is False:
        return "FAIL"
    return "UNKNOWN"


def _latest(prefix: str) -> dict[str, Any]:
    artifacts = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not artifacts:
        return {
            "found": False,
            "path": None,
            "status": "MISSING",
            "payload": {},
            "passed": False,
        }
    path = artifacts[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - reported in artifact
        return {
            "found": True,
            "path": str(path),
            "status": "UNREADABLE",
            "payload": {},
            "passed": False,
            "error": str(exc),
        }
    status = _status(payload)
    return {
        "found": True,
        "path": str(path),
        "status": status,
        "payload": payload,
        "passed": status == "PASS",
    }


def _progress_file_status() -> dict[str, Any]:
    expected_terms = {
        "family_strategy_program_master_roadmap": (
            PROGRESS_DIR / "family_strategy_program_master_roadmap.md",
            ("family_architecture_end_to_end_audit: PASS", "PASS: 9", "PARTIAL: 0", "FAIL: 0"),
        ),
        "design_guide_smoothness_cleanup_progress": (
            PROGRESS_DIR / "design_guide_smoothness_cleanup_progress.md",
            ("Family architecture audit: PASS", "9 PASS / 0 PARTIAL / 0 FAIL"),
        ),
    }
    output: dict[str, Any] = {}
    for key, (path, terms) in expected_terms.items():
        text = path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""
        output[key] = {
            "path": str(path),
            "found": path.exists(),
            "expected_terms_present": all(term in text for term in terms),
        }
    return output


def _family_process_checks(architecture: dict[str, Any]) -> dict[str, Any]:
    families = list(architecture.get("families") or [])
    per_family: list[dict[str, Any]] = []
    for row in families:
        checks = dict(row.get("checks") or {})
        per_family.append(
            {
                "family_id": row.get("family_id"),
                "status": row.get("status"),
                "contract_passed": checks.get("contract_passed") is True,
                "runtime_or_ladder_passed": checks.get("runtime_or_ladder_passed") is True,
                "lock_passed": checks.get("lock_passed") is True,
                "product_path_evidence_passed": checks.get("product_path_evidence_passed") is True,
                "apply_effect_evidence_passed": checks.get("apply_effect_evidence_passed") is True,
                "gaps": list(row.get("gaps") or []),
            }
        )
    return {
        "tracked_family_count": len(families),
        "all_families_pass": all(row.get("status") == "PASS" for row in families),
        "all_families_have_complete_process": all(
            entry["contract_passed"]
            and entry["runtime_or_ladder_passed"]
            and entry["lock_passed"]
            and entry["product_path_evidence_passed"]
            and entry["apply_effect_evidence_passed"]
            and not entry["gaps"]
            for entry in per_family
        ),
        "per_family": per_family,
    }


def _live_wiring_checks(wiring: dict[str, Any]) -> dict[str, Any]:
    families = list(wiring.get("families") or [])
    shared = dict(wiring.get("shared_ownership") or {})
    return {
        "result_pass": _status(wiring) == "PASS",
        "tracked_family_count": len(families),
        "all_family_wiring_pass": all(_status(dict(row)) == "PASS" for row in families),
        "shared_cta_publication_apply_ui_stay_outside_family": all(
            shared.get(key) is True
            for key in (
                "candidate_evaluation_loop_in_inputs_page",
                "cta_contracts_imported_by_inputs_page",
                "publication_imported_by_inputs_page",
                "publication_gate_exists",
                "apply_routing_exists",
                "one_click_orchestration_exists",
                "ui_session_debug_exists",
            )
        ),
        "shared_ownership": shared,
    }


def _smoothness_checks(gates: dict[str, dict[str, Any]]) -> dict[str, Any]:
    duplicate = gates["duplicate_publication_stamp_bypass_live_impact"]["payload"]
    card = gates["card_render_model_bypass_live_impact"]["payload"]
    candidate = gates["no_input_candidate_search_reuse_live_impact"]["payload"]
    candidate_impact = dict(candidate.get("impact") or {})
    candidate_search_not_exercised = bool(candidate.get("candidate_search_not_exercised"))
    return {
        "duplicate_publication_stamp_bypass_active": (
            duplicate.get("status") == "PASS"
            and duplicate.get("stable_non_debug_bypass_hits", 0) > 0
            and duplicate.get("rerun_without_input_changes_bypass_hits", 0) > 0
            and duplicate.get("forced_rebuilds_in_guarded_cases", 0) > 0
            and duplicate.get("product_behavior_changed") is False
        ),
        "card_render_model_bypass_active": (
            card.get("status") == "PASS"
            and card.get("stable_non_debug_bypass_hits", 0) > 0
            and card.get("rerun_without_input_changes_bypass_hits", 0) > 0
            and card.get("forced_rebuilds_in_guarded_cases", 0) > 0
            and card.get("product_behavior_changed") is False
        ),
        "candidate_search_reuse_active": (
            candidate.get("status") == "PASS"
            and (
                (
                    candidate_impact.get("stable_no_input_reuse_hits", 0) > 0
                    and candidate_impact.get("total_reuse_hits", 0) > 0
                )
                or candidate_search_not_exercised
            )
            and candidate_impact.get("stable_no_input_force_rebuilds", -1) == 0
            and candidate.get("product_behavior_changed") is False
            and candidate_impact.get("product_behaviour_changed") is False
        ),
        "candidate_profile_status_accepted": candidate_impact.get("profile_status") in {"PASS", "PARTIAL"},
        "known_churn_reducers_product_safe": all(
            payload.get("product_behavior_changed") is False
            for payload in (duplicate, card, candidate)
        ),
        "impact_summary": {
            "duplicate_publication_stamp_bypass_hits": duplicate.get("stable_non_debug_bypass_hits"),
            "card_render_model_bypass_hits": card.get("stable_non_debug_bypass_hits"),
            "candidate_search_reuse_hits": candidate_impact.get("stable_no_input_reuse_hits"),
            "candidate_profile_status": candidate_impact.get("profile_status"),
        },
    }


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Design Brain Family Process And Churn Lock",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Summary",
        "",
        f"- Family process lock: `{payload['summary']['family_process_lock']}`",
        f"- Live wiring lock: `{payload['summary']['live_wiring_lock']}`",
        f"- Publication/CTA/apply lock: `{payload['summary']['publication_cta_apply_lock']}`",
        f"- Churn guard lock: `{payload['summary']['churn_guard_lock']}`",
        f"- Progress files current: `{payload['summary']['progress_files_current']}`",
        "",
        "## Family Process",
        "",
        "| Family | Status | Contract | Runtime/Ladder | Lock | Product Path | Apply/No-op | Gaps |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["family_process"]["per_family"]:
        lines.append(
            "| `{family}` | `{status}` | `{contract}` | `{runtime}` | `{lock}` | `{product}` | `{apply}` | {gaps} |".format(
                family=row["family_id"],
                status=row["status"],
                contract=row["contract_passed"],
                runtime=row["runtime_or_ladder_passed"],
                lock=row["lock_passed"],
                product=row["product_path_evidence_passed"],
                apply=row["apply_effect_evidence_passed"],
                gaps=", ".join(f"`{gap}`" for gap in row["gaps"]) or "none",
            )
        )
    lines.extend(
        [
            "",
            "## Composed Gates",
            "",
            "| Gate | Status | Artifact |",
            "| --- | --- | --- |",
        ]
    )
    for gate_id, row in payload["gates"].items():
        lines.append(f"| `{gate_id}` | `{row['status']}` | `{row['path']}` |")
    lines.extend(
        [
            "",
            "## Churn Guards",
            "",
            f"- Duplicate publication stamp bypass active: `{payload['smoothness']['duplicate_publication_stamp_bypass_active']}`",
            f"- Card render-model bypass active: `{payload['smoothness']['card_render_model_bypass_active']}`",
            f"- Candidate-search reuse active: `{payload['smoothness']['candidate_search_reuse_active']}`",
            f"- Candidate profile status accepted: `{payload['smoothness']['candidate_profile_status_accepted']}`",
            f"- Product behaviour changed by churn reducers: `{not payload['smoothness']['known_churn_reducers_product_safe']}`",
            "",
            "## Failures",
            "",
        ]
    )
    lines.extend([f"- {failure}" for failure in payload["failures"]] or ["- none"])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    stamp = datetime.now().isoformat(timespec="seconds").replace(":", "-")
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    gates = {gate["id"]: _latest(gate["prefix"]) for gate in REQUIRED_GATES}
    architecture = gates["family_architecture_end_to_end"]["payload"]
    wiring = gates["locked_family_live_wiring"]["payload"]
    family_process = _family_process_checks(architecture)
    live_wiring = _live_wiring_checks(wiring)
    smoothness = _smoothness_checks(gates)
    progress_files = _progress_file_status()

    summary = {
        "family_process_lock": (
            gates["family_architecture_end_to_end"]["passed"]
            and architecture.get("summary") == {"fail": 0, "partial": 0, "pass": TRACKED_FAMILY_COUNT}
            and family_process["tracked_family_count"] == TRACKED_FAMILY_COUNT
            and family_process["all_families_pass"]
            and family_process["all_families_have_complete_process"]
        ),
        "live_wiring_lock": (
            gates["locked_family_live_wiring"]["passed"]
            and live_wiring["tracked_family_count"] == TRACKED_FAMILY_COUNT
            and live_wiring["all_family_wiring_pass"]
            and live_wiring["shared_cta_publication_apply_ui_stay_outside_family"]
        ),
        "publication_cta_apply_lock": all(
            gates[gate_id]["passed"]
            for gate_id in (
                "design_guide_independence_lock",
                "design_guide_render_bridge_lock",
                "design_guide_compute_resolver_publication_bridge_lock",
                "design_guide_apply_current_state_safety",
                "cta_button_contract",
            )
        ),
        "classification_lock": all(
            gates[gate_id]["passed"]
            for gate_id in (
                "family_classification_contract",
                "family_chooser_regression",
                "family_classification_lock",
            )
        ),
        "churn_guard_lock": (
            smoothness["duplicate_publication_stamp_bypass_active"]
            and smoothness["card_render_model_bypass_active"]
            and smoothness["candidate_search_reuse_active"]
            and smoothness["candidate_profile_status_accepted"]
            and smoothness["known_churn_reducers_product_safe"]
        ),
        "progress_files_current": all(row["found"] and row["expected_terms_present"] for row in progress_files.values()),
    }

    failures: list[str] = []
    for gate_id, row in gates.items():
        if not row["passed"]:
            failures.append(f"gate_not_passed:{gate_id}:{row['status']}")
    for name, passed in summary.items():
        if not passed:
            failures.append(f"summary_check_failed:{name}")
    if architecture.get("product_behaviour_changed") not in (False, None):
        failures.append("family_architecture_reported_product_behaviour_changed")
    if family_process["tracked_family_count"] != TRACKED_FAMILY_COUNT:
        failures.append(f"tracked_family_count_mismatch:{family_process['tracked_family_count']}")
    if live_wiring["tracked_family_count"] != TRACKED_FAMILY_COUNT:
        failures.append(f"live_wiring_family_count_mismatch:{live_wiring['tracked_family_count']}")

    payload = {
        "schema": "design_brain_family_process_and_churn_lock_verifier.v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": "PASS" if not failures else "FAIL",
        "lock_status": (
            "Design Brain family process and churn lock complete"
            if not failures
            else "Design Brain family process and churn lock incomplete"
        ),
        "summary": summary,
        "tracked_family_count": TRACKED_FAMILY_COUNT,
        "family_process": family_process,
        "live_wiring": live_wiring,
        "smoothness": smoothness,
        "progress_files": progress_files,
        "gates": {
            gate_id: {
                "path": row["path"],
                "status": row["status"],
                "passed": row["passed"],
            }
            for gate_id, row in gates.items()
        },
        "composition_mode": "latest_pass_artifacts_plus_direct_artifact_checks",
        "scope_note": (
            "This lock proves the currently tracked process/churn gates. It does not claim all future "
            "smoothness or deletion work is complete."
        ),
        "failures": failures,
    }

    artifact_path = ARTIFACT_DIR / f"design_brain_family_process_and_churn_lock_{stamp}.json"
    report_path = AUDIT_DIR / f"design_brain_family_process_and_churn_lock_{stamp}.md"
    payload["artifact"] = str(artifact_path)
    payload["report"] = str(report_path)
    artifact_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    _write_report(payload, report_path)
    print(f"design_brain_family_process_and_churn_lock {payload['status']}")
    print(payload["lock_status"])
    print(f"artifact={artifact_path}")
    print(f"report={report_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
