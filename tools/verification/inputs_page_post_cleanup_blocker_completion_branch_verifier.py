from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _function_node(module: ast.Module, name: str) -> ast.FunctionDef:
    for node in module.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"missing function {name}")


def _calls(function_node: ast.FunctionDef) -> set[str]:
    calls: set[str] = set()
    for node in ast.walk(function_node):
        if isinstance(node, ast.Call):
            target = node.func
            if isinstance(target, ast.Name):
                calls.add(target.id)
            elif isinstance(target, ast.Attribute):
                calls.add(target.attr)
    return calls


def main() -> int:
    import inputs_page

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"inputs_page_post_cleanup_blocker_completion_branch_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_post_cleanup_blocker_completion_branch_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    calls: list[dict] = []

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    names = {
        "missing": "render_design_guide_post_cleanup_invalid_render_missing_blocker_terminal_state_stamping",
        "visible": "render_design_guide_post_cleanup_invalid_render_visible_blocker_completion_and_promotion",
        "is_visible": "_design_guide_item_is_visible_blocker",
        "contract_enabled": "_design_guide_button_contract_enabled",
        "st": "st",
    }
    originals = {key: getattr(inputs_page, value) for key, value in names.items()}
    session_state: dict = {}

    def missing(**kwargs):
        calls.append({"event": "missing", "reason": kwargs.get("blocked_render_reason")})
        item = dict(kwargs.get("blocked_render_item") or {})
        item["missing_checked"] = True
        return item, True

    def visible(**kwargs):
        calls.append({"event": "visible", "best_safe": kwargs.get("blocked_render_is_best_safe_action")})
        item = dict(kwargs.get("blocked_render_item") or {})
        item.update(
            {
                "visible_promoted": True,
                "button_contract": {"enabled": False, "family": "shear"},
                "display_truth": {"displayed_util": 0.44},
                "candidate_search_evidence": {"evidence": True},
                "exact_blockers_by_family": {"shear": {"blocked": True}},
            }
        )
        visible_utils = dict(kwargs.get("visible_utils_for_exact_blockers") or {})
        visible_utils["shear"] = 0.44
        return item, False, visible_utils

    try:
        inputs_page.render_design_guide_post_cleanup_invalid_render_missing_blocker_terminal_state_stamping = missing
        inputs_page.render_design_guide_post_cleanup_invalid_render_visible_blocker_completion_and_promotion = visible
        inputs_page._design_guide_item_is_visible_blocker = lambda item: True
        inputs_page._design_guide_button_contract_enabled = lambda contract: bool(contract.get("enabled"))
        inputs_page.st = SimpleNamespace(session_state=session_state)

        result = inputs_page.render_design_guide_post_cleanup_invalid_render_blocker_completion_branch(
            blocked_render_item={"title_main": "Initial"},
            blocked_render_truth={"truth": "initial"},
            blocked_render_is_best_safe_action=True,
            blocked_render_reason="blocked_reason",
            blocked_render_util=0.5,
            shear_blocker_util=0.44,
            guidance_debug={"debug": True},
            guidance_disp_state={"state": True},
            dg_overview={"overview": True},
            visible_utils_for_exact_blockers={"bending": 0.88},
            restamp_exact_blocker_current_utils_fn=lambda source: source,
        )
    finally:
        for key, value in names.items():
            setattr(inputs_page, value, originals[key])

    expected_item = {
        "title_main": "Initial",
        "missing_checked": True,
        "visible_promoted": True,
        "button_contract": {"enabled": False, "family": "shear"},
        "display_truth": {"displayed_util": 0.44},
        "candidate_search_evidence": {"evidence": True},
        "exact_blockers_by_family": {"shear": {"blocked": True}},
    }
    expect(
        "call_order",
        [call["event"] for call in calls] == ["missing", "visible"],
        f"calls={calls}",
    )
    expect(
        "output_contract",
        result
        == (
            expected_item,
            True,
            False,
            {"bending": 0.88, "shear": 0.44},
            {"enabled": False, "family": "shear"},
            {"displayed_util": 0.44},
            {"evidence": True},
            {"shear": {"blocked": True}},
            False,
        ),
        f"result={result}",
    )
    expect(
        "session_contract_handoff",
        session_state.get("design_guide_primary_button_contract") == {"enabled": False, "family": "shear"}
        and session_state.get("design_guide_primary_button_contract_enabled") is False
        and session_state.get(inputs_page.DESIGN_GUIDE_PRIMARY_APPLY_PAYLOAD_KEY) == {},
        f"session_state={session_state}",
    )

    source = (ROOT / "inputs_page.py").read_text(encoding="utf-8")
    module = ast.parse(source)
    new_node = _function_node(module, "render_design_guide_post_cleanup_invalid_render_blocker_completion_branch")
    legacy_node = _function_node(module, "_render_fast_design_guidance_panel")
    moved_calls = {
        "render_design_guide_post_cleanup_invalid_render_missing_blocker_terminal_state_stamping",
        "render_design_guide_post_cleanup_invalid_render_visible_blocker_completion_and_promotion",
    }
    new_calls = _calls(new_node)
    legacy_calls = _calls(legacy_node)
    expect(
        "new_pipeline_owns_moved_calls",
        moved_calls <= new_calls,
        f"missing={sorted(moved_calls - new_calls)}",
    )
    expect(
        "legacy_delegates_once",
        "render_design_guide_post_cleanup_invalid_render_blocker_completion_branch" in legacy_calls,
        "missing completion branch call",
    )
    expect(
        "legacy_no_longer_directly_calls_moved_helpers",
        not (moved_calls & legacy_calls),
        f"still_direct={sorted(moved_calls & legacy_calls)}",
    )

    payload = {
        "verdict": "PASS" if not failures else "FAIL",
        "failures": failures,
        "calls": calls,
        "result": result,
        "session_state": session_state,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Post Cleanup Blocker Completion Branch Verifier",
                "",
                f"Verdict: `{payload['verdict']}`",
                "",
                "## Purpose",
                "",
                "Locks the extracted invalid-render missing-blocker, visible-blocker completion, primary contract handoff, and bundle seed branch.",
                "",
                "## Failures",
                "",
                *(f"- {failure}" for failure in failures),
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps({**payload, "json": str(json_path), "report": str(report_path)}, indent=2, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
