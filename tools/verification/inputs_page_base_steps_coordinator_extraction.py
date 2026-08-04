"""Verify one-click base steps coordinator extraction."""

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


def _old_steps(
    *,
    stop_reason: str | None,
    step_count: int,
    init_u: Any,
    fin_u: Any,
    reached: Any,
    dbg: dict[str, Any],
    win_l: str | None,
    solver_final_updates: dict[str, Any] | None,
    commit_blocked_reason: str | None,
    commit_rejected: bool,
) -> list[str]:
    base_steps = [
        f"One-click solve: stop={stop_reason}, steps={step_count}, util {init_u} \u2192 {fin_u}, band_reached={reached}.",
    ]
    if stop_reason in ("no_actionable_candidates_after_full_tightening_search", "non_material_remaining_candidates"):
        gdom = str(dbg.get("governing_domain") or "governing")
        base_steps.append(f"No further practical {gdom}-tightening candidate found.")
    if bool(dbg.get("shear_governing_mode_active")) and str(win_l or "").strip().lower() == "combined shear + geometry tightening":
        base_steps.append("Direct link-only tightening was insufficient; combined geometry + shear reinforcement was selected.")
    if solver_final_updates:
        if commit_blocked_reason:
            base_steps.append(
                "No single one-click update currently covers all failing checks; no changes were applied.",
            )
        elif commit_rejected:
            base_steps.append(
                "Live post-commit validation failed; the candidate was rolled back and no changes were kept.",
            )
        else:
            base_steps.append("Updates committed to the beam (single batch).")
    else:
        base_steps.append("No shared-state changes applied.")
    return base_steps


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(source, "_build_one_click_base_steps_coordinator")
    run_start, run_end, run_body = _function_segment(source, "run_one_click_auto_design")
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    cases = [
        {
            "case": "no_updates",
            "stop_reason": "no_action",
            "step_count": 0,
            "init_u": 1.1,
            "fin_u": 1.1,
            "reached": False,
            "dbg": {},
            "win_l": None,
            "solver_final_updates": {},
            "commit_blocked_reason": None,
            "commit_rejected": False,
        },
        {
            "case": "tightening_exhausted",
            "stop_reason": "no_actionable_candidates_after_full_tightening_search",
            "step_count": 3,
            "init_u": 0.7,
            "fin_u": 0.8,
            "reached": False,
            "dbg": {"governing_domain": "shear"},
            "win_l": None,
            "solver_final_updates": {},
            "commit_blocked_reason": None,
            "commit_rejected": False,
        },
        {
            "case": "combined_shear_geometry",
            "stop_reason": "reached_target_band",
            "step_count": 2,
            "init_u": 1.2,
            "fin_u": 0.95,
            "reached": True,
            "dbg": {"shear_governing_mode_active": True},
            "win_l": "Combined shear + geometry tightening",
            "solver_final_updates": {"D": 700},
            "commit_blocked_reason": None,
            "commit_rejected": False,
        },
        {
            "case": "commit_blocked",
            "stop_reason": "partial_failure_coverage",
            "step_count": 1,
            "init_u": 1.0,
            "fin_u": 0.9,
            "reached": False,
            "dbg": {},
            "win_l": "Candidate",
            "solver_final_updates": {"D": 650},
            "commit_blocked_reason": "partial_failure_coverage",
            "commit_rejected": False,
        },
        {
            "case": "commit_rejected",
            "stop_reason": "commit_validation_failed",
            "step_count": 1,
            "init_u": 1.0,
            "fin_u": 0.9,
            "reached": False,
            "dbg": {},
            "win_l": "Candidate",
            "solver_final_updates": {"D": 650},
            "commit_blocked_reason": None,
            "commit_rejected": True,
        },
    ]
    rows: list[dict[str, Any]] = []
    for case in cases:
        kwargs = {key: value for key, value in case.items() if key != "case"}
        old = _old_steps(**kwargs)
        new = module._build_one_click_base_steps_coordinator(**kwargs)
        rows.append({"case": case["case"], "old": old, "new": new, "matches": old == new})

    static_checks = {
        "helper_present": "def _build_one_click_base_steps_coordinator(" in source,
        "helper_preserves_summary_line": "One-click solve: stop=" in helper and "\\u2192" in helper,
        "helper_preserves_visible_messages": all(
            token in helper
            for token in (
                "No further practical",
                "Direct link-only tightening was insufficient",
                "No single one-click update currently covers all failing checks",
                "Live post-commit validation failed",
                "Updates committed to the beam",
                "No shared-state changes applied",
            )
        ),
        "run_delegates_to_helper": "_build_one_click_base_steps_coordinator(" in run_body,
        "run_no_longer_assembles_base_steps_inline": "base_steps = [" not in run_body
        and "base_steps.append(" not in run_body,
        "return_uses_base_steps_preserved": run_body.count("steps\": base_steps") >= 6,
    }
    status = "PASS"
    if not all(static_checks.values()) or any(not row["matches"] for row in rows):
        status = "FAIL"
    return {
        "status": status,
        "surface": "run_one_click_auto_design_base_steps_coordinator",
        "helper_segment": {
            "function": "_build_one_click_base_steps_coordinator",
            "start_line": helper_start,
            "end_line": helper_end,
            "line_count": helper_end - helper_start + 1,
        },
        "run_segment": {
            "function": "run_one_click_auto_design",
            "start_line": run_start,
            "end_line": run_end,
            "line_count": run_end - run_start + 1,
        },
        "static_checks": static_checks,
        "rows": rows,
        "product_behavior_changed": False,
        "next_safe_slice": "extract another return-payload assembly block or start solver phase harness",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_base_steps_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_base_steps_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# One-Click Base Steps Coordinator Extraction",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Static Checks",
    ]
    for key, value in payload["static_checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Cases"])
    for row in payload["rows"]:
        lines.append(f"- `{row['case']}`: `{row['matches']}`")
    lines.extend(["", "## Next Safe Slice", "", str(payload["next_safe_slice"])])
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main() -> int:
    payload = build_payload()
    json_path, md_path = write_artifacts(payload)
    print(json.dumps({"status": payload["status"], "json": str(json_path), "report": str(md_path)}, indent=2))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
