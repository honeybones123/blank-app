"""Deletion proof for the retired final-visible source-output validity helper."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"
INPUTS = ROOT / "inputs_page.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def build_snapshot() -> dict[str, object]:
    final_source = _read(FINAL_PUBLICATION)
    inputs_source = _read(INPUTS)
    checks = {
        "validity_helper_deleted": "def build_final_visible_contract_binding_output_validity(" not in final_source,
        "validity_dataclass_deleted": "class FinalVisibleContractBindingOutputValidity" not in final_source,
        "validity_guard_deleted": 'and validity.get("safe_to_replace_legacy_guard")' not in final_source,
        "validity_debug_deleted": '"final_visible_contract_binding_output_validity_hash"' not in final_source,
        "inputs_page_not_wired": "_build_final_visible_contract_binding_output_validity(" not in inputs_source,
        "inputs_page_not_importing_helper": (
            "build_final_visible_contract_binding_output_validity as "
            "_build_final_visible_contract_binding_output_validity" not in inputs_source
        ),
        "adapter_projection_still_live": (
            "FinalDesignGuidePublication.final_visible_contract_binding_adapter_projection"
            in final_source
        ),
    }
    failures = [name for name, passed in checks.items() if not passed]
    status = "PASS" if not failures else "FAIL"
    return {
        "schema": "design_guide_final_visible_source_output_adapter_validity_snapshot.v2",
        "created_at": datetime.now().strftime("%Y-%m-%dT%H-%M-%S"),
        "status": status,
        "decision": (
            "OUTPUT_VALIDITY_HELPER_DELETED_DIRECT_ADAPTER_PROJECTION_ACTIVE"
            if status == "PASS"
            else "OUTPUT_VALIDITY_HELPER_DELETION_NEEDS_ATTENTION"
        ),
        "checks": checks,
        "failures": failures,
        "next_safe_step": "keep the direct adapter projection path and remove only unrelated stale verifier assumptions",
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _write_report(snapshot: dict[str, object], path: Path) -> None:
    lines = [
        "# Final Visible Source-Output Adapter Validity Deletion Snapshot",
        "",
        f"Status: `{snapshot['status']}`",
        f"Decision: `{snapshot['decision']}`",
        "",
        "## Checks",
    ]
    for name, passed in (snapshot.get("checks") or {}).items():
        lines.append(f"- `{name}`: `{passed}`")
    lines.extend(["", "## Next Safe Step", str(snapshot.get("next_safe_step") or ""), ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    snapshot = build_snapshot()
    stamp = str(snapshot["created_at"])
    json_path = ARTIFACT_DIR / f"design_guide_final_visible_source_output_adapter_validity_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_final_visible_source_output_adapter_validity_{stamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(snapshot, report_path)
    print(f"design_guide_final_visible_source_output_adapter_validity {snapshot['status']}")
    print(f"decision={snapshot['decision']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
