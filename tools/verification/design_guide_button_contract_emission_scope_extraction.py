"""Verify extraction of button-contract emission context packaging."""

from __future__ import annotations

import ast
from datetime import datetime, timezone
import importlib
import json
from pathlib import Path
import subprocess
import sys


REPO = Path(__file__).resolve().parents[2]
INPUTS_PATH = REPO / "inputs_page.py"
PUBLICATION_PATH = REPO / "design_brain" / "publication.py"
FINAL_PUBLICATION_PATH = REPO / "design_brain" / "final_publication.py"
VERIFICATION_DIR = REPO / "artifacts" / "verification"
AUDITS_DIR = REPO / "artifacts" / "audits"


FOCUSED_COMMANDS = [
    [sys.executable, "tools/verification/cta_button_contract_check.py"],
]

LOCK_COMMANDS = [
    [sys.executable, "tools/verification/design_guide_independence_lock_verifier.py"],
    [sys.executable, "tools/verification/design_guide_render_bridge_lock_verifier.py"],
    [sys.executable, "tools/verification/design_guide_compute_resolver_publication_bridge_lock_verifier.py"],
]


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function_source(source: str, function_name: str) -> str:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            start = min([node.lineno, *(decorator.lineno for decorator in node.decorator_list)]) - 1
            end = node.end_lineno or node.lineno
            return "\n".join(lines[start:end])
    return ""


def _run(command: list[str]) -> dict[str, object]:
    completed = subprocess.run(
        command,
        cwd=REPO,
        text=True,
        capture_output=True,
        timeout=300,
    )
    return {
        "command": " ".join(command),
        "returncode": completed.returncode,
        "stdout_tail": completed.stdout[-4000:],
        "stderr_tail": completed.stderr[-4000:],
        "passed": completed.returncode == 0,
    }


def _sample_emission_scope() -> dict[str, object]:
    publication = importlib.import_module("design_brain.publication")
    item = {
        "title": "Apply recommendation",
        "action_type": "apply_resolved_candidate",
        "family": "bending",
        "candidate_id": "candidate-650",
    }
    updates = {"D": 650}
    state_result = publication.resolve_design_guide_button_contract_state_result(
        item=item,
        action_type="apply_resolved_candidate",
        effective_action_type="apply_resolved_candidate",
        family="bending",
        updates=updates,
        executor_allowed=True,
        preview_pass=True,
        expected_util=0.92,
        blocking_reason=None,
    )
    kwargs = {
        "item_index": 2,
        "item": item,
        "work_after": {"updates": updates},
        "updates": updates,
        "updates_source": "sample",
        "final_contract": state_result.final_result.final_contract,
        "action_type": "apply_resolved_candidate",
        "effective_action_type": "apply_resolved_candidate",
        "family": "bending",
        "expected_util": 0.92,
        "blocking_reason": None,
        "executor_allowed": True,
        "executor_reason": None,
        "executor_exception_type": None,
        "executor_contract_evaluated": True,
        "preview_pass": True,
        "preview_util": 0.92,
        "preview_reason": None,
        "preview_evaluated": True,
        "source_candidate_id": state_result.source_candidate_id,
        "actionable": state_result.actionable,
        "update_decision_reason": "sample",
        "update_exception_type": None,
        "safe_incremental_below_threshold": False,
        "family_exact_cleanup_blocker": False,
        "local_cleanup_post_apply_acceptance_matches": None,
        "best_safe_partial_cleanup": False,
        "low_util_exact_blocker": False,
        "accepted_band_cleanup_evaluated": False,
        "accepted_band_cleanup": None,
        "accepted_band_family_preview_util": None,
        "accepted_band_override_applied": False,
        "partial_cleanup_override_applied": False,
        "exact_blocker_override_applied": False,
        "family_truth_probe_evaluated": True,
        "family_truth_probe_exception_type": None,
        "family_truth_probe_expected_util": 0.92,
        "combined_truth_probe_evaluated": False,
        "combined_truth_probe_exception_type": None,
        "combined_truth_probe_expected_util": None,
        "resolution_blocking_reason_before": None,
        "resolution_executor_allowed_before": False,
        "resolution_preview_pass_before": False,
        "resolution_expected_util_before": 1.21,
        "resolution_family_before": "bending",
        "resolution_actionable_before": False,
        "resolution_enabled_before": False,
        "update_resolution_input_record": None,
        "update_resolution_applicable": True,
        "update_family_before": "bending",
        "update_action_type_before": "apply_resolved_candidate",
        "update_expected_util_before": 1.21,
        "blocking_reason_override": None,
        "work_before": dict(item),
        "item_snapshot_before": dict(item),
        "work_mutation_record": None,
        "work_mutation_input_snapshot": dict(item),
        "work_mutation_output_snapshot": {"updates": updates},
        "work_mutation_selected_source": "sample",
        "work_mutation_selected_updates": updates,
        "work_mutation_selected_candidate_id": "candidate-650",
        "work_mutation_selected_util": 0.92,
        "work_mutation_applied": True,
        "work_mutation_object_id_before": 100,
        "work_mutation_object_id_after": 200,
        "actionability_resolution_records": None,
        "actionability_probe_output_records": None,
        "actionability_helper_output_records": None,
        "actionability_input_records": None,
        "actionability_predicate_records": None,
        "actionability_application_records": None,
        "actionability_decision_records": None,
        "update_resolution_input_records": None,
        "update_resolution_decision_records": None,
        "scalar_records": None,
        "work_mutation_records": None,
        "update_resolution_records": None,
    }
    legacy = publication.build_design_guide_button_contract_emission_context(**kwargs)
    scoped = publication.build_design_guide_button_contract_emission_context_from_scope(
        item_index=2,
        item=item,
        scope={key: value for key, value in kwargs.items() if key not in {"item_index", "item", "final_contract", "source_candidate_id", "actionable"}},
        final_result=state_result.final_result,
    )
    return {
        "legacy_hash": publication.publication_snapshot_hash(legacy.to_dict()),
        "scoped_hash": publication.publication_snapshot_hash(scoped.to_dict()),
        "contexts_match": legacy.to_dict() == scoped.to_dict(),
        "final_contract_preserved": scoped.final_contract == state_result.final_result.final_contract,
        "source_candidate_id_preserved": scoped.source_candidate_id == state_result.source_candidate_id,
        "actionable_preserved": scoped.actionable == state_result.actionable,
    }


def main() -> int:
    sys.path.insert(0, str(REPO))
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDITS_DIR.mkdir(parents=True, exist_ok=True)

    inputs_source = _read(INPUTS_PATH)
    publication_source = _read(PUBLICATION_PATH)
    final_publication_source = _read(FINAL_PUBLICATION_PATH)
    helper_source = _function_source(inputs_source, "_design_guide_button_contract")
    scope_builder_source = _function_source(
        publication_source,
        "build_design_guide_button_contract_emission_context_from_scope",
    )
    sample = _sample_emission_scope()
    focused_results = [_run(command) for command in FOCUSED_COMMANDS]
    lock_results = [_run(command) for command in LOCK_COMMANDS]

    checks = {
        "page_helper_exists": bool(helper_source),
        "publication_scope_builder_present": bool(scope_builder_source),
        "page_delegates_scope_packaging": (
            "build_design_guide_button_contract_emission_context_from_scope(" in helper_source
        ),
        "page_no_longer_calls_raw_emission_builder": (
            "build_design_guide_button_contract_emission_context(" not in helper_source
            and "build_design_guide_button_contract_emission_context," not in inputs_source
        ),
        "scope_builder_whitelists_fields": (
            'get("work_after")' in scope_builder_source
            and 'get("updates_source")' in scope_builder_source
            and 'get("actionability_resolution_records")' in scope_builder_source
        ),
        "scope_builder_does_not_store_whole_scope": (
            "scope=" not in scope_builder_source.replace("scope: Mapping[str, Any]", "")
            and ".to_dict()" not in scope_builder_source
        ),
        "apply_routing_remains_page_owned": (
            "_record_rendered_design_guide_primary_apply_payload" in inputs_source
            and ".button(" not in scope_builder_source
        ),
        "probe_callbacks_remain_page_owned": (
            "_collect_design_guide_button_contract_actionability_probe_outputs(" in helper_source
        ),
        "publication_helper_has_no_streamlit_or_session": all(
            token not in scope_builder_source
            for token in ("inputs_page", "st.session_state", "streamlit", ".button(")
        ),
        "cta_authority_remains_final_publication": "FinalDesignGuidePublication.cta" in final_publication_source,
        "sample_contexts_match": bool(sample.get("contexts_match")),
        "sample_final_contract_preserved": bool(sample.get("final_contract_preserved")),
        "sample_source_candidate_id_preserved": bool(sample.get("source_candidate_id_preserved")),
        "sample_actionable_preserved": bool(sample.get("actionable_preserved")),
        "focused_verifiers_pass": all(result["passed"] for result in focused_results),
        "composed_locks_pass": all(result["passed"] for result in lock_results),
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    timestamp = _timestamp()
    payload = {
        "status": status,
        "timestamp": timestamp,
        "checks": checks,
        "sample": sample,
        "helper_line_count": len(helper_source.splitlines()),
        "focused_results": focused_results,
        "lock_results": lock_results,
        "remaining_page_owned_boundaries": [
            "Apply routing",
            "page-owned probe callback execution",
            "Streamlit/session state",
            "rendered button/click execution",
            "execution proof append",
        ],
        "next_extractable_section": "shell/deadness check for remaining button-contract body",
    }
    json_path = VERIFICATION_DIR / f"design_guide_button_contract_emission_scope_extraction_{timestamp.replace(':', '-')}.json"
    report_path = AUDITS_DIR / f"design_guide_button_contract_emission_scope_extraction_{timestamp.replace(':', '-')}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report = [
        "# Design Guide Button Contract Emission Scope Extraction",
        "",
        f"## Result: {status}",
        "",
        f"Helper line count: `{payload['helper_line_count']}`",
        "",
        "## Proof",
        "",
        "- `_design_guide_button_contract(...)` delegates emission-context packaging to `design_brain.publication.build_design_guide_button_contract_emission_context_from_scope(...)`.",
        "- The helper consumes a whitelist of resolved contract fields and does not store the whole page scope.",
        "- Sample scoped context matches the existing explicit publication builder context.",
        "- Apply routing and probe callback execution remain page-owned.",
        "",
        "## Next Safe Target",
        "",
        "Shell/deadness check for the remaining `_design_guide_button_contract(...)` body.",
    ]
    report_path.write_text("\n".join(report) + "\n", encoding="utf-8")
    print(status)
    print(json_path)
    print(report_path)
    if status != "PASS":
        print(json.dumps({k: v for k, v in checks.items() if not v}, indent=2, sort_keys=True))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
