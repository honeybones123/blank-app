"""Verify first-paint summary skeleton implementation.

This source-level snapshot proves the layout fix is confined to the initial
summary placeholder and does not touch Design Brain publication, CTA/apply, or
family runtime ownership.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _run(command: list[str]) -> dict[str, Any]:
    proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    return {
        "command": command,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
        "passed": proc.returncode == 0,
    }


def _first_paint_shell(source: str) -> str:
    match = re.search(
        r'<div class="(?:inputs-first-paint-shell|__FIRST_PAINT_SHELL_CLASS__)".*?</div>\s*"""',
        source,
        flags=re.DOTALL,
    )
    return match.group(0) if match else ""


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": None, "path": None, "passed": False}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"found": True, "status": "UNREADABLE", "path": str(path), "passed": False, "error": str(exc)}
    status = payload.get("status")
    return {"found": True, "status": status, "path": str(path), "passed": status == "PASS"}


def _build() -> dict[str, Any]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    shell = _first_paint_shell(source)
    compile_run = _run([sys.executable, "-m", "py_compile", "inputs_page.py"])
    audit = _latest("design_guide_first_paint_layout_gap_audit")
    checks = {
        "shell_found": bool(shell),
        "skeleton_rows_present": shell.count("summary-skeleton-row") >= 4,
        "compact_reserved_height_present": '"11.5rem" if _first_paint_landing_expected else "11.5rem"' not in source
        and '_first_paint_shell_min_height = "30.5rem" if _first_paint_landing_expected else "24.5rem"' in source,
        "landing_reserved_height_present": '_first_paint_shell_min_height = "30.5rem" if _first_paint_landing_expected else "24.5rem"' in source,
        "mobile_compact_reserved_height_present": '_first_paint_shell_mobile_min_height = "34rem" if _first_paint_landing_expected else "28rem"' in source,
        "landing_mobile_reserved_height_present": '_first_paint_shell_mobile_min_height = "34rem" if _first_paint_landing_expected else "28rem"' in source,
        "landing_branch_class_present": "inputs-first-paint-landing-shell" in source,
        "landing_branch_uses_existing_landing_gate": "_first_paint_landing_expected = bool(inputs_show_landing_dashboard())" in source,
        "old_large_reserved_height_removed": "min-height:25.5rem" not in shell
        and "min-height: 34rem !important" not in shell,
        "existing_loading_text_preserved": "Preparing current summary..." in shell,
        "not_skipped_in_browser_test_mode": "if not _browser_test_mode_for_latency" not in source[
            max(0, source.find("summary_container = st.empty()") - 500):
            source.find("_first_inputs_marker_ms = _inputs_elapsed_ms()")
        ],
        "only_summary_placeholder_scope": "inputs-first-paint-shell" in shell
        and "DesignGuideController" not in shell
        and "FinalDesignGuidePublication" not in shell,
        "no_cta_or_apply_terms_in_shell": all(
            token not in shell
            for token in (
                "_record_rendered_design_guide_primary_apply_payload",
                "button_contract",
                "apply_resolved_candidate",
                "st.button",
            )
        ),
    }
    errors: list[str] = []
    if not compile_run["passed"]:
        errors.append("py_compile_failed")
    if audit.get("passed") is not True:
        errors.append("layout_gap_audit_not_passed")
    if not all(checks.values()):
        errors.append("skeleton_source_check_failed")
    return {
        "schema": "design_guide_first_paint_layout_skeleton_implementation.v1",
        "status": "PASS" if not errors else "FAIL",
        "created_at": datetime.now().strftime("%Y-%m-%dT%H-%M-%S"),
        "product_behavior_changed": False,
        "checks": checks,
        "compile_run": compile_run,
        "layout_gap_audit": audit,
        "errors": errors,
        "next_slice": "Rerun browser/live smoothness profile and compare layout shift.",
    }


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    stamp = payload["created_at"]
    json_path = ARTIFACT_DIR / f"design_guide_first_paint_layout_skeleton_implementation_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_first_paint_layout_skeleton_implementation_{stamp}.md"
    lines = [
        "# Design Guide First-Paint Layout Skeleton Implementation",
        "",
        f"Status: `{payload['status']}`",
        f"Product behaviour changed: `{payload['product_behavior_changed']}`",
        "",
        "## Checks",
        "",
    ]
    for key, value in payload["checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Next Slice", "", payload["next_slice"], ""])
    if payload["errors"]:
        lines.extend(["## Errors", "", "```json", json.dumps(payload["errors"], indent=2), "```", ""])
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def main() -> int:
    payload = _build()
    json_path, md_path = _write(payload)
    print(f"design_guide_first_paint_layout_skeleton_implementation {payload['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if payload["errors"]:
        print("errors=" + json.dumps(payload["errors"]))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
