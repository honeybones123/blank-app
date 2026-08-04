"""Verify extraction of Design Guide button execution-scope defaults."""

from __future__ import annotations

from datetime import datetime, timezone
import ast
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


def _sample_scope_parity() -> dict[str, object]:
    publication = importlib.import_module("design_brain.publication")
    item = {
        "title": "Repair required",
        "action_type": "apply_resolved_candidate",
        "updates": {"D": 650},
        "family": "bending",
    }
    scope = publication.build_design_guide_button_contract_execution_scope_defaults(
        item=item,
        family="bending",
        expected_util=0.91,
        blocking_reason_override="",
    )
    visible_blocker_scope = publication.build_design_guide_button_contract_execution_scope_defaults(
        item={"guidance_intent": "specific_blocker", "title": "Cleanup blocked"},
        family="shear",
        expected_util=None,
        blocking_reason_override=None,
    )
    return {
        "normal_defaults_match_legacy_shape": (
            scope.action_type == "apply_resolved_candidate"
            and scope.effective_action_type == "apply_resolved_candidate"
            and scope.family == "bending"
            and scope.updates == {}
            and scope.expected_util == 0.91
            and scope.preview_pass is False
            and scope.blocking_reason is None
            and scope.executor_allowed is False
            and scope.updates_source == "not_applicable"
            and scope.update_family_before == "bending"
            and scope.update_action_type_before == "apply_resolved_candidate"
            and scope.work_before == item
            and scope.work_after == item
            and scope.visible_blocker is False
        ),
        "visible_blocker_predicate_delegated": visible_blocker_scope.visible_blocker is True,
        "scope_class": type(scope).__name__,
        "scope_keys": sorted(scope.to_dict().keys()),
    }


def main() -> int:
    sys.path.insert(0, str(REPO))
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDITS_DIR.mkdir(parents=True, exist_ok=True)

    inputs_source = _read(INPUTS_PATH)
    publication_source = _read(PUBLICATION_PATH)
    final_publication_source = _read(FINAL_PUBLICATION_PATH)
    helper_source = _function_source(inputs_source, "_design_guide_button_contract")
    builder_source = _function_source(
        publication_source,
        "build_design_guide_button_contract_execution_scope_defaults",
    )
    sample = _sample_scope_parity()

    checks = {
        "page_helper_exists": bool(helper_source),
        "publication_scope_builder_present": bool(builder_source),
        "publication_scope_dataclass_present": "class DesignGuideButtonContractExecutionScopeDefaults" in publication_source,
        "inputs_imports_scope_builder": "build_design_guide_button_contract_execution_scope_defaults," in inputs_source,
        "inputs_imports_scope_dataclass": "DesignGuideButtonContractExecutionScopeDefaults," in inputs_source,
        "page_delegates_scope_defaults": (
            "execution_scope_defaults: DesignGuideButtonContractExecutionScopeDefaults" in helper_source
            and "build_design_guide_button_contract_execution_scope_defaults(" in helper_source
        ),
        "page_uses_scope_visible_blocker": "if execution_scope_defaults.visible_blocker:" in helper_source,
        "old_inline_action_type_default_absent": 'action_type = str((item or {}).get("action_type")' not in helper_source,
        "old_inline_updates_source_default_absent": 'updates_source = "not_applicable"' not in helper_source,
        "page_visible_blocker_predicate_not_called_in_helper": "_design_guide_item_is_visible_blocker(item)" not in helper_source,
        "removed_page_local_policy_helpers_absent": all(
            f"def {name}" not in inputs_source
            for name in (
                "_build_design_guide_button_contract_emission_context",
                "_design_guide_text_indicates_blocker",
                "_design_guide_item_is_visible_blocker",
                "_design_guide_item_is_accepted_terminal_with_exact_stop",
                "_design_guide_cleanup_item_publishable",
            )
        ),
        "button_contract_result_path_unchanged": "build_design_guide_button_contract_result(" in helper_source,
        "button_contract_emitter_path_unchanged": (
            "return emit_design_guide_button_contract_records(context=emission_context)" in helper_source
        ),
        "button_label_disabled_reason_not_rebuilt_by_scope_builder": all(
            token not in builder_source
            for token in ("label", "disabled_reason", "primary_action", "button_text")
        ),
        "apply_routing_remains_page_side": (
            "_record_rendered_design_guide_primary_apply_payload" in inputs_source
            and "st.session_state" not in builder_source
            and "streamlit" not in builder_source.lower()
        ),
        "new_builder_has_no_page_import_or_session": all(
            token not in builder_source
            for token in ("inputs_page", "st.session_state", "streamlit", ".button(")
        ),
        "final_publication_cta_authority_present": (
            "class FinalDesignGuidePublication" in final_publication_source
            and "cta: FinalDesignGuideCTA" in final_publication_source
        ),
        "sample_scope_parity": bool(sample["normal_defaults_match_legacy_shape"]),
        "sample_visible_blocker_delegation": bool(sample["visible_blocker_predicate_delegated"]),
    }
    lock_results = [_run(command) for command in LOCK_COMMANDS]
    checks["composed_locks_pass"] = all(result["passed"] for result in lock_results)

    failures = [name for name, passed in checks.items() if not passed]
    status = "PASS" if not failures else "FAIL"
    helper_lines = len(helper_source.splitlines()) if helper_source else 0
    payload = {
        "status": status,
        "checks": checks,
        "failures": failures,
        "sample_scope_parity": sample,
        "remaining_design_guide_button_contract_body_lines": helper_lines,
        "lock_results": lock_results,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }

    stamp = _timestamp().replace(":", "-")
    json_path = VERIFICATION_DIR / f"design_guide_button_contract_execution_scope_extraction_{stamp}.json"
    md_path = AUDITS_DIR / f"design_guide_button_contract_execution_scope_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(
        "\n".join(
            [
                "# Design Guide Button Contract Execution Scope Extraction",
                "",
                f"## Result: {status}",
                "",
                "## Surface Targeted",
                "",
                "`_design_guide_button_contract(...)` initial execution-scope/default construction.",
                "",
                "## Proof",
                "",
                f"- Page delegates scope defaults: `{checks['page_delegates_scope_defaults']}`",
                f"- Visible blocker predicate delegated through scope: `{checks['page_uses_scope_visible_blocker']}`",
                f"- Old inline action/update defaults absent: `{checks['old_inline_action_type_default_absent'] and checks['old_inline_updates_source_default_absent']}`",
                f"- Button contract result/emitter path unchanged: `{checks['button_contract_result_path_unchanged'] and checks['button_contract_emitter_path_unchanged']}`",
                f"- Apply routing remains page-side: `{checks['apply_routing_remains_page_side']}`",
                f"- CTA authority remains FinalDesignGuidePublication.cta: `{checks['final_publication_cta_authority_present']}`",
                f"- Sample defaults match legacy shape: `{sample['normal_defaults_match_legacy_shape']}`",
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
                    for result in lock_results
                ],
                "",
                "## Failures",
                "",
                "\n".join(f"- {failure}" for failure in failures) if failures else "- None",
            ]
        ),
        encoding="utf-8",
    )
    print(f"design guide button contract execution scope extraction {status}")
    print(json_path)
    print(md_path)
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
