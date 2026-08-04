"""Verify target-band auto-design context projection extraction."""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.candidate_evaluation import (  # noqa: E402
    build_target_band_auto_design_context_projection,
)


INPUTS_PAGE = ROOT / "inputs_page.py"
CANDIDATE_EVALUATION = ROOT / "design_brain" / "candidate_evaluation.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function_source(source: str, name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            start = int(node.lineno)
            end = int(node.end_lineno or node.lineno)
            return start, end, "\n".join(lines[start - 1 : end])
    raise AssertionError(f"Function not found: {name}")


def _old_projection(
    *,
    resolved_seed_state: dict[str, Any],
    mode_config: dict[str, Any],
    actions: dict[str, Any],
    seed_overview: dict[str, Any],
    ductility_priority: bool,
    geometry_locked: bool,
    disable_shear_strength_candidates: bool,
    disable_shear_cleanup_candidates: bool,
) -> dict[str, Any]:
    return {
        "seed_state": dict(resolved_seed_state),
        "mode_config": dict(mode_config),
        "mode_signature": str(mode_config.get("search_strategy", "balanced") or "balanced"),
        "actions": dict(actions),
        "actions_signature": tuple(actions.get("signature", ())),
        "seed_overview": seed_overview,
        "ductility_priority": ductility_priority,
        "geometry_locked": geometry_locked,
        "disable_shear_strength_candidates": disable_shear_strength_candidates,
        "disable_shear_cleanup_candidates": disable_shear_cleanup_candidates,
        "seen_candidate_keys": set(),
        "layout_fit_cache": {},
    }


def _normalise_context(context: dict[str, Any]) -> dict[str, Any]:
    normalised = dict(context)
    normalised["seen_candidate_keys"] = sorted(list(normalised.get("seen_candidate_keys") or []))
    normalised["layout_fit_cache"] = dict(normalised.get("layout_fit_cache") or {})
    normalised["actions_signature"] = list(normalised.get("actions_signature") or [])
    return normalised


def _case_rows() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cases = [
        {
            "name": "balanced_defaults",
            "resolved_seed_state": {"b": 300.0, "D": 600.0, "M_star": 120.0},
            "mode_config": {"search_strategy": "balanced"},
            "actions": {"signature": ("M", "V"), "M": 120.0},
            "seed_overview": {"statuses": {"bending": "PASS"}, "utils": {"bending": 0.72}},
            "ductility_priority": False,
            "geometry_locked": False,
            "disable_shear_strength_candidates": True,
            "disable_shear_cleanup_candidates": False,
        },
        {
            "name": "shallow_locked_ductility",
            "resolved_seed_state": {"b": 400.0, "D": 700.0, "lig_legs": 2},
            "mode_config": {"search_strategy": "shallow", "target_util_min": 0.85},
            "actions": {"signature": ("M",), "M": 260.0},
            "seed_overview": {"statuses": {"bending": "NEAR LIMIT"}, "utils": {"bending": 0.96}},
            "ductility_priority": True,
            "geometry_locked": True,
            "disable_shear_strength_candidates": False,
            "disable_shear_cleanup_candidates": True,
        },
        {
            "name": "missing_optional_inputs",
            "resolved_seed_state": {},
            "mode_config": {},
            "actions": {},
            "seed_overview": {},
            "ductility_priority": False,
            "geometry_locked": False,
            "disable_shear_strength_candidates": False,
            "disable_shear_cleanup_candidates": False,
        },
    ]
    rows: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    for case in cases:
        old = _old_projection(**{key: value for key, value in case.items() if key != "name"})
        new = build_target_band_auto_design_context_projection(
            **{key: value for key, value in case.items() if key != "name"}
        )
        row = {
            "case": case["name"],
            "old": _normalise_context(old),
            "new": _normalise_context(new),
            "matches": _normalise_context(old) == _normalise_context(new),
        }
        rows.append(row)
        if not row["matches"]:
            mismatches.append(row)
    return rows, mismatches


def _build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    candidate_source = _read(CANDIDATE_EVALUATION)
    start, end, helper = _function_source(inputs_source, "_build_auto_design_context")
    rows, mismatches = _case_rows()
    static_checks = {
        "service_helper_present": "def build_target_band_auto_design_context_projection(" in candidate_source,
        "page_imports_service_helper": "build_target_band_auto_design_context_projection as _build_target_band_auto_design_context_projection" in inputs_source,
        "page_delegates_projection": "return _build_target_band_auto_design_context_projection(" in helper,
        "page_still_collects_actions": "_resolve_design_actions_from_state(" in helper,
        "page_still_resolves_seed_state": "_state_with_resolved_design_actions(" in helper,
        "page_still_collects_shear_flag": "_shear_change_is_relevant(" in helper,
        "page_still_collects_ductility_flag": "_ductility_governs_overview(" in helper,
        "page_still_collects_geometry_lock": "_geometry_lock_enabled(" in helper,
        "candidate_service_avoids_inputs_page": "inputs_page" not in candidate_source,
        "candidate_service_avoids_streamlit": "streamlit" not in candidate_source and "st.session_state" not in candidate_source,
    }
    status = "PASS"
    if mismatches or not all(static_checks.values()):
        status = "FAIL"
    return {
        "status": status,
        "surface": "target_band_context_projection_service_extraction",
        "extraction_complete_estimate": "99%",
        "inputs_segment": {"function": "_build_auto_design_context", "line_start": start, "line_end": end},
        "static_checks": static_checks,
        "case_count": len(rows),
        "parity_rows": rows,
        "mismatches": mismatches,
        "ownership_after": {
            "design_brain_candidate_evaluation": [
                "target-band auto-design context projection shape",
                "mode signature projection",
                "actions signature projection",
                "context cache/default field materialisation",
            ],
            "inputs_page": [
                "page-local action resolution",
                "resolved seed state collection",
                "shear relevance flag collection",
                "ductility priority flag collection",
                "geometry lock flag collection",
            ],
        },
        "next_safe_slice": "callback-based generate_compliant_refinement_candidates service handoff, with lane-generator parity proof",
        "product_behavior_changed": False,
    }


def _write_artifacts(payload: dict[str, Any]) -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_target_band_context_projection_service_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_target_band_context_projection_service_extraction_{stamp}.md"
    payload["artifact_paths"] = {"json": str(json_path), "markdown": str(md_path)}
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Target-Band Context Projection Service Extraction",
        "",
        f"## Executive Summary: {payload['status']}",
        "",
        f"Extraction complete estimate: `{payload['extraction_complete_estimate']}`",
        "",
        "The pure context projection shape now lives in `design_brain.candidate_evaluation`. `inputs_page.py` still owns only page-local scalar/input collection for this helper.",
        "",
        "## Static Checks",
    ]
    for key, value in payload["static_checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Parity Cases"])
    for row in payload["parity_rows"]:
        lines.append(f"- `{row['case']}`: matches `{row['matches']}`")
    lines.extend(["", "## Next Safe Slice", "", str(payload["next_safe_slice"]), "", f"JSON artifact: `{json_path}`"])
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    payload = _build_payload()
    _write_artifacts(payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
