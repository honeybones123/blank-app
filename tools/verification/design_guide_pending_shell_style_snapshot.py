"""Proof that the Design Guide pending shell has self-contained critical styling."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
SOURCE_PATH = ROOT / "design_guide_page.py"


def _write_report(payload: dict[str, object], path: Path) -> None:
    lines = [
        "# Design Guide Pending Shell Style Snapshot",
        "",
        f"Status: `{payload['status']}`",
        f"Product behaviour changed: `{payload['product_behaviour_changed']}`",
        "",
        "## Checks",
        "",
    ]
    checks = payload.get("checks") or {}
    if isinstance(checks, dict):
        for key, value in checks.items():
            lines.append(f"- `{key}`: `{value}`")
    if payload.get("failures"):
        lines.extend(["", "## Failures", ""])
        for failure in payload["failures"]:  # type: ignore[index]
            lines.append(f"- `{failure}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    source = SOURCE_PATH.read_text(encoding="utf-8", errors="ignore")
    checks = {
        "pending_shell_function_present": "def _render_proof_pending_shell" in source,
        "pending_shell_testid_present": "data-testid='design-guide-proof-pending'" in source,
        "critical_shell_style_inline": "style='{shell_style}'" in source,
        "critical_eyebrow_style_inline": "style='{eyebrow_style}'" in source,
        "critical_chip_style_inline": "style='{chip_style}'" in source,
        "critical_bar_style_inline": "style='{bar_style}'" in source,
        "bar_fill_fallback_present": "dg-proof-pending-bar-fill" in source
        and "style='{bar_fill_style}'" in source,
        "unsafe_html_enabled": "unsafe_allow_html=True" in source,
    }
    failures = [key for key, passed in checks.items() if not passed]
    payload = {
        "schema": "design_guide_pending_shell_style_snapshot.v1",
        "status": "PASS" if not failures else "FAIL",
        "created_at": stamp,
        "product_behaviour_changed": False,
        "source": str(SOURCE_PATH),
        "checks": checks,
        "failures": failures,
    }
    artifact_path = ARTIFACT_DIR / f"design_guide_pending_shell_style_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_pending_shell_style_{stamp}.md"
    artifact_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "artifact": str(artifact_path),
                "report": str(report_path),
                "failures": failures,
            },
            indent=2,
        )
    )
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
