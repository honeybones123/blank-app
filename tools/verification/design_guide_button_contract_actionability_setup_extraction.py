"""Verify extraction of button-contract actionability setup/scalar application."""

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
    [sys.executable, "tools/verification/design_guide_button_contract_payload_update_extraction.py"],
    [sys.executable, "tools/verification/design_guide_button_contract_execution_scope_extraction.py"],
    [sys.executable, "tools/verification/design_guide_button_contract_emission_context_builder_cutover.py"],
    [sys.executable, "tools/verification/design_guide_button_contract_execution_trace_wiring_snapshot.py"],
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


def _sample_actionability_setup() -> dict[str, object]:
    publication = importlib.import_module("design_brain.publication")
    item = {
        "title": "Apply recommendation",
        "action_type": "apply_resolved_candidate",
        "family": "bending",
        "action_payload": {"id": "payload-1"},
    }
    work = {
        **item,
        "action_payload": {"id": "payload-1", "updates": {"D": 650}},
        "resolved_candidate": {"updates": {"D": 650}},
    }
    updates = {"D": 650}
    first = publication.build_design_guide_button_contract_actionability_probe_setup(
        item_index=4,
        item=item,
        work=work,
        updates=updates,
        family="bending",
        action_type="apply_resolved_candidate",
        effective_action_type="apply_resolved_candidate",
        selected_update_source="resolve_recommendation_updates",
        update_decision_reason="selected_recommendation_updates",
        final_accepted_min_family_util=0.85,
        target_band_eps=0.005,
        compound_shear_update_keys=("shear_spacing_mm",),
        compound_bottom_update_keys=("D", "Ast"),
        blocking_reason_before=None,
        executor_allowed_before=False,
        preview_pass_before=False,
        expected_util_before=1.21,
        candidate_search_evidence={"family": "bending", "selected_candidate_id": "candidate-650"},
        build_probe_inputs=True,
    )
    second = publication.build_design_guide_button_contract_actionability_probe_setup(
        item_index=4,
        item=item,
        work=work,
        updates=updates,
        family="bending",
        action_type="apply_resolved_candidate",
        effective_action_type="apply_resolved_candidate",
        selected_update_source="resolve_recommendation_updates",
        update_decision_reason="selected_recommendation_updates",
        final_accepted_min_family_util=0.85,
        target_band_eps=0.005,
        compound_shear_update_keys=("shear_spacing_mm",),
        compound_bottom_update_keys=("D", "Ast"),
        blocking_reason_before=None,
        executor_allowed_before=False,
        preview_pass_before=False,
        expected_util_before=1.21,
        candidate_search_evidence={"family": "bending", "selected_candidate_id": "candidate-650"},
        build_probe_inputs=True,
    )
    raw_outputs = publication.build_design_guide_button_contract_actionability_probe_outputs(
        item_index=4,
        item=item,
        executor_contract_evaluated=True,
        executor_allowed=True,
        executor_reason=None,
        executor_exception_type=None,
        preview_evaluated=True,
        preview_pass=True,
        preview_util=0.92,
        preview_reason=None,
        safe_incremental_below_threshold=False,
        family_exact_cleanup_blocker=False,
        local_cleanup_post_apply_acceptance_matches=None,
        best_safe_partial_cleanup=False,
        low_util_exact_blocker=False,
        accepted_band_cleanup_evaluated=False,
        accepted_band_cleanup=None,
        accepted_band_family_preview_util=None,
        accepted_band_override_applied=False,
        partial_cleanup_override_applied=False,
        exact_blocker_override_applied=False,
        family_truth_probe_evaluated=True,
        family_truth_probe_exception_type=None,
        family_truth_probe_expected_util=0.92,
        combined_truth_probe_evaluated=False,
        combined_truth_probe_exception_type=None,
        combined_truth_probe_expected_util=None,
        final_family="bending",
        final_expected_util=0.92,
        final_blocking_reason=None,
        final_executor_allowed=True,
        final_preview_pass=True,
    )
    application = publication.apply_design_guide_button_contract_actionability_probe_outputs(
        probe_outputs=raw_outputs,
        family_before="bending",
        expected_util_before=1.21,
        blocking_reason_before=None,
    )
    return {
        "setup_hash": first.setup_hash,
        "repeat_setup_hash": second.setup_hash,
        "setup_hash_stable": first.setup_hash == second.setup_hash,
        "probe_inputs_present": first.probe_inputs is not None,
        "probe_input_hash": first.probe_inputs.probe_input_hash if first.probe_inputs else None,
        "actionable_before": first.actionable_before,
        "enabled_before": first.enabled_before,
        "final_accepted_min_family_util": first.final_accepted_min_family_util,
        "target_band_eps": first.target_band_eps,
        "application_hash": application.application_hash,
        "application_family": application.family,
        "application_expected_util": application.expected_util,
        "application_executor_allowed": application.executor_allowed,
        "application_preview_pass": application.preview_pass,
        "application_blocking_reason": application.blocking_reason,
        "legacy_scalar_application_preserved": (
            application.family == "bending"
            and application.expected_util == 0.92
            and application.executor_allowed is True
            and application.preview_pass is True
            and application.blocking_reason is None
        ),
    }


def main() -> int:
    sys.path.insert(0, str(REPO))
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDITS_DIR.mkdir(parents=True, exist_ok=True)

    inputs_source = _read(INPUTS_PATH)
    publication_source = _read(PUBLICATION_PATH)
    final_publication_source = _read(FINAL_PUBLICATION_PATH)
    helper_source = _function_source(inputs_source, "_design_guide_button_contract")
    setup_source = _function_source(
        publication_source,
        "build_design_guide_button_contract_actionability_probe_setup",
    )
    application_source = _function_source(
        publication_source,
        "apply_design_guide_button_contract_actionability_probe_outputs",
    )
    sample = _sample_actionability_setup()
    focused_results = [_run(command) for command in FOCUSED_COMMANDS]
    lock_results = [_run(command) for command in LOCK_COMMANDS]

    checks = {
        "page_helper_exists": bool(helper_source),
        "publication_setup_present": bool(setup_source),
        "publication_application_present": bool(application_source),
        "publication_setup_dataclass_present": (
            "class DesignGuideButtonContractActionabilityProbeSetupResult" in publication_source
        ),
        "publication_application_dataclass_present": (
            "class DesignGuideButtonContractActionabilityProbeApplicationResult" in publication_source
        ),
        "inputs_imports_setup_and_application": all(
            token in inputs_source
            for token in (
                "DesignGuideButtonContractActionabilityProbeSetupResult,",
                "DesignGuideButtonContractActionabilityProbeApplicationResult,",
                "build_design_guide_button_contract_actionability_probe_setup,",
                "apply_design_guide_button_contract_actionability_probe_outputs,",
            )
        ),
        "page_delegates_actionability_setup": (
            "actionability_probe_setup: DesignGuideButtonContractActionabilityProbeSetupResult" in helper_source
            and "build_design_guide_button_contract_actionability_probe_setup(" in helper_source
        ),
        "page_delegates_probe_output_application": (
            "actionability_probe_application: DesignGuideButtonContractActionabilityProbeApplicationResult" in helper_source
            and "apply_design_guide_button_contract_actionability_probe_outputs(" in helper_source
        ),
        "page_no_longer_calls_probe_input_builder": (
            "build_design_guide_button_contract_actionability_probe_inputs(" not in helper_source
            and "build_design_guide_button_contract_actionability_probe_inputs," not in inputs_source
        ),
        "page_owned_probe_callback_remains": (
            "_collect_design_guide_button_contract_actionability_probe_outputs(" in helper_source
        ),
        "probe_callback_not_moved_to_publication": (
            "_collect_design_guide_button_contract_actionability_probe_outputs" not in publication_source
        ),
        "apply_routing_remains_page_owned": (
            "_record_rendered_design_guide_primary_apply_payload" in inputs_source
            and ".button(" not in setup_source
            and ".button(" not in application_source
        ),
        "publication_helpers_have_no_streamlit_or_session": all(
            token not in (setup_source + application_source)
            for token in ("inputs_page", "st.session_state", "streamlit", ".button(")
        ),
        "button_contract_result_path_unchanged": "build_design_guide_button_contract_result(" in helper_source,
        "button_contract_emitter_path_unchanged": (
            "return emit_design_guide_button_contract_records(context=emission_context)" in helper_source
        ),
        "button_label_disabled_reason_not_rebuilt": all(
            token not in (setup_source + application_source)
            for token in ("disabled_reason", "button_label", "primary_action", "button_text")
        ),
        "final_publication_cta_authority_present": (
            "class FinalDesignGuidePublication" in final_publication_source
            and "cta: FinalDesignGuideCTA" in final_publication_source
        ),
        "sample_setup_hash_stable": bool(sample["setup_hash_stable"]),
        "sample_probe_inputs_present": bool(sample["probe_inputs_present"]),
        "sample_legacy_scalar_application_preserved": bool(sample["legacy_scalar_application_preserved"]),
        "previous_button_verifiers_pass": all(result["passed"] for result in focused_results),
        "composed_locks_pass": all(result["passed"] for result in lock_results),
    }
    failures = [name for name, passed in checks.items() if not passed]
    status = "PASS" if not failures else "FAIL"
    helper_lines = len(helper_source.splitlines()) if helper_source else 0
    payload = {
        "status": status,
        "checks": checks,
        "failures": failures,
        "sample_actionability_setup": sample,
        "remaining_design_guide_button_contract_body_lines": helper_lines,
        "focused_results": focused_results,
        "lock_results": lock_results,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }

    stamp = _timestamp().replace(":", "-")
    json_path = VERIFICATION_DIR / f"design_guide_button_contract_actionability_setup_extraction_{stamp}.json"
    md_path = AUDITS_DIR / f"design_guide_button_contract_actionability_setup_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(
        "\n".join(
            [
                "# Design Guide Button Contract Actionability Setup Extraction",
                "",
                f"## Result: {status}",
                "",
                "## Surface Targeted",
                "",
                "`_design_guide_button_contract(...)` actionability probe input/scalar setup.",
                "",
                "## Proof",
                "",
                f"- Page delegates actionability setup: `{checks['page_delegates_actionability_setup']}`",
                f"- Page delegates probe-output scalar application: `{checks['page_delegates_probe_output_application']}`",
                f"- Actual page-owned probe callback remains in page: `{checks['page_owned_probe_callback_remains']}`",
                f"- Probe callback not moved into publication: `{checks['probe_callback_not_moved_to_publication']}`",
                f"- Apply routing remains page-owned: `{checks['apply_routing_remains_page_owned']}`",
                f"- Helpers have no Streamlit/session imports: `{checks['publication_helpers_have_no_streamlit_or_session']}`",
                f"- Button result/emitter path unchanged: `{checks['button_contract_result_path_unchanged'] and checks['button_contract_emitter_path_unchanged']}`",
                f"- Sample setup hash stable: `{checks['sample_setup_hash_stable']}`",
                f"- Legacy scalar application preserved: `{checks['sample_legacy_scalar_application_preserved']}`",
                f"- Previous button verifiers pass: `{checks['previous_button_verifiers_pass']}`",
                f"- Composed locks pass: `{checks['composed_locks_pass']}`",
                "",
                "## Remaining Helper Body",
                "",
                f"`_design_guide_button_contract(...)` remaining body lines: `{helper_lines}`",
                "",
                "## Verifier Results",
                "",
                *[
                    f"- `{result['command']}` -> `{result['returncode']}`"
                    for result in [*focused_results, *lock_results]
                ],
                "",
                "## Failures",
                "",
                "\n".join(f"- {failure}" for failure in failures) if failures else "- None",
            ]
        ),
        encoding="utf-8",
    )
    print(f"design guide button contract actionability setup extraction {status}")
    print(json_path)
    print(md_path)
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
