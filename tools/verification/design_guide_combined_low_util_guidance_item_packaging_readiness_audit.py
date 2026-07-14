"""Readiness audit for combined low-util guidance item packaging extraction."""

from __future__ import annotations

import ast
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
FUNCTION_NAME = "_combine_best_safe_shear_with_bending_cleanup_item"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _function_source(path: Path, function_name: str) -> tuple[str, int, int]:
    source = path.read_text(encoding="utf-8", errors="replace")
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            end_lineno = getattr(node, "end_lineno", None)
            if end_lineno is None:
                raise RuntimeError(f"Missing end_lineno for {function_name}")
            return "\n".join(lines[node.lineno - 1 : end_lineno]), node.lineno, end_lineno
    raise RuntimeError(f"Could not find {function_name} in {path}")


VISIBLE_PACKAGING_TOKENS = {
    "builder_call": "_guidance_item_from_resolved_candidate(",
    "title": '"Shear and bending cleanup - one-click optimisation"',
    "reasoning_prefix": '"This combines the best safe shear-link cleanup with the bending reinforcement cleanup "',
    "status": 'status="EFFICIENCY"',
    "primary_action": 'primary_action="Run one-click auto design"',
}

MUTATION_TOKENS_AFTER_PACKAGING = {
    "button_contract": 'item["button_contract"] = contract',
    "action_payload": 'item["action_payload"] = payload',
    "resolved_candidate": 'item["resolved_candidate"] = resolved',
    "selected_action_updates": '"selected_action_updates": dict(combined_updates)',
    "candidate_search_evidence": '"candidate_search_evidence": dict(evidence)',
}


def _capture() -> dict[str, Any]:
    function_source, start_line, end_line = _function_source(INPUTS_PAGE, FUNCTION_NAME)
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    visible_tokens = {
        name: token in function_source for name, token in VISIBLE_PACKAGING_TOKENS.items()
    }
    mutation_tokens = {
        name: token in function_source for name, token in MUTATION_TOKENS_AFTER_PACKAGING.items()
    }
    builder_call_count = function_source.count("_guidance_item_from_resolved_candidate(")
    decision = "READY_FOR_PROOF_ONLY_CONTROLLER_WRAPPER"
    blockers: list[str] = []
    if builder_call_count != 1:
        blockers.append("unexpected_guidance_item_builder_call_count")
    if not all(visible_tokens.values()):
        blockers.append("visible_packaging_tokens_missing")
    if not all(mutation_tokens.values()):
        blockers.append("post_packaging_mutation_tokens_missing")
    if "st.session_state" in controller_source or "import streamlit" in controller_source:
        blockers.append("controller_has_ui_import_or_streamlit_reference")
    if blockers:
        decision = "NOT_READY_FOR_CONTROLLER_WRAPPER"
    replacement_shape = {
        "wrapper_owner": "DesignGuideController.combined_low_util_guidance_item_packaging",
        "page_owned_builder_dependency": "_guidance_item_from_resolved_candidate",
        "preserve_visible_wording": True,
        "preserve_cta_apply_semantics": True,
        "preserve_post_packaging_mutations": True,
        "allowed_first_move": (
            "inject guidance_item_builder into controller wrapper and return item plus packaging proof"
        ),
        "not_allowed": [
            "change title/reasoning/status/primary action",
            "move Streamlit rendering",
            "move apply routing",
            "delete post-packaging payload mutation before parity proof",
        ],
    }
    replacement_shape["replacement_hash"] = _stable_hash(replacement_shape)
    return {
        "decision": decision,
        "function": {
            "name": FUNCTION_NAME,
            "start_line": start_line,
            "end_line": end_line,
            "line_count": end_line - start_line + 1,
        },
        "builder_call_count": builder_call_count,
        "visible_packaging_tokens": visible_tokens,
        "post_packaging_mutation_tokens": mutation_tokens,
        "blockers": blockers,
        "replacement_shape": replacement_shape,
        "safe_deletion_candidates": [],
        "recommended_next_slice": (
            "add controller wrapper with injected guidance item builder; do not delete post-packaging mutations yet"
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "function_found": bool((capture.get("function") or {}).get("line_count")),
        "single_builder_call": int(capture.get("builder_call_count") or 0) == 1,
        "visible_tokens_present": all((capture.get("visible_packaging_tokens") or {}).values()),
        "post_packaging_mutations_mapped": all(
            (capture.get("post_packaging_mutation_tokens") or {}).values()
        ),
        "no_blockers": not capture.get("blockers"),
        "no_safe_deletion_candidates_yet": not capture.get("safe_deletion_candidates"),
        "replacement_shape_recorded": bool(
            (capture.get("replacement_shape") or {}).get("replacement_hash")
        ),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Combined Low-Util Guidance Item Packaging Readiness Audit",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(["", "## Visible Packaging Tokens"])
    lines.extend(
        f"- {key}: `{value}`"
        for key, value in (capture.get("visible_packaging_tokens") or {}).items()
    )
    lines.extend(["", "## Post-Packaging Mutation Tokens"])
    lines.extend(
        f"- {key}: `{value}`"
        for key, value in (capture.get("post_packaging_mutation_tokens") or {}).items()
    )
    lines.extend(
        [
            "",
            "## Recommendation",
            "",
            str(capture.get("recommended_next_slice") or ""),
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {"status": status, "checks": checks, "capture": capture}
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = _stamp()
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_combined_low_util_guidance_item_packaging_readiness_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_combined_low_util_guidance_item_packaging_readiness_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_combined_low_util_guidance_item_packaging_readiness {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
