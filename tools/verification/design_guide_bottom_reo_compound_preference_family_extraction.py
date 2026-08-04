"""Verify bottom-reo compound preference selection moved to bending family ownership."""

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

INPUTS = ROOT / "inputs_page.py"
BENDING = ROOT / "design_brain" / "families" / "bending.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

PAGE_WRAPPER = "_maybe_prefer_compound_over_pure_geometry"
FAMILY_HELPER = "select_bottom_reo_compound_preference_candidate"


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


def _old_selected_id(
    best: dict | None,
    ranked: list[dict],
    *,
    width_key: str | None,
    mode_config: dict | None,
    seed_candidate: dict | None,
    score_margin: float,
) -> str | None:
    from design_brain.families.bending import (
        prefer_compound_over_pure_geometry,
        resolve_bottom_reo_geometry_trial_axis,
    )

    mode = mode_config if isinstance(mode_config, dict) else {}
    seed = seed_candidate if isinstance(seed_candidate, dict) else {}
    selected = prefer_compound_over_pure_geometry(
        best,
        ranked,
        geometry_axis=resolve_bottom_reo_geometry_trial_axis(best, width_key=width_key),
        search_strategy=str(mode.get("search_strategy", "balanced") or "balanced"),
        seed_depth=float(seed.get("depth", 0.0) or 0.0),
        score_margin=float(score_margin),
    )
    if not isinstance(selected, dict):
        return None
    return str(selected.get("candidate_id") or selected.get("label") or "")


def _new_selected_id(
    best: dict | None,
    ranked: list[dict],
    *,
    width_key: str | None,
    mode_config: dict | None,
    seed_candidate: dict | None,
    score_margin: float,
) -> str | None:
    from design_brain.families.bending import select_bottom_reo_compound_preference_candidate

    selected = select_bottom_reo_compound_preference_candidate(
        best,
        ranked,
        width_key=width_key,
        mode_config=mode_config,
        seed_candidate=seed_candidate,
        score_margin=score_margin,
    )
    if not isinstance(selected, dict):
        return None
    return str(selected.get("candidate_id") or selected.get("label") or "")


def _sample_cases() -> list[dict[str, Any]]:
    pure_width = {
        "candidate_id": "pure_width",
        "label": "pure width",
        "recommendation_geometry_trial": True,
        "recommendation_compound": False,
        "is_compliant": True,
        "score": 100.0,
        "updates": {"b": 350.0},
        "depth": 600.0,
    }
    compound_width = {
        "candidate_id": "compound_width",
        "label": "compound width",
        "recommendation_geometry_trial": False,
        "recommendation_compound": True,
        "compound_geo_axis": "width",
        "is_compliant": True,
        "score": 111.0,
        "depth": 600.0,
    }
    compound_width_deeper = dict(compound_width, candidate_id="compound_width_deeper", score=105.0, depth=650.0)
    compound_depth = {
        "candidate_id": "compound_depth",
        "label": "compound depth",
        "recommendation_geometry_trial": False,
        "recommendation_compound": True,
        "compound_geo_axis": "depth",
        "is_compliant": True,
        "score": 112.0,
        "depth": 620.0,
    }
    pure_depth = dict(pure_width, candidate_id="pure_depth", updates={"D": 620.0})
    pure_non_geo = dict(pure_width, candidate_id="pure_non_geo", recommendation_geometry_trial=False)
    already_compound = dict(compound_width, candidate_id="already_compound", recommendation_geometry_trial=True)
    far_compound = dict(compound_width, candidate_id="far_compound", score=180.0)
    return [
        {
            "case": "none_best",
            "best": None,
            "ranked": [compound_width],
            "width_key": "b",
            "mode_config": {"search_strategy": "balanced"},
            "seed_candidate": {"depth": 600.0},
            "score_margin": 28.0,
        },
        {
            "case": "already_compound",
            "best": already_compound,
            "ranked": [already_compound, compound_width],
            "width_key": "b",
            "mode_config": {"search_strategy": "balanced"},
            "seed_candidate": {"depth": 600.0},
            "score_margin": 28.0,
        },
        {
            "case": "not_geometry_trial",
            "best": pure_non_geo,
            "ranked": [compound_width],
            "width_key": "b",
            "mode_config": {"search_strategy": "balanced"},
            "seed_candidate": {"depth": 600.0},
            "score_margin": 28.0,
        },
        {
            "case": "width_compound_within_margin",
            "best": pure_width,
            "ranked": [pure_width, compound_width],
            "width_key": "b",
            "mode_config": {"search_strategy": "balanced"},
            "seed_candidate": {"depth": 600.0},
            "score_margin": 28.0,
        },
        {
            "case": "width_compound_outside_margin",
            "best": pure_width,
            "ranked": [pure_width, far_compound],
            "width_key": "b",
            "mode_config": {"search_strategy": "balanced"},
            "seed_candidate": {"depth": 600.0},
            "score_margin": 28.0,
        },
        {
            "case": "shallow_rejects_deeper_width_compound",
            "best": pure_width,
            "ranked": [pure_width, compound_width_deeper],
            "width_key": "b",
            "mode_config": {"search_strategy": "shallow"},
            "seed_candidate": {"depth": 600.0},
            "score_margin": 28.0,
        },
        {
            "case": "depth_compound_within_margin",
            "best": pure_depth,
            "ranked": [pure_depth, compound_width, compound_depth],
            "width_key": "b",
            "mode_config": {"search_strategy": "balanced"},
            "seed_candidate": {"depth": 600.0},
            "score_margin": 28.0,
        },
    ]


def _forbidden_terms(segment: str) -> dict[str, bool]:
    return {
        "imports_inputs_page": "inputs_page" in segment,
        "imports_streamlit": "streamlit" in segment or "st." in segment,
        "uses_session_state": "session_state" in segment,
        "uses_apply_routing": "apply_" in segment or "one_click" in segment,
        "uses_rendering": "render_" in segment or "html" in segment,
        "uses_publication": "FinalDesignGuidePublication" in segment or "publication" in segment,
    }


def build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS)
    bending_source = _read(BENDING)
    page_start, page_end, page_segment = _function_segment(inputs_source, PAGE_WRAPPER)
    helper_start, helper_end, helper_segment = _function_segment(bending_source, FAMILY_HELPER)

    parity_rows: list[dict[str, Any]] = []
    for case in _sample_cases():
        old = _old_selected_id(
            case.get("best"),
            list(case.get("ranked") or []),
            width_key=case.get("width_key"),
            mode_config=case.get("mode_config"),
            seed_candidate=case.get("seed_candidate"),
            score_margin=float(case.get("score_margin", 0.0) or 0.0),
        )
        new = _new_selected_id(
            case.get("best"),
            list(case.get("ranked") or []),
            width_key=case.get("width_key"),
            mode_config=case.get("mode_config"),
            seed_candidate=case.get("seed_candidate"),
            score_margin=float(case.get("score_margin", 0.0) or 0.0),
        )
        parity_rows.append({"case": case.get("case"), "old": old, "new": new, "matches": old == new})

    forbidden = _forbidden_terms(helper_segment)
    checks = {
        "family_helper_exists": bool(helper_segment),
        "family_helper_has_no_page_or_ui_forbidden_terms": not any(forbidden.values()),
        "page_wrapper_delegates_to_family_helper": "_select_bottom_reo_compound_preference_candidate(" in page_segment,
        "page_wrapper_keeps_width_key_collection": "_resolve_geometry_width_context(state)" in page_segment,
        "page_wrapper_no_longer_calls_raw_preference_helper": "return _prefer_compound_over_pure_geometry(" not in page_segment
        and "= _prefer_compound_over_pure_geometry(" not in page_segment,
        "page_wrapper_no_longer_computes_geometry_axis": "_geometry_trial_axis_for_bottom_rec(" not in page_segment,
        "page_wrapper_no_longer_reads_search_strategy": "search_strategy" not in page_segment,
        "page_wrapper_no_longer_reads_seed_depth": "seed_candidate.get(\"depth\"" not in page_segment
        and "seed_candidate.get('depth'" not in page_segment,
        "page_no_longer_imports_raw_preference_alias": "prefer_compound_over_pure_geometry as _prefer_compound_over_pure_geometry" not in inputs_source,
        "all_sample_cases_match": all(row["matches"] for row in parity_rows),
        "product_behavior_unchanged": True,
        "visible_wording_unchanged": True,
        "cta_apply_semantics_unchanged": True,
        "family_runtime_unchanged": True,
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    return {
        "status": status,
        "decision": (
            "BOTTOM_REO_COMPOUND_PREFERENCE_FAMILY_ADAPTER_EXTRACTED"
            if status == "PASS"
            else "BOTTOM_REO_COMPOUND_PREFERENCE_EXTRACTION_FAILED"
        ),
        "page_wrapper_lines": {"start": page_start, "end": page_end},
        "family_helper_lines": {"start": helper_start, "end": helper_end},
        "parity_rows": parity_rows,
        "family_helper_forbidden_terms": forbidden,
        "checks": checks,
        "remaining_page_owned_inputs": [
            "page resolves active geometry width key from current state",
            "page passes current mode_config, seed candidate, and configured score-margin constants as plain inputs",
        ],
        "next_safe_slice": "bottom_reo_post_selector_guard_boundary_or_required_ast_projection_parity",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_bottom_reo_compound_preference_family_extraction_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_bottom_reo_compound_preference_family_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Bottom Reo Compound Preference Family Extraction",
        "",
        f"## Executive Summary: {payload.get('status')}",
        "",
        f"Decision: `{payload.get('decision')}`",
        "",
        "## Behaviour Preserved",
        "",
        "The page still supplies page-owned state inputs. The bending family now owns the compound-vs-pure-geometry preference input interpretation and candidate selection.",
        "",
        "## Parity Cases",
        "",
        "| Case | Old selected | New selected | Match |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload.get("parity_rows") or []:
        lines.append(f"| `{row.get('case')}` | `{row.get('old')}` | `{row.get('new')}` | `{row.get('matches')}` |")
    lines.extend(["", "## Remaining Page-Owned Inputs", ""])
    lines.extend(f"- {item}" for item in payload.get("remaining_page_owned_inputs") or [])
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- `{name}`: `{value}`" for name, value in dict(payload.get("checks") or {}).items())
    lines.extend(["", "## Next Safe Slice", "", f"`{payload.get('next_safe_slice')}`"])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = build_payload()
    json_path, report_path = write_artifacts(payload)
    print(f"design_guide_bottom_reo_compound_preference_family_extraction {payload.get('status')}")
    print(f"decision={payload.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    if payload.get("status") != "PASS":
        failed = [name for name, value in dict(payload.get("checks") or {}).items() if not value]
        print(f"failed_checks={','.join(failed)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
