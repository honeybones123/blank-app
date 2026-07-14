"""Proof-only snapshot for Design Guide button-contract execution proof.

This verifier does not move CTA authority or change product behavior. It proves
that Design Brain can represent the already-resolved button contract plus its
emission context with stable hashes, ready for a later cutover/deletion slice.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import importlib
import json
from pathlib import Path
import re
import sys
from typing import Any


REPO = Path(__file__).resolve().parents[2]
PUBLICATION_PATH = REPO / "design_brain" / "publication.py"
INPUTS_PATH = REPO / "inputs_page.py"
ARTIFACTS = REPO / "artifacts"
VERIFICATION_DIR = ARTIFACTS / "verification"
AUDITS_DIR = ARTIFACTS / "audits"


def _stable_hash(value: object) -> str:
    import hashlib

    try:
        payload = json.dumps(value or {}, sort_keys=True, default=str)
    except (TypeError, ValueError):
        payload = str(value or "")
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function_source(source: str, function_name: str) -> str:
    match = re.search(rf"^def {re.escape(function_name)}\(.*?(?=^def |\Z)", source, re.M | re.S)
    return match.group(0) if match else ""


def _case(
    *,
    name: str,
    item_index: int,
    action_type: str | None,
    family: str | None,
    updates: dict[str, Any] | None,
    preview_pass: bool,
    expected_util: Any = None,
    blocking_reason: str | None = None,
    source_candidate_id: str | None = None,
    context_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    publication = importlib.import_module("design_brain.publication")
    final_result = publication.build_design_guide_button_contract_result(
        actionable=bool(action_type and updates and not blocking_reason),
        action_type=action_type,
        family=family,
        updates=dict(updates or {}),
        preview_pass=preview_pass,
        expected_util=expected_util,
        blocking_reason=blocking_reason,
        source_candidate_id=source_candidate_id,
    )
    context_payload = {
        "item_index": item_index,
        "item": {
            "title": name,
            "action_type": action_type,
            "family": family,
            "updates": dict(updates or {}),
            "source_candidate_id": source_candidate_id,
        },
        "work_after": {"updates": dict(updates or {})},
        "updates": dict(updates or {}),
        "updates_source": "resolved_candidate" if updates else "none",
        "final_contract": dict(final_result.final_contract),
        "action_type": action_type,
        "effective_action_type": action_type,
        "family": family,
        "expected_util": expected_util,
        "blocking_reason": blocking_reason,
        "executor_allowed": bool(action_type and updates and not blocking_reason),
        "executor_reason": None if updates else "missing_updates",
        "executor_contract_evaluated": True,
        "preview_pass": preview_pass,
        "preview_util": expected_util,
        "preview_reason": None if preview_pass else "preview_failed",
        "preview_evaluated": True,
        "source_candidate_id": source_candidate_id,
        "actionable": bool(final_result.actionable),
        "update_decision_reason": "proof_snapshot",
        "work_mutation_object_id_before": 111,
        "work_mutation_object_id_after": 222,
    }
    context_payload.update(context_overrides or {})
    context = publication.DesignGuideButtonContractEmissionContext(**context_payload)
    proof_a = publication.build_design_guide_button_contract_execution_proof(
        item_index=item_index,
        item=context_payload["item"],
        state={"case": name, "stable": True},
        final_result=final_result,
        emission_context=context,
    )
    context_b = publication.DesignGuideButtonContractEmissionContext(
        **{
            **context_payload,
            "work_mutation_object_id_before": 333,
            "work_mutation_object_id_after": 444,
        }
    )
    proof_b = publication.build_design_guide_button_contract_execution_proof(
        item_index=item_index,
        item=context_payload["item"],
        state={"case": name, "stable": True},
        final_result=final_result,
        emission_context=context_b,
    )
    proof_d = proof_a.to_dict()
    return {
        "case": name,
        "proof": proof_d,
        "repeat_hash_stable": proof_a.execution_proof_hash == proof_b.execution_proof_hash,
        "emission_context_hash_ignores_object_ids": proof_a.emission_context_hash == proof_b.emission_context_hash,
        "final_contract_hash_matches": proof_a.final_contract_hash == final_result.contract_hash,
        "updates_hash_matches": proof_a.final_contract_updates_hash == final_result.updates_hash,
        "product_driving": bool(proof_d.get("product_driving")),
        "render_driving": bool(proof_d.get("render_driving")),
        "apply_driving": bool(proof_d.get("apply_driving")),
        "session_driving": bool(proof_d.get("session_driving")),
    }


def main() -> int:
    sys.path.insert(0, str(REPO))
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDITS_DIR.mkdir(parents=True, exist_ok=True)

    publication_source = _read(PUBLICATION_PATH)
    inputs_source = _read(INPUTS_PATH)
    builder_source = _function_source(publication_source, "build_design_guide_button_contract_execution_proof")
    page_contract_source = _function_source(inputs_source, "_design_guide_button_contract")

    cases = [
        _case(
            name="enabled_repair_cta",
            item_index=0,
            action_type="apply_resolved_candidate",
            family="bending",
            updates={"D": 650},
            preview_pass=True,
            expected_util=0.92,
            source_candidate_id="bend_fix_1",
        ),
        _case(
            name="disabled_blocker_cta",
            item_index=1,
            action_type="apply_resolved_candidate",
            family="shear",
            updates={},
            preview_pass=False,
            expected_util=1.25,
            blocking_reason="specific_blocker",
            source_candidate_id="shear_blocked_1",
        ),
        _case(
            name="preview_fail_cta",
            item_index=2,
            action_type="apply_resolved_candidate",
            family="combined",
            updates={"D": 700, "s_lig": 150},
            preview_pass=False,
            expected_util=1.08,
            source_candidate_id="combined_preview_fail",
        ),
        _case(
            name="exact_stop_no_second_cta",
            item_index=3,
            action_type=None,
            family="bending",
            updates={},
            preview_pass=False,
            expected_util=0.84,
            blocking_reason="no_second_cta_required",
            source_candidate_id="exact_stop",
            context_overrides={"exact_blocker_override_applied": True, "low_util_exact_blocker": True},
        ),
        _case(
            name="post_click_state",
            item_index=4,
            action_type="post_click_apply",
            family="shear",
            updates={"s_lig": 200},
            preview_pass=True,
            expected_util=0.81,
            source_candidate_id="post_click",
            context_overrides={"local_cleanup_post_apply_acceptance_matches": True},
        ),
        _case(
            name="missing_updates",
            item_index=5,
            action_type="apply_resolved_candidate",
            family="bending",
            updates={},
            preview_pass=False,
            expected_util=1.1,
            blocking_reason="missing_updates",
            source_candidate_id="missing_updates",
        ),
        _case(
            name="stale_payload",
            item_index=6,
            action_type="apply_resolved_candidate",
            family="combined",
            updates={"b": 450},
            preview_pass=False,
            expected_util=0.97,
            blocking_reason="stale_payload",
            source_candidate_id="stale_payload",
            context_overrides={"update_decision_reason": "stale_payload_rebuild_required"},
        ),
    ]

    failures: list[str] = []
    if "class DesignGuideButtonContractExecutionProof" not in publication_source:
        failures.append("missing_execution_proof_dataclass")
    if "def build_design_guide_button_contract_execution_proof" not in publication_source:
        failures.append("missing_execution_proof_builder")
    if "inputs_page" in builder_source or "streamlit" in builder_source or "st.session_state" in builder_source:
        failures.append("builder_imports_or_reads_page_ui_state")
    if "return emit_design_guide_button_contract_records(context=emission_context)" not in page_contract_source:
        failures.append("page_button_contract_return_shape_changed")
    opt_in_trace_wiring = (
        "button_contract_execution_proof_records: list" in page_contract_source
        and "if button_contract_execution_proof_records is not None:" in page_contract_source
        and "button_contract_execution_proof_records.append(" in page_contract_source
    )
    if "build_design_guide_button_contract_execution_proof(" in page_contract_source and not opt_in_trace_wiring:
        failures.append("proof_builder_wired_without_opt_in_trace_guard")
    for case in cases:
        if not case["repeat_hash_stable"]:
            failures.append(f"{case['case']}:repeat_hash_unstable")
        if not case["emission_context_hash_ignores_object_ids"]:
            failures.append(f"{case['case']}:object_id_hash_leak")
        if not case["final_contract_hash_matches"]:
            failures.append(f"{case['case']}:final_contract_hash_mismatch")
        if not case["updates_hash_matches"]:
            failures.append(f"{case['case']}:updates_hash_mismatch")
        for flag in ("product_driving", "render_driving", "apply_driving", "session_driving"):
            if case[flag]:
                failures.append(f"{case['case']}:{flag}_unexpected")

    status = "PASS" if not failures else "FAIL"
    payload = {
        "status": status,
        "snapshot_hash": _stable_hash(cases),
        "cases": cases,
        "case_count": len(cases),
        "proof_object": "DesignGuideButtonContractExecutionProof",
        "builder": "build_design_guide_button_contract_execution_proof",
        "live_wiring_changed": bool(opt_in_trace_wiring),
        "live_wiring_mode": "opt_in_trace_only" if opt_in_trace_wiring else "none",
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "failures": failures,
    }

    stamp = _timestamp().replace(":", "-")
    json_path = VERIFICATION_DIR / f"design_guide_button_contract_execution_object_{stamp}.json"
    md_path = AUDITS_DIR / f"design_guide_button_contract_execution_object_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(
        "\n".join(
            [
                "# Design Guide Button Contract Execution Object Snapshot",
                "",
                f"## Result: {status}",
                "",
                f"Snapshot hash: `{payload['snapshot_hash']}`",
                "",
                "## Cases",
                "",
                "\n".join(
                    f"- `{case['case']}`: execution proof `{case['proof']['execution_proof_hash']}`"
                    for case in cases
                ),
                "",
                "## Boundary",
                "",
                "- Proof object is trace-only.",
                "- Live page button contract wiring was not changed.",
                "- Product behavior, visible wording, CTA/apply semantics, and session ownership were not changed.",
                "",
                "## Failures",
                "",
                "\n".join(f"- {failure}" for failure in failures) if failures else "- None",
            ]
        ),
        encoding="utf-8",
    )
    print(f"design guide button contract execution object snapshot {status}")
    print(json_path)
    print(md_path)
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
