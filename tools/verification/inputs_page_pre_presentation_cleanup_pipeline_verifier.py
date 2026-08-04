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


def main() -> int:
    import inputs_page

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"inputs_page_pre_presentation_cleanup_pipeline_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_pre_presentation_cleanup_pipeline_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    calls: list[dict] = []
    stage_events: list[str] = []

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    names = {
        "merge": "render_design_guide_pre_presentation_combined_cleanup_merge",
        "context": "render_design_guide_pre_presentation_bending_cleanup_context",
        "action_setup": "render_design_guide_pre_presentation_bending_action_setup",
        "same_click": "render_design_guide_pre_presentation_same_click_shear_updates",
        "merge_fold": "render_design_guide_pre_presentation_same_click_shear_merge_fold",
        "terminal_bending": "render_design_guide_pre_presentation_terminal_bending_fold",
        "combined_fold": "render_design_guide_pre_presentation_combined_terminal_fold",
        "publication": "render_design_guide_pre_presentation_action_publication",
        "checks": "_overview_required_checks_acceptable",
    }
    originals = {key: getattr(inputs_page, value) for key, value in names.items()}

    def stage(name: str) -> None:
        calls.append({"event": "stage", "name": name})
        stage_events.append(name)

    def merge(**kwargs):
        calls.append({"event": "merge", "rr": kwargs.get("recommendation_result")})
        return [{"id": "merged"}], {"rr": "merged"}

    def context(**kwargs):
        calls.append({"event": "context", "items": list(kwargs.get("guidance_items") or [])})
        return (
            {"id": "primary"},
            {"any_fail": False},
            {"utils": True},
            0.42,
            {
                "search_scope": "design_guide_bending_only_test",
                "safe_executor_backed_candidates_count": 2,
            },
            {"b": 350},
            0.5,
        )

    def action_setup(**kwargs):
        calls.append({"event": "action_setup", "primary": dict(kwargs.get("pre_presentation_primary") or {})})
        return (
            {"id": "bending_action"},
            "candidate-a",
            "bending",
            ["bending"],
            "Bending cleanup",
            0.4,
            ["shear"],
            "bending",
            False,
            1.0,
        )

    def same_click(**kwargs):
        calls.append({"event": "same_click", "updates": dict(kwargs.get("pre_presentation_updates") or {})})
        return {"shear_links": 180}

    def merge_fold(**kwargs):
        calls.append(
            {
                "event": "merge_fold",
                "same_click": dict(kwargs.get("same_click_shear_updates") or {}),
                "family": kwargs.get("bending_action_family"),
            }
        )
        return (
            {"b": 350, "shear_links": 180},
            0.45,
            {"folded": True},
            "bending",
            ["bending", "shear"],
            "Bending cleanup with shear fold",
            "candidate-folded",
        )

    def terminal_bending(**kwargs):
        calls.append({"event": "terminal_bending", "util": kwargs.get("pre_presentation_util")})
        return (
            {"b": 360},
            0.86,
            {"terminal_bending": True},
            ["bending"],
            "candidate-terminal",
        )

    def combined_fold(**kwargs):
        calls.append({"event": "combined_fold"})
        return (
            dict(kwargs.get("pre_presentation_updates") or {}, combined=True),
            0.9,
            dict(kwargs.get("pre_presentation_evidence") or {}, combined=True),
            "candidate-combined",
        )

    def publication(**kwargs):
        calls.append(
            {
                "event": "publication",
                "family": kwargs.get("bending_action_family"),
                "candidate": kwargs.get("bending_action_candidate_id"),
                "updates": dict(kwargs.get("pre_presentation_updates") or {}),
            }
        )
        return [{"id": "published", "updates": dict(kwargs.get("pre_presentation_updates") or {})}], {"rr": "published"}, {"id": "published_action"}

    try:
        inputs_page.render_design_guide_pre_presentation_combined_cleanup_merge = merge
        inputs_page.render_design_guide_pre_presentation_bending_cleanup_context = context
        inputs_page.render_design_guide_pre_presentation_bending_action_setup = action_setup
        inputs_page.render_design_guide_pre_presentation_same_click_shear_updates = same_click
        inputs_page.render_design_guide_pre_presentation_same_click_shear_merge_fold = merge_fold
        inputs_page.render_design_guide_pre_presentation_terminal_bending_fold = terminal_bending
        inputs_page.render_design_guide_pre_presentation_combined_terminal_fold = combined_fold
        inputs_page.render_design_guide_pre_presentation_action_publication = publication
        inputs_page._overview_required_checks_acceptable = lambda overview: True

        result = inputs_page.render_design_guide_pre_presentation_cleanup_pipeline(
            guidance_items=[{"id": "start"}],
            recommendation_result={"rr": "initial"},
            guidance_disp_state={"state": True},
            dg_overview={"overview": True},
            guidance_debug={"debug": True},
            stage=stage,
        )
    finally:
        for key, value in names.items():
            setattr(inputs_page, value, originals[key])

    output_items, output_rr = result
    expect(
        "call_order",
        [call["event"] for call in calls]
        == [
            "stage",
            "merge",
            "context",
            "action_setup",
            "same_click",
            "merge_fold",
            "terminal_bending",
            "publication",
        ],
        f"calls={calls}",
    )
    expect(
        "stage_order",
        stage_events == ["post_plan.after_local_cleanup_adapter_block"],
        f"stage_events={stage_events}",
    )
    expect(
        "output_flow",
        output_items == [{"id": "published", "updates": {"b": 360}}]
        and output_rr == {"rr": "published"}
        and calls[-1]["candidate"] == "candidate-terminal",
        f"result={result} calls={calls}",
    )

    module = ast.parse((ROOT / "inputs_page.py").read_text(encoding="utf-8"))
    fast_panel = next(
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == "_render_fast_design_guidance_panel"
    )
    fast_calls = [
        node.func.id
        for node in ast.walk(fast_panel)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    ]
    removed_direct_calls = {
        "render_design_guide_pre_presentation_combined_cleanup_merge",
        "render_design_guide_pre_presentation_bending_cleanup_context",
        "render_design_guide_pre_presentation_bending_action_setup",
        "render_design_guide_pre_presentation_same_click_shear_updates",
        "render_design_guide_pre_presentation_same_click_shear_merge_fold",
        "render_design_guide_pre_presentation_terminal_bending_fold",
        "render_design_guide_pre_presentation_combined_terminal_fold",
        "render_design_guide_pre_presentation_action_publication",
    }
    expect(
        "fast_panel_delegates_once_without_inline_helper_calls",
        fast_calls.count("render_design_guide_pre_presentation_cleanup_pipeline") == 1
        and not (removed_direct_calls & set(fast_calls)),
        (
            "pipeline_calls="
            f"{fast_calls.count('render_design_guide_pre_presentation_cleanup_pipeline')} "
            f"direct={sorted(removed_direct_calls & set(fast_calls))}"
        ),
    )

    payload = {
        "verdict": "PASS" if not failures else "FAIL",
        "json": str(json_path),
        "report": str(report_path),
        "failures": failures,
        "calls": calls,
        "stage_events": stage_events,
        "result": result,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Pre Presentation Cleanup Pipeline Verifier",
                "",
                f"Verdict: `{payload['verdict']}`",
                "",
                f"JSON: `{json_path}`",
                "",
                "## Failures",
                "",
                *(failures or ["None."]),
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
