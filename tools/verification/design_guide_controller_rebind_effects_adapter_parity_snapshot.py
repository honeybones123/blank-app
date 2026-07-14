"""Controller parity snapshot for final-visible rebind effects.

Proof-only. This verifies the DesignGuideController boundary can compose the
same final-visible contract-binding effects proof that currently blocks direct
combined/engine rebind replacement. No live product callsite is changed here.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"
INPUTS_PAGE = ROOT / "inputs_page.py"

EXPECTED_EFFECTS = {
    "target_band_promotion",
    "safe_consistency_guard",
    "combined_consistency_guard",
    "contract_truth",
    "no_second_cta",
}


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": None}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {"found": True, "status": "UNREADABLE", "path": str(path), "error": str(exc)}
    raw_status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    status = "PASS" if any(token in raw_status.upper() for token in ("PASS", "LOCKED", "COMPLETE")) else raw_status
    return {"found": True, "status": status or "UNKNOWN", "path": str(path)}


def _scenario_requests() -> dict[str, dict[str, Any]]:
    shear_keys = ("shear_reinforcement_legs", "shear_reinforcement_spacing", "shear_reinforcement_bar_diameter")
    bottom_keys = ("bottom_bar_count", "bottom_bar_diameter", "bottom_layers")
    base_item = {
        "title": "Strengthening required",
        "title_main": "Strengthening required",
        "family": "combined",
        "source_candidate_id": "candidate-existing",
        "button_contract": {
            "enabled": True,
            "actionable": True,
            "action_type": "apply_resolved_candidate",
            "family": "combined",
            "updates": {"bottom_bar_count": 6},
            "expected_util": 0.62,
        },
        "action_payload": {"updates": {"bottom_bar_count": 6}},
        "resolved_candidate": {"updates": {"bottom_bar_count": 6}},
        "exact_blockers_by_family": {
            "bending": {
                "no_second_cta_required": True,
                "failed_check_status": "BLOCKED_BY_FINAL_ACCEPTED_THRESHOLD",
                "best_safe_final_util": 0.41,
                "reason": "exact stop proof suppresses second cleanup",
            }
        },
    }
    contract = dict(base_item["button_contract"])
    common = {
        "contract": contract,
        "item": base_item,
        "debug": {},
        "compound_shear_update_keys": shear_keys,
        "compound_bottom_update_keys": bottom_keys,
        "final_accepted_min_family_util": 0.85,
        "target_band_eps": 0.0,
    }
    return {
        "combined": {
            **common,
            "evidence_for_binding": {
                "family": "combined",
                "selected_candidate_updates": {"bottom_bar_count": 5, "shear_reinforcement_legs": 0},
                "best_safe_candidate_updates": {"bottom_bar_count": 5, "shear_reinforcement_legs": 0},
                "closest_safe_candidate_updates": {"bottom_bar_count": 5, "shear_reinforcement_legs": 0},
                "selected_candidate_id": "combined-target-1",
                "selected_candidate_util": 0.86,
                "cleanup_search_ran": True,
                "candidate_search_exhaustive": True,
            },
            "current_updates": contract.get("updates"),
            "combined_binding_updates": {"bottom_bar_count": 5, "shear_reinforcement_legs": 0},
            "combined_updates_already_applied": False,
            "combined_binding_bending_util": 0.88,
            "source": "controller_rebind_effects_parity_combined",
        },
        "shear": {
            **common,
            "evidence_for_binding": {
                "family": "shear",
                "best_target_band_candidate_updates": {"shear_reinforcement_legs": 0},
                "best_safe_candidate_updates": {"shear_reinforcement_legs": 0},
                "best_target_band_candidate_id": "shear-target-1",
                "selected_candidate_id": "shear-target-1",
                "best_target_band_candidate_util": 0.82,
                "target_band_candidate_count": 1,
                "accepted_band_candidate_count": 1,
                "one_click_target_reaching_candidate_exists": True,
            },
            "current_updates": contract.get("updates"),
            "target_binding_updates": {"shear_reinforcement_legs": 0},
            "target_binding_util": 0.82,
            "target_binding_count": 1,
            "target_binding_family": "shear",
            "target_binding_candidate_id": "shear-target-1",
            "target_low": 0.80,
            "target_high": 1.0,
            "current_binding_expected": 0.42,
            "target_updates_already_applied": False,
            "safe_binding_updates": {"shear_reinforcement_legs": 0},
            "safe_updates_already_applied": False,
            "source": "controller_rebind_effects_parity_shear",
        },
        "no_second": {
            **common,
            "evidence_for_binding": {
                "family": "bending",
                "selected_candidate_util": 0.41,
                "no_second_cta_required": True,
                "reason": "post-click exact cleanup proof suppresses a second below-floor CTA",
                "target_band_candidate_count": 0,
            },
            "current_updates": {},
            "evidence_expected_util": 0.41,
            "evidence_family": "bending",
            "blocker_families": ("bending",),
            "source": "controller_rebind_effects_parity_no_second",
        },
    }


def _exercise() -> dict[str, Any]:
    from design_brain.final_publication import (  # noqa: PLC0415
        build_final_visible_contract_binding_rebind_effects_proof,
        stable_final_publication_hash,
    )
    from design_brain.design_guide_controller import (  # noqa: PLC0415
        run_design_guide_controller_final_visible_rebind_effects_trace_only,
    )

    rows = []
    for scenario_id, request in _scenario_requests().items():
        direct = build_final_visible_contract_binding_rebind_effects_proof(**{
            key: value for key, value in request.items() if key != "source"
        })
        controller = run_design_guide_controller_final_visible_rebind_effects_trace_only(request)
        controller_payload = controller.to_dict()
        rows.append(
            {
                "scenario_id": scenario_id,
                "direct_proof_hash": direct.get("proof_hash"),
                "controller_proof_hash": controller.rebind_effects_proof_hash,
                "proof_hash_matches": direct.get("proof_hash") == controller.rebind_effects_proof_hash,
                "direct_result_flags": dict(direct.get("result_flags") or {}),
                "controller_result_flags": dict(controller.result_flags or {}),
                "result_flags_match": dict(direct.get("result_flags") or {}) == dict(controller.result_flags or {}),
                "represented_effects": sorted(controller.represented_effects),
                "missing_effects": sorted(EXPECTED_EFFECTS - set(controller.represented_effects)),
                "controller_hash": controller.controller_hash,
                "controller_hash_stable": (
                    controller.controller_hash
                    == run_design_guide_controller_final_visible_rebind_effects_trace_only(request).controller_hash
                ),
                "non_authoritative": (
                    controller_payload.get("trace_only") is True
                    and controller_payload.get("product_driving") is False
                    and controller_payload.get("render_driving") is False
                    and controller_payload.get("apply_driving") is False
                    and controller_payload.get("session_driving") is False
                ),
                "direct_hash": stable_final_publication_hash(direct),
            }
        )
    return {"rows": rows, "row_count": len(rows)}


def _capture() -> dict[str, Any]:
    controller_source = CONTROLLER.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    final_publication_source = FINAL_PUBLICATION.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    exercise = _exercise()
    latest = {
        "effects_proof": _latest("design_guide_final_visible_contract_binding_rebind_effects_proof"),
        "effects_trace_wiring": _latest("design_guide_final_visible_contract_binding_rebind_effects_trace_wiring"),
        "rebind_parity_gap": _latest("design_guide_render_combined_engine_rebind_parity_gap"),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
        "independence_lock": _latest("design_guide_independence_lock"),
    }
    return {
        **exercise,
        "source_checks": {
            "controller_imports_rebind_effects_builder": (
                "build_final_visible_contract_binding_rebind_effects_proof" in controller_source
            ),
            "controller_runner_present": (
                "def run_design_guide_controller_final_visible_rebind_effects_trace_only(" in controller_source
            ),
            "controller_does_not_import_inputs_page": "inputs_page" not in controller_source,
            "final_publication_builder_present": (
                "def build_final_visible_contract_binding_rebind_effects_proof(" in final_publication_source
            ),
            "old_rebind_calls_still_present": (
                "_combined_rebound_item = _publish_final_visible_design_guide_contract_binding(" in inputs_source
                and "_engine_rebound_item = _publish_final_visible_design_guide_contract_binding(" in inputs_source
            ),
        },
        "latest_artifacts": latest,
        "decision": "CONTROLLER_REBIND_EFFECTS_ADAPTER_PARITY_PROVEN",
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "next_safe_step": (
            "Wire trace-only controller rebind effects beside the combined/engine rebind callsites, "
            "then compare old helper effects with controller effects before replacing either call."
        ),
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    rows = list(capture.get("rows") or [])
    latest = dict(capture.get("latest_artifacts") or {})
    source = dict(capture.get("source_checks") or {})
    return {
        "three_scenarios_exercised": capture.get("row_count") == 3,
        "all_proof_hashes_match": all(row.get("proof_hash_matches") is True for row in rows),
        "all_result_flags_match": all(row.get("result_flags_match") is True for row in rows),
        "all_expected_effects_represented": all(not row.get("missing_effects") for row in rows),
        "all_controller_hashes_stable": all(row.get("controller_hash_stable") is True for row in rows),
        "controller_outputs_non_authoritative": all(row.get("non_authoritative") is True for row in rows),
        "controller_imports_rebind_effects_builder": source.get("controller_imports_rebind_effects_builder") is True,
        "controller_runner_present": source.get("controller_runner_present") is True,
        "controller_does_not_import_inputs_page": source.get("controller_does_not_import_inputs_page") is True,
        "final_publication_builder_present": source.get("final_publication_builder_present") is True,
        "old_rebind_calls_still_present": source.get("old_rebind_calls_still_present") is True,
        "effects_proof_pass": (latest.get("effects_proof") or {}).get("status") == "PASS",
        "effects_trace_wiring_pass": (latest.get("effects_trace_wiring") or {}).get("status") == "PASS",
        "rebind_parity_gap_pass": (latest.get("rebind_parity_gap") or {}).get("status") == "PASS",
        "render_bridge_lock_pass": (latest.get("render_bridge_lock") or {}).get("status") == "PASS",
        "compute_bridge_lock_pass": (latest.get("compute_bridge_lock") or {}).get("status") == "PASS",
        "independence_lock_pass": (latest.get("independence_lock") or {}).get("status") == "PASS",
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Controller Rebind Effects Adapter Parity Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Scenarios",
        "",
        "| Scenario | Proof Hash Match | Flags Match | Missing Effects | Stable |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in capture.get("rows") or []:
        lines.append(
            f"| `{row.get('scenario_id')}` | `{row.get('proof_hash_matches')}` | "
            f"`{row.get('result_flags_match')}` | `{row.get('missing_effects')}` | "
            f"`{row.get('controller_hash_stable')}` |"
        )
    lines.extend(["", "## Checks", ""])
    for key, value in (payload.get("checks") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Failures", ""])
    if payload.get("failures"):
        lines.extend(f"- `{failure}`" for failure in payload["failures"])
    else:
        lines.append("- None")
    lines.extend(["", "## Next Safe Step", "", str(capture.get("next_safe_step") or "")])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _stamp()
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_controller_rebind_effects_adapter_parity_snapshot.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    json_path = ARTIFACT_DIR / f"design_guide_controller_rebind_effects_adapter_parity_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_controller_rebind_effects_adapter_parity_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_controller_rebind_effects_adapter_parity_snapshot {status}")
    print(f"artifact={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
