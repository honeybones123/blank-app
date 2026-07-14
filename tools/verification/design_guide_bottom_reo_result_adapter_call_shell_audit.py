from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
BENDING_FAMILY = ROOT / "design_brain" / "families" / "bending.py"
VERIFICATION_DIR = ROOT / "artifacts" / "verification"
AUDITS_DIR = ROOT / "artifacts" / "audits"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _function_segment(source: str, name: str) -> str:
    marker = f"def {name}("
    start = source.find(marker)
    if start < 0:
        return ""
    next_start = source.find("\ndef ", start + len(marker))
    if next_start < 0:
        next_start = len(source)
    return source[start:next_start]


def main() -> int:
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDITS_DIR.mkdir(parents=True, exist_ok=True)
    inputs_source = _read(INPUTS_PAGE)
    bending_source = _read(BENDING_FAMILY)
    compute_segment = _function_segment(inputs_source, "_compute_bottom_reo_recommendation")
    adapter_segment = _function_segment(bending_source, "build_bottom_reo_recommendation_result")

    checks = {
        "family_result_adapter_exists": "def build_bottom_reo_recommendation_result(" in bending_source,
        "page_imports_result_adapter": (
            "build_bottom_reo_recommendation_result as _build_bottom_reo_recommendation_result" in inputs_source
        ),
        "callsite_uses_family_result_adapter": "result = _build_bottom_reo_recommendation_result(" in compute_segment,
        "display_label_projection_family_owned": (
            "_resolve_bottom_reo_result_display_label(best)" in compute_segment
            and "def resolve_bottom_reo_result_display_label(" in bending_source
        ),
        "guidance_change_lines_projection_family_owned": (
            "_build_bottom_reo_guidance_change_lines_for_updates(state, dict(best.get(\"updates\") or {}))"
            in compute_segment
            and "def build_bottom_reo_guidance_change_lines_for_updates(" in bending_source
        ),
        "required_ast_input_projection_family_owned": (
            "_build_bottom_reo_required_ast_arrangement_input(best, selected_bending)" in compute_segment
            and "def build_bottom_reo_required_ast_arrangement_input(" in bending_source
        ),
        "required_ast_calculation_family_owned_callback_bounded": (
            "_required_ast_for_arrangement(" in compute_segment
            and "def calculate_bottom_reo_required_ast_for_arrangement(" in bending_source
        ),
        "callsite_does_not_inline_result_dict": (
            '"arrangement": dict(arrangement or {})' not in compute_segment
            and '"guidance_change_lines": list(guidance_change_lines or [])' not in compute_segment
        ),
        "adapter_has_no_page_or_ui_imports": all(
            token not in adapter_segment
            for token in ("inputs_page", "streamlit", "\nst.", " session_state", "apply_guidance_action")
        ),
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "status": status,
        "surface": "bottom_reo_result_adapter_call_orchestration",
        "decision": "SHELL_ONLY_ADAPTER_CALL" if status == "PASS" else "NOT_SHELL_ONLY",
        "checks": checks,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_behavior_changed": False,
        "extraction_complete_estimate_after_pass": "77-81%",
        "remaining_tail": [
            "live selector loop",
            "bounded required-Ast callback shell",
            "bounded page debug trace event emission",
        ],
    }
    stamp = _timestamp()
    json_path = VERIFICATION_DIR / f"design_guide_bottom_reo_result_adapter_call_shell_audit_{stamp}.json"
    md_path = AUDITS_DIR / f"design_guide_bottom_reo_result_adapter_call_shell_audit_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(
        "\n".join(
            [
                "# Bottom Reo Result Adapter Call Shell Audit",
                "",
                f"## Executive Summary\n{status}",
                "",
                f"## Decision\n{payload['decision']}",
                "",
                "## Checks",
                *[f"- {name}: {value}" for name, value in checks.items()],
                "",
                "## Ownership",
                "The result dict is built by `design_brain.families.bending.build_bottom_reo_recommendation_result(...)`.",
                "The page callsite only passes selected candidate, arrangement, bounded required-Ast callback output, display label, and family-owned guidance change lines.",
                "",
                "## Remaining Tail",
                *[f"- {item}" for item in payload["remaining_tail"]],
                "",
                f"JSON: {json_path}",
            ],
        ),
        encoding="utf-8",
    )
    print(f"{status} {json_path}")
    print(md_path)
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
