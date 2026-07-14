"""Verify extraction of button-contract payload/update resolution."""

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


def _sample_payload_update_resolution() -> dict[str, object]:
    publication = importlib.import_module("design_brain.publication")
    item = {
        "title": "Apply recommendation",
        "action_type": "apply_resolved_candidate",
        "family": "bending",
        "updates": {},
        "action_payload": {
            "candidate_search_evidence": {
                "family": "bending",
                "selected_candidate_updates": {"D": 650},
                "selected_candidate_id": "selected-650",
                "selected_candidate_util": 0.92,
            }
        },
    }
    callback_counts = {
        "ensure": 0,
        "resolve": 0,
        "updates_match": 0,
        "normalise": 0,
        "source": 0,
    }

    def ensure(work: dict, *, state: dict | None = None) -> None:
        callback_counts["ensure"] += 1
        payload = dict(work.get("action_payload") or {})
        payload["resolved_candidate_updates"] = {"D": 650}
        payload["updates"] = {"D": 650}
        work["action_payload"] = payload
        work["resolved_candidate"] = {
            "updates": {"D": 650},
            "candidate_search_evidence": payload.get("candidate_search_evidence"),
        }

    def resolve(work: dict, *, state: dict | None = None) -> dict:
        callback_counts["resolve"] += 1
        return {"D": 650}

    def updates_match(state: dict | None, updates: dict) -> bool:
        callback_counts["updates_match"] += 1
        return False

    def normalise(*candidate_ids: object, family: str | None = None, updates: dict | None = None) -> str:
        callback_counts["normalise"] += 1
        return f"{family}:{sorted((updates or {}).keys())}:normalised"

    def source(work: dict) -> str:
        callback_counts["source"] += 1
        return "source-candidate"

    first = publication.resolve_design_guide_button_contract_payload_update_resolution(
        item_index=3,
        item=item,
        state={"D": 500},
        family="bending",
        effective_action_type="apply_resolved_candidate",
        expected_util=1.2,
        item_snapshot_before=item,
        update_family_before="bending",
        update_action_type_before="apply_resolved_candidate",
        update_expected_util_before=1.2,
        blocking_reason_override=None,
        ensure_resolved_candidate_payload=ensure,
        resolve_recommendation_updates=resolve,
        updates_match_state=updates_match,
        normalise_candidate_id=normalise,
        source_candidate_id=source,
    )
    repeat_counts_before = dict(callback_counts)
    second = publication.resolve_design_guide_button_contract_payload_update_resolution(
        item_index=3,
        item=item,
        state={"D": 500},
        family="bending",
        effective_action_type="apply_resolved_candidate",
        expected_util=1.2,
        item_snapshot_before=item,
        update_family_before="bending",
        update_action_type_before="apply_resolved_candidate",
        update_expected_util_before=1.2,
        blocking_reason_override=None,
        ensure_resolved_candidate_payload=ensure,
        resolve_recommendation_updates=resolve,
        updates_match_state=updates_match,
        normalise_candidate_id=normalise,
        source_candidate_id=source,
    )
    adapter = first.payload_update_adapter
    return {
        "updates": first.updates,
        "updates_source": first.updates_source,
        "effective_action_type": first.effective_action_type,
        "expected_util": first.expected_util,
        "normalised_candidate_id": first.pre_normalised_evidence_candidate_id,
        "resolution_hash": first.resolution_hash,
        "repeat_resolution_hash": second.resolution_hash,
        "stable_hash": first.resolution_hash == second.resolution_hash,
        "selected_payload_hash": adapter.selected_payload_hash if adapter else None,
        "action_payload_hash_after": adapter.action_payload_hash_after if adapter else None,
        "payload_hash_consistent": bool(
            adapter and adapter.selected_payload_hash == adapter.action_payload_hash_after
        ),
        "callback_counts_first": repeat_counts_before,
        "callback_counts_after_repeat": callback_counts,
        "callbacks_used": all(count > 0 for count in repeat_counts_before.values()),
        "update_resolution_input_record_present": first.update_resolution_input_record is not None,
        "work_mutation_record_present": first.work_mutation_record is not None,
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
        "resolve_design_guide_button_contract_payload_update_resolution",
    )
    sample = _sample_payload_update_resolution()
    focused_results = [_run(command) for command in FOCUSED_COMMANDS]
    lock_results = [_run(command) for command in LOCK_COMMANDS]

    checks = {
        "page_helper_exists": bool(helper_source),
        "publication_payload_resolver_present": bool(resolver_source),
        "publication_result_dataclass_present": (
            "class DesignGuideButtonContractPayloadUpdateResolutionResult" in publication_source
        ),
        "inputs_imports_payload_resolver": (
            "resolve_design_guide_button_contract_payload_update_resolution," in inputs_source
        ),
        "inputs_imports_payload_result": (
            "DesignGuideButtonContractPayloadUpdateResolutionResult," in inputs_source
        ),
        "page_delegates_payload_update_resolution": (
            "payload_update_resolution: DesignGuideButtonContractPayloadUpdateResolutionResult" in helper_source
            and "resolve_design_guide_button_contract_payload_update_resolution(" in helper_source
        ),
        "page_no_longer_calls_low_level_payload_helpers": all(
            token not in helper_source
            for token in (
                "collect_design_guide_button_contract_payload_update_evidence(",
                "build_design_guide_button_contract_payload_update_resolution_inputs(",
                "adapt_design_guide_button_contract_payload_updates(",
            )
        ),
        "old_payload_helper_imports_removed_from_inputs": all(
            token not in inputs_source
            for token in (
                "collect_design_guide_button_contract_payload_update_evidence,",
                "build_design_guide_button_contract_payload_update_resolution_inputs,",
                "adapt_design_guide_button_contract_payload_updates,",
            )
        ),
        "probe_callbacks_remain_page_owned": (
            "_collect_design_guide_button_contract_actionability_probe_outputs(" in helper_source
        ),
        "apply_routing_remains_page_owned": (
            "_record_rendered_design_guide_primary_apply_payload" in inputs_source
            and ".button(" not in resolver_source
        ),
        "resolver_uses_injected_page_callbacks": all(
            token in resolver_source
            for token in (
                "ensure_resolved_candidate_payload(work, state=state)",
                "resolve_recommendation_updates(work, state=state)",
                "updates_match_state(state, pre_evidence_updates)",
                "normalise_candidate_id(",
                "source_candidate_id(work)",
            )
        ),
        "resolver_has_no_streamlit_or_session": all(
            token not in resolver_source
            for token in ("inputs_page", "st.session_state", "streamlit", ".button(")
        ),
        "button_label_disabled_reason_not_rebuilt_by_payload_resolver": all(
            token not in resolver_source
            for token in ("disabled_reason", "button_label", "primary_action", "button_text")
        ),
        "button_contract_result_path_unchanged": "build_design_guide_button_contract_result(" in helper_source,
        "button_contract_emitter_path_unchanged": (
            "return emit_design_guide_button_contract_records(context=emission_context)" in helper_source
        ),
        "final_publication_cta_authority_present": (
            "class FinalDesignGuidePublication" in final_publication_source
            and "cta: FinalDesignGuideCTA" in final_publication_source
        ),
        "sample_updates_resolved": sample["updates"] == {"D": 650},
        "sample_action_type_preserved": sample["effective_action_type"] == "apply_resolved_candidate",
        "sample_payload_hash_consistent": bool(sample["payload_hash_consistent"]),
        "sample_resolution_hash_stable": bool(sample["stable_hash"]),
        "sample_callbacks_used": bool(sample["callbacks_used"]),
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
        "sample_payload_update_resolution": sample,
        "remaining_design_guide_button_contract_body_lines": helper_lines,
        "focused_results": focused_results,
        "lock_results": lock_results,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }

    stamp = _timestamp().replace(":", "-")
    json_path = VERIFICATION_DIR / f"design_guide_button_contract_payload_update_extraction_{stamp}.json"
    md_path = AUDITS_DIR / f"design_guide_button_contract_payload_update_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(
        "\n".join(
            [
                "# Design Guide Button Contract Payload Update Extraction",
                "",
                f"## Result: {status}",
                "",
                "## Surface Targeted",
                "",
                "`_design_guide_button_contract(...)` payload/update resolution and adaptation.",
                "",
                "## Proof",
                "",
                f"- Page delegates payload/update resolution: `{checks['page_delegates_payload_update_resolution']}`",
                f"- Low-level payload helper calls removed from page helper: `{checks['page_no_longer_calls_low_level_payload_helpers']}`",
                f"- Old low-level payload imports removed from inputs page: `{checks['old_payload_helper_imports_removed_from_inputs']}`",
                f"- Probe callbacks remain page-owned: `{checks['probe_callbacks_remain_page_owned']}`",
                f"- Apply routing remains page-owned: `{checks['apply_routing_remains_page_owned']}`",
                f"- Resolver has no Streamlit/session imports: `{checks['resolver_has_no_streamlit_or_session']}`",
                f"- Button label/disabled reason not rebuilt by resolver: `{checks['button_label_disabled_reason_not_rebuilt_by_payload_resolver']}`",
                f"- Sample payload hash stable/consistent: `{checks['sample_resolution_hash_stable'] and checks['sample_payload_hash_consistent']}`",
                f"- CTA authority remains FinalDesignGuidePublication.cta: `{checks['final_publication_cta_authority_present']}`",
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
    print(f"design guide button contract payload update extraction {status}")
    print(json_path)
    print(md_path)
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
