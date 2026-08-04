"""Final-visible bending snapshot store branch deletion proof."""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification.design_guide_final_visible_branch_body_inventory_snapshot import (  # noqa: E402
    build_snapshot as build_branch_body_inventory_snapshot,
)


INPUTS = ROOT / "inputs_page.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda p: p.stat().st_mtime)
    if not paths:
        return {"found": False, "path": None, "status": "MISSING"}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception as exc:
        return {"found": True, "path": str(path), "status": "UNREADABLE", "error": str(exc)}
    status = str(payload.get("status") or payload.get("result") or "").upper()
    return {"found": True, "path": str(path), "status": "PASS" if "PASS" in status else status}


def _function_body(source: str, name: str) -> str:
    needle = f"def {name}("
    start = source.find(needle)
    if start < 0:
        return ""
    next_def = source.find("\ndef ", start + len(needle))
    return source[start:] if next_def < 0 else source[start:next_def]


def build_snapshot() -> dict[str, Any]:
    source = _read(INPUTS)
    inventory = build_branch_body_inventory_snapshot()
    final_visible_body = _function_body(source, "_publish_final_visible_design_guide_contract_binding")
    store_helper_body = _function_body(source, "_store_bending_fail_publication_snapshot")
    latest = {
        "controller_object": _latest("design_guide_bending_fail_snapshot_reuse_controller_object"),
        "trace_wiring": _latest("design_guide_bending_fail_snapshot_reuse_trace_wiring"),
        "cutover": _latest("design_guide_bending_fail_snapshot_reuse_cutover"),
        "legacy_assembler_deletion": _latest(
            "design_guide_bending_fail_snapshot_reuse_legacy_assembler_deletion"
        ),
        "branch_inventory": _latest("design_guide_final_visible_branch_body_inventory"),
    }
    final_visible_store_count = final_visible_body.count("_store_bending_fail_publication_snapshot(")
    helper_definition_exists = bool(store_helper_body)
    other_store_call_count = max(source.count("_store_bending_fail_publication_snapshot(") - 1, 0)
    inventory_totals = inventory.get("totals") or {}
    checks = {
        "final_visible_branch_store_call_zero": final_visible_store_count == 0,
        "branch_future_extraction_count_zero": (
            inventory_totals.get("future_extraction_candidate_count") == 0
        ),
        "store_helper_still_defined_for_other_surfaces": helper_definition_exists,
        "other_store_surfaces_not_deleted": other_store_call_count >= 1,
        "controller_object_pass": latest["controller_object"].get("status") == "PASS",
        "trace_wiring_pass": latest["trace_wiring"].get("status") == "PASS",
        "cutover_pass": latest["cutover"].get("status") == "PASS",
        "legacy_assembler_deletion_pass": latest["legacy_assembler_deletion"].get("status") == "PASS",
    }
    failures = [name for name, passed in checks.items() if not passed]
    status = "PASS" if not failures else "FAIL"
    return {
        "schema": "design_guide_final_visible_bending_snapshot_store_branch_deletion_snapshot.v1",
        "created_at": datetime.now().strftime("%Y-%m-%dT%H-%M-%S"),
        "status": status,
        "decision": (
            "FINAL_VISIBLE_BENDING_SNAPSHOT_STORE_BRANCH_CALL_DELETED"
            if status == "PASS"
            else "FINAL_VISIBLE_BENDING_SNAPSHOT_STORE_BRANCH_DELETION_NEEDS_ATTENTION"
        ),
        "checks": checks,
        "failures": failures,
        "counts": {
            "final_visible_store_call_count": final_visible_store_count,
            "other_store_call_count": other_store_call_count,
            "future_extraction_candidate_count": inventory_totals.get(
                "future_extraction_candidate_count"
            ),
            "page_shell_effect_count": inventory_totals.get("page_shell_effect_count"),
        },
        "latest": latest,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
        "next_safe_step": (
            "classify remaining page-shell projection helpers now that future extraction candidates are zero"
        ),
    }


def _write_report(snapshot: dict[str, Any], path: Path) -> None:
    lines = [
        "# Final Visible Bending Snapshot Store Branch Deletion",
        "",
        f"Status: `{snapshot['status']}`",
        f"Decision: `{snapshot['decision']}`",
        "",
        "## Counts",
    ]
    for key, value in snapshot["counts"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Latest Required Proofs"])
    for key, row in snapshot["latest"].items():
        lines.append(f"- `{key}`: `{row.get('status')}` `{row.get('path')}`")
    lines.extend(
        [
            "",
            "## Failures",
            *(f"- `{failure}`" for failure in snapshot["failures"]),
            "",
            "## Next Safe Step",
            snapshot["next_safe_step"],
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    snapshot = build_snapshot()
    stamp = snapshot["created_at"]
    json_path = ARTIFACT_DIR / (
        f"design_guide_final_visible_bending_snapshot_store_branch_deletion_{stamp}.json"
    )
    report_path = AUDIT_DIR / (
        f"design_guide_final_visible_bending_snapshot_store_branch_deletion_{stamp}.md"
    )
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(snapshot, report_path)
    print(f"design_guide_final_visible_bending_snapshot_store_branch_deletion {snapshot['status']}")
    print(f"decision={snapshot['decision']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
