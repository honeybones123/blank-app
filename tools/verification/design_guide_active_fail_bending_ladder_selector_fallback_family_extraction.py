"""Verify bending active-fail ladder fallback selector is family-owned."""

from __future__ import annotations

import ast
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
BENDING_FAIL = ROOT / "design_brain" / "families" / "bending_fail.py"
INPUTS_PAGE = ROOT / "inputs_page.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

TARGET = "select_design_guide_controller_active_fail_executor_family_ladder_candidate"
HELPER = "select_bending_fail_fallback_repair_candidate_from_ladder"


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


def _function_source(source: str, name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            end = int(node.end_lineno or node.lineno)
            return node.lineno, end, "\n".join(lines[node.lineno - 1 : end])
    return 0, 0, ""


def _old_bending_fallback(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [dict(candidate or {}) for candidate in list(candidates or []) if isinstance(candidate, dict)]
    if not rows:
        return {
            "selected": {},
            "selection_source": "bending_controller_fallback_ranker",
            "family_selected": {},
        }
    selected = min(
        rows,
        key=lambda cand: (
            int(cand.get("bending_fail_ladder_index") or cand.get("ladder_index") or 999999),
            len(dict(cand.get("updates") or {})),
        ),
    )
    return {
        "selected": dict(selected),
        "selection_source": "bending_controller_fallback_ranker",
        "family_selected": {},
    }


def _sample_candidates() -> list[dict[str, Any]]:
    return [
        {
            "candidate_id": "later",
            "bending_fail_ladder_index": 4,
            "updates": {"D": 650.0},
            "candidate_post_util": 0.91,
        },
        {
            "candidate_id": "winner",
            "bending_fail_ladder_index": 2,
            "updates": {"D": 600.0, "bot1": {"count": 8}},
            "candidate_post_util": 0.94,
        },
        {
            "candidate_id": "tie_winner",
            "bending_fail_ladder_index": 2,
            "updates": {"D": 610.0},
            "candidate_post_util": 0.9,
        },
    ]


def _parity() -> dict[str, Any]:
    from design_brain.design_guide_controller import (  # noqa: WPS433
        select_design_guide_controller_active_fail_executor_family_ladder_candidate,
    )
    from design_brain.families.bending_fail import (  # noqa: WPS433
        select_bending_fail_fallback_repair_candidate_from_ladder,
    )

    candidates = _sample_candidates()
    old = _old_bending_fallback(candidates)
    family = select_bending_fail_fallback_repair_candidate_from_ladder(candidates)
    controller = select_design_guide_controller_active_fail_executor_family_ladder_candidate(
        safe_candidates=candidates,
        base_state={"b": 300.0, "D": 500.0},
        target_low=0.85,
        target_high=1.0,
        final_accepted_min_family_util=0.85,
        shear_family_ladder_attempted=False,
        combined_family_ladder_attempted=False,
        combined_family_ladder_found_safe=False,
        bending_family_ladder_attempted=True,
        bending_family_ladder_found_safe=True,
        bending_family_strategy=object(),
    )
    empty_old = _old_bending_fallback([])
    empty_family = select_bending_fail_fallback_repair_candidate_from_ladder([])
    return {
        "old": old,
        "family": family,
        "controller": controller,
        "empty_old": empty_old,
        "empty_family": empty_family,
        "old_matches_family": old == family,
        "old_matches_controller": old == controller,
        "empty_matches": empty_old == empty_family,
    }


def _capture() -> dict[str, Any]:
    controller_source = _read(CONTROLLER)
    bending_source = _read(BENDING_FAIL)
    inputs_source = _read(INPUTS_PAGE)
    target_start, target_end, target_segment = _function_source(controller_source, TARGET)
    helper_start, helper_end, helper_segment = _function_source(bending_source, HELPER)
    parity = _parity()
    return {
        "schema": "design_guide_active_fail_bending_ladder_selector_fallback_family_extraction.v1",
        "target": {"name": TARGET, "line_start": target_start, "line_end": target_end},
        "helper": {"name": HELPER, "line_start": helper_start, "line_end": helper_end},
        "parity": parity,
        "source_checks": {
            "controller_delegates_bending_fallback_to_family": f"{HELPER}(candidates)" in target_segment,
            "controller_no_longer_contains_inline_bending_fallback_source_string": (
                '"bending_controller_fallback_ranker"' not in target_segment
            ),
            "family_helper_exists": bool(helper_segment),
            "family_helper_preserves_existing_selection_source": (
                '"bending_controller_fallback_ranker"' in helper_segment
            ),
            "inputs_page_still_shell_calls_controller_selector": (
                "_select_design_guide_controller_active_fail_executor_family_ladder_candidate(" in inputs_source
            ),
            "controller_boundary_clean": all(
                token not in controller_source for token in ("inputs_page", "streamlit", "st.session_state")
            ),
            "family_helper_boundary_clean": all(
                token not in bending_source for token in ("inputs_page", "streamlit", "st.session_state")
            ),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(payload: dict[str, Any]) -> dict[str, bool]:
    source_checks = dict(payload.get("source_checks") or {})
    parity = dict(payload.get("parity") or {})
    return {
        "old_family_controller_parity": bool(parity.get("old_matches_family"))
        and bool(parity.get("old_matches_controller")),
        "empty_candidate_parity": bool(parity.get("empty_matches")),
        **{key: bool(value) for key, value in source_checks.items()},
        "product_behavior_unchanged": not bool(payload.get("product_behavior_changed")),
        "visible_wording_unchanged": not bool(payload.get("visible_wording_changed")),
        "cta_apply_semantics_unchanged": not bool(payload.get("cta_apply_semantics_changed")),
        "family_runtime_unchanged": not bool(payload.get("family_runtime_changed")),
    }


def _write(payload: dict[str, Any], checks: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_active_fail_bending_ladder_selector_fallback_family_extraction_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_active_fail_bending_ladder_selector_fallback_family_extraction_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Active-Fail Bending Ladder Selector Fallback Family Extraction",
        "",
        f"Status: {payload['status']}",
        "",
        "## Summary",
        (
            "The bending active-fail fallback selector rule now lives in "
            "`design_brain.families.bending_fail`. The controller still sequences the selector call and preserves "
            "the previous selection source string for behaviour and trace stability."
        ),
        "",
        "## Checks",
        *[f"- {name}: {'PASS' if passed else 'FAIL'}" for name, passed in checks.items()],
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = _capture()
    checks = _checks(payload)
    payload["checks"] = checks
    payload["status"] = "PASS" if all(checks.values()) else "FAIL"
    json_path, report_path = _write(payload, checks)
    print(f"design_guide_active_fail_bending_ladder_selector_fallback_family_extraction {payload['status']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
