from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from calculations.bending import effective_depth_with_links_mm
from design_brain.candidate_evaluation import (
    build_fast_candidate_evaluation_physical_metric_projection,
)


INPUTS_PAGE = ROOT / "inputs_page.py"
CANDIDATE_EVALUATION = ROOT / "design_brain" / "candidate_evaluation.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _float_from_state(state: dict[str, Any], key: str, default: float) -> float:
    value = state.get(key)
    if value is None:
        return float(default)
    try:
        return float(value)
    except Exception:
        return float(default)


def _int_from_state(state: dict[str, Any], key: str, default: int) -> int:
    value = state.get(key)
    if value is None:
        return int(default)
    try:
        return int(value)
    except Exception:
        return int(default)


def _resolve_geometry_width_context(state: dict[str, Any]) -> tuple[str, str, float]:
    sec_shape = str(state.get("sec_shape", "RECT") or "RECT")
    if sec_shape == "T":
        return "bw", "Web width bw (mm)", float(state.get("bw", state.get("b", 300.0)) or 300.0)
    if sec_shape == "I":
        return "tw", "Web thickness tw (mm)", float(state.get("tw", state.get("b", 200.0)) or 200.0)
    return "b", "Width b (mm)", float(state.get("b", 300.0) or 300.0)


def _design_width_value(state: dict[str, Any]) -> float:
    _, _, width = _resolve_geometry_width_context(state)
    return float(width)


def _effective_bottom_design_state(
    state: dict[str, Any],
    bottom_updates: dict[str, Any] | None = None,
) -> dict[str, Any]:
    d = _float_from_state(state, "D", 600.0)
    cover_bot = _float_from_state(state, "cover_bot", 40.0)
    if bottom_updates:
        db_bot = float(bottom_updates["db_bot_1"])
        nb_bot = int(bottom_updates["bot1_count"]) + int(bottom_updates["bot2_count"])
        ast_bot = (nb_bot * 3.141592653589793 * db_bot**2) / 4.0
    else:
        db_bot = _float_from_state(
            state,
            "db_bot",
            _float_from_state(state, "db_bot_1", 20.0),
        )
        nb_bot = _int_from_state(state, "nb_bot", 0)
        ast_bot = _float_from_state(state, "Ast_bot", 0.0)
    lig_diameter = _float_from_state(state, "lig_d", 10.0)
    d_centroid = effective_depth_with_links_mm(
        D_mm=d,
        cover_to_ligs_mm=cover_bot,
        lig_diameter_mm=lig_diameter,
        bar_diameter_mm=float(db_bot or 0.0),
    )
    return {
        "Ast_bot": float(ast_bot),
        "db_bot": float(db_bot),
        "nb_bot": int(nb_bot),
        "d_centroid": float(d_centroid),
    }


def _bottom_row_count_from_state(state: dict[str, Any]) -> int:
    explicit = _int_from_state(state, "bot_row_count", 0)
    if explicit > 0:
        return explicit
    return 2 if _int_from_state(state, "bot2_count", 0) > 0 else 1


def _bottom_bar_count_from_state(
    state: dict[str, Any],
    bottom_state: dict[str, Any] | None = None,
) -> int:
    resolved = bottom_state or _effective_bottom_design_state(state)
    count = int(resolved.get("nb_bot", 0) or 0)
    if count > 0:
        return count
    return _int_from_state(state, "bot1_count", 0) + _int_from_state(state, "bot2_count", 0)


def _reo_congestion_index(
    state: dict[str, Any],
    bottom_state: dict[str, Any] | None = None,
) -> float:
    resolved = bottom_state or _effective_bottom_design_state(state)
    total_bars = _bottom_bar_count_from_state(state, resolved)
    row_count = max(_bottom_row_count_from_state(state), 1)
    bar_dia = float(resolved.get("db_bot", 0.0) or _float_from_state(state, "db_bot_1", 0.0))
    width = max(_design_width_value(state), 1.0)
    rows_penalty = max(row_count - 1, 0) * 2.5
    density_penalty = (total_bars * max(bar_dia, 1.0)) / width
    return float(total_bars + rows_penalty + density_penalty)


def _old_physical_projection(
    eval_state: dict[str, Any],
    bottom_updates: dict[str, Any] | None,
) -> dict[str, Any]:
    bottom_state = _effective_bottom_design_state(eval_state, bottom_updates)
    shear_density = (
        _int_from_state(eval_state, "lig_legs", 0)
        * max(_int_from_state(eval_state, "lig_d", 0), 1) ** 2
    ) / max(_float_from_state(eval_state, "s_lig", 200.0), 1.0)
    return {
        "bottom_state": bottom_state,
        "width": _design_width_value(eval_state),
        "depth": _float_from_state(eval_state, "D", 600.0),
        "ast_top": _float_from_state(eval_state, "Ast_top", 0.0),
        "bar_count": _bottom_bar_count_from_state(eval_state, bottom_state),
        "row_count": _bottom_row_count_from_state(eval_state),
        "reo_congestion_index": _reo_congestion_index(eval_state, bottom_state),
        "shear_density": shear_density,
    }


def _sample_cases() -> dict[str, dict[str, Any]]:
    return {
        "rect_single_row": {
            "state": {
                "sec_shape": "RECT",
                "b": 300,
                "D": 600,
                "cover_bot": 40,
                "lig_d": 10,
                "lig_legs": 2,
                "s_lig": 200,
                "Ast_bot": 1256.0,
                "Ast_top": 402.0,
                "db_bot": 20,
                "nb_bot": 4,
                "bot1_count": 4,
                "bot2_count": 0,
            },
            "bottom_updates": None,
        },
        "rect_two_row_updates": {
            "state": {
                "sec_shape": "RECT",
                "b": 450,
                "D": 700,
                "cover_bot": 45,
                "lig_d": 12,
                "lig_legs": 4,
                "s_lig": 150,
                "Ast_bot": 1600.0,
                "Ast_top": 600.0,
                "db_bot_1": 20,
                "db_bot_2": 20,
                "bot1_count": 4,
                "bot2_count": 3,
            },
            "bottom_updates": {
                "db_bot_1": 16,
                "db_bot_2": 16,
                "bot1_count": 3,
                "bot2_count": 2,
            },
        },
        "t_beam_width_context": {
            "state": {
                "sec_shape": "T",
                "b": 900,
                "bw": 280,
                "D": 550,
                "cover_bot": 35,
                "lig_d": 10,
                "lig_legs": 0,
                "s_lig": 250,
                "Ast_bot": 900.0,
                "Ast_top": 300.0,
                "db_bot": 16,
                "nb_bot": 5,
                "bot1_count": 5,
                "bot2_count": 0,
            },
            "bottom_updates": None,
        },
    }


def _function_body(source: str, start_token: str, end_token: str) -> str:
    start = source.index(start_token)
    end = source.index(end_token, start)
    return source[start:end]


def build_snapshot() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8")
    candidate_source = CANDIDATE_EVALUATION.read_text(encoding="utf-8")
    fast_body = _function_body(
        inputs_source,
        "def evaluate_candidate_fast(",
        "def _evaluate_candidate_fast(",
    )
    parity_cases: dict[str, Any] = {}
    for name, case in _sample_cases().items():
        state = dict(case["state"])
        bottom_updates = case.get("bottom_updates")
        old = _old_physical_projection(state, bottom_updates)
        new = build_fast_candidate_evaluation_physical_metric_projection(
            eval_state=state,
            bottom_updates=bottom_updates,
        )
        comparable_new = {
            key: new.get(key)
            for key in (
                "bottom_state",
                "width",
                "depth",
                "ast_top",
                "bar_count",
                "row_count",
                "reo_congestion_index",
                "shear_density",
            )
        }
        parity_cases[name] = {
            "old": old,
            "new": comparable_new,
            "matches": old == comparable_new,
            "case_hash": _stable_hash({"old": old, "new": comparable_new}),
        }

    legacy_tokens = {
        "bottom_state_inline": "bottom_state = _effective_bottom_design_state(eval_state, bottom_updates)",
        "width_inline": "width = _design_width_value(eval_state)",
        "depth_inline": 'depth = _float_from_state(eval_state, "D", 600.0)',
        "shear_density_inline": "shear_density = (",
        "bar_count_inline": "_bottom_bar_count_from_state(eval_state, bottom_state)",
        "row_count_inline": "_bottom_row_count_from_state(eval_state)",
        "congestion_inline": "_reo_congestion_index(eval_state, bottom_state)",
    }
    checks = {
        "service_helper_exists": "def build_fast_candidate_evaluation_physical_metric_projection(" in candidate_source,
        "service_helper_exported": '"build_fast_candidate_evaluation_physical_metric_projection"' in candidate_source,
        "inputs_imports_service_helper": "_build_fast_candidate_evaluation_physical_metric_projection" in inputs_source,
        "fast_body_calls_service_helper": "_build_fast_candidate_evaluation_physical_metric_projection(" in fast_body,
        "legacy_inline_metric_block_absent": all(
            token not in fast_body for token in legacy_tokens.values()
        ),
        "parity_cases_match": all(case["matches"] for case in parity_cases.values()),
        "no_inputs_page_import_in_candidate_service": "inputs_page" not in candidate_source,
        "no_streamlit_import_in_candidate_service": "streamlit" not in candidate_source,
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    return {
        "snapshot": "design_guide_fast_candidate_evaluation_physical_metric_projection_extraction",
        "generated_at": _stamp(),
        "status": status,
        "decision": (
            "FAST_CANDIDATE_EVALUATION_PHYSICAL_METRIC_PROJECTION_SERVICE_OWNED"
            if status == "PASS"
            else "FAST_CANDIDATE_EVALUATION_PHYSICAL_METRIC_PROJECTION_NOT_LOCKED"
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
        "checks": checks,
        "legacy_tokens": legacy_tokens,
        "parity_cases": parity_cases,
        "remaining_fast_surfaces": [
            "solver/evaluator callback execution",
            "shear detailing failure input collection",
            "_evaluate_candidate_fast cache/cap/metrics runner",
            "evaluate_candidate_full kernel/output packaging",
        ],
        "snapshot_hash": _stable_hash({"checks": checks, "cases": parity_cases}),
    }


def write_outputs(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = snapshot["generated_at"]
    json_path = ARTIFACT_DIR / f"design_guide_fast_candidate_evaluation_physical_metric_projection_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_fast_candidate_evaluation_physical_metric_projection_extraction_{stamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    checks = "\n".join(
        f"- `{key}`: `{value}`" for key, value in sorted(snapshot["checks"].items())
    )
    cases = "\n".join(
        f"- `{name}`: matches `{case['matches']}`"
        for name, case in sorted(snapshot["parity_cases"].items())
    )
    md_path.write_text(
        "\n".join(
            [
                "# Fast Candidate Evaluation Physical Metric Projection Extraction",
                "",
                f"Status: `{snapshot['status']}`",
                f"Decision: `{snapshot['decision']}`",
                f"Snapshot hash: `{snapshot['snapshot_hash']}`",
                "",
                "## Checks",
                checks,
                "",
                "## Parity Cases",
                cases,
                "",
                "## Remaining Fast Surfaces",
                *[f"- {item}" for item in snapshot["remaining_fast_surfaces"]],
                "",
            ]
        ),
        encoding="utf-8",
    )
    return json_path, md_path


def main() -> int:
    snapshot = build_snapshot()
    json_path, md_path = write_outputs(snapshot)
    print("design_guide_fast_candidate_evaluation_physical_metric_projection_extraction " + snapshot["status"])
    print("decision=" + snapshot["decision"])
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
