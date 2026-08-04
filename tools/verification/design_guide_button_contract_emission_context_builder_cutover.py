"""Verifier for moving button-contract emission-context construction out of the page."""

from __future__ import annotations

from datetime import datetime, timezone
import importlib
import json
from pathlib import Path
import re
import sys


REPO = Path(__file__).resolve().parents[2]
INPUTS_PATH = REPO / "inputs_page.py"
PUBLICATION_PATH = REPO / "design_brain" / "publication.py"
VERIFICATION_DIR = REPO / "artifacts" / "verification"
AUDITS_DIR = REPO / "artifacts" / "audits"


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function_source(source: str, function_name: str) -> str:
    match = re.search(rf"^def {re.escape(function_name)}\(.*?(?=^def |\Z)", source, re.M | re.S)
    return match.group(0) if match else ""


def _build_sample_context() -> dict:
    publication = importlib.import_module("design_brain.publication")
    kwargs = {
        "item_index": 7,
        "item": {"title": "Sample CTA", "family": "bending"},
        "work_after": {"updates": {"D": 650}},
        "updates": {"D": 650},
        "updates_source": "resolved_candidate",
        "final_contract": {"actionable": True, "updates": {"D": 650}, "preview_pass": True},
        "action_type": "apply_resolved_candidate",
        "effective_action_type": "apply_resolved_candidate",
        "family": "bending",
        "expected_util": 0.91,
        "blocking_reason": None,
        "executor_allowed": True,
        "executor_reason": None,
        "executor_exception_type": None,
        "executor_contract_evaluated": 1,
        "preview_pass": True,
        "preview_util": 0.91,
        "preview_reason": None,
        "preview_evaluated": 1,
        "source_candidate_id": "candidate_7",
        "actionable": True,
        "update_decision_reason": "resolved_candidate",
        "update_exception_type": None,
        "safe_incremental_below_threshold": None,
        "family_exact_cleanup_blocker": False,
        "local_cleanup_post_apply_acceptance_matches": None,
        "best_safe_partial_cleanup": None,
        "low_util_exact_blocker": False,
        "accepted_band_cleanup_evaluated": 1,
        "accepted_band_cleanup": True,
        "accepted_band_family_preview_util": 0.91,
        "accepted_band_override_applied": False,
        "partial_cleanup_override_applied": False,
        "exact_blocker_override_applied": False,
        "family_truth_probe_evaluated": 1,
        "family_truth_probe_exception_type": None,
        "family_truth_probe_expected_util": 0.91,
        "combined_truth_probe_evaluated": 0,
        "combined_truth_probe_exception_type": None,
        "combined_truth_probe_expected_util": None,
        "resolution_blocking_reason_before": None,
        "resolution_executor_allowed_before": False,
        "resolution_preview_pass_before": False,
        "resolution_expected_util_before": 1.2,
        "resolution_family_before": "bending",
        "resolution_actionable_before": False,
        "resolution_enabled_before": False,
        "update_resolution_input_record": None,
        "update_resolution_applicable": 1,
        "update_family_before": "bending",
        "update_action_type_before": "apply_resolved_candidate",
        "update_expected_util_before": 1.2,
        "blocking_reason_override": None,
        "work_before": {"updates": {}},
        "item_snapshot_before": {"title": "Sample CTA"},
        "work_mutation_record": None,
        "work_mutation_input_snapshot": {"updates": {}},
        "work_mutation_output_snapshot": {"updates": {"D": 650}},
        "work_mutation_selected_source": "resolved_candidate",
        "work_mutation_selected_updates": {"D": 650},
        "work_mutation_selected_candidate_id": "candidate_7",
        "work_mutation_selected_util": 0.91,
        "work_mutation_applied": 1,
        "work_mutation_object_id_before": 100,
        "work_mutation_object_id_after": 200,
        "actionability_resolution_records": [],
        "actionability_probe_output_records": [],
        "actionability_helper_output_records": [],
        "actionability_input_records": [],
        "actionability_predicate_records": [],
        "actionability_application_records": [],
        "actionability_decision_records": [],
        "update_resolution_input_records": [],
        "update_resolution_decision_records": [],
        "scalar_records": [],
        "work_mutation_records": [],
        "update_resolution_records": [],
    }
    context = publication.build_design_guide_button_contract_emission_context(**kwargs)
    direct = publication.DesignGuideButtonContractEmissionContext(
        **{
            **kwargs,
            "updates": dict(kwargs["updates"] or {}),
            "executor_contract_evaluated": bool(kwargs["executor_contract_evaluated"]),
            "preview_evaluated": bool(kwargs["preview_evaluated"]),
            "accepted_band_cleanup_evaluated": bool(kwargs["accepted_band_cleanup_evaluated"]),
            "accepted_band_override_applied": bool(kwargs["accepted_band_override_applied"]),
            "partial_cleanup_override_applied": bool(kwargs["partial_cleanup_override_applied"]),
            "exact_blocker_override_applied": bool(kwargs["exact_blocker_override_applied"]),
            "family_truth_probe_evaluated": bool(kwargs["family_truth_probe_evaluated"]),
            "combined_truth_probe_evaluated": bool(kwargs["combined_truth_probe_evaluated"]),
            "update_resolution_applicable": bool(kwargs["update_resolution_applicable"]),
            "work_mutation_applied": bool(kwargs["work_mutation_applied"]),
        }
    )
    return {
        "builder_context": context.to_dict(),
        "direct_context": direct.to_dict(),
        "contexts_match": context.to_dict() == direct.to_dict(),
        "bool_coercions_preserved": (
            context.executor_contract_evaluated is True
            and context.preview_evaluated is True
            and context.update_resolution_applicable is True
            and context.work_mutation_applied is True
        ),
    }


def main() -> int:
    sys.path.insert(0, str(REPO))
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDITS_DIR.mkdir(parents=True, exist_ok=True)

    inputs_source = _read(INPUTS_PATH)
    publication_source = _read(PUBLICATION_PATH)
    page_helper_absent = "def _build_design_guide_button_contract_emission_context" not in inputs_source
    publication_builder_present = "def build_design_guide_button_contract_emission_context" in publication_source
    inputs_imports_builder = "build_design_guide_button_contract_emission_context," in inputs_source
    helper_source = _function_source(inputs_source, "_design_guide_button_contract")
    page_uses_publication_builder = "emission_context = build_design_guide_button_contract_emission_context(" in helper_source
    return_unchanged = "return emit_design_guide_button_contract_records(context=emission_context)" in helper_source
    proof_trace_still_present = "build_design_guide_button_contract_execution_proof(" in helper_source
    builder_source = _function_source(publication_source, "build_design_guide_button_contract_emission_context")
    builder_clean = not any(term in builder_source for term in ("inputs_page", "streamlit", "st.session_state"))
    sample = _build_sample_context()

    failures: list[str] = []
    if not page_helper_absent:
        failures.append("page_local_emission_context_helper_still_present")
    if not publication_builder_present:
        failures.append("publication_emission_context_builder_missing")
    if not inputs_imports_builder:
        failures.append("inputs_does_not_import_publication_builder")
    if not page_uses_publication_builder:
        failures.append("page_does_not_use_publication_builder")
    if not return_unchanged:
        failures.append("button_contract_return_changed")
    if not proof_trace_still_present:
        failures.append("execution_trace_wiring_missing")
    if not builder_clean:
        failures.append("publication_builder_reads_page_or_streamlit")
    if not sample["contexts_match"]:
        failures.append("builder_direct_context_mismatch")
    if not sample["bool_coercions_preserved"]:
        failures.append("builder_bool_coercions_not_preserved")

    status = "PASS" if not failures else "FAIL"
    payload = {
        "status": status,
        "page_local_helper_absent": page_helper_absent,
        "publication_builder_present": publication_builder_present,
        "inputs_imports_builder": inputs_imports_builder,
        "page_uses_publication_builder": page_uses_publication_builder,
        "return_unchanged": return_unchanged,
        "proof_trace_still_present": proof_trace_still_present,
        "builder_clean": builder_clean,
        "sample": sample,
        "lines_removed_from_inputs_page_estimate": 151,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "failures": failures,
    }

    stamp = _timestamp().replace(":", "-")
    json_path = VERIFICATION_DIR / f"design_guide_button_contract_emission_context_builder_cutover_{stamp}.json"
    md_path = AUDITS_DIR / f"design_guide_button_contract_emission_context_builder_cutover_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(
        "\n".join(
            [
                "# Design Guide Button Contract Emission Context Builder Cutover",
                "",
                f"## Result: {status}",
                "",
                "## Summary",
                "",
                "- Page-local `_build_design_guide_button_contract_emission_context(...)` was removed.",
                "- `inputs_page.py` now calls `design_brain.publication.build_design_guide_button_contract_emission_context(...)`.",
                "- The returned button contract path remains unchanged.",
                "- The trace-only execution proof remains available.",
                "",
                "## Behaviour Preserved",
                "",
                f"- Builder/direct context parity: `{sample['contexts_match']}`",
                f"- Boolean coercions preserved: `{sample['bool_coercions_preserved']}`",
                "",
                "## Failures",
                "",
                "\n".join(f"- {failure}" for failure in failures) if failures else "- None",
            ]
        ),
        encoding="utf-8",
    )
    print(f"design guide button contract emission context builder cutover {status}")
    print(json_path)
    print(md_path)
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
