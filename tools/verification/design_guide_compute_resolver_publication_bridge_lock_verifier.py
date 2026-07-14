"""Final lock verifier for the compute resolver/publication bridge.

This verifier composes the compute-stage Design Guide proof chain from the
latest PASS artifacts and direct source checks. It proves publication-owned
compute truth has been narrowed to FinalDesignGuidePublication evidence, while
remaining B-class and D-class surfaces stay live because they are legitimate
compute pre-publication input and fallback/safety logic.
"""

from __future__ import annotations

import hashlib
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
INPUTS_PAGE = ROOT / "inputs_page.py"
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"

COMPOSED_GATES: tuple[dict[str, str], ...] = (
    {
        "id": "raw_compute_resolver_truth_ownership",
        "script": "tools/verification/design_guide_raw_compute_resolver_truth_ownership_audit.py",
        "artifact_prefix": "design_guide_raw_compute_resolver_truth_ownership_audit",
        "label": "Raw compute resolver truth ownership audit",
    },
    {
        "id": "compute_handoff_rebound_proof_object",
        "script": "tools/verification/design_guide_compute_publication_handoff_rebound_decision_snapshot.py",
        "artifact_prefix": "design_guide_compute_publication_handoff_rebound_decision",
        "label": "Compute handoff/rebound proof object",
    },
    {
        "id": "live_compute_handoff_rebound_bridge",
        "script": "tools/verification/design_guide_live_compute_publication_handoff_rebound_decision_bridge_snapshot.py",
        "artifact_prefix": "design_guide_live_compute_publication_handoff_rebound_decision_bridge",
        "label": "Live compute handoff/rebound bridge",
    },
    {
        "id": "focused_parity_scenarios",
        "script": "tools/verification/design_guide_live_compute_publication_handoff_rebound_parity_scenarios.py",
        "artifact_prefix": "design_guide_live_compute_publication_handoff_rebound_parity_scenarios",
        "label": "Focused live parity scenarios",
    },
    {
        "id": "compute_rebound_mutation_adapter_parity",
        "script": "tools/verification/design_guide_compute_rebound_mutation_adapter_parity_snapshot.py",
        "artifact_prefix": "design_guide_compute_rebound_mutation_adapter_parity",
        "label": "Compute rebound mutation adapter parity",
    },
    {
        "id": "compute_rebound_mutation_adapter_cutover",
        "script": "tools/verification/design_guide_compute_rebound_mutation_adapter_cutover_snapshot.py",
        "artifact_prefix": "design_guide_compute_rebound_mutation_adapter_cutover",
        "label": "Compute rebound mutation adapter cutover",
    },
    {
        "id": "compute_debug_restamp_metadata_narrowing",
        "script": "tools/verification/design_guide_compute_debug_restamp_metadata_narrowing_snapshot.py",
        "artifact_prefix": "design_guide_compute_debug_restamp_metadata_narrowing",
        "label": "Compute debug/restamp metadata narrowing",
    },
    {
        "id": "remaining_compute_truth_ownership",
        "script": "tools/verification/design_guide_remaining_compute_truth_ownership_snapshot.py",
        "artifact_prefix": "design_guide_remaining_compute_truth_ownership",
        "label": "Remaining compute truth ownership",
    },
    {
        "id": "publication_evidence_same_object",
        "script": "tools/verification/design_guide_publication_evidence_compute_truth_same_object_snapshot.py",
        "artifact_prefix": "design_guide_publication_evidence_compute_truth_same_object",
        "label": "Publication evidence same-object proof",
    },
    {
        "id": "a_class_compute_truth_narrowing",
        "script": "tools/verification/design_guide_a_class_compute_truth_narrowing_snapshot.py",
        "artifact_prefix": "design_guide_a_class_compute_truth_narrowing",
        "label": "A-class compute truth narrowing",
    },
    {
        "id": "design_guide_independence_lock",
        "script": "tools/verification/design_guide_independence_lock_verifier.py",
        "artifact_prefix": "design_guide_independence_lock",
        "label": "Design Guide independence lock",
    },
    {
        "id": "render_bridge_lock",
        "script": "tools/verification/design_guide_render_bridge_lock_verifier.py",
        "artifact_prefix": "design_guide_render_bridge_lock",
        "label": "Render bridge lock",
    },
)

B_D_LIVE_GUARD_TOKENS: dict[str, tuple[str, ...]] = {
    "late_evidence_acceptance_condition": ("_late_evidence_acceptance",),
    "post_core_evidence_mismatch_condition": ("_post_core_mismatch",),
    "rebound_update_payload_summary_hash": ('_late_rebound_contract.get("updates")',),
    "rebound_contract_enabled_safety": ("_design_guide_button_contract_enabled(_late_rebound_contract)",),
    "pre_resolver_collapsed_item_mutation": (
        "collapsed_guidance_items[0] = dict(_post_evidence_rebound)",
        "_post_mutation_collapsed_items = list(",
    ),
}

FORBIDDEN_FINAL_PUBLICATION_TOKENS = (
    "import inputs_page",
    "from inputs_page",
    "import streamlit",
    "st.session_state",
    "session_state",
    "render_html",
    "route_apply",
    "_queue_primary_design_guide_button_action",
    "_record_rendered_design_guide_primary_apply_payload",
    "design_guide_page.render_final_panel",
    "_design_guide_dashboard_card_html_from_render_model",
)

FORBIDDEN_TOKEN_EXCEPTIONS = {
    "session_state": ("stale_fresh_token_proof",),
}


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _escape_md(value: Any) -> str:
    return str(value).replace("|", "\\|")


def _latest(prefix: str) -> dict[str, Any]:
    artifacts = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not artifacts:
        return {"found": False, "path": None, "snapshot": {}, "passed": False}
    path = artifacts[-1]
    try:
        snapshot = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"found": True, "path": str(path), "snapshot": {}, "passed": False, "error": str(exc)}
    return {
        "found": True,
        "path": str(path),
        "snapshot": snapshot,
        "passed": snapshot.get("status") == "PASS",
    }


def _source_guards() -> dict[str, bool]:
    input_source = INPUTS_PAGE.read_text(encoding="utf-8")
    final_source = FINAL_PUBLICATION.read_text(encoding="utf-8")
    forbidden: dict[str, bool] = {}
    for token in FORBIDDEN_FINAL_PUBLICATION_TOKENS:
        scrubbed = final_source
        for allowed in FORBIDDEN_TOKEN_EXCEPTIONS.get(token, ()):
            scrubbed = scrubbed.replace(allowed, "")
        forbidden[f"final_publication_forbidden_absent::{token}"] = token not in scrubbed
    return {
        "final_publication_object_exists": "class FinalDesignGuidePublication" in final_source,
        "final_publication_evidence_has_compute_surface": "compute_publication_evidence:" in final_source,
        "final_publication_evidence_has_compute_hash": "compute_publication_evidence_hash:" in final_source,
        "a_class_rows_removed_or_compatibility_stamped": (
            (
                "_mark_compute_publication_evidence_a_class_compatibility_only" not in input_source
                and "final_publication_compute_a_class_evidence_rows" not in input_source
            )
            or (
                "_mark_compute_publication_evidence_a_class_compatibility_only" in input_source
                and "final_publication_compute_a_class_evidence_rows" in input_source
            )
        ),
        "compute_debug_rows_removed_or_compatibility_stamped": (
            (
                "_mark_compute_debug_restamp_metadata_compatibility_only" not in input_source
                and "final_publication_compute_debug_restamp_metadata_rows" not in input_source
            )
            or (
                "_mark_compute_debug_restamp_metadata_compatibility_only" in input_source
                and "final_publication_compute_debug_restamp_metadata_rows" in input_source
            )
        ),
        "b_d_guard_tokens_live": all(
            any(token in input_source for token in alternatives)
            for alternatives in B_D_LIVE_GUARD_TOKENS.values()
        ),
        "apply_routing_still_page_owned": (
            "_record_rendered_design_guide_primary_apply_payload" in input_source
            and "_record_rendered_design_guide_primary_apply_payload" not in final_source
        ),
        "cta_rendering_still_page_owned": (
            "_render_final_design_guide_card_html(" in input_source
            and "_render_final_design_guide_card_html(" not in final_source
        ),
        "session_ui_not_moved_to_design_brain": (
            "streamlit" not in final_source and "st.session_state" not in final_source
        ),
        **forbidden,
    }


def _direct_artifact_guards(gate_results: dict[str, dict[str, Any]]) -> dict[str, Any]:
    raw = dict(gate_results["raw_compute_resolver_truth_ownership"]["artifact"].get("snapshot") or {})
    debug = dict(gate_results["compute_debug_restamp_metadata_narrowing"]["artifact"].get("snapshot") or {})
    remaining = dict(gate_results["remaining_compute_truth_ownership"]["artifact"].get("snapshot") or {})
    same_object = dict(gate_results["publication_evidence_same_object"]["artifact"].get("snapshot") or {})
    a_class = dict(gate_results["a_class_compute_truth_narrowing"]["artifact"].get("snapshot") or {})
    bridge = dict(gate_results["live_compute_handoff_rebound_bridge"]["artifact"].get("snapshot") or {})
    parity = dict(gate_results["focused_parity_scenarios"]["artifact"].get("snapshot") or {})

    return {
        "raw_audit_no_unsafe_unclear_fields": raw.get("classification_counts", {}).get(
            "E. unsafe / unclear",
            0,
        )
        == 0,
        "compute_handoff_proof_all_fields_represented": bridge.get("all_9_blocking_fields_represented") is True,
        "debug_metadata_rows_cannot_override_publication": (
            debug.get("narrowed_rows_cannot_override_final_publication") is True
            and debug.get("only_c_class_debug_restamp_rows_narrowed") is True
        ),
        "all_publication_owned_compute_truth_narrowed": (
            a_class.get("only_a_class_fields_narrowed") is True
            and a_class.get("a_class_rows_narrowed") == 4
            and a_class.get("narrowed_rows_cannot_override_final_publication") is True
            and a_class.get("all_narrowed_rows_carry_compute_publication_evidence_hash") is True
        ),
        "b_class_fields_remain_compute_only": (
            remaining.get("compute_only_records") == ["compute_pre_publication_rebound_inputs"]
            and same_object.get("b_class_compute_inputs_not_moved") is True
            and a_class.get("b_class_and_d_class_fields_remain_live_unchanged") is True
        ),
        "d_class_fields_remain_fallback_safety": (
            remaining.get("fallback_safety_records") == ["fallback_safety_rebound_surfaces"]
            and same_object.get("d_class_fallback_safety_fields_not_moved") is True
            and a_class.get("b_class_and_d_class_fields_remain_live_unchanged") is True
        ),
        "remaining_compute_blockers_are_expected_groups": (
            a_class.get("remaining_compute_blocker_group_count") == 2
            and a_class.get("remaining_compute_blocker_groups")
            == [
                "B-class compute-only pre-publication inputs",
                "D-class fallback/safety logic",
            ]
        ),
        "compute_paths_do_not_override_after_publication": (
            debug.get("narrowed_rows_cannot_override_final_publication") is True
            and a_class.get("narrowed_rows_cannot_override_final_publication") is True
            and remaining.get("narrowing_only_recommended_for_publication_evidence_fields") is True
        ),
        "parity_product_behavior_unchanged": parity.get("product_behavior_changed") is False,
        "a_class_product_behavior_unchanged": a_class.get("product_behavior_changed") is False,
        "same_object_product_behavior_unchanged": same_object.get("product_behavior_changed") is False,
        "debug_product_behavior_unchanged": debug.get("product_behavior_changed") is False,
        "lock_status": "Design Guide compute resolver/publication bridge locked",
    }


def _write_report(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# Design Guide Compute Resolver/Publication Bridge Lock Verifier",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Summary",
        "",
        f"- Lock status: `{payload['lock_status']}`",
        f"- Product behaviour changed: `{payload['product_behavior_changed']}`",
        f"- Unsafe/unclear fields remain: `{not payload['direct_proof']['raw_audit_no_unsafe_unclear_fields']}`",
        f"- Publication-owned compute truth narrowed: `{payload['direct_proof']['all_publication_owned_compute_truth_narrowed']}`",
        f"- B-class remains compute-only: `{payload['direct_proof']['b_class_fields_remain_compute_only']}`",
        f"- D-class remains fallback/safety: `{payload['direct_proof']['d_class_fields_remain_fallback_safety']}`",
        "",
        "## Composed Gates",
        "",
        "| Gate | Script | PASS | Artifact |",
        "| --- | --- | --- | --- |",
    ]
    for gate_id, result in payload["gates"].items():
        lines.append(
            "| `{gate}` | `{script}` | `{passed}` | {artifact} |".format(
                gate=_escape_md(gate_id),
                script=_escape_md(result["script"]),
                passed=result["passed"] and result["artifact_passed"],
                artifact=_escape_md(result.get("artifact_path")),
            )
        )
    lines.extend(["", "## Direct Proof", "", "| Check | PASS |", "| --- | --- |"])
    for key, value in payload["direct_proof"].items():
        if isinstance(value, bool):
            lines.append(f"| `{_escape_md(key)}` | `{value}` |")
    lines.extend(["", "## Source Guards", "", "| Check | PASS |", "| --- | --- |"])
    for key, value in payload["source_guards"].items():
        lines.append(f"| `{_escape_md(key)}` | `{value}` |")
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

    gate_results: dict[str, dict[str, Any]] = {}
    for gate in COMPOSED_GATES:
        artifact = _latest(gate["artifact_prefix"])
        gate_results[gate["id"]] = {
            "script": gate["script"],
            "returncode": 0 if artifact.get("passed") is True else 1,
            "passed": artifact.get("passed") is True,
            "stdout_tail": [],
            "stderr_tail": [],
            "label": gate["label"],
            "artifact": artifact,
            "artifact_path": artifact.get("path"),
            "artifact_passed": artifact.get("passed") is True,
            "executed_in_this_run": False,
        }

    source_guards = _source_guards()
    direct_proof = _direct_artifact_guards(gate_results)

    failures: list[str] = []
    for gate_id, result in gate_results.items():
        if not result["passed"] or not result["artifact_passed"]:
            failures.append(f"{gate_id}_not_passed")
    for key, value in source_guards.items():
        if value is not True:
            failures.append(f"source_guard_failed::{key}")
    for key, value in direct_proof.items():
        if isinstance(value, bool) and value is not True:
            failures.append(f"direct_proof_failed::{key}")

    payload = {
        "schema": "design_guide_compute_resolver_publication_bridge_lock_verifier.v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "product_behavior_changed": False,
        "composition_mode": "latest_pass_artifacts_plus_direct_source_checks",
        "lock_status": (
            "Design Guide compute resolver/publication bridge locked"
            if not failures
            else "Design Guide compute resolver/publication bridge not locked"
        ),
        "gates": {
            gate_id: {
                "script": result["script"],
                "returncode": result["returncode"],
                "passed": result["passed"],
                "artifact_path": result["artifact_path"],
                "artifact_passed": result["artifact_passed"],
                "executed_in_this_run": result["executed_in_this_run"],
                "stdout_tail": result["stdout_tail"],
                "stderr_tail": result["stderr_tail"],
            }
            for gate_id, result in gate_results.items()
        },
        "source_guards": source_guards,
        "direct_proof": direct_proof,
        "lock_hash": _stable_hash(
            {
                "gates": {
                    gate_id: result["artifact_path"]
                    for gate_id, result in gate_results.items()
                },
                "source_guards": source_guards,
                "direct_proof": direct_proof,
            }
        ),
        "recommended_next_slice": (
            "Move into cleanup/speed work: audit deletion candidates and hot-path duplicate compatibility "
            "stamps now that compute publication ownership is locked. Keep B-class compute inputs and "
            "D-class fallback/safety logic live unless a separate safety ownership audit says otherwise."
        ),
    }

    stamp = datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_compute_resolver_publication_bridge_lock_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_compute_resolver_publication_bridge_lock_{stamp}.md"
    payload["artifact"] = str(json_path)
    payload["report"] = str(md_path)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(payload, md_path)

    print(f"design_guide_compute_resolver_publication_bridge_lock_verifier {payload['status']}")
    print(payload["lock_status"])
    print(f"json={json_path}")
    print(f"report={md_path}")
    if failures:
        print("failures:", json.dumps(failures, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
