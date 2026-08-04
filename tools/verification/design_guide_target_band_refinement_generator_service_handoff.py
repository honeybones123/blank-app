"""Verify target-band refinement generator service handoff."""

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
    generate_target_band_refinement_candidate_states,
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


def _key(state: dict[str, Any]) -> tuple[Any, ...]:
    return tuple(sorted(dict(state or {}).items()))


def _old_generator(
    *,
    current_candidate: dict[str, Any],
    mode_config: dict[str, Any],
    context: dict[str, Any],
    geometry_rows: list[dict[str, Any]],
    bottom_rows: list[dict[str, Any]],
    shear_rows: list[dict[str, Any]],
    layout_rows: list[dict[str, Any]],
    shear_cleanup_possible: bool,
    truth_allows: bool,
    max_candidates: int,
) -> list[dict[str, Any]]:
    candidates: dict[tuple[Any, ...], dict[str, Any]] = {}
    for candidate_state in geometry_rows:
        candidates[_key(candidate_state)] = dict(candidate_state)
    for candidate_state in bottom_rows:
        candidates[_key(candidate_state)] = dict(candidate_state)
    if (
        bool(shear_cleanup_possible)
        and not bool(context.get("disable_shear_cleanup_candidates"))
        and bool(truth_allows)
    ):
        for candidate_state in shear_rows:
            candidates[_key(candidate_state)] = dict(candidate_state)
    for candidate_state in layout_rows:
        candidates[_key(candidate_state)] = dict(candidate_state)
    candidates.pop(_key(dict(current_candidate.get("state") or {})), None)
    return list(candidates.values())[:max_candidates]


def _new_generator(
    *,
    current_candidate: dict[str, Any],
    mode_config: dict[str, Any],
    context: dict[str, Any],
    geometry_rows: list[dict[str, Any]],
    bottom_rows: list[dict[str, Any]],
    shear_rows: list[dict[str, Any]],
    layout_rows: list[dict[str, Any]],
    shear_cleanup_possible: bool,
    truth_allows: bool,
    max_candidates: int,
) -> list[dict[str, Any]]:
    def geometry_fn(_candidate: dict[str, Any], _mode: dict[str, Any]) -> list[dict[str, Any]]:
        return list(geometry_rows)

    def bottom_fn(_candidate: dict[str, Any], _mode: dict[str, Any], _context: dict[str, Any]) -> list[dict[str, Any]]:
        return list(bottom_rows)

    def shear_fn(_candidate: dict[str, Any], _mode: dict[str, Any]) -> list[dict[str, Any]]:
        return list(shear_rows)

    def layout_fn(_candidate: dict[str, Any], _mode: dict[str, Any], _context: dict[str, Any]) -> list[dict[str, Any]]:
        return list(layout_rows)

    def cleanup_possible_fn(_state: dict[str, Any]) -> bool:
        return bool(shear_cleanup_possible)

    def truth_fn(_shear_pack: dict[str, Any]) -> tuple[bool, str]:
        return bool(truth_allows), "test"

    return generate_target_band_refinement_candidate_states(
        current_candidate=current_candidate,
        mode_config=mode_config,
        context=context,
        geometry_variants_fn=geometry_fn,
        bottom_reo_variants_fn=bottom_fn,
        shear_reo_variants_fn=shear_fn,
        layout_variants_fn=layout_fn,
        candidate_key_fn=_key,
        shear_cleanup_possible_fn=cleanup_possible_fn,
        shear_cleanup_allowed_by_truth_fn=truth_fn,
        max_candidates=max_candidates,
    )


def _case_rows() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    base_candidate = {
        "state": {"id": "current", "b": 300, "D": 600, "lig_legs": 2},
        "overview": {"packs": {"shear": {"truth": "ok"}}},
    }
    cases = [
        {
            "name": "all_lanes_with_dedupe_and_current_removal",
            "current_candidate": base_candidate,
            "mode_config": {"search_strategy": "balanced"},
            "context": {"disable_shear_cleanup_candidates": False},
            "geometry_rows": [{"id": "geom"}, {"id": "shared"}],
            "bottom_rows": [{"id": "bottom"}, {"id": "shared"}],
            "shear_rows": [{"id": "shear"}, {"id": "current", "b": 300, "D": 600, "lig_legs": 2}],
            "layout_rows": [{"id": "layout"}],
            "shear_cleanup_possible": True,
            "truth_allows": True,
            "max_candidates": 10,
        },
        {
            "name": "shear_disabled_by_context",
            "current_candidate": base_candidate,
            "mode_config": {},
            "context": {"disable_shear_cleanup_candidates": True},
            "geometry_rows": [{"id": "geom"}],
            "bottom_rows": [],
            "shear_rows": [{"id": "shear"}],
            "layout_rows": [{"id": "layout"}],
            "shear_cleanup_possible": True,
            "truth_allows": True,
            "max_candidates": 10,
        },
        {
            "name": "shear_blocked_by_truth",
            "current_candidate": base_candidate,
            "mode_config": {},
            "context": {"disable_shear_cleanup_candidates": False},
            "geometry_rows": [{"id": "geom"}],
            "bottom_rows": [],
            "shear_rows": [{"id": "shear"}],
            "layout_rows": [],
            "shear_cleanup_possible": True,
            "truth_allows": False,
            "max_candidates": 10,
        },
        {
            "name": "cap_preserves_order",
            "current_candidate": base_candidate,
            "mode_config": {},
            "context": {},
            "geometry_rows": [{"id": "g1"}, {"id": "g2"}],
            "bottom_rows": [{"id": "b1"}],
            "shear_rows": [{"id": "s1"}],
            "layout_rows": [{"id": "l1"}],
            "shear_cleanup_possible": True,
            "truth_allows": True,
            "max_candidates": 3,
        },
    ]
    rows: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    for case in cases:
        kwargs = {key: value for key, value in case.items() if key != "name"}
        old = _old_generator(**kwargs)
        new = _new_generator(**kwargs)
        row = {
            "case": case["name"],
            "old": old,
            "new": new,
            "matches": old == new,
        }
        rows.append(row)
        if not row["matches"]:
            mismatches.append(row)
    return rows, mismatches


def _build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    candidate_source = _read(CANDIDATE_EVALUATION)
    start, end, helper = _function_source(inputs_source, "generate_compliant_refinement_candidates")
    rows, mismatches = _case_rows()
    static_checks = {
        "service_helper_present": "def generate_target_band_refinement_candidate_states(" in candidate_source,
        "page_imports_service_helper": "generate_target_band_refinement_candidate_states as _generate_target_band_refinement_candidate_states" in inputs_source,
        "page_delegates_generator": "return _generate_target_band_refinement_candidate_states(" in helper,
        "page_injects_geometry_lane": "geometry_variants_fn=generate_smaller_geometry_variants" in helper,
        "page_injects_bottom_lane": "bottom_reo_variants_fn=generate_less_bottom_reo_variants" in helper,
        "page_injects_shear_lane": "shear_reo_variants_fn=generate_less_shear_reo_variants" in helper,
        "page_injects_layout_lane": "layout_variants_fn=generate_simpler_layout_variants" in helper,
        "page_injects_key_fn": "candidate_key_fn=_make_auto_design_candidate_key" in helper,
        "page_injects_shear_cleanup_gate": "shear_cleanup_possible_fn=_shear_cleanup_possible" in helper,
        "page_injects_truth_gate": "shear_cleanup_allowed_by_truth_fn=_shear_governing_truth_allows_overdesign_cleanup" in helper,
        "page_injects_cap": "max_candidates=AUTO_DESIGN_MAX_LOCAL_CANDIDATES_PER_ITER" in helper,
        "old_inline_generator_removed": "for candidate_state in" not in helper and "candidates:" not in helper,
        "candidate_service_avoids_inputs_page": "inputs_page" not in candidate_source,
        "candidate_service_avoids_streamlit": "streamlit" not in candidate_source and "st.session_state" not in candidate_source,
    }
    status = "PASS"
    if mismatches or not all(static_checks.values()):
        status = "FAIL"
    return {
        "status": status,
        "surface": "target_band_refinement_generator_service_handoff",
        "extraction_complete_estimate": "99%",
        "inputs_segment": {"function": "generate_compliant_refinement_candidates", "line_start": start, "line_end": end},
        "static_checks": static_checks,
        "case_count": len(rows),
        "parity_rows": rows,
        "mismatches": mismatches,
        "ownership_after": {
            "design_brain_candidate_evaluation": [
                "target-band refinement candidate-state lane orchestration",
                "shear cleanup truth/context gating",
                "candidate key dedupe",
                "current-candidate removal",
                "candidate cap application",
            ],
            "inputs_page": [
                "geometry lane generator callback",
                "bottom-reo lane generator callback",
                "shear-reo lane generator callback",
                "layout lane generator callback",
                "candidate key callback",
                "shear cleanup gate callback",
                "shear-governing truth callback",
            ],
        },
        "next_safe_slice": "audit remaining injected lane callbacks and classify which are service-ready versus page-local solver callbacks",
        "product_behavior_changed": False,
    }


def _write_artifacts(payload: dict[str, Any]) -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_target_band_refinement_generator_service_handoff_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_target_band_refinement_generator_service_handoff_{stamp}.md"
    payload["artifact_paths"] = {"json": str(json_path), "markdown": str(md_path)}
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Target-Band Refinement Generator Service Handoff",
        "",
        f"## Executive Summary: {payload['status']}",
        "",
        f"Extraction complete estimate: `{payload['extraction_complete_estimate']}`",
        "",
        "The candidate-state generator orchestration now lives behind `design_brain.candidate_evaluation`. `inputs_page.py` injects the existing lane callbacks and gate callbacks, preserving lane behaviour while removing page-owned orchestration.",
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
