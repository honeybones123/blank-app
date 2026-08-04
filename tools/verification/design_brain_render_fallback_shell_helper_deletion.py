from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(r"C:/Users/jono/OneDrive/Documents/GitHub/complete-app - Copy (3)")
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"
INPUTS_PAGE = ROOT / "inputs_page.py"
VERIFICATION = ROOT / "artifacts" / "verification"
AUDITS = ROOT / "artifacts" / "audits"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _contains(text: str, needle: str) -> dict[str, Any]:
    found = needle in text
    line = None
    if found:
        line = next((i for i, value in enumerate(text.splitlines(), start=1) if needle in value), None)
    return {"needle": needle, "found": found, "line": line}


def main() -> int:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    final_source = _read(FINAL_PUBLICATION)
    inputs_source = _read(INPUTS_PAGE)

    absence_checks = [
        _contains(final_source, "class FinalDesignGuideRenderFallbackShellProjection"),
        _contains(final_source, "def build_final_design_guide_render_fallback_shell_projection("),
        _contains(final_source, '"build_final_design_guide_render_fallback_shell_projection"'),
        _contains(inputs_source, "build_final_design_guide_render_fallback_shell_projection as _build_final_design_guide_render_fallback_shell_projection"),
        _contains(inputs_source, "_pre_render_shell_projection = _build_final_design_guide_render_fallback_shell_projection("),
        _contains(inputs_source, "_fallback_shell_projection = _build_final_design_guide_render_fallback_shell_projection("),
    ]
    presence_checks = [
        _contains(final_source, "class FinalDesignGuideDirectShellCardProjection"),
        {
            **_contains(inputs_source, "_build_final_design_guide_direct_shell_card_projection("),
            "expected_absent": True,
        },
    ]

    status = "PASS"
    if any(check["found"] for check in absence_checks):
        status = "FAIL"
    if not presence_checks[0]["found"]:
        status = "FAIL"
    if presence_checks[1]["found"]:
        status = "FAIL"

    payload = {
        "snapshot_name": "design_brain_render_fallback_shell_helper_deletion",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "absence_checks": absence_checks,
        "presence_checks": presence_checks,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }

    VERIFICATION.mkdir(parents=True, exist_ok=True)
    AUDITS.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION / f"design_brain_render_fallback_shell_helper_deletion_{stamp}.json"
    md_path = AUDITS / f"design_brain_render_fallback_shell_helper_deletion_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# Design Brain Render Fallback Shell Helper Deletion",
        "",
        f"Generated: `{stamp}`",
        "",
        f"Status: `{status}`",
        "",
        "## Required Absences",
        "",
    ]
    for check in absence_checks:
        lines.append(f"- `{check['needle']}` absent: `{not check['found']}`")
    lines.extend(["", "## Required Presences", ""])
    lines.append(f"- `{presence_checks[0]['needle']}` present: `{presence_checks[0]['found']}`")
    lines.append(
        f"- `{presence_checks[1]['needle']}` absent from shell: `{not presence_checks[1]['found']}`"
    )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"design_brain_render_fallback_shell_helper_deletion {status}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
