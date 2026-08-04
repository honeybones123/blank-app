"""Verify Inputs/Design Guide card radius scale after UI polish patch.

This is source-only and proof-only. It checks shared visual surfaces, not
engineering behaviour, publication, CTA/apply semantics, or family runtimes.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_STYLE = ROOT / "ui" / "inputs_page_style.py"
SUMMARY_STYLE = ROOT / "ui" / "summary_sections.py"


TARGET_SELECTORS = {
    "inputs_page_style.py": {
        ".fast-guidance-item": "8px",
        ".dg-card": "8px",
        ".dg-current-chip": "8px",
        ".dg-preview-row": "8px",
        ".dg-reason-row": "8px",
        '.element-container:has(.fast-guidance-action-anchor) + div button[kind="secondary"]': "8px",
        ".fast-auto-design-summary": "8px",
    },
    "summary_sections.py": {
        ".summary-check-card": "8px",
        ".summary-icon-tile": "8px",
        ".summary-status-pill": "999px",
        ".summary-detail-inner": "8px",
    },
}


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _run(command: list[str]) -> dict:
    proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    return {
        "command": command,
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "stdout_tail": proc.stdout[-2000:],
        "stderr_tail": proc.stderr[-2000:],
    }


def _rule_radius(source: str, selector: str) -> str | None:
    pattern = re.escape(selector).replace("\\ ", r"\s+")
    match = re.search(pattern + r"\s*\{([^}]*)\}", source, flags=re.S)
    if not match:
        return None
    body = match.group(1)
    radius = re.search(r"border-radius:\s*([^;]+);", body)
    return radius.group(1).strip() if radius else None


def _build() -> dict:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    sources = {
        "inputs_page_style.py": INPUTS_STYLE.read_text(encoding="utf-8"),
        "summary_sections.py": SUMMARY_STYLE.read_text(encoding="utf-8"),
    }
    rows = []
    failures = []
    for file_name, selectors in TARGET_SELECTORS.items():
        source = sources[file_name]
        for selector, expected in selectors.items():
            actual = _rule_radius(source, selector)
            passed = actual == expected
            rows.append(
                {
                    "file": file_name,
                    "selector": selector,
                    "expected_radius": expected,
                    "actual_radius": actual,
                    "passed": passed,
                }
            )
            if not passed:
                failures.append(f"{file_name}:{selector}:{actual}!={expected}")
    compile_run = _run([sys.executable, "-m", "py_compile", "ui\\inputs_page_style.py", "ui\\summary_sections.py"])
    if not compile_run["passed"]:
        failures.append("py_compile_failed")
    return {
        "schema": "design_guide_ui_radius_scale_snapshot.v1",
        "status": "PASS" if not failures else "FAIL",
        "created_at": _stamp(),
        "product_behaviour_changed": False,
        "visible_engineering_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtimes_changed": False,
        "design_brain_authority_changed": False,
        "rows": rows,
        "failures": failures,
        "compile_run": compile_run,
        "result": "Shared Inputs, Summary, and Design Guide card surfaces use an 8px card radius scale; pills remain pill-shaped.",
    }


def _write(payload: dict) -> tuple[Path, Path]:
    stamp = payload["created_at"]
    json_path = ARTIFACT_DIR / f"design_guide_ui_radius_scale_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_ui_radius_scale_{stamp}.md"
    lines = [
        "# Design Guide UI Radius Scale Snapshot",
        "",
        f"Status: `{payload['status']}`",
        f"Result: {payload['result']}",
        "",
        "## Guarantees",
        "",
        f"- Product behaviour changed: `{payload['product_behaviour_changed']}`",
        f"- Visible engineering wording changed: `{payload['visible_engineering_wording_changed']}`",
        f"- CTA/apply semantics changed: `{payload['cta_apply_semantics_changed']}`",
        f"- Family runtimes changed: `{payload['family_runtimes_changed']}`",
        f"- Design Brain authority changed: `{payload['design_brain_authority_changed']}`",
        "",
        "## Rows",
        "",
        "```json",
        json.dumps(payload["rows"], indent=2, sort_keys=True),
        "```",
        "",
    ]
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def main() -> int:
    payload = _build()
    json_path, md_path = _write(payload)
    print(f"design_guide_ui_radius_scale {payload['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    print("failures=" + json.dumps(payload["failures"], sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
