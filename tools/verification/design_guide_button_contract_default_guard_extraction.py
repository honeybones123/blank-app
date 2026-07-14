"""Verify extraction of _design_guide_button_contract default guard."""

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


def _sample_default_guard() -> dict[str, object]:
    publication = importlib.import_module("design_brain.publication")
    valid = publication.resolve_design_guide_button_contract_default_guard(
        item={"action_type": "apply_resolved_candidate"},
        action_type="apply_resolved_candidate",
        blocking_reason=None,
        update_decision_reason=None,
    )
    invalid = publication.resolve_design_guide_button_contract_default_guard(
        item=None,
        action_type="apply_resolved_candidate",
        blocking_reason=None,
        update_decision_reason=None,
    )
    missing = publication.resolve_design_guide_button_contract_default_guard(
        item={"title": "No action"},
        action_type="",
        blocking_reason=None,
        update_decision_reason=None,
    )
    override = publication.resolve_design_guide_button_contract_default_guard(
        item=None,
        action_type="apply_resolved_candidate",
        blocking_reason="existing_block",
        update_decision_reason="previous_reason",
    )
    repeat = publication.resolve_design_guide_button_contract_default_guard(
        item=None,
        action_type="apply_resolved_candidate",
        blocking_reason=None,
        update_decision_reason=None,
    )
    return {
        "valid_should_resolve": valid.should_resolve_payload is True,
        "valid_reason": valid.guard_reason,
        "invalid_should_not_resolve": invalid.should_resolve_payload is False,
        "invalid_blocking_reason": invalid.blocking_reason,
        "invalid_update_decision_reason": invalid.update_decision_reason,
        "missing_should_not_resolve": missing.should_resolve_payload is False,
        "missing_blocking_reason": missing.blocking_reason,
        "missing_update_decision_reason": missing.update_decision_reason,
        "override_preserves_existing_blocking_reason": override.blocking_reason == "existing_block",
        "override_updates_decision_to_guard_reason": override.update_decision_reason == "invalid_guidance_item",
        "invalid_hash_stable": invalid.guard_hash == repeat.guard_hash,
    }


def main() -> int:
    sys.path.insert(0, str(REPO))
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDITS_DIR.mkdir(parents=True, exist_ok=True)

    inputs_source = _read(INPUTS_PATH)
    publication_source = _read(PUBLICATION_PATH)
    final_publication_source = _read(FINAL_PUBLICATION_PATH)
    helper_source = _function_source(inputs_source, "_design_guide_button_contract")
    guard_source = _function_source(
        publication_source,
        "resolve_design_guide_button_contract_default_guard",
    )
    sample = _sample_default_guard()
    focused_results = [_run(command) for command in FOCUSED_COMMANDS]
    lock_results = [_run(command) for command in LOCK_COMMANDS]

    checks = {
        "page_helper_exists": bool(helper_source),
        "publication_guard_present": bool(guard_source),
        "publication_guard_dataclass_present": (
            "class DesignGuideButtonContractDefaultGuardResult" in publication_source
        ),
        "inputs_imports_guard": (
            "resolve_design_guide_button_contract_default_guard," in inputs_source
        ),
        "inputs_imports_guard_result": (
            "DesignGuideButtonContractDefaultGuardResult," in inputs_source
        ),
        "page_delegates_default_guard": (
            "default_guard: DesignGuideButtonContractDefaultGuardResult" in helper_source
            and "resolve_design_guide_button_contract_default_guard(" in helper_source
            and "if default_guard.should_resolve_payload:" in helper_source
        ),
        "page_no_longer_owns_invalid_missing_guard_literals": all(
            token not in helper_source
            for token in (
                'blocking_reason = blocking_reason or "invalid_guidance_item"',
                'update_decision_reason = "invalid_guidance_item"',
                'blocking_reason = blocking_reason or "missing_action_type"',
                'update_decision_reason = "missing_action_type"',
                "if not isinstance(item, dict):",
                "elif not action_type:",
            )
        ),
        "page_no_longer_assigns_source_candidate_id_for_final_result": (
            "source_candidate_id = state_resolution.source_candidate_id" not in helper_source
        ),
        "apply_routing_remains_page_owned": (
            "_record_rendered_design_guide_primary_apply_payload" in inputs_source
            and ".button(" not in guard_source
        ),
        "probe_callbacks_remain_page_owned": (
            "_collect_design_guide_button_contract_actionability_probe_outputs(" in helper_source
        ),
        "publication_helper_has_no_streamlit_or_session": all(
            token not in guard_source
            for token in ("inputs_page", "st.session_state", "streamlit", ".button(")
        ),
        "cta_authority_remains_final_publication": "FinalDesignGuidePublication.cta" in final_publication_source,
        "sample_valid_passes": bool(sample.get("valid_should_resolve") and sample.get("valid_reason") is None),
        "sample_invalid_matches_legacy": bool(
            sample.get("invalid_should_not_resolve")
            and sample.get("invalid_blocking_reason") == "invalid_guidance_item"
            and sample.get("invalid_update_decision_reason") == "invalid_guidance_item"
        ),
        "sample_missing_action_matches_legacy": bool(
            sample.get("missing_should_not_resolve")
            and sample.get("missing_blocking_reason") == "missing_action_type"
            and sample.get("missing_update_decision_reason") == "missing_action_type"
        ),
        "sample_existing_blocking_reason_preserved": bool(
            sample.get("override_preserves_existing_blocking_reason")
            and sample.get("override_updates_decision_to_guard_reason")
        ),
        "sample_hash_stable": bool(sample.get("invalid_hash_stable")),
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
        "next_extractable_section": "rerun shell/deadness audit and lock no remaining Design Brain-owned logic",
    }
    json_path = VERIFICATION_DIR / f"design_guide_button_contract_default_guard_extraction_{timestamp.replace(':', '-')}.json"
    report_path = AUDITS_DIR / f"design_guide_button_contract_default_guard_extraction_{timestamp.replace(':', '-')}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report = [
        "# Design Guide Button Contract Default Guard Extraction",
        "",
        f"## Result: {status}",
        "",
        f"Helper line count: `{payload['helper_line_count']}`",
        "",
        "## Proof",
        "",
        "- `_design_guide_button_contract(...)` delegates invalid item / missing action defaults to `design_brain.publication.resolve_design_guide_button_contract_default_guard(...)`.",
        "- The legacy reason values are preserved exactly: `invalid_guidance_item` and `missing_action_type`.",
        "- Apply routing and actionability probe callback execution remain page-owned.",
        "- The publication helper has no Streamlit/session/render/apply ownership.",
        "",
        "## Next Safe Target",
        "",
        "Rerun shell/deadness audit and lock no remaining Design Brain-owned logic.",
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
