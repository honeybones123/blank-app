"""Verify mixed-direction rank-adjustment service extraction."""

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
    resolve_candidate_domain_score,
    resolve_candidate_mixed_direction_rank_adjustment,
)


INPUTS = ROOT / "inputs_page.py"
CANDIDATE_EVALUATION = ROOT / "design_brain" / "candidate_evaluation.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
DEFAULT_MIN = 0.85
DEFAULT_MAX = 1.0
FAIL = "FAIL"


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


def _candidate(*, bending: Any = None, shear: Any = None, mu: Any = None, phi: Any = None, statuses: dict[str, Any] | None = None) -> dict[str, Any]:
    bending_pack: dict[str, Any] = {}
    if mu is not None:
        bending_pack["summary_Mu_star_kNm"] = mu
    if phi is not None:
        bending_pack["summary_phiMu_kNm"] = phi
    return {
        "overview": {
            "statuses": dict(statuses or {}),
            "utils": {"bending": bending, "shear": shear},
            "packs": {"bending": bending_pack},
        }
    }


def _score(eval_obj: dict[str, Any] | None, domain: str, mode_config: dict[str, Any]) -> dict[str, Any]:
    return resolve_candidate_domain_score(
        eval_obj,
        domain,
        mode_config,
        default_target_min=DEFAULT_MIN,
        default_target_max=DEFAULT_MAX,
        fail_status=FAIL,
    )


def _old_rank(
    cur_eval: dict[str, Any] | None,
    candidate_eval: dict[str, Any] | None,
    mixed_mode: str | None,
    mode_config: dict[str, Any],
    *,
    primary_improvement_margin: float = 0.02,
) -> dict[str, Any]:
    if mixed_mode == "bending_under_shear_over":
        primary_domain = "bending"
        secondary_domain = "shear"
    elif mixed_mode == "bending_over_shear_under":
        primary_domain = "shear"
        secondary_domain = "bending"
    else:
        return {
            "active": False,
            "mixed_mode": None,
            "primary_domain": None,
            "secondary_domain": None,
            "primary_material_improvement": False,
            "primary_distance": float("inf"),
            "secondary_distance": float("inf"),
            "current_secondary_distance": float("inf"),
        }

    current_primary = _score(cur_eval, primary_domain, mode_config)
    candidate_primary = _score(candidate_eval, primary_domain, mode_config)
    current_secondary = _score(cur_eval, secondary_domain, mode_config)
    candidate_secondary = _score(candidate_eval, secondary_domain, mode_config)
    current_primary_pass = bool(current_primary.get("pass"))
    candidate_primary_pass = bool(candidate_primary.get("pass"))
    current_primary_distance = float(current_primary.get("distance", float("inf")) or float("inf"))
    candidate_primary_distance = float(candidate_primary.get("distance", float("inf")) or float("inf"))
    current_secondary_distance = float(current_secondary.get("distance", float("inf")) or float("inf"))
    candidate_secondary_distance = float(candidate_secondary.get("distance", float("inf")) or float("inf"))
    margin = float(max(0.0, primary_improvement_margin))
    primary_material_improvement = bool(
        (candidate_primary_pass and not current_primary_pass)
        or (
            math.isfinite(current_primary_distance)
            and math.isfinite(candidate_primary_distance)
            and candidate_primary_distance <= (current_primary_distance - margin)
        )
    )
    return {
        "active": True,
        "mixed_mode": mixed_mode,
        "primary_domain": primary_domain,
        "secondary_domain": secondary_domain,
        "primary_material_improvement": primary_material_improvement,
        "primary_distance": candidate_primary_distance,
        "secondary_distance": candidate_secondary_distance if primary_material_improvement else current_secondary_distance,
        "current_secondary_distance": current_secondary_distance,
    }


def _new_rank(
    cur_eval: dict[str, Any] | None,
    candidate_eval: dict[str, Any] | None,
    mixed_mode: str | None,
    mode_config: dict[str, Any],
    *,
    primary_improvement_margin: float = 0.02,
) -> dict[str, Any]:
    return resolve_candidate_mixed_direction_rank_adjustment(
        cur_eval,
        candidate_eval,
        mixed_mode,
        mode_config,
        default_target_min=DEFAULT_MIN,
        default_target_max=DEFAULT_MAX,
        fail_status=FAIL,
        primary_improvement_margin=primary_improvement_margin,
    )


def _normalize(value: Any) -> Any:
    if isinstance(value, float) and math.isinf(value):
        return "inf"
    if isinstance(value, dict):
        return {key: _normalize(inner) for key, inner in value.items()}
    return value


def build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS)
    candidate_source = _read(CANDIDATE_EVALUATION)
    _, _, wrapper = _function_segment(inputs_source, "_one_click_mixed_direction_rank_adjustment")
    _, _, classification = _function_segment(inputs_source, "_one_click_mixed_direction_classification")
    cases = [
        (
            "inactive_mode",
            _candidate(mu=90.0, phi=100.0, shear=0.6, statuses={"bending": "PASS", "shear": "PASS"}),
            _candidate(mu=90.0, phi=100.0, shear=0.9, statuses={"bending": "PASS", "shear": "PASS"}),
            None,
            {},
        ),
        (
            "bending_primary_passes",
            _candidate(mu=70.0, phi=100.0, shear=0.6, statuses={"bending": "FAIL", "shear": "PASS"}),
            _candidate(mu=90.0, phi=100.0, shear=0.7, statuses={"bending": "PASS", "shear": "PASS"}),
            "bending_under_shear_over",
            {},
        ),
        (
            "bending_primary_distance_improves",
            _candidate(mu=60.0, phi=100.0, shear=0.6, statuses={"bending": "PASS", "shear": "PASS"}),
            _candidate(mu=78.0, phi=100.0, shear=0.7, statuses={"bending": "PASS", "shear": "PASS"}),
            "bending_under_shear_over",
            {},
        ),
        (
            "bending_primary_not_material",
            _candidate(mu=80.0, phi=100.0, shear=0.6, statuses={"bending": "PASS", "shear": "PASS"}),
            _candidate(mu=81.0, phi=100.0, shear=0.7, statuses={"bending": "PASS", "shear": "PASS"}),
            "bending_under_shear_over",
            {},
        ),
        (
            "shear_primary_distance_improves",
            _candidate(bending=0.6, shear=1.2, statuses={"bending": "PASS", "shear": "PASS"}),
            _candidate(bending=0.7, shear=1.0, statuses={"bending": "PASS", "shear": "PASS"}),
            "bending_over_shear_under",
            {},
        ),
        (
            "custom_margin",
            _candidate(mu=70.0, phi=100.0, shear=0.6, statuses={"bending": "PASS", "shear": "PASS"}),
            _candidate(mu=72.0, phi=100.0, shear=0.7, statuses={"bending": "PASS", "shear": "PASS"}),
            "bending_under_shear_over",
            {"target_util_min": 0.7, "target_util_max": 0.95},
        ),
    ]
    rows: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    for name, cur_eval, candidate_eval, mixed_mode, mode_config in cases:
        old = _old_rank(cur_eval, candidate_eval, mixed_mode, mode_config)
        new = _new_rank(cur_eval, candidate_eval, mixed_mode, mode_config)
        row = {"case": name, "old": _normalize(old), "new": _normalize(new), "matches": _normalize(old) == _normalize(new)}
        rows.append(row)
        if not row["matches"]:
            mismatches.append(row)

    wrapper_thin = (
        "_resolve_candidate_mixed_direction_rank_adjustment(" in wrapper
        and "_one_click_domain_score(" not in wrapper
        and "primary_material_improvement" not in wrapper
    )
    service_present = "def resolve_candidate_mixed_direction_rank_adjustment(" in candidate_source
    classification_bounded = (
        "_build_design_actions_context_isolated(" in classification
        and "_shear_demands_negligible(" in classification
        and "_bending_demands_negligible(" in classification
    )
    forbidden_service_import_hits = [
        token
        for token in (
            "import inputs_page",
            "from inputs_page",
            "import streamlit",
            "from streamlit",
            "st.session_state",
        )
        if token in candidate_source
    ]
    status = "PASS"
    if mismatches or not wrapper_thin or not service_present or not classification_bounded or forbidden_service_import_hits:
        status = "FAIL"
    return {
        "status": status,
        "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "wrapper_thin": wrapper_thin,
        "service_present": service_present,
        "classification_bounded_page_owned": classification_bounded,
        "classification_move_deferred_reason": "classification still builds page-local actions and calls demand-negligible helpers",
        "forbidden_service_import_hits": forbidden_service_import_hits,
        "case_count": len(rows),
        "mismatch_count": len(mismatches),
        "rows": rows,
        "mismatches": mismatches,
        "product_behavior_changed": False,
        "next_safe_slice": "extract or inject action-demand inputs for mixed-direction classification",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_mixed_direction_rank_adjustment_service_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_mixed_direction_rank_adjustment_service_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Mixed-Direction Rank Adjustment Service Extraction",
        "",
        "## Executive Summary",
        f"Status: `{payload['status']}`",
        f"Product behaviour changed: `{payload['product_behavior_changed']}`",
        "",
        "## Proof",
        f"- Thin page wrapper: `{payload['wrapper_thin']}`",
        f"- Service helper present: `{payload['service_present']}`",
        f"- Classification bounded page-owned: `{payload['classification_bounded_page_owned']}`",
        f"- Classification deferred reason: `{payload['classification_move_deferred_reason']}`",
        f"- Forbidden service import hits: `{payload['forbidden_service_import_hits']}`",
        f"- Cases: `{payload['case_count']}`",
        f"- Mismatches: `{payload['mismatch_count']}`",
        "",
        "## Next Safe Slice",
        f"`{payload['next_safe_slice']}`",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main() -> int:
    payload = build_payload()
    json_path, md_path = write_artifacts(payload)
    print(json.dumps({"status": payload["status"], "json": str(json_path), "report": str(md_path)}, indent=2))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
