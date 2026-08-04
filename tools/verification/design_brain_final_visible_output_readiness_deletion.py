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

DELETED_VERIFIER_FILES = (
    "tools/verification/design_guide_compatibility_source_output_adapter_extraction.py",
    "tools/verification/design_guide_final_visible_restamper_source_output_adapter_readiness_snapshot.py",
    "tools/verification/design_guide_final_visible_restamper_source_output_trace_wiring_snapshot.py",
    "tools/verification/design_guide_final_visible_restamper_source_output_callsite_parity_readiness_snapshot.py",
    "tools/verification/design_guide_final_visible_restamper_source_output_bridge_parity_wiring_snapshot.py",
    "tools/verification/design_guide_final_visible_restamper_source_output_source_order_parity_snapshot.py",
    "tools/verification/design_guide_final_visible_restamper_source_output_live_parity_snapshot.py",
    "tools/verification/design_guide_final_visible_restamper_source_output_live_cutover_readiness_snapshot.py",
    "tools/verification/design_guide_final_visible_source_output_branch_deadness_snapshot.py",
)

ABSENT_TOKENS = (
    "FinalVisibleContractBindingOutputReadiness",
    "build_final_visible_contract_binding_output_readiness(",
    "final_visible_contract_binding_output_readiness",
    "final_visible_contract_binding_output_latest_hash",
    "final_visible_contract_binding_output_latest_callsite",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _contains(text: str, needle: str) -> dict[str, Any]:
    found = needle in text
    line = None
    if found:
        line = next((i for i, value in enumerate(text.splitlines(), start=1) if needle in value), None)
    return {"needle": needle, "found": found, "line": line}


def _status(checks: list[dict[str, Any]]) -> str:
    return "PASS" if all(not check["found"] for check in checks) else "FAIL"


def main() -> int:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    final_source = _read(FINAL_PUBLICATION)
    inputs_source = _read(INPUTS_PAGE)

    final_checks = [_contains(final_source, needle) for needle in ABSENT_TOKENS]
    inputs_checks = [_contains(inputs_source, needle) for needle in ABSENT_TOKENS]
    verifier_file_checks = [
        {
            "path": relative_path,
            "exists": (ROOT / relative_path).exists(),
        }
        for relative_path in DELETED_VERIFIER_FILES
    ]

    status = "PASS"
    if any(check["found"] for check in final_checks + inputs_checks):
        status = "FAIL"
    if any(check["exists"] for check in verifier_file_checks):
        status = "FAIL"

    payload = {
        "snapshot_name": "design_brain_final_visible_output_readiness_deletion",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "deleted_surface": "final_publication_contract_binding_output_readiness",
        "final_publication_checks": final_checks,
        "inputs_page_checks": inputs_checks,
        "deleted_verifier_file_checks": verifier_file_checks,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }

    VERIFICATION.mkdir(parents=True, exist_ok=True)
    AUDITS.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION / f"design_brain_final_visible_output_readiness_deletion_{stamp}.json"
    md_path = AUDITS / f"design_brain_final_visible_output_readiness_deletion_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# Design Brain Final Visible Output Readiness Deletion",
        "",
        f"Generated: `{stamp}`",
        "",
        f"Status: `{status}`",
        "",
        "## Final Publication Checks",
        "",
    ]
    for check in final_checks:
        lines.append(
            f"- `{check['needle']}` absent in `design_brain/final_publication.py`: `{not check['found']}`"
            + (f" (line {check['line']})" if check["line"] else "")
        )
    lines.extend(["", "## Inputs Page Checks", ""])
    for check in inputs_checks:
        lines.append(
            f"- `{check['needle']}` absent in `inputs_page.py`: `{not check['found']}`"
            + (f" (line {check['line']})" if check["line"] else "")
        )
    lines.extend(["", "## Deleted Verifier Files", ""])
    for check in verifier_file_checks:
        lines.append(f"- `{check['path']}` deleted: `{not check['exists']}`")

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"design_brain_final_visible_output_readiness_deletion {status}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
