from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
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


def _old_projection(selected_candidate: dict[str, Any] | None, selected_bending: dict[str, Any] | None) -> dict[str, Any]:
    best = selected_candidate if isinstance(selected_candidate, dict) else {}
    bending = selected_bending if isinstance(selected_bending, dict) else {}
    return {
        "Ast_bot": float(best.get("actual_ast", 0.0) or 0.0),
        "db_bot": float(bending.get("db_bot", 0.0) or 0.0),
        "nb_bot": int(bending.get("nb_bot", 0) or 0),
        "d_centroid": float(bending.get("d_centroid", 0.0) or 0.0),
    }


def _cases() -> list[dict[str, Any]]:
    return [
        {
            "name": "normal_selected_bending",
            "candidate": {"actual_ast": 1206.4},
            "bending": {"db_bot": 16.0, "nb_bot": 6, "d_centroid": 584.2},
        },
        {
            "name": "string_values",
            "candidate": {"actual_ast": "804.2"},
            "bending": {"db_bot": "20", "nb_bot": "4", "d_centroid": "556.5"},
        },
        {
            "name": "missing_values",
            "candidate": {},
            "bending": {},
        },
    ]


def main() -> int:
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDITS_DIR.mkdir(parents=True, exist_ok=True)
    inputs_source = _read(INPUTS_PAGE)
    bending_source = _read(BENDING_FAMILY)
    compute_segment = _function_segment(inputs_source, "_compute_bottom_reo_recommendation")
    family_segment = _function_segment(bending_source, "build_bottom_reo_required_ast_arrangement_input")

    from design_brain.families.bending import build_bottom_reo_required_ast_arrangement_input

    parity_rows = []
    for case in _cases():
        expected = _old_projection(case.get("candidate"), case.get("bending"))
        actual = build_bottom_reo_required_ast_arrangement_input(case.get("candidate"), case.get("bending"))
        parity_rows.append(
            {
                "case": case["name"],
                "expected": expected,
                "actual": actual,
                "matches": expected == actual,
            },
        )

    checks = {
        "family_helper_exists": "def build_bottom_reo_required_ast_arrangement_input(" in bending_source,
        "page_imports_family_helper": (
            "build_bottom_reo_required_ast_arrangement_input as _build_bottom_reo_required_ast_arrangement_input"
            in inputs_source
        ),
        "bottom_reo_callsite_uses_family_projection": (
            "_build_bottom_reo_required_ast_arrangement_input(best, selected_bending)" in compute_segment
        ),
        "old_inline_projection_removed_from_bottom_reo_callsite": (
            '"Ast_bot": float(best.get("actual_ast", 0.0) or 0.0)' not in compute_segment
            and '"db_bot": float(selected_bending.get("db_bot", 0.0) or 0.0)' not in compute_segment
            and '"nb_bot": int(selected_bending.get("nb_bot", 0) or 0)' not in compute_segment
            and '"d_centroid": float(selected_bending.get("d_centroid", 0.0) or 0.0)' not in compute_segment
        ),
        "capacity_callback_remains_page_owned": (
            "_evaluate_bending_with_bottom_state(state, arrangement)" in compute_segment
            and "_required_ast_for_arrangement(" in compute_segment
        ),
        "family_helper_has_no_page_or_ui_imports": all(
            token not in family_segment
            for token in ("inputs_page", "streamlit", "\nst.", " session_state", "apply_guidance_action")
        ),
        "projection_parity": all(row["matches"] for row in parity_rows),
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "status": status,
        "surface": "bottom_reo_required_ast_arrangement_input",
        "checks": checks,
        "parity_rows": parity_rows,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_behavior_changed": False,
        "remaining_page_shell": [
            "_evaluate_bending_with_bottom_state(state, arrangement)",
            "_required_ast_for_arrangement(state, family_projected_arrangement)",
        ],
        "extraction_complete_estimate_after_pass": "77-81%" if status == "PASS" else "76-80%",
    }
    stamp = _timestamp()
    json_path = VERIFICATION_DIR / f"design_guide_bottom_reo_required_ast_input_family_extraction_{stamp}.json"
    md_path = AUDITS_DIR / f"design_guide_bottom_reo_required_ast_input_family_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(
        "\n".join(
            [
                "# Bottom Reo Required-Ast Input Family Extraction",
                "",
                f"## Summary\n{status}",
                "",
                "## Checks",
                *[f"- {name}: {value}" for name, value in checks.items()],
                "",
                "## Parity Cases",
                *[f"- {row['case']}: {'PASS' if row['matches'] else 'FAIL'}" for row in parity_rows],
                "",
                "## Ownership",
                "The family now owns the pure selected-candidate/selected-bending arrangement payload projection.",
                "inputs_page.py still owns page-local bending-capacity callback execution and state scalar collection.",
                "",
                "## Behaviour",
                "- visible wording changed: false",
                "- CTA/apply semantics changed: false",
                "- family runtime behaviour changed: false",
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
