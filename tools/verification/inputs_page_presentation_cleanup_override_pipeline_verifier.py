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
    json_path = ARTIFACT_DIR / f"inputs_page_presentation_cleanup_override_pipeline_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_presentation_cleanup_override_pipeline_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    calls: list[dict] = []

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    names = {
        "specific": "render_design_guide_specific_blocker_presentation_override",
        "setup": "render_design_guide_presentation_bending_cleanup_override_setup",
        "applicable": "render_design_guide_presentation_bending_cleanup_override_applicable",
        "identity": "render_design_guide_presentation_bending_cleanup_identity_setup",
        "fold_gate": "render_design_guide_presentation_bending_cleanup_same_click_shear_fold_setup",
        "shear_item": "render_design_guide_presentation_bending_cleanup_same_click_shear_item_resolution",
        "updates_match": "_updates_match_state",
        "merge_setup": "render_design_guide_presentation_bending_cleanup_same_click_shear_merge_setup",
        "merge_accepted": "render_design_guide_presentation_bending_cleanup_same_click_shear_merge_accepted",
        "merge_stamp": "render_design_guide_presentation_bending_cleanup_same_click_shear_merge_stamping",
        "expected": "render_design_guide_presentation_bending_cleanup_expected_util_setup",
        "followup_gate": "render_design_guide_presentation_terminal_bending_followup_gate_setup",
        "followup": "render_design_guide_presentation_terminal_bending_followup_item_resolution",
        "packaging": "render_design_guide_presentation_bending_cleanup_item_packaging",
        "publication": "render_design_guide_presentation_bending_cleanup_publication_debug_setup",
    }
    originals = {key: getattr(inputs_page, value) for key, value in names.items()}

    def specific(**kwargs):
        calls.append({"event": "specific", "headline": dict(kwargs.get("dg_presentation") or {}).get("headline")})
        debug = dict(kwargs.get("guidance_debug") or {})
        debug["specific"] = True
        return dict(kwargs.get("dg_presentation") or {}, specific=True), debug

    def setup(**kwargs):
        calls.append({"event": "setup"})
        return (
            "Target band achieved",
            "Initial subtext",
            0.42,
            {"search_scope": "design_guide_bending_only_test", "safe_executor_backed_candidates_count": 2},
            {"b": 350},
        )

    def applicable(**kwargs):
        calls.append({"event": "applicable", "headline": kwargs.get("presentation_headline")})
        return True

    def identity(**kwargs):
        calls.append({"event": "identity"})
        return {"id": "bending_item"}, "Bending cleanup", "bending-a", "bending", ["bottom_reinforcement"]

    def fold_gate(**kwargs):
        calls.append({"event": "fold_gate", "updates": dict(kwargs.get("presentation_bending_updates") or {})})
        return 0.4, 1.0, True

    def shear_item(**kwargs):
        calls.append({"event": "shear_item"})
        return {"id": "shear"}, {"updates": {"link_spacing": 180}}, {"shear": True}, {"link_spacing": 180}

    def updates_match(state, updates):
        calls.append({"event": "updates_match", "updates": dict(updates or {})})
        return False

    def merge_setup(**kwargs):
        calls.append({"event": "merge_setup", "updates": dict(kwargs.get("presentation_shear_updates") or {})})
        return (
            {"merged": True},
            {"b": 350, "link_spacing": 180},
            {"any_fail": False, "utils": {"bending": 0.9, "shear": 0.88}},
            {"bending": "PASS", "shear": "PASS"},
            0.9,
            0.88,
            {"merged_evidence": True},
            {"shear": {"reason": "exact"}},
            True,
        )

    def merge_accepted(**kwargs):
        calls.append({"event": "merge_accepted", "util": kwargs.get("presentation_same_util")})
        return True

    def merge_stamp(**kwargs):
        calls.append({"event": "merge_stamp", "updates": dict(kwargs.get("presentation_same_updates") or {})})
        debug = dict(kwargs.get("guidance_debug") or {})
        debug["merge_stamp"] = True
        return (
            dict(kwargs.get("presentation_same_updates") or {}),
            "Combined cleanup",
            "combined",
            ["shear", "bottom_reinforcement"],
            "combined-a",
            dict(kwargs.get("presentation_bending_evidence") or {}, merged=True),
            debug,
        )

    def expected(**kwargs):
        calls.append({"event": "expected", "family": kwargs.get("presentation_bending_family")})
        return 0.9

    def followup_gate(**kwargs):
        calls.append({"event": "followup_gate", "expected": kwargs.get("presentation_bending_expected_for_contract")})
        return {}, {}, None, False

    def followup(**kwargs):
        calls.append({"event": "followup"})
        return (
            kwargs.get("presentation_bending_updates"),
            kwargs.get("presentation_bending_expected_for_contract"),
            kwargs.get("presentation_bending_subfamilies"),
            kwargs.get("presentation_bending_candidate_id"),
            kwargs.get("presentation_bending_evidence"),
            kwargs.get("guidance_debug"),
        )

    def packaging(**kwargs):
        calls.append({"event": "packaging", "family": kwargs.get("presentation_bending_family")})
        return dict(kwargs.get("presentation_bending_item") or {}, packaged=True), {"enabled": True}, True

    def publication(**kwargs):
        calls.append({"event": "publication", "title": kwargs.get("presentation_bending_title")})
        debug = dict(kwargs.get("guidance_debug") or {})
        debug["publication"] = True
        return (
            [dict(kwargs.get("presentation_bending_item") or {}, published=True)],
            {"headline": kwargs.get("presentation_bending_title"), "published": True},
            kwargs.get("presentation_bending_title"),
            "Published subtext",
            {"rr": "published"},
            debug,
        )

    try:
        inputs_page.render_design_guide_specific_blocker_presentation_override = specific
        inputs_page.render_design_guide_presentation_bending_cleanup_override_setup = setup
        inputs_page.render_design_guide_presentation_bending_cleanup_override_applicable = applicable
        inputs_page.render_design_guide_presentation_bending_cleanup_identity_setup = identity
        inputs_page.render_design_guide_presentation_bending_cleanup_same_click_shear_fold_setup = fold_gate
        inputs_page.render_design_guide_presentation_bending_cleanup_same_click_shear_item_resolution = shear_item
        inputs_page._updates_match_state = updates_match
        inputs_page.render_design_guide_presentation_bending_cleanup_same_click_shear_merge_setup = merge_setup
        inputs_page.render_design_guide_presentation_bending_cleanup_same_click_shear_merge_accepted = merge_accepted
        inputs_page.render_design_guide_presentation_bending_cleanup_same_click_shear_merge_stamping = merge_stamp
        inputs_page.render_design_guide_presentation_bending_cleanup_expected_util_setup = expected
        inputs_page.render_design_guide_presentation_terminal_bending_followup_gate_setup = followup_gate
        inputs_page.render_design_guide_presentation_terminal_bending_followup_item_resolution = followup
        inputs_page.render_design_guide_presentation_bending_cleanup_item_packaging = packaging
        inputs_page.render_design_guide_presentation_bending_cleanup_publication_debug_setup = publication

        result = inputs_page.render_design_guide_presentation_cleanup_override_pipeline(
            guidance_items=[{"id": "primary"}],
            dg_presentation={"headline": "initial"},
            guidance_debug={"debug": True},
            guidance_disp_state={"state": True},
            recommendation_result={"rr": "initial"},
        )
    finally:
        for key, value in names.items():
            setattr(inputs_page, value, originals[key])

    output_items, output_presentation, output_headline, output_subtext, output_rr, output_debug = result
    expect(
        "call_order",
        [call["event"] for call in calls]
        == [
            "specific",
            "setup",
            "applicable",
            "identity",
            "fold_gate",
            "shear_item",
            "updates_match",
            "merge_setup",
            "merge_accepted",
            "merge_stamp",
            "expected",
            "followup_gate",
            "followup",
            "packaging",
            "publication",
        ],
        f"calls={calls}",
    )
    expect(
        "output_flow",
        output_items == [{"id": "bending_item", "packaged": True, "published": True}]
        and output_presentation == {"headline": "Combined cleanup", "published": True}
        and output_headline == "Combined cleanup"
        and output_subtext == "Published subtext"
        and output_rr == {"rr": "published"}
        and output_debug.get("specific") is True
        and output_debug.get("merge_stamp") is True
        and output_debug.get("publication") is True,
        f"result={result}",
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
        "render_design_guide_specific_blocker_presentation_override",
        "render_design_guide_presentation_bending_cleanup_override_setup",
        "render_design_guide_presentation_bending_cleanup_override_applicable",
        "render_design_guide_presentation_bending_cleanup_identity_setup",
        "render_design_guide_presentation_bending_cleanup_same_click_shear_fold_setup",
        "render_design_guide_presentation_bending_cleanup_same_click_shear_item_resolution",
        "render_design_guide_presentation_bending_cleanup_same_click_shear_merge_setup",
        "render_design_guide_presentation_bending_cleanup_same_click_shear_merge_accepted",
        "render_design_guide_presentation_bending_cleanup_same_click_shear_merge_stamping",
        "render_design_guide_presentation_bending_cleanup_expected_util_setup",
        "render_design_guide_presentation_terminal_bending_followup_gate_setup",
        "render_design_guide_presentation_terminal_bending_followup_item_resolution",
        "render_design_guide_presentation_bending_cleanup_item_packaging",
        "render_design_guide_presentation_bending_cleanup_publication_debug_setup",
    }
    expect(
        "fast_panel_delegates_once_without_inline_helper_calls",
        fast_calls.count("render_design_guide_presentation_cleanup_override_pipeline") == 1
        and not (removed_direct_calls & set(fast_calls)),
        (
            "pipeline_calls="
            f"{fast_calls.count('render_design_guide_presentation_cleanup_override_pipeline')} "
            f"direct={sorted(removed_direct_calls & set(fast_calls))}"
        ),
    )

    payload = {
        "verdict": "PASS" if not failures else "FAIL",
        "json": str(json_path),
        "report": str(report_path),
        "failures": failures,
        "calls": calls,
        "result": result,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Presentation Cleanup Override Pipeline Verifier",
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
