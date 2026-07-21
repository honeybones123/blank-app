"""Verify one-click solver candidate-preparation coordinator extraction."""

from __future__ import annotations

import ast
import datetime as _dt
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

AUTO_DESIGN_COMPUTE = ROOT / "inputs_page_modules" / "auto_design_compute.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function_segment(source: str, name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            start = int(node.lineno)
            end = int(getattr(node, "end_lineno", node.lineno))
            lines = source.splitlines()
            return start, end, "\n".join(lines[start - 1 : end])
    raise AssertionError(f"Function not found: {name}")


def _run_case(module: Any) -> dict[str, Any]:
    originals = {
        "_design_guide_candidate_family": getattr(module, "_design_guide_candidate_family", None),
        "_candidate_family_matches_governing_domain": getattr(module, "_candidate_family_matches_governing_domain", None),
        "_normalise_invalid_shear_state_updates": getattr(module, "_normalise_invalid_shear_state_updates", None),
        "_one_click_update_direction_summary": getattr(module, "_one_click_update_direction_summary", None),
        "_one_click_mixed_direction_classification": getattr(module, "_one_click_mixed_direction_classification", None),
    }

    def _family(item: Any) -> str:
        return str((item or {}).get("family") or "")

    def _matches(family: str, domain: str) -> bool:
        return str(domain) in str(family)

    def _normalise(working: dict[str, Any], raw_u: dict[str, Any], *, source: str) -> dict[str, Any]:
        return {k: v for k, v in raw_u.items() if k != "drop_me"}

    def _direction(working: dict[str, Any], norm_u: dict[str, Any]) -> dict[str, bool]:
        return {
            "is_reduction_candidate": bool(norm_u.get("D", working.get("D", 0)) < working.get("D", 0)),
            "is_growth_only": bool(norm_u.get("D", working.get("D", 0)) > working.get("D", 0)),
        }

    def _mixed(cur_eval: dict[str, Any], mode_config: dict[str, Any]) -> str:
        return f"{cur_eval.get('mode')}:{mode_config.get('mode')}"

    try:
        module._design_guide_candidate_family = _family
        module._candidate_family_matches_governing_domain = _matches
        module._normalise_invalid_shear_state_updates = _normalise
        module._one_click_update_direction_summary = _direction
        module._one_click_mixed_direction_classification = _mixed
        result = module._prepare_one_click_solver_candidates_coordinator(
            raw_candidates=[
                {
                    "title": "Reduce depth",
                    "action_type": "tighten",
                    "raw_updates": {"D": 550, "drop_me": True},
                    "item": {"family": "bending_depth"},
                },
                {
                    "title": "Tighten links",
                    "action_type": "shear",
                    "raw_updates": {"s_lig": 150},
                    "_tightening_family": "shear_spacing",
                    "item": {"family": "ignored"},
                },
            ],
            working={"D": 600},
            governing_domain="shear",
            use_governing_domain_candidates=True,
            cur_eval={"mode": "current"},
            mode_config={"mode": "target"},
        )
    finally:
        for name, original in originals.items():
            if original is not None:
                setattr(module, name, original)

    expected = {
        "pool_labels": [
            {
                "label": "Reduce depth",
                "action_type": "tighten",
                "updates": {"D": 550, "drop_me": True},
                "family": "bending_depth",
            },
            {
                "label": "Tighten links",
                "action_type": "shear",
                "updates": {"s_lig": 150},
                "family": "shear_spacing",
            },
        ],
        "prepared": [
            {
                "rc": {
                    "title": "Reduce depth",
                    "action_type": "tighten",
                    "raw_updates": {"D": 550, "drop_me": True},
                    "item": {"family": "bending_depth"},
                },
                "raw_u": {"D": 550, "drop_me": True},
                "norm_u": {"D": 550},
                "direction": {"is_reduction_candidate": True, "is_growth_only": False},
                "family": "bending_depth",
            },
            {
                "rc": {
                    "title": "Tighten links",
                    "action_type": "shear",
                    "raw_updates": {"s_lig": 150},
                    "_tightening_family": "shear_spacing",
                    "item": {"family": "ignored"},
                },
                "raw_u": {"s_lig": 150},
                "norm_u": {"s_lig": 150},
                "direction": {"is_reduction_candidate": False, "is_growth_only": False},
                "family": "shear_spacing",
            },
        ],
        "prepared_samples": [
            {
                "label": "Reduce depth",
                "action_type": "tighten",
                "family": "bending_depth",
                "raw_updates": {"D": 550, "drop_me": True},
                "normalized_updates": {"D": 550},
            },
            {
                "label": "Tighten links",
                "action_type": "shear",
                "family": "shear_spacing",
                "raw_updates": {"s_lig": 150},
                "normalized_updates": {"s_lig": 150},
            },
        ],
        "reduction_candidates_considered": 1,
        "governing_family_exists": True,
        "shear_governing_family_detected": True,
        "governing_family_exists_after_domain_fix": True,
        "shear_domain_prune_active": True,
        "should_apply_domain_prune": True,
        "mixed_direction_mode": "current:target",
    }
    return {"result": result, "matches": result == expected}


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_prepare_one_click_solver_candidates_coordinator",
    )
    solve_start, solve_end, solve_body = _function_segment(source, "_solve_one_click_to_target")
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    runtime = _run_case(module)
    static_checks = {
        "helper_present": "def _prepare_one_click_solver_candidates_coordinator(" in source,
        "helper_builds_pool_labels": '"pool_labels": pool_labels' in helper,
        "helper_builds_prepared_candidates": '"prepared": prepared' in helper,
        "helper_preserves_prepared_sample_limit": "if len(prepared_samples) < 6:" in helper,
        "helper_preserves_normalization_source": 'source="one_click_iter:normalize"' in helper,
        "helper_preserves_governing_family_detection": "_candidate_family_matches_governing_domain(" in helper,
        "helper_preserves_mixed_direction_mode": "_one_click_mixed_direction_classification(cur_eval, mode_config)" in helper,
        "solver_delegates_candidate_preparation": "_prepare_one_click_solver_candidates_coordinator(" in solve_body,
        "solver_rehydrates_prune_flags": 'should_apply_domain_prune = bool(prepared_candidate_state["should_apply_domain_prune"])' in solve_body,
        "solver_keeps_rejection_counters": all(
            token in solve_body
            for token in [
                "rejected_as_non_governing_cleanup = 0",
                "rejected_as_non_material_improvement = 0",
                "rejected_as_no_real_change = 0",
                "rejected_as_duplicate_signature = 0",
                "rejected_as_evaluation_failed = 0",
            ]
        ),
    }
    status = "PASS"
    if not all(static_checks.values()) or not runtime["matches"]:
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_candidate_preparation_coordinator",
        "helper_segment": {
            "function": "_prepare_one_click_solver_candidates_coordinator",
            "start_line": helper_start,
            "end_line": helper_end,
            "line_count": helper_end - helper_start + 1,
        },
        "solver_segment": {
            "function": "_solve_one_click_to_target",
            "start_line": solve_start,
            "end_line": solve_end,
            "line_count": solve_end - solve_start + 1,
        },
        "static_checks": static_checks,
        "runtime": runtime,
        "product_behavior_changed": False,
        "next_safe_slice": "extract a narrow candidate no-real-change/prune prefilter coordinator",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_candidate_preparation_solver_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_candidate_preparation_solver_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Candidate Preparation Solver Coordinator Extraction",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Static Checks",
    ]
    for key, value in payload["static_checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## Runtime",
            f"- Candidate preparation bundle matches: `{payload['runtime']['matches']}`",
            "",
            "## Next Safe Slice",
            "",
            str(payload["next_safe_slice"]),
        ],
    )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main() -> int:
    payload = build_payload()
    json_path, md_path = write_artifacts(payload)
    print(json.dumps({"status": payload["status"], "json": str(json_path), "report": str(md_path)}, indent=2))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
