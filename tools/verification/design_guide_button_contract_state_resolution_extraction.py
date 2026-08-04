"""Verify extraction of pure button-contract state/result resolution."""

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


def _sample_state_resolution() -> dict[str, object]:
    publication = importlib.import_module("design_brain.publication")
    item = {
        "title": "Apply recommendation",
        "action_type": "apply_resolved_candidate",
        "family": "bending",
        "candidate_id": "candidate-650",
        "action_payload": {"updates": {"D": 650}},
    }
    updates = {"D": 650}
    source_candidate_id = publication.normalise_design_guide_candidate_id(
        publication.guidance_item_source_candidate_id(item),
        family="bending",
        updates=updates,
    )
    legacy = publication.build_design_guide_button_contract_result(
        actionable=True,
        action_type="apply_resolved_candidate",
        family="bending",
        updates=updates,
        preview_pass=True,
        expected_util=0.92,
        blocking_reason=None,
        source_candidate_id=source_candidate_id,
    )
    resolved = publication.resolve_design_guide_button_contract_state_result(
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
    blocked = publication.resolve_design_guide_button_contract_state_result(
        item=item,
        action_type="apply_resolved_candidate",
        effective_action_type="apply_resolved_candidate",
        family="bending",
        updates=updates,
        executor_allowed=True,
        preview_pass=False,
        expected_util=1.3,
        blocking_reason="contract_blocked",
    )
    repeat = publication.resolve_design_guide_button_contract_state_result(
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
    return {
        "legacy_contract": legacy.final_contract,
        "resolved_contract": resolved.final_result.final_contract,
        "contract_matches_legacy": resolved.final_result.final_contract == legacy.final_contract,
        "source_candidate_id_matches": resolved.source_candidate_id == source_candidate_id,
        "actionable_matches_legacy": resolved.actionable == legacy.actionable,
        "action_type_preserved": resolved.final_result.final_contract.get("action_type") == "apply_resolved_candidate",
        "blocking_reason_preserved": blocked.final_result.final_contract.get("blocking_reason") == "contract_blocked",
        "blocked_actionable_false": blocked.actionable is False,
        "updates_hash_matches": resolved.updates_hash == legacy.updates_hash,
        "contract_hash_matches": resolved.contract_hash == legacy.contract_hash,
        "state_resolution_hash_stable": resolved.state_resolution_hash == repeat.state_resolution_hash,
    }


def main() -> int:
    sys.path.insert(0, str(REPO))
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDITS_DIR.mkdir(parents=True, exist_ok=True)

    inputs_source = _read(INPUTS_PATH)
    publication_source = _read(PUBLICATION_PATH)
    final_publication_source = _read(FINAL_PUBLICATION_PATH)
    helper_source = _function_source(inputs_source, "_design_guide_button_contract")
    resolver_source = _function_source(
        publication_source,
        "resolve_design_guide_button_contract_state_result",
    )
    sample = _sample_state_resolution()
    focused_results = [_run(command) for command in FOCUSED_COMMANDS]
    lock_results = [_run(command) for command in LOCK_COMMANDS]

    checks = {
        "page_helper_exists": bool(helper_source),
        "publication_state_resolver_present": bool(resolver_source),
        "publication_state_result_dataclass_present": (
            "class DesignGuideButtonContractStateResolutionResult" in publication_source
        ),
        "inputs_imports_state_resolver": (
            "resolve_design_guide_button_contract_state_result," in inputs_source
        ),
        "inputs_imports_state_result": (
            "DesignGuideButtonContractStateResolutionResult," in inputs_source
        ),
        "page_delegates_state_resolution": (
            "state_resolution: DesignGuideButtonContractStateResolutionResult" in helper_source
            and "resolve_design_guide_button_contract_state_result(" in helper_source
        ),
        "page_no_longer_builds_final_result_inline": (
            "final_result = build_design_guide_button_contract_result(" not in helper_source
            and "source_candidate_id = _normalise_design_guide_candidate_id(" not in helper_source
        ),
        "old_final_result_import_removed_from_inputs": (
            "build_design_guide_button_contract_result," not in inputs_source
        ),
        "publication_resolver_uses_existing_result_builder": (
            "build_design_guide_button_contract_result(" in resolver_source
        ),
        "previous_extraction_boundaries_still_delegated": all(
            token in helper_source
            for token in (
                "build_design_guide_button_contract_execution_scope_defaults(",
                "resolve_design_guide_button_contract_payload_update_resolution(",
                "build_design_guide_button_contract_actionability_probe_setup(",
                "apply_design_guide_button_contract_actionability_probe_outputs(",
                "build_design_guide_button_contract_emission_context(",
                "build_design_guide_button_contract_execution_proof(",
            )
        ),
        "probe_callbacks_remain_page_owned": (
            "_collect_design_guide_button_contract_actionability_probe_outputs(" in helper_source
        ),
        "apply_routing_remains_page_owned": (
            "_record_rendered_design_guide_primary_apply_payload" in inputs_source
            and ".button(" not in resolver_source
        ),
        "publication_helper_has_no_streamlit_or_session": all(
            token not in resolver_source
            for token in ("inputs_page", "st.session_state", "streamlit", ".button(")
        ),
        "cta_authority_remains_final_publication": "FinalDesignGuidePublication.cta" in final_publication_source,
        "sample_contract_matches_legacy": bool(sample.get("contract_matches_legacy")),
        "sample_source_candidate_id_matches": bool(sample.get("source_candidate_id_matches")),
        "sample_actionable_matches_legacy": bool(sample.get("actionable_matches_legacy")),
        "sample_action_type_preserved": bool(sample.get("action_type_preserved")),
        "sample_blocking_reason_preserved": bool(sample.get("blocking_reason_preserved")),
        "sample_blocked_actionable_false": bool(sample.get("blocked_actionable_false")),
        "sample_hashes_match": bool(
            sample.get("updates_hash_matches") and sample.get("contract_hash_matches")
        ),
        "sample_state_resolution_hash_stable": bool(sample.get("state_resolution_hash_stable")),
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
        "recursive_verifier_note": (
            "Prior extraction verifiers are not nested here because they recursively "
            "rerun the same composed locks. This verifier performs direct source/sample "
            "checks for the prerequisite boundaries and runs the composed locks directly."
        ),
        "remaining_page_owned_boundaries": [
            "Apply routing",
            "page-owned probe callback execution",
            "Streamlit/session reads and writes",
            "rendered button/click execution",
            "large emission context packaging",
        ],
        "next_extractable_section": "button contract emission/context packaging extraction",
    }
    json_path = VERIFICATION_DIR / f"design_guide_button_contract_state_resolution_extraction_{timestamp.replace(':', '-')}.json"
    report_path = AUDITS_DIR / f"design_guide_button_contract_state_resolution_extraction_{timestamp.replace(':', '-')}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report = [
        "# Design Guide Button Contract State Resolution Extraction",
        "",
        f"## Result: {status}",
        "",
        f"Helper line count: `{payload['helper_line_count']}`",
        "",
        "## Proof",
        "",
        "- `_design_guide_button_contract(...)` delegates final state/result shaping to `design_brain.publication.resolve_design_guide_button_contract_state_result(...)`.",
        "- Page-local source candidate/final result assembly is removed from the helper.",
        "- The publication helper has no Streamlit/session/render/apply ownership.",
        "- Sample contract, action type, blocking reason, actionable state, source candidate id, and hashes match the legacy builder path.",
        "- Apply routing and probe callback execution remain page-owned.",
        "",
        "## Remaining Body",
        "",
        "- Execution-scope defaults delegation.",
        "- Payload/update resolution delegation.",
        "- Actionability probe setup and page-owned callback execution.",
        "- Emission context packaging and execution proof append.",
        "- Final emission to existing records helper.",
        "",
        "## Next Safe Target",
        "",
        "Button contract emission/context packaging extraction.",
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
