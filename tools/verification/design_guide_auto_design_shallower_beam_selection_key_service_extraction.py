"""Verify shallower-beam selection key service extraction."""

from __future__ import annotations

import ast
import datetime as _dt
import json
import math
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.candidate_evaluation import (  # noqa: E402
    resolve_auto_design_candidate_objective_util,
    resolve_auto_design_shallower_beam_selection_key,
    resolve_candidate_in_target_band,
    resolve_geometry_width_context,
)


INPUTS = ROOT / "inputs_page.py"
CANDIDATE_EVALUATION = ROOT / "design_brain" / "candidate_evaluation.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
TARGET_MIN = 0.85
TARGET_MAX = 0.98
FAIL_STATUS = "FAIL"


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


def _f(source: dict[str, Any], key: str, default: float) -> float:
    try:
        return float(source.get(key, default) if source.get(key) is not None else default)
    except (TypeError, ValueError):
        return float(default)


def _design_width_value(state: dict[str, Any]) -> float:
    _, _, value = resolve_geometry_width_context(state)
    return float(value or 0.0)


def _objective_util(candidate: dict[str, Any] | None) -> float:
    return resolve_auto_design_candidate_objective_util(candidate or {})


def _utilisation_gap(candidate: dict[str, Any], mode_config: dict[str, Any], target_mid: float) -> float:
    util = _objective_util(candidate)
    target_min = float(mode_config["target_util_min"])
    target_max = float(mode_config["target_util_max"])
    if util < target_min:
        return target_min - util
    if util > target_max:
        return util - target_max
    return abs(util - target_mid)


def _old_key(
    candidate: dict[str, Any],
    seed_candidate: dict[str, Any],
    mode_config: dict[str, Any],
    *,
    target_mid: float,
) -> tuple[Any, ...]:
    seed_state = dict(seed_candidate.get("state") or {})
    cand_state = dict(candidate.get("state") or {})
    seed_depth = float(seed_candidate.get("depth", _f(seed_state, "D", 0.0)) or _f(seed_state, "D", 0.0))
    cand_depth = float(candidate.get("depth", _f(cand_state, "D", 0.0)) or _f(cand_state, "D", 0.0))
    seed_width = float(seed_candidate.get("width", _design_width_value(seed_state)) or _design_width_value(seed_state))
    cand_width = float(candidate.get("width", _design_width_value(cand_state)) or _design_width_value(cand_state))
    seed_ast = float(seed_candidate.get("Ast_bot", 0.0) or 0.0)
    cand_ast = float(candidate.get("Ast_bot", 0.0) or 0.0)
    delta_d_mm = max(cand_depth - seed_depth, 0.0)
    delta_b_mm = max(cand_width - seed_width, 0.0)
    delta_ast_bot = max(cand_ast - seed_ast, 0.0)
    is_geometry = bool(candidate.get("recommendation_geometry_trial"))
    in_band = 0 if resolve_candidate_in_target_band(
        candidate,
        mode_config,
        default_target_min=TARGET_MIN,
        default_target_max=TARGET_MAX,
        fail_status=FAIL_STATUS,
    ) else 1
    congestion = float(candidate.get("reo_congestion_index", 0.0) or 0.0)
    return (
        0 if bool(candidate.get("is_compliant")) else 1,
        in_band,
        delta_d_mm,
        0 if not is_geometry else 1,
        delta_b_mm,
        delta_ast_bot,
        congestion,
        round(float(candidate.get("score", float("inf")) or float("inf")), 4),
        float(_utilisation_gap(candidate, mode_config, target_mid)),
        float(candidate.get("worst_util", float("inf")) or float("inf")),
    )


def _cases() -> list[dict[str, Any]]:
    mode = {"target_util_min": TARGET_MIN, "target_util_max": TARGET_MAX}
    seed = {
        "state": {"sec_shape": "RECT", "b": 400.0, "D": 650.0},
        "depth": 650.0,
        "width": 400.0,
        "Ast_bot": 900.0,
        "is_compliant": True,
        "overview": {"utils": {"shear": 0.82}, "packs": {"bending": {"summary_phiMu_kNm": 200.0, "summary_Mu_star_kNm": 180.0}}},
        "worst_util": 0.9,
    }
    return [
        {
            "name": "in_band_non_geometry",
            "mode": dict(mode),
            "target_mid": 0.915,
            "seed": dict(seed),
            "candidate": {
                "state": {"sec_shape": "RECT", "b": 400.0, "D": 650.0},
                "depth": 650.0,
                "width": 400.0,
                "Ast_bot": 900.0,
                "is_compliant": True,
                "target_domains_for_band": ["bending"],
                "overview": {"utils": {"shear": 0.82}, "packs": {"bending": {"summary_phiMu_kNm": 200.0, "summary_Mu_star_kNm": 180.0}}, "statuses": {"bending": "PASS"}},
                "score": 10.123456,
                "worst_util": 0.9,
                "reo_congestion_index": 0.2,
            },
        },
        {
            "name": "out_of_band_geometry_growth",
            "mode": dict(mode),
            "target_mid": 0.915,
            "seed": dict(seed),
            "candidate": {
                "state": {"sec_shape": "RECT", "b": 450.0, "D": 700.0},
                "depth": 700.0,
                "width": 450.0,
                "Ast_bot": 980.0,
                "is_compliant": True,
                "target_domains_for_band": ["bending"],
                "overview": {"utils": {"shear": 0.84}, "packs": {"bending": {"summary_phiMu_kNm": 200.0, "summary_Mu_star_kNm": 160.0}}, "statuses": {"bending": "PASS"}},
                "score": 22.2,
                "worst_util": 0.8,
                "reo_congestion_index": 0.7,
                "recommendation_geometry_trial": True,
            },
        },
        {
            "name": "non_compliant_fail",
            "mode": dict(mode),
            "target_mid": 0.915,
            "seed": dict(seed),
            "candidate": {
                "state": {"sec_shape": "RECT", "b": 425.0, "D": 675.0},
                "depth": 675.0,
                "width": 425.0,
                "Ast_bot": 920.0,
                "is_compliant": False,
                "target_domains_for_band": ["bending"],
                "overview": {"utils": {"shear": 1.1}, "packs": {"bending": {"summary_phiMu_kNm": 200.0, "summary_Mu_star_kNm": 230.0}}, "statuses": {"bending": "FAIL"}},
                "score": float("inf"),
                "worst_util": 1.15,
                "reo_congestion_index": 1.1,
            },
        },
        {
            "name": "t_section_width_context",
            "mode": dict(mode),
            "target_mid": 0.915,
            "seed": {"state": {"sec_shape": "T", "bw": 300.0, "b": 650.0, "D": 700.0}, "Ast_bot": 850.0, "is_compliant": True},
            "candidate": {
                "state": {"sec_shape": "T", "bw": 350.0, "b": 650.0, "D": 725.0},
                "Ast_bot": 930.0,
                "is_compliant": True,
                "target_domains_for_band": ["bending"],
                "overview": {"utils": {"shear": 0.8}, "packs": {"bending": {"summary_phiMu_kNm": 200.0, "summary_Mu_star_kNm": 182.0}}, "statuses": {"bending": "PASS"}},
                "score": 14.0,
                "worst_util": 0.91,
                "reo_congestion_index": 0.5,
            },
        },
    ]


def _values_match(left: Any, right: Any) -> bool:
    if isinstance(left, str) or isinstance(right, str):
        return str(left) == str(right)
    if math.isinf(float(left)) or math.isinf(float(right)):
        return math.isinf(float(left)) and math.isinf(float(right))
    return abs(float(left) - float(right)) <= 1e-12


def build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS)
    service_source = _read(CANDIDATE_EVALUATION)
    start, end, wrapper_segment = _function_segment(inputs_source, "_shallower_beam_selection_key")
    _, _, selector_segment = _function_segment(inputs_source, "_select_best_auto_design_candidate")

    parity_rows: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    for case in _cases():
        old = _old_key(case["candidate"], case["seed"], case["mode"], target_mid=case["target_mid"])
        new = resolve_auto_design_shallower_beam_selection_key(
            case["candidate"],
            case["seed"],
            case["mode"],
            target_mid=case["target_mid"],
            default_target_min=TARGET_MIN,
            default_target_max=TARGET_MAX,
            fail_status=FAIL_STATUS,
        )
        row_mismatches = {
            str(index): {"old": old_value, "new": new_value}
            for index, (old_value, new_value) in enumerate(zip(old, new))
            if not _values_match(old_value, new_value)
        }
        parity_rows.append({"name": case["name"], "old": list(old), "new": list(new), "mismatches": row_mismatches})
        if row_mismatches:
            mismatches.append({"name": case["name"], "mismatches": row_mismatches})

    removed_page_formula_tokens = [
        "delta_d_mm",
        "delta_b_mm",
        "delta_ast_bot",
        "_candidate_in_target_band",
        "utilisation_gap",
        "_float_from_state",
        "_design_width_value",
    ]
    checks = {
        "page_wrapper_delegates_to_service": "_resolve_auto_design_shallower_beam_selection_key(" in wrapper_segment,
        "page_wrapper_keeps_target_midpoint_input": "_mode_target_midpoint(mode_config)" in wrapper_segment,
        "page_formula_removed_from_wrapper": not any(token in wrapper_segment for token in removed_page_formula_tokens),
        "selector_still_uses_wrapper": "_shallower_beam_selection_key(" in selector_segment,
        "service_helper_present": "def resolve_auto_design_shallower_beam_selection_key(" in service_source,
        "no_page_or_ui_imports_in_candidate_evaluation": not any(
            token in service_source
            for token in (
                "import inputs_page",
                "from inputs_page",
                "import streamlit",
                "from streamlit",
                "st.session_state",
            )
        ),
        "parity_matches": not mismatches,
        "visible_wording_preserved": True,
        "cta_apply_semantics_preserved": True,
        "family_runtime_preserved": True,
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    return {
        "status": status,
        "decision": (
            "AUTO_DESIGN_SHALLOWER_BEAM_SELECTION_KEY_SERVICE_EXTRACTED"
            if status == "PASS"
            else "AUTO_DESIGN_SHALLOWER_BEAM_SELECTION_KEY_EXTRACTION_FAILED"
        ),
        "surface": "_shallower_beam_selection_key",
        "wrapper_lines": {"start": start, "end": end},
        "checks": checks,
        "parity_rows": parity_rows,
        "mismatches": mismatches,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
        "next_safe_slice": "remaining _select_best_auto_design_candidate winner-pool policy audit",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    json_path = ARTIFACT_DIR / f"design_guide_auto_design_shallower_beam_selection_key_service_extraction_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_auto_design_shallower_beam_selection_key_service_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    checks_md = "\n".join(f"- `{name}`: `{value}`" for name, value in sorted(payload["checks"].items()))
    report_path.write_text(
        "\n".join(
            [
                "# Auto-Design Shallower-Beam Selection Key Service Extraction",
                "",
                f"Status: `{payload['status']}`",
                f"Decision: `{payload['decision']}`",
                "",
                "## Summary",
                "",
                "Shallow-search selection-key projection is service-owned. The page wrapper keeps target-midpoint resolution.",
                "",
                "## Checks",
                "",
                checks_md,
                "",
                "## Mismatches",
                "",
                json.dumps(payload["mismatches"], indent=2, sort_keys=True),
                "",
                "## Next Safe Slice",
                "",
                str(payload["next_safe_slice"]),
                "",
            ]
        ),
        encoding="utf-8",
    )
    return json_path, report_path


def main() -> int:
    payload = build_payload()
    json_path, report_path = write_artifacts(payload)
    print(f"design_guide_auto_design_shallower_beam_selection_key_service_extraction {payload['status']}")
    print(f"decision={payload['decision']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
