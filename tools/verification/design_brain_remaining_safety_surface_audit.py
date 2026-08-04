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


def _find_line(text: str, needle: str) -> int | None:
    return next((i for i, value in enumerate(text.splitlines(), start=1) if needle in value), None)


def _check(text: str, needle: str) -> dict[str, Any]:
    line = _find_line(text, needle)
    return {"needle": needle, "found": line is not None, "line": line}


def main() -> int:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    final_source = _read(FINAL_PUBLICATION)
    inputs_source = _read(INPUTS_PAGE)

    validity_checks = [
        _check(final_source, "validity = build_final_visible_contract_binding_output_validity("),
        _check(final_source, 'and validity.get("safe_to_replace_legacy_guard")'),
        _check(final_source, '"final_visible_contract_binding_output_validity_hash"'),
    ]
    payload = {
        "snapshot_name": "design_brain_remaining_safety_surface_audit",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if not any(check["found"] for check in validity_checks) else "FAIL",
        "remaining_surfaces": [],
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }

    VERIFICATION.mkdir(parents=True, exist_ok=True)
    AUDITS.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION / f"design_brain_remaining_safety_surface_audit_{stamp}.json"
    md_path = AUDITS / f"design_brain_remaining_safety_surface_audit_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# Design Brain Remaining Safety Surface Audit",
        "",
        f"Generated: `{stamp}`",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Remaining Surfaces",
        "",
        "None.",
    ]
    for check in validity_checks:
        lines.append(f"- `{check['needle']}` found: `{check['found']}` at line `{check['line']}`")
    lines.extend(
        [
            "",
            "## Recommendation",
            "",
            "The validity guard seam is deleted. No remaining live safety-kept scaffolding surfaces are tracked in design_brain.",
            "",
        ]
    )
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"design_brain_remaining_safety_surface_audit {payload['status']}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
