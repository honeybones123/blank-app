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


def _check(text: str, needle: str) -> dict[str, Any]:
    found = needle in text
    line = None
    if found:
        line = next((i for i, value in enumerate(text.splitlines(), start=1) if needle in value), None)
    return {"needle": needle, "found": found, "line": line}


def main() -> int:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    final_source = _read(FINAL_PUBLICATION)
    inputs_source = _read(INPUTS_PAGE)

    final_checks = [
        _check(final_source, "class FinalVisibleContractBindingOutputValidity"),
        _check(final_source, "def build_final_visible_contract_binding_output_validity("),
        _check(final_source, 'and validity.get("valid_without_legacy_source")'),
        _check(final_source, 'and validity.get("safe_to_replace_legacy_guard")'),
        _check(final_source, '"branch_not_supported"'),
        _check(final_source, '"adapter_validity_failed"'),
        _check(final_source, '"missing_projected_item"'),
        _check(final_source, '"final_visible_contract_binding_output_validity_hash"'),
    ]
    input_checks = [
        _check(inputs_source, "_build_final_visible_contract_binding_output_validity("),
        _check(inputs_source, "build_final_visible_contract_binding_output_validity as _build_final_visible_contract_binding_output_validity"),
        _check(inputs_source, "final_visible_contract_binding_output_validity_hash"),
    ]

    status = "PASS" if not any(check["found"] for check in final_checks + input_checks) else "FAIL"
    payload = {
        "snapshot_name": "design_brain_final_visible_output_validity_guard_audit",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "classification": "deleted" if status == "PASS" else "still_present",
        "design_brain_checks": final_checks,
        "inputs_page_checks": input_checks,
        "next_slice": "keep the adapter projection direct and update inventory to zero remaining scaffolding surfaces",
        "product_behavior_changed": False,
    }

    VERIFICATION.mkdir(parents=True, exist_ok=True)
    AUDITS.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION / f"design_brain_final_visible_output_validity_guard_audit_{stamp}.json"
    md_path = AUDITS / f"design_brain_final_visible_output_validity_guard_audit_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    lines = [
        "# Design Brain Final Visible Output Validity Guard Audit",
        "",
        f"Generated: `{stamp}`",
        "",
        f"Status: `{status}`",
        "",
        "## Design Brain Checks (should all be absent)",
        "",
    ]
    for check in final_checks:
        lines.append(f"- `{check['needle']}` found: `{check['found']}` at `{check['line']}`")
    lines.extend(["", "## Inputs Page Checks (should all be absent)", ""])
    for check in input_checks:
        lines.append(f"- `{check['needle']}` found: `{check['found']}` at `{check['line']}`")
    lines.extend(["", "## Recommendation", "", payload["next_slice"], ""])
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"design_brain_final_visible_output_validity_guard_audit {status}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
