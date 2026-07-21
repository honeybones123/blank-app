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
    json_path = ARTIFACT_DIR / f"inputs_page_post_cleanup_audit_early_shear_pipeline_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_post_cleanup_audit_early_shear_pipeline_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    calls: list[dict] = []
    stages: list[str] = []

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    names = {
        "audit": "_post_click_accepted_green_audit",
        "state": "render_design_guide_post_cleanup_early_shear_state_setup",
        "gate": "render_design_guide_post_cleanup_early_shear_gate_setup",
        "action": "render_design_guide_post_cleanup_early_shear_action_acquisition",
        "seed": "render_design_guide_post_cleanup_early_shear_seed_setup",
        "packaging": "render_design_guide_post_cleanup_early_shear_candidate_packaging",
        "contract": "render_design_guide_post_cleanup_early_shear_seed_contract_setup",
        "enabled": "_design_guide_button_contract_enabled",
        "stamp": "render_design_guide_post_cleanup_early_shear_publication_debug_stamping",
        "promotion": "render_design_guide_post_cleanup_early_shear_combined_promotion_handoff",
        "pending": "render_design_guide_post_cleanup_early_shear_pending_apply_setup",
        "projection": "render_design_guide_post_cleanup_early_shear_direct_shell_projection_setup",
        "refresh": "render_design_guide_post_cleanup_early_shear_display_truth_contract_refresh",
        "render_return": "render_design_guide_post_cleanup_early_shear_refreshed_action_debug_render_return",
    }
    originals = {key: getattr(inputs_page, value) for key, value in names.items()}

    def stage(label: str) -> None:
        stages.append(label)

    def audit(*args, **kwargs):
        calls.append({"event": "audit", "build_active": kwargs.get("build_active_shear_blocker")})
        return {"audit": True, "overview": {"any_fail": False}}

    def state(**kwargs):
        calls.append({"event": "state", "audit": kwargs.get("guidance_debug", {}).get("audit")})
        return {"state": True}, {"any_fail": False}

    def gate(**kwargs):
        calls.append({"event": "gate"})
        return {"utils": True}, 0.5, 0.8, 1.0, 10.0, [], True

    def action(**kwargs):
        calls.append({"event": "action", "target_low": kwargs.get("early_shear_target_low")})
        return {"action": True}

    def seed(**kwargs):
        calls.append({"event": "seed"})
        return {"evidence": True}, {"link_spacing": 180}, True

    def packaging(**kwargs):
        calls.append({"event": "packaging"})
        action_dict = dict(kwargs.get("early_shear_cleanup_action") or {})
        action_dict["packaged"] = True
        return action_dict, "early-shear-a", "Reduce shear reinforcement"

    def contract(**kwargs):
        calls.append({"event": "contract", "candidate": kwargs.get("early_shear_cleanup_candidate_id")})
        return {"enabled": True, "updates": {"link_spacing": 180}}, 0.9, True

    def enabled(contract_dict):
        calls.append({"event": "enabled", "updates": dict(contract_dict or {}).get("updates")})
        return True

    def stamp(**kwargs):
        calls.append({"event": "stamp", "label": kwargs.get("early_shear_cleanup_label")})
        debug = dict(kwargs.get("guidance_debug") or {})
        debug["stamped"] = True
        action_dict = dict(kwargs.get("early_shear_cleanup_action") or {})
        action_dict["stamped"] = True
        return action_dict, {"publication": True}, debug

    def promotion(**kwargs):
        calls.append({"event": "promotion"})
        debug = dict(kwargs.get("guidance_debug") or {})
        debug["promoted"] = True
        return (
            kwargs.get("early_shear_cleanup_action"),
            kwargs.get("early_shear_cleanup_seed_contract"),
            kwargs.get("early_shear_cleanup_seed_updates"),
            kwargs.get("early_shear_cleanup_candidate_id"),
            kwargs.get("early_shear_cleanup_label"),
            debug,
        )

    def pending(**kwargs):
        calls.append({"event": "pending"})
        return {"rec": True}, {"payload": True}

    def projection(**kwargs):
        calls.append({"event": "projection"})
        return {"projection": True}

    def refresh(**kwargs):
        calls.append({"event": "refresh"})
        return (
            kwargs.get("early_shear_cleanup_action"),
            [{"item": True}],
            {"enabled": True},
            {"contract_evidence": True},
            0.91,
            True,
        )

    def render_return(**kwargs):
        calls.append(
            {
                "event": "render_return",
                "renderable": kwargs.get("early_shear_cleanup_contract_renderable"),
                "stamped": kwargs.get("guidance_debug", {}).get("stamped"),
            }
        )
        kwargs["stage"]("post_plan.render_return_called")
        return True

    try:
        inputs_page._post_click_accepted_green_audit = audit
        inputs_page.render_design_guide_post_cleanup_early_shear_state_setup = state
        inputs_page.render_design_guide_post_cleanup_early_shear_gate_setup = gate
        inputs_page.render_design_guide_post_cleanup_early_shear_action_acquisition = action
        inputs_page.render_design_guide_post_cleanup_early_shear_seed_setup = seed
        inputs_page.render_design_guide_post_cleanup_early_shear_candidate_packaging = packaging
        inputs_page.render_design_guide_post_cleanup_early_shear_seed_contract_setup = contract
        inputs_page._design_guide_button_contract_enabled = enabled
        inputs_page.render_design_guide_post_cleanup_early_shear_publication_debug_stamping = stamp
        inputs_page.render_design_guide_post_cleanup_early_shear_combined_promotion_handoff = promotion
        inputs_page.render_design_guide_post_cleanup_early_shear_pending_apply_setup = pending
        inputs_page.render_design_guide_post_cleanup_early_shear_direct_shell_projection_setup = projection
        inputs_page.render_design_guide_post_cleanup_early_shear_display_truth_contract_refresh = refresh
        inputs_page.render_design_guide_post_cleanup_early_shear_refreshed_action_debug_render_return = render_return

        result = inputs_page.render_design_guide_post_cleanup_audit_and_early_shear_pipeline(
            guidance_debug={"overview": {"any_fail": False}},
            guidance_disp_state={"state": True},
            dg_overview={"dg": True},
            post_cleanup_build_active_shear_blocker=True,
            inputs_render_audit={"render": True},
            stage=stage,
        )
    finally:
        for key, value in names.items():
            setattr(inputs_page, value, originals[key])

    post_cleanup_render_audit, output_debug, should_return = result
    expect(
        "call_order",
        [call["event"] for call in calls]
        == [
            "audit",
            "state",
            "gate",
            "action",
            "seed",
            "packaging",
            "contract",
            "enabled",
            "stamp",
            "promotion",
            "pending",
            "projection",
            "refresh",
            "render_return",
        ],
        f"calls={calls}",
    )
    expect(
        "stage_order",
        stages
        == [
            "post_plan.before_post_cleanup_audit",
            "post_plan.after_post_cleanup_audit",
            "post_plan.after_early_shear_overdesign_direct_action_shell_deleted",
            "post_plan.render_return_called",
        ],
        f"stages={stages}",
    )
    expect(
        "output_flow",
        post_cleanup_render_audit == {"audit": True, "overview": {"any_fail": False}}
        and output_debug.get("audit") is True
        and output_debug.get("stamped") is True
        and output_debug.get("promoted") is True
        and should_return is True,
        f"result={result}",
    )

    source = (ROOT / "inputs_page.py").read_text(encoding="utf-8")
    module = ast.parse(source)
    new_node = _function_node(module, "render_design_guide_post_cleanup_audit_and_early_shear_pipeline")
    legacy_node = _function_node(module, "_render_fast_design_guidance_panel")
    new_calls = _calls(new_node)
    legacy_calls = _calls(legacy_node)
    moved_calls = set(names.values())
    direct_call_migration_calls = moved_calls - {"_design_guide_button_contract_enabled"}
    expect(
        "new_pipeline_owns_moved_calls",
        moved_calls <= new_calls,
        f"missing={sorted(moved_calls - new_calls)}",
    )
    expect(
        "legacy_delegates_once",
        "render_design_guide_post_cleanup_audit_and_early_shear_pipeline" in legacy_calls,
        "missing pipeline call",
    )
    expect(
        "legacy_no_longer_directly_calls_moved_helpers",
        not (direct_call_migration_calls & legacy_calls),
        f"still_direct={sorted(direct_call_migration_calls & legacy_calls)}",
    )

    payload = {
        "verdict": "PASS" if not failures else "FAIL",
        "failures": failures,
        "calls": calls,
        "stages": stages,
        "result": result,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Post Cleanup Audit Early Shear Pipeline Verifier",
                "",
                f"Verdict: `{payload['verdict']}`",
                "",
                "## Purpose",
                "",
                "Locks the extracted post-cleanup audit and early-shear coordinator, including parent early-return preservation.",
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
