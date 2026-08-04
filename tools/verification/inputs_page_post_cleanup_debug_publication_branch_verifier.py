from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path


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
    json_path = ARTIFACT_DIR / f"inputs_page_post_cleanup_debug_publication_branch_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_post_cleanup_debug_publication_branch_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    calls: list[dict] = []

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    names = {
        "accepted": "_post_active_repair_target_accepted_item",
        "debug": "render_design_guide_post_cleanup_invalid_render_debug_bundle_stamping",
        "publication": "render_design_guide_post_cleanup_invalid_render_publication_and_secondary_items",
        "family": "_design_guide_candidate_family",
        "mode": "_design_mode_config",
        "goal": "_design_optimisation_goal",
    }
    originals = {key: getattr(inputs_page, value) for key, value in names.items()}

    def accepted(*args, **kwargs):
        calls.append({"event": "accepted", "allow": kwargs.get("allow_required_checks_terminal")})
        return {
            "title_main": "Accepted active repair",
            "guidance_intent": "already_efficient",
            "button_contract": {"enabled": False, "family": "combined"},
            "display_truth": {"displayed_util": 0.91, "display_truth_source": "active"},
            "candidate_search_evidence": {"active": True},
            "exact_blockers_by_family": {"shear": {"blocked": True}},
            "cleanup_evidence_by_family": {"shear": {"clean": True}},
            "local_cleanup_search_ran": True,
            "local_cleanup_search_exhaustive": True,
        }

    def debug_bundle(**kwargs):
        calls.append(
            {
                "event": "debug",
                "rewritten": kwargs.get("blocked_render_rewritten_to_active_green"),
                "terminal_blocked": dict(kwargs.get("blocked_render_engine_decision_for_bundle") or {})
                .get("debug", {})
                .get("terminal_state_blocked_by_local_cleanup"),
            }
        )
        return (
            {"shear": 0.91},
            {"debug_evidence": True},
            {"debug_exact": True},
            {"debug_cleanup": True},
        )

    def publication(**kwargs):
        calls.append({"event": "publication", "title": kwargs.get("blocked_render_item", {}).get("title_main")})
        item = dict(kwargs.get("blocked_render_item") or {})
        item["published"] = True
        debug = dict(kwargs.get("guidance_debug") or {})
        debug["published"] = True
        return (
            item,
            debug,
            {"visible_guidance_items": [item], "render_primary_only": True},
            {"headline": "Accepted active repair"},
            True,
        )

    try:
        inputs_page._post_active_repair_target_accepted_item = accepted
        inputs_page.render_design_guide_post_cleanup_invalid_render_debug_bundle_stamping = debug_bundle
        inputs_page.render_design_guide_post_cleanup_invalid_render_publication_and_secondary_items = publication
        inputs_page._design_guide_candidate_family = lambda item: str((item or {}).get("family") or "shear")
        inputs_page._design_mode_config = lambda goal: {"target_low": 0.75, "target_high": 1.0}
        inputs_page._design_optimisation_goal = lambda state: "balanced"

        result = inputs_page.render_design_guide_post_cleanup_invalid_render_debug_publication_branch(
            blocked_render_item={
                "title_main": "Blocked item",
                "family": "shear",
                "button_contract": {"enabled": False, "family": "shear"},
                "display_truth": {"displayed_util": 0.42},
                "candidate_search_evidence": {"before": True},
                "exact_blockers_by_family": {"shear": {"before": True}},
                "cleanup_evidence_by_family": {"shear": {"before_cleanup": True}},
                "local_cleanup_blocked_reasons": ["reason"],
                "local_cleanup_blocked_reasons_by_family": {"shear": ["reason"]},
            },
            blocked_render_truth={"displayed_util": 0.42},
            blocked_render_reason="blocked_reason",
            blocked_render_is_best_safe_action=True,
            blocked_render_contract={"enabled": False, "family": "shear"},
            blocked_render_truth_for_bundle={"displayed_util": 0.42},
            blocked_render_evidence_for_bundle={"before": True},
            blocked_render_exact_blockers_for_bundle={"shear": {"before": True}},
            blocked_render_rewritten_to_active_green=False,
            post_active_failure_repair_render=True,
            post_cleanup_render_audit={"post_click_exact_blockers_by_family": {"shear": {"audit": True}}},
            guidance_debug={"overview": {"utils": {"shear": 0.91}}},
            guidance_disp_state={"state": True},
            dg_overview={"utils": {"shear": 0.91}},
            render_plan={"old": True},
            dg_presentation={"headline": "old"},
            inputs_render_audit={"audit": True},
            visible_utils_for_exact_blockers={"before": 0.42},
            restamp_exact_blocker_maps_in_evidence_fn=lambda source: source,
            restamp_exact_blocker_current_utils_fn=lambda source: source,
            stage_fn=lambda label: None,
        )
    finally:
        for key, value in names.items():
            setattr(inputs_page, value, originals[key])

    expect(
        "call_order",
        [call["event"] for call in calls] == ["accepted", "debug", "publication"],
        f"calls={calls}",
    )
    expect(
        "active_rewrite_debug_flag",
        len(calls) >= 2 and calls[1].get("rewritten") is True and calls[1].get("terminal_blocked") is False,
        f"calls={calls}",
    )
    expected_item = {
        "title_main": "Accepted active repair",
        "guidance_intent": "already_efficient",
        "button_contract": {"enabled": False, "family": "combined"},
        "display_truth": {"displayed_util": 0.91, "display_truth_source": "active"},
        "candidate_search_evidence": {"active": True},
        "exact_blockers_by_family": {"shear": {"blocked": True}},
        "cleanup_evidence_by_family": {"shear": {"clean": True}},
        "local_cleanup_search_ran": True,
        "local_cleanup_search_exhaustive": True,
        "published": True,
    }
    expect(
        "output_contract",
        result
        == (
            expected_item,
            {"overview": {"utils": {"shear": 0.91}}, "published": True},
            {"visible_guidance_items": [expected_item], "render_primary_only": True},
            {"headline": "Accepted active repair"},
            {"shear": 0.91},
            True,
        ),
        f"result={result}",
    )

    source = (ROOT / "inputs_page.py").read_text(encoding="utf-8")
    module = ast.parse(source)
    new_node = _function_node(module, "render_design_guide_post_cleanup_invalid_render_debug_publication_branch")
    legacy_node = _function_node(module, "_render_fast_design_guidance_panel")
    moved_calls = {
        "_post_active_repair_target_accepted_item",
        "render_design_guide_post_cleanup_invalid_render_debug_bundle_stamping",
        "render_design_guide_post_cleanup_invalid_render_publication_and_secondary_items",
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
        "render_design_guide_post_cleanup_invalid_render_debug_publication_branch" in legacy_calls,
        "missing debug publication branch call",
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
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Post Cleanup Debug Publication Branch Verifier",
                "",
                f"Verdict: `{payload['verdict']}`",
                "",
                "## Purpose",
                "",
                "Locks the extracted invalid-render active rewrite, debug bundle stamping, and publication handoff branch.",
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
