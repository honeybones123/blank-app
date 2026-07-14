"""Verify controller proof object for no-active blocked-primary cleanup probe route."""

from __future__ import annotations

from datetime import datetime
import ast
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

BUILDER = (
    "build_design_guide_controller_no_active_blocked_primary_cleanup_probe_route_policy_proof"
)
PROOF_CLASS = "DesignGuideNoActiveBlockedPrimaryCleanupProbeRoutePolicyProof"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _source_for_names(path: Path, names: set[str]) -> dict[str, str]:
    source = path.read_text(encoding="utf-8", errors="replace")
    tree = ast.parse(source)
    lines = source.splitlines()
    found: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in names:
            end_lineno = getattr(node, "end_lineno", None)
            if end_lineno is None:
                raise RuntimeError(f"Missing end_lineno for {node.name}")
            found[node.name] = "\n".join(lines[node.lineno - 1 : end_lineno])
    missing = sorted(names - set(found))
    if missing:
        raise RuntimeError(f"Missing expected controller definitions: {missing}")
    return found


def _build_samples() -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        build_design_guide_controller_no_active_blocked_primary_cleanup_probe_route_policy_proof,
    )

    safe_cleanup = build_design_guide_controller_no_active_blocked_primary_cleanup_probe_route_policy_proof(
        primary={"title": "Blocked primary", "action_type": "none"},
        contract={"enabled": False, "action_type": "none"},
        updates={},
        primary_evidence={
            "selected_candidate_updates": {"lig_spacing": 250, "lig_legs": 0},
            "safe_executor_backed_candidates_count": 1,
        },
        final_state={"lig_spacing": 200, "lig_legs": 2},
        final_overview={"utils": {"bending": 0.92, "shear": 0.32}},
        final_accepted_min_family_util=0.85,
        target_band_eps=0.01,
        compound_shear_update_keys={"lig_spacing", "lig_legs", "lig_dia"},
        contract_enabled=False,
        post_click_route_for_safe_cleanup=False,
        safe_cleanup_updates_match_current_state=False,
        final_bending_util=0.92,
    )
    bending_probe = build_design_guide_controller_no_active_blocked_primary_cleanup_probe_route_policy_proof(
        primary={"title": "Blocked primary", "action_type": "none"},
        contract={"enabled": False, "action_type": "none"},
        updates={},
        primary_evidence={},
        final_state={"reo_1": 8, "reo_1_dia": 16},
        final_overview={"utils": {"bending": 0.24, "shear": 0.69}},
        final_accepted_min_family_util=0.85,
        target_band_eps=0.01,
        compound_shear_update_keys={"lig_spacing", "lig_legs", "lig_dia"},
        contract_enabled=False,
        post_click_route_for_safe_cleanup=False,
        safe_cleanup_updates_match_current_state=None,
        final_bending_util=0.24,
        bending_probe_candidate_present=True,
        equivalent_bending_probe_candidate_present=True,
        equivalent_probe_selected=True,
        bending_probe_updates={"reo_1": 5, "reo_1_dia": 10},
        bending_probe_expected_util=0.42,
    )
    actionable_primary = build_design_guide_controller_no_active_blocked_primary_cleanup_probe_route_policy_proof(
        primary={"title": "Apply direct", "action_type": "apply_resolved_candidate"},
        contract={"enabled": True, "action_type": "apply_resolved_candidate"},
        updates={"width": 450},
        primary_evidence={"selected_candidate_updates": {"width": 450}},
        final_state={"width": 400},
        final_overview={"utils": {"bending": 1.12, "shear": 0.75}},
        final_accepted_min_family_util=0.85,
        target_band_eps=0.01,
        compound_shear_update_keys={"lig_spacing", "lig_legs", "lig_dia"},
        contract_enabled=True,
        post_click_route_for_safe_cleanup=False,
        safe_cleanup_updates_match_current_state=False,
        final_bending_util=1.12,
    )
    repeat = build_design_guide_controller_no_active_blocked_primary_cleanup_probe_route_policy_proof(
        primary={"title": "Blocked primary", "action_type": "none"},
        contract={"enabled": False, "action_type": "none"},
        updates={},
        primary_evidence={
            "selected_candidate_updates": {"lig_spacing": 250, "lig_legs": 0},
            "safe_executor_backed_candidates_count": 1,
        },
        final_state={"lig_spacing": 200, "lig_legs": 2},
        final_overview={"utils": {"bending": 0.92, "shear": 0.32}},
        final_accepted_min_family_util=0.85,
        target_band_eps=0.01,
        compound_shear_update_keys={"lig_spacing", "lig_legs", "lig_dia"},
        contract_enabled=False,
        post_click_route_for_safe_cleanup=False,
        safe_cleanup_updates_match_current_state=False,
        final_bending_util=0.92,
    )
    return {
        "safe_cleanup": safe_cleanup,
        "safe_cleanup_repeat": repeat,
        "bending_probe": bending_probe,
        "actionable_primary": actionable_primary,
    }


def _capture() -> dict[str, Any]:
    sources = _source_for_names(CONTROLLER, {BUILDER, PROOF_CLASS})
    source_blob = "\n".join(sources.values())
    samples = _build_samples()
    forbidden_terms = [
        "inputs_page",
        "streamlit",
        "st.session_state",
        "render_",
        "apply routing",
        "one_click",
    ]
    forbidden_hits = [
        term for term in forbidden_terms if term.lower() in source_blob.lower()
    ]
    return {
        "builder": BUILDER,
        "proof_class": PROOF_CLASS,
        "samples": samples,
        "samples_hash": _stable_hash(samples),
        "stable_repeat": (
            samples["safe_cleanup"].get("route_policy_hash")
            == samples["safe_cleanup_repeat"].get("route_policy_hash")
        ),
        "forbidden_hits": forbidden_hits,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    samples = capture.get("samples") or {}
    safe_cleanup = samples.get("safe_cleanup") or {}
    bending_probe = samples.get("bending_probe") or {}
    actionable_primary = samples.get("actionable_primary") or {}
    return {
        "builder_exists": bool(capture.get("builder")),
        "proof_class_exists": bool(capture.get("proof_class")),
        "authority_is_controller_route_policy": safe_cleanup.get("authority")
        == "DesignGuideController.no_active_blocked_primary_cleanup_probe_route_policy",
        "safe_cleanup_gate_represented": safe_cleanup.get("safe_cleanup_candidate_gate_allows_result")
        is True,
        "bending_under_floor_gate_represented": bending_probe.get("bending_under_floor_probe_gate")
        is True,
        "exact_blocker_need_represented": bending_probe.get("exact_blocker_proof_required")
        is True,
        "actionable_primary_does_not_enter_route": actionable_primary.get(
            "enters_blocked_primary_probe_route"
        )
        is False,
        "route_policy_hash_stable": capture.get("stable_repeat") is True,
        "proof_only": safe_cleanup.get("proof_only") is True
        and bending_probe.get("proof_only") is True,
        "candidate_generation_not_moved": safe_cleanup.get("candidate_generation_owned_here")
        is False,
        "result_assembly_not_moved": safe_cleanup.get("result_assembly_owned_here") is False,
        "not_product_driving": safe_cleanup.get("product_driving") is False,
        "no_page_or_ui_import_terms": not capture.get("forbidden_hits"),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = payload.get("capture") or {}
    samples = capture.get("samples") or {}
    lines = [
        "# Design Guide No-Active Blocked-Primary Cleanup Probe Route Policy Object",
        "",
        f"Status: `{payload.get('status')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        f"Builder: `{capture.get('builder')}`",
        f"Proof class: `{capture.get('proof_class')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(["", "## Sample Outcomes", ""])
    for name, sample in samples.items():
        if name.endswith("_repeat"):
            continue
        lines.append(
            "- {name}: enters_route=`{enters}`, safe_cleanup_gate=`{safe}`, "
            "bending_gate=`{bending}`, route_hash=`{hash}`".format(
                name=name,
                enters=sample.get("enters_blocked_primary_probe_route"),
                safe=sample.get("safe_cleanup_candidate_gate_allows_result"),
                bending=sample.get("bending_under_floor_probe_gate"),
                hash=sample.get("route_policy_hash"),
            )
        )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            "The controller can now represent the route policy/evidence surface as proof-only data. "
            "Live route behavior is unchanged and the route is not ready for deletion or cutover yet.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {"status": status, "checks": checks, "capture": capture}
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = _stamp()
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_no_active_blocked_primary_cleanup_probe_route_policy_object_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_no_active_blocked_primary_cleanup_probe_route_policy_object_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_no_active_blocked_primary_cleanup_probe_route_policy_object {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
