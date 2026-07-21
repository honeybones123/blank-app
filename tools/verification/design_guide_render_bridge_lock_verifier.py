"""Final lock verifier for the Design Guide render-stage bridge.

This verifier composes the post-resolver bridge and narrowing proof chain. It
proves the render stage no longer owns final selected-item mutation truth after
FinalDesignGuidePublication exists. Rendering, apply routing, session/debug,
fallback, wording, and family runtime ownership remain outside this lock.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"
ROUTE_COORDINATORS = ROOT / "inputs_page_route_coordinators.py"
APP_CONTRACT_BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"
FINAL_FORMATTER = ROOT / "design_brain" / "final_design_guide_formatter.py"

COMPOSED_GATES: list[dict[str, str]] = [
    {
        "id": "live_post_resolver_mutation_bridge",
        "script": "tools/verification/design_guide_live_post_resolver_mutation_bridge_snapshot.py",
        "artifact_prefix": "design_guide_live_post_resolver_mutation_bridge",
        "label": "Trace-only live post-resolver mutation bridge",
    },
    {
        "id": "adapter_owned_render_mutation_narrowing",
        "script": "tools/verification/design_guide_adapter_owned_render_mutation_narrowing_snapshot.py",
        "artifact_prefix": "design_guide_adapter_owned_render_mutation_narrowing",
        "label": "Adapter-owned render mutation narrowing",
    },
    {
        "id": "remaining_live_render_resolver_truth",
        "script": "tools/verification/design_guide_remaining_live_render_resolver_truth_snapshot.py",
        "artifact_prefix": "design_guide_remaining_live_render_resolver_truth",
        "label": "Remaining live render resolver truth classification",
    },
    {
        "id": "class_a_identity_narrowing",
        "script": "tools/verification/design_guide_final_resolver_identity_narrowing_snapshot.py",
        "artifact_prefix": "design_guide_final_resolver_identity_narrowing",
        "label": "Class-A identity narrowing",
    },
    {
        "id": "class_b_metadata_narrowing",
        "script": "tools/verification/design_guide_final_visible_resolution_metadata_narrowing_snapshot.py",
        "artifact_prefix": "design_guide_final_visible_resolution_metadata_narrowing",
        "label": "Class-B metadata narrowing",
    },
    {
        "id": "class_c_safe_low_util_narrowing",
        "script": "tools/verification/design_guide_safe_low_util_replacement_narrowing_snapshot.py",
        "artifact_prefix": "design_guide_safe_low_util_replacement_narrowing",
        "label": "Class-C safe-low-util narrowing",
    },
    {
        "id": "class_d_combined_cleanup_narrowing",
        "script": "tools/verification/design_guide_combined_cleanup_rescue_replacement_narrowing_snapshot.py",
        "artifact_prefix": "design_guide_combined_cleanup_rescue_replacement_narrowing",
        "label": "Class-D combined cleanup rescue narrowing",
    },
    {
        "id": "class_e_post_click_exact_blocker_narrowing",
        "script": "tools/verification/design_guide_post_click_exact_blocker_replacement_narrowing_snapshot.py",
        "artifact_prefix": "design_guide_post_click_exact_blocker_replacement_narrowing",
        "label": "Class-E post-click exact blocker narrowing",
    },
    {
        "id": "design_guide_independence_lock",
        "script": "tools/verification/design_guide_independence_lock_verifier.py",
        "artifact_prefix": "design_guide_independence_lock",
        "label": "Design Guide independence lock",
    },
    {
        "id": "collapsed_replacement_authority_cutover",
        "script": "tools/verification/design_guide_collapsed_replacement_authority_cutover.py",
        "artifact_prefix": "design_guide_collapsed_replacement_authority_cutover",
        "label": "Collapsed replacement authority cutover",
    },
]


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    import hashlib

    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _escape_md(value: Any) -> str:
    return str(value).replace("|", "\\|")


def _run_gate(script: str) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, script],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "script": script,
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "stdout_tail": proc.stdout.strip().splitlines()[-12:],
        "stderr_tail": proc.stderr.strip().splitlines()[-12:],
    }


def _latest_artifact(prefix: str) -> dict[str, Any]:
    artifacts = sorted(
        ARTIFACT_DIR.glob(f"{prefix}_*.json"),
        key=lambda path: path.stat().st_mtime,
    )
    if not artifacts:
        return {"path": None, "snapshot": None, "found": False, "passed": False}
    path = artifacts[-1]
    try:
        snapshot = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {
            "path": str(path),
            "snapshot": None,
            "found": True,
            "passed": False,
            "error": str(exc),
        }
    return {
        "path": str(path),
        "snapshot": snapshot,
        "found": True,
        "passed": snapshot.get("status") == "PASS",
        "summary": snapshot.get("summary"),
        "failures": snapshot.get("failures"),
    }


def _direct_source_guards() -> dict[str, bool]:
    input_source = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in (INPUTS_PAGE, ROUTE_COORDINATORS, APP_CONTRACT_BRIDGE)
        if path.exists()
    )
    final_source = FINAL_PUBLICATION.read_text(encoding="utf-8")
    formatter_source = FINAL_FORMATTER.read_text(encoding="utf-8")
    renderer_source = (ROOT / "ui" / "final_design_guide_card.py").read_text(
        encoding="utf-8", errors="replace"
    )
    compatibility_markers = {
        "post_resolver_adapter_owned": "final_publication_post_resolver_adapter_owned_rows_compatibility_only",
    }
    final_visible_resolver_deleted = "def resolve_final_visible_design_guide_item(" not in input_source
    return {
        "final_publication_object_exists": "class FinalDesignGuidePublication" in final_source,
        "final_publication_cta_exists": "class FinalDesignGuideCTA" in final_source,
        "final_publication_display_exists": "class FinalDesignGuideDisplay" in final_source,
        "final_publication_evidence_exists": "class FinalDesignGuideEvidence" in final_source,
        "post_resolver_proof_exists": "class FinalDesignGuidePostResolverMutationProof" in final_source,
        "cta_authority_live": '_FINAL_PUBLICATION_CTA_AUTHORITY = "FinalDesignGuidePublication.cta"' in input_source,
        "display_authority_live": "class FinalDesignGuideDisplay" in final_source,
        "all_render_mutation_rows_compatibility_stamped": final_visible_resolver_deleted
        or all(marker in input_source for marker in compatibility_markers.values()),
        "render_stage_compatibility_proof_only": (
            final_visible_resolver_deleted
            or (
                "final_publication_post_resolver_adapter_owned_rows_compatibility_only" in input_source
                and "compatibility_only" in input_source
                and "proof_only" in input_source
            )
        ),
        "cta_rendering_remains_render_only": (
            "def render_final_design_guide_card_html(" in renderer_source
            and "_design_guide_dashboard_card_html_from_render_model" not in input_source
            and "_design_guide_dashboard_card_html_from_render_model" not in final_source
        ),
        "apply_routing_remains_page_owned": (
            "_record_rendered_design_guide_primary_apply_payload" in input_source
            and "_record_rendered_design_guide_primary_apply_payload" not in final_source
        ),
        "session_debug_remains_non_authoritative": (
            final_visible_resolver_deleted
            and "session_state" not in final_source
        ),
        "fallback_remains_non_authoritative": (
            "FinalDesignGuidePublication.cta" in input_source
            and "render_fallback_shell_model" in final_source
            and "renderer_driving=False" in final_source
        ),
        "ui_rendering_not_moved": "ui.design_guide_cards" not in final_source,
        "legacy_wording_helper_deleted": (
            "_design_guide_clean_main_card_text" not in input_source
            and "clean_final_design_guide_reason_text" in formatter_source
        ),
        "family_runtime_ownership_not_moved": (
            "run_bending_fail_governs_ladder_runtime" not in final_source
            and "run_shear_fail_governs_ladder_runtime" not in final_source
        ),
        "final_publication_has_no_page_imports": (
            "inputs_page" not in final_source
            and "streamlit" not in final_source
            and "session_state" not in final_source
        ),
    }


def _extract_final_narrowing_summary(gate_results: dict[str, dict[str, Any]]) -> dict[str, Any]:
    artifact = gate_results["class_e_post_click_exact_blocker_narrowing"]["artifact"]
    snapshot = artifact.get("snapshot") or {}
    summary = dict(snapshot.get("summary") or {})
    return {
        "remaining_live_resolver_rows": summary.get("remaining_live_rows_after_post_click_narrowing"),
        "render_bridge_fully_narrowed": summary.get("render_bridge_fully_narrowed"),
        "product_behavior_changed": summary.get("product_behavior_changed"),
        "class_a_b_c_d_narrowing_verifiers_pass": summary.get("class_a_b_c_d_narrowing_verifiers_pass"),
        "class_e_rows_narrowed": summary.get("class_e_rows_narrowed"),
    }


def _build_snapshot() -> dict[str, Any]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    refresh_gates = os.environ.get("DESIGN_GUIDE_RENDER_BRIDGE_LOCK_REFRESH", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    gate_results: dict[str, dict[str, Any]] = {}
    for gate in COMPOSED_GATES:
        run = (
            _run_gate(gate["script"])
            if refresh_gates
            else {
                "script": gate["script"],
                "returncode": None,
                "passed": True,
                "stdout_tail": [],
                "stderr_tail": [],
                "skipped": True,
                "reason": "using_latest_artifact; set DESIGN_GUIDE_RENDER_BRIDGE_LOCK_REFRESH=1 to rerun",
            }
        )
        artifact = _latest_artifact(gate["artifact_prefix"])
        gate_results[gate["id"]] = {
            **gate,
            "run": run,
            "artifact": artifact,
            "passed": bool(run["passed"] and artifact["passed"]),
        }

    source_guards = _direct_source_guards()
    final_summary = _extract_final_narrowing_summary(gate_results)
    proof_claims = {
        "all_composed_gates_pass": all(result["passed"] for result in gate_results.values()),
        "remaining_live_resolver_rows_zero": final_summary["remaining_live_resolver_rows"] == 0,
        "render_bridge_fully_narrowed": final_summary["render_bridge_fully_narrowed"] is True,
        "product_behavior_changed_false": final_summary["product_behavior_changed"] is False,
        "class_a_b_c_d_narrowing_verifiers_pass": (
            final_summary["class_a_b_c_d_narrowing_verifiers_pass"] is True
        ),
        "class_e_row_narrowed": final_summary["class_e_rows_narrowed"] == 1,
        "final_publication_authority_for_cta_display_evidence_identity": all(
            source_guards[key]
            for key in (
                "final_publication_object_exists",
                "final_publication_cta_exists",
                "final_publication_display_exists",
                "final_publication_evidence_exists",
                "cta_authority_live",
                "display_authority_live",
            )
        ),
        "render_stage_compatibility_proof_only_for_selected_item_mutation_truth": all(
            source_guards[key]
            for key in (
                "post_resolver_proof_exists",
                "all_render_mutation_rows_compatibility_stamped",
                "render_stage_compatibility_proof_only",
            )
        ),
        "cta_rendering_render_only": source_guards["cta_rendering_remains_render_only"],
        "apply_routing_page_shared_owned": source_guards["apply_routing_remains_page_owned"],
        "session_debug_fallback_non_authoritative": all(
            source_guards[key]
            for key in (
                "session_debug_remains_non_authoritative",
                "fallback_remains_non_authoritative",
            )
        ),
        "ui_wording_family_runtime_ownership_not_moved": all(
            source_guards[key]
            for key in (
                "ui_rendering_not_moved",
                "legacy_wording_helper_deleted",
                "family_runtime_ownership_not_moved",
                "final_publication_has_no_page_imports",
            )
        ),
    }
    failures: list[str] = []
    for gate_id, result in gate_results.items():
        if not result["passed"]:
            failures.append(f"{gate_id}_failed")
    for claim, passed in proof_claims.items():
        if not passed:
            failures.append(f"{claim}_failed")
    for guard, passed in source_guards.items():
        if not passed:
            failures.append(f"{guard}_guard_failed")

    proof_surface = {
        "gate_statuses": {gate_id: result["passed"] for gate_id, result in gate_results.items()},
        "final_summary": final_summary,
        "proof_claims": proof_claims,
        "source_guards": source_guards,
    }
    return {
        "snapshot_name": "design_guide_render_bridge_lock_verifier",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "summary": {
            "remaining_live_resolver_rows": final_summary["remaining_live_resolver_rows"],
            "render_bridge_fully_narrowed": final_summary["render_bridge_fully_narrowed"],
            "product_behavior_changed": final_summary["product_behavior_changed"],
            "all_composed_gates_pass": proof_claims["all_composed_gates_pass"],
            "final_publication_remains_authority": proof_claims[
                "final_publication_authority_for_cta_display_evidence_identity"
            ],
            "render_stage_compatibility_proof_only": proof_claims[
                "render_stage_compatibility_proof_only_for_selected_item_mutation_truth"
            ],
        },
        "gate_results": gate_results,
        "proof_claims": proof_claims,
        "source_guards": source_guards,
        "snapshot_hash": _stable_hash(proof_surface),
    }


def _write_markdown(snapshot: dict[str, Any], path: Path) -> None:
    gate_rows = "\n".join(
        "| {label} | `{passed}` | `{artifact}` |".format(
            label=_escape_md(result["label"]),
            passed=result["passed"],
            artifact=_escape_md((result["artifact"] or {}).get("path")),
        )
        for result in snapshot["gate_results"].values()
    )
    body = "\n".join(
        [
            "# Design Guide Render Bridge Lock Verifier",
            "",
            f"Timestamp: `{snapshot['generated_at']}`",
            f"Result: `{snapshot['status']}`",
            "",
            "## Summary",
            "",
            f"- Remaining live resolver rows: `{snapshot['summary']['remaining_live_resolver_rows']}`",
            f"- Render bridge fully narrowed: `{snapshot['summary']['render_bridge_fully_narrowed']}`",
            f"- Product behaviour changed: `{snapshot['summary']['product_behavior_changed']}`",
            f"- All composed gates pass: `{snapshot['summary']['all_composed_gates_pass']}`",
            (
                "- FinalDesignGuidePublication remains authority: "
                f"`{snapshot['summary']['final_publication_remains_authority']}`"
            ),
            (
                "- Render stage selected-item mutation truth is compatibility/proof-only: "
                f"`{snapshot['summary']['render_stage_compatibility_proof_only']}`"
            ),
            "",
            "## Composed Gates",
            "",
            "| Gate | PASS | Latest artifact |",
            "| --- | --- | --- |",
            gate_rows,
            "",
            "## Proof Claims",
            "",
            *[f"- {key}: `{value}`" for key, value in snapshot["proof_claims"].items()],
            "",
            "## Source Guards",
            "",
            *[f"- {key}: `{value}`" for key, value in snapshot["source_guards"].items()],
            "",
            "## Next Slice",
            "",
            "Start deletion/speed cleanup with reachability snapshots; do not delete without a fresh reachability proof.",
        ]
    )
    path.write_text(body + "\n", encoding="utf-8")


def main() -> int:
    snapshot = _build_snapshot()
    timestamp = snapshot["generated_at"].replace(":", "-")
    artifact_path = ARTIFACT_DIR / f"design_guide_render_bridge_lock_{timestamp}.json"
    report_path = AUDIT_DIR / f"design_guide_render_bridge_lock_{timestamp}.md"
    artifact_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown(snapshot, report_path)
    print(f"design_guide_render_bridge_lock {snapshot['status']}")
    print(f"json={artifact_path}")
    print(f"report={report_path}")
    if snapshot["failures"]:
        print("failures:")
        for failure in snapshot["failures"]:
            print(f"- {failure}")
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
