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
    json_path = ARTIFACT_DIR / f"inputs_page_post_cleanup_shear_blocker_packaging_branch_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_post_cleanup_shear_blocker_packaging_branch_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    calls: list[dict] = []

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    names = {
        "seed": "render_design_guide_post_cleanup_invalid_render_shear_blocker_seed_setup",
        "detailing_floor": "render_design_guide_post_cleanup_invalid_render_shear_blocker_detailing_floor_setup",
        "best_safe": "render_design_guide_post_cleanup_invalid_render_best_safe_shear_action_setup",
        "final_safe": "render_design_guide_post_cleanup_invalid_render_final_safe_shear_action_setup",
        "stale_replacement": "render_design_guide_post_cleanup_invalid_render_stale_shear_blocker_safe_cleanup_replacement",
        "final_packaging": "render_design_guide_post_cleanup_invalid_render_final_blocker_action_packaging",
        "terminal_acceptance": "render_design_guide_post_cleanup_invalid_render_terminal_exact_acceptance",
        "mode_config": "_design_mode_config",
        "goal": "_design_optimisation_goal",
    }
    originals = {key: getattr(inputs_page, value) for key, value in names.items()}

    def seed(**kwargs):
        calls.append({"event": "seed", "reason": kwargs.get("blocked_render_reason")})
        return (
            {"blocker": True},
            {"evidence": True},
            {"lig_d": 10},
            0.91,
            True,
            "seed_reason",
            0.42,
            {"lig_d": 10},
            False,
        )

    def detailing_floor(**kwargs):
        calls.append({"event": "detailing_floor", "util": kwargs.get("shear_blocker_util")})
        return {"blocker": "detailed"}, 0.43, False, False

    def best_safe(**kwargs):
        calls.append({"event": "best_safe", "floor": kwargs.get("shear_links_at_detailing_floor")})
        return {
            "title_main": "Best safe shear cleanup",
            "button_contract": {"enabled": True},
            "candidate_search_evidence": {"safe": True},
        }

    def final_safe(**kwargs):
        calls.append({"event": "final_safe", "title": kwargs.get("blocked_render_title_lower")})
        item = dict(kwargs.get("blocked_render_item") or {})
        item["final_safe"] = True
        return item, "final title"

    def stale_replacement(**kwargs):
        calls.append({"event": "stale_replacement", "title": kwargs.get("blocked_render_title_lower")})
        item = dict(kwargs.get("blocked_render_item") or {})
        item["stale_checked"] = True
        return item, "stale title", {"truth": "stale"}

    def final_packaging(**kwargs):
        calls.append({"event": "final_packaging", "title": kwargs.get("blocked_render_title_lower")})
        item = dict(kwargs.get("blocked_render_item") or {})
        item["packaged"] = True
        return item, {"truth": "packaged"}, True

    def terminal_acceptance(**kwargs):
        calls.append({"event": "terminal_acceptance", "util": kwargs.get("blocked_render_util")})
        item = dict(kwargs.get("blocked_render_item") or {})
        item["terminal"] = True
        return item, {"enabled": False}, {"truth": "terminal"}

    try:
        inputs_page.render_design_guide_post_cleanup_invalid_render_shear_blocker_seed_setup = seed
        inputs_page.render_design_guide_post_cleanup_invalid_render_shear_blocker_detailing_floor_setup = detailing_floor
        inputs_page.render_design_guide_post_cleanup_invalid_render_best_safe_shear_action_setup = best_safe
        inputs_page.render_design_guide_post_cleanup_invalid_render_final_safe_shear_action_setup = final_safe
        inputs_page.render_design_guide_post_cleanup_invalid_render_stale_shear_blocker_safe_cleanup_replacement = stale_replacement
        inputs_page.render_design_guide_post_cleanup_invalid_render_final_blocker_action_packaging = final_packaging
        inputs_page.render_design_guide_post_cleanup_invalid_render_terminal_exact_acceptance = terminal_acceptance
        inputs_page._design_mode_config = lambda goal: {"target_low": 0.75, "target_high": 1.0}
        inputs_page._design_optimisation_goal = lambda state: "balanced"

        result = inputs_page.render_design_guide_post_cleanup_invalid_render_shear_blocker_packaging_branch(
            blocked_render_is_best_safe_action=False,
            blocked_render_util=0.66,
            blocked_render_truth={"truth": "initial"},
            blocked_render_reason="initial_reason",
            blocked_render_item={"title_main": "Initial"},
            current_state={"state": True},
            guidance_debug={"debug": True},
            guidance_disp_state={"state": True},
            dg_overview={"overview": True},
            post_cleanup_render_audit={"audit": True},
        )
    finally:
        for key, value in names.items():
            setattr(inputs_page, value, originals[key])

    expect(
        "call_order",
        [call["event"] for call in calls]
        == [
            "seed",
            "detailing_floor",
            "best_safe",
            "final_safe",
            "stale_replacement",
            "final_packaging",
            "terminal_acceptance",
        ],
        f"calls={calls}",
    )
    expect(
        "output_contract",
        result
        == (
            {
                "title_main": "Best safe shear cleanup",
                "button_contract": {"enabled": True},
                "candidate_search_evidence": {"safe": True},
                "final_safe": True,
                "stale_checked": True,
                "packaged": True,
                "terminal": True,
            },
            {"truth": "terminal"},
            True,
            0.43,
        ),
        f"result={result}",
    )

    source = (ROOT / "inputs_page.py").read_text(encoding="utf-8")
    module = ast.parse(source)
    new_node = _function_node(
        module,
        "render_design_guide_post_cleanup_invalid_render_shear_blocker_packaging_branch",
    )
    legacy_node = _function_node(module, "_render_fast_design_guidance_panel")
    moved_calls = {value for key, value in names.items() if key not in {"mode_config", "goal"}}
    new_calls = _calls(new_node)
    legacy_calls = _calls(legacy_node)
    expect(
        "new_pipeline_owns_moved_calls",
        moved_calls <= new_calls,
        f"missing={sorted(moved_calls - new_calls)}",
    )
    expect(
        "legacy_delegates_once",
        "render_design_guide_post_cleanup_invalid_render_shear_blocker_packaging_branch" in legacy_calls,
        "missing packaging branch call",
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
                "# Inputs Page Post Cleanup Shear Blocker Packaging Branch Verifier",
                "",
                f"Verdict: `{payload['verdict']}`",
                "",
                "## Purpose",
                "",
                "Locks the extracted invalid-render shear-blocker packaging branch from seed setup through terminal exact acceptance.",
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
