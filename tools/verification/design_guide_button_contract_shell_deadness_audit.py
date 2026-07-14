"""Audit the remaining _design_guide_button_contract body after extraction slices."""

from __future__ import annotations

import ast
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys


REPO = Path(__file__).resolve().parents[2]
INPUTS_PATH = REPO / "inputs_page.py"
PUBLICATION_PATH = REPO / "design_brain" / "publication.py"
VERIFICATION_DIR = REPO / "artifacts" / "verification"
AUDITS_DIR = REPO / "artifacts" / "audits"


COMMANDS = [
    [sys.executable, "tools/verification/cta_button_contract_check.py"],
    [sys.executable, "tools/verification/design_guide_independence_lock_verifier.py"],
    [sys.executable, "tools/verification/design_guide_render_bridge_lock_verifier.py"],
    [sys.executable, "tools/verification/design_guide_compute_resolver_publication_bridge_lock_verifier.py"],
]


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function_node(source: str, function_name: str) -> tuple[ast.FunctionDef | None, str]:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            start = min([node.lineno, *(decorator.lineno for decorator in node.decorator_list)]) - 1
            end = node.end_lineno or node.lineno
            return node, "\n".join(lines[start:end])
    return None, ""


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


def _line_range_for_token(source_lines: list[str], token: str) -> dict[str, object]:
    matches = [index + 1 for index, line in enumerate(source_lines) if token in line]
    return {
        "token": token,
        "lines": matches,
        "present": bool(matches),
    }


def main() -> int:
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDITS_DIR.mkdir(parents=True, exist_ok=True)

    inputs_source = _read(INPUTS_PATH)
    publication_source = _read(PUBLICATION_PATH)
    node, helper_source = _function_node(inputs_source, "_design_guide_button_contract")
    helper_lines = helper_source.splitlines()
    command_results = [_run(command) for command in COMMANDS]

    markers = {
        "delegated_design_brain_publication_boundaries": [
            "build_design_guide_button_contract_execution_scope_defaults(",
            "resolve_design_guide_visible_blocker_disabled_contract(",
            "resolve_design_guide_button_contract_default_guard(",
            "resolve_design_guide_button_contract_payload_update_resolution(",
            "build_design_guide_button_contract_actionability_probe_setup(",
            "apply_design_guide_button_contract_actionability_probe_outputs(",
            "resolve_design_guide_button_contract_state_result(",
            "build_design_guide_button_contract_emission_context_from_scope(",
            "build_design_guide_button_contract_execution_proof(",
            "emit_design_guide_button_contract_records(",
        ],
        "page_owned_allowed_boundaries": [
            "_collect_design_guide_button_contract_actionability_probe_outputs(",
            "state=state",
            "button_contract_execution_proof_records.append(",
        ],
        "remaining_extractable_logic": [
        ],
        "deleted_or_absent_page_owned_builders": [
            "final_result = build_design_guide_button_contract_result(",
            "build_design_guide_button_contract_emission_context(",
            "source_candidate_id = _normalise_design_guide_candidate_id(",
            "collect_design_guide_button_contract_payload_update_evidence(",
            "build_design_guide_button_contract_actionability_probe_inputs(",
            "if not isinstance(item, dict):",
            'blocking_reason = blocking_reason or "invalid_guidance_item"',
            "elif not action_type:",
            'blocking_reason = blocking_reason or "missing_action_type"',
            "source_candidate_id = state_resolution.source_candidate_id",
        ],
    }
    marker_results = {
        category: [_line_range_for_token(helper_lines, token) for token in tokens]
        for category, tokens in markers.items()
    }
    remaining_extractable_present = [
        item for item in marker_results["remaining_extractable_logic"] if item["present"]
    ]
    deleted_absent = all(
        not item["present"] for item in marker_results["deleted_or_absent_page_owned_builders"]
    )
    delegated_present = all(
        item["present"] for item in marker_results["delegated_design_brain_publication_boundaries"]
    )
    allowed_present = all(item["present"] for item in marker_results["page_owned_allowed_boundaries"])

    classification = {
        "signature_and_records": {
            "classification": "page-owned callback/proof wiring",
            "deletion_readiness": "SHELL_ONLY",
        },
        "execution_scope_defaults": {
            "classification": "Design Brain-owned via publication helper",
            "deletion_readiness": "SHELL_ONLY",
        },
        "visible_blocker_branch": {
            "classification": "Design Brain-owned via publication helper; page returns helper result",
            "deletion_readiness": "SHELL_ONLY",
        },
        "invalid_or_missing_action_guard": {
            "classification": "Design Brain-owned via publication helper",
            "deletion_readiness": "SHELL_ONLY",
        },
        "payload_update_resolution": {
            "classification": "Design Brain-owned via publication helper with page callback dependencies",
            "deletion_readiness": "SHELL_ONLY",
        },
        "actionability_probe_callback": {
            "classification": "page-owned callback execution",
            "deletion_readiness": "SHELL_ONLY",
        },
        "state_resolution": {
            "classification": "Design Brain-owned via publication helper",
            "deletion_readiness": "SHELL_ONLY",
        },
        "emission_scope_packaging": {
            "classification": "Design Brain-owned via publication scope adapter",
            "deletion_readiness": "SHELL_ONLY",
        },
        "execution_proof_append": {
            "classification": "page-owned proof record sink append",
            "deletion_readiness": "SHELL_ONLY",
        },
    }
    status = "PASS" if (delegated_present and allowed_present and deleted_absent and all(r["passed"] for r in command_results)) else "FAIL"
    timestamp = _timestamp()
    payload = {
        "status": status,
        "timestamp": timestamp,
        "helper_line_count": len(helper_lines),
        "helper_start_line": node.lineno if node is not None else None,
        "helper_end_line": node.end_lineno if node is not None else None,
        "classification": classification,
        "markers": marker_results,
        "remaining_extractable_present": remaining_extractable_present,
        "deleted_absent": deleted_absent,
        "delegated_publication_boundaries_present": delegated_present,
        "allowed_page_boundaries_present": allowed_present,
        "command_results": command_results,
        "next_exact_target": "button-contract helper is shell-only by current audit; next target is broader inputs_page.py extraction inventory",
        "publication_has_no_streamlit_session_for_new_helpers": all(
            token not in publication_source
            for token in ("streamlit", "st.session_state")
        ),
    }
    json_path = VERIFICATION_DIR / f"design_guide_button_contract_shell_deadness_audit_{timestamp.replace(':', '-')}.json"
    report_path = AUDITS_DIR / f"design_guide_button_contract_shell_deadness_audit_{timestamp.replace(':', '-')}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report = [
        "# Design Guide Button Contract Shell/Deadness Audit",
        "",
        f"## Result: {status}",
        "",
        f"Remaining helper line count: `{payload['helper_line_count']}`",
        "",
        "## Current Classification",
        "",
    ]
    for name, row in classification.items():
        report.append(f"- `{name}`: {row['classification']} ({row['deletion_readiness']})")
    report.extend(
        [
            "",
            "## Remaining Extractable Logic",
            "",
        ]
    )
    if remaining_extractable_present:
        for item in remaining_extractable_present:
            report.append(f"- `{item['token']}` at helper-relative lines `{item['lines']}`")
    else:
        report.append("- None found by this audit.")
    report.extend(
        [
            "",
            "## Deleted/Absent Page Builders",
            "",
            f"- Old inline final-result/source-candidate/emission low-level builders absent: `{deleted_absent}`",
            "",
            "## Next Exact Target",
            "",
            payload["next_exact_target"],
        ]
    )
    report_path.write_text("\n".join(report) + "\n", encoding="utf-8")
    print(status)
    print(json_path)
    print(report_path)
    if status != "PASS":
        print(json.dumps({k: v for k, v in payload.items() if k in {"deleted_absent", "delegated_publication_boundaries_present", "allowed_page_boundaries_present"}}, indent=2, sort_keys=True))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
