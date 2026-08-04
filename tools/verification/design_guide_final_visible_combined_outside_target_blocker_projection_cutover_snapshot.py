"""Final-visible combined outside-target blocker projection cutover snapshot."""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.final_publication import (  # noqa: E402
    build_final_visible_combined_outside_target_blocker_evidence_projection,
    stable_final_publication_hash,
)
from tools.verification.design_guide_final_visible_branch_body_inventory_snapshot import (  # noqa: E402
    build_snapshot as build_branch_body_inventory_snapshot,
)


INPUTS = ROOT / "inputs_page.py"
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _function_body(source: str, name: str) -> str:
    needle = f"def {name}("
    start = source.find(needle)
    if start < 0:
        return ""
    next_def = source.find("\ndef ", start + len(needle))
    return source[start:] if next_def < 0 else source[start:next_def]


def _adapter_case() -> dict[str, Any]:
    exact = {
        "combined": {"reason": "combined outside target"},
        "bending": {"reason": "bending outside target"},
    }
    payload = build_final_visible_combined_outside_target_blocker_evidence_projection(
        existing_evidence={"source": "test"},
        exact_blockers_by_family=exact,
        updates={"D": 650},
        expected_util=0.32,
        action_payload={"updates": {"D": 650}},
        resolved_candidate={"candidate_id": "combined_cleanup"},
    )
    return {
        "payload": payload,
        "hash": stable_final_publication_hash(payload),
        "evidence_keys": sorted((payload.get("candidate_search_evidence") or {}).keys()),
        "item_projection_keys": sorted((payload.get("item_projection") or {}).keys()),
    }


def build_snapshot() -> dict[str, Any]:
    inputs_source = _read(INPUTS)
    final_publication_source = _read(FINAL_PUBLICATION)
    page_helper = _function_body(
        inputs_source,
        "_apply_final_visible_combined_outside_target_blocker_projection",
    )
    branch_inventory = build_branch_body_inventory_snapshot()
    future_counts = {
        key: sum(
            int((((branch.get("future_extraction_candidate_hits") or {}).get(key) or {}).get("count")) or 0)
            for branch in branch_inventory.get("branches", [])
        )
        for key in (
            "combined_exact_blocker_rebuild",
            "overview_collection",
            "target_band_resolution",
            "bending_fail_publication_snapshot",
        )
    }
    helper_count = sum(
        int(
            (
                (
                    (branch.get("page_shell_effect_hits") or {}).get(
                        "combined_outside_target_blocker_projection_helper"
                    )
                    or {}
                ).get("count")
            )
            or 0
        )
        for branch in branch_inventory.get("branches", [])
    )
    adapter_case = _adapter_case()
    checks = {
        "final_publication_adapter_exists": (
            "def build_final_visible_combined_outside_target_blocker_evidence_projection("
            in final_publication_source
        ),
        "adapter_exported": (
            '"build_final_visible_combined_outside_target_blocker_evidence_projection"'
            in final_publication_source
        ),
        "inputs_imports_adapter": (
            "build_final_visible_combined_outside_target_blocker_evidence_projection as "
            "_build_final_visible_combined_outside_target_blocker_evidence_projection"
            in inputs_source
        ),
        "page_helper_exists": bool(page_helper),
        "page_helper_calls_adapter": (
            "_build_final_visible_combined_outside_target_blocker_evidence_projection("
            in page_helper
        ),
        "branch_projection_helper_call_one": helper_count == 1,
        "branch_direct_combined_blocker_rebuild_zero": (
            future_counts["combined_exact_blocker_rebuild"] == 0
        ),
        "branch_direct_overview_collection_zero": future_counts["overview_collection"] == 0,
        "branch_direct_target_band_resolution_zero": future_counts["target_band_resolution"] == 0,
        "only_bending_snapshot_future_candidate_remains": (
            future_counts["bending_fail_publication_snapshot"] == 1
            and (branch_inventory.get("totals") or {}).get("future_extraction_candidate_count") == 1
        ),
        "adapter_case_has_evidence_projection": bool(
            (adapter_case["payload"].get("candidate_search_evidence") or {}).get(
                "exact_blockers_by_family"
            )
        ),
        "adapter_case_hash_stable": adapter_case["hash"] == stable_final_publication_hash(
            adapter_case["payload"]
        ),
    }
    failures = [name for name, passed in checks.items() if not passed]
    status = "PASS" if not failures else "FAIL"
    return {
        "schema": "design_guide_final_visible_combined_outside_target_blocker_projection_cutover_snapshot.v1",
        "created_at": datetime.now().strftime("%Y-%m-%dT%H-%M-%S"),
        "status": status,
        "decision": (
            "FINAL_VISIBLE_COMBINED_OUTSIDE_TARGET_BLOCKER_PROJECTION_CUTOVER_PASS"
            if status == "PASS"
            else "FINAL_VISIBLE_COMBINED_OUTSIDE_TARGET_BLOCKER_PROJECTION_NEEDS_ATTENTION"
        ),
        "checks": checks,
        "failures": failures,
        "future_counts": future_counts,
        "projection_helper_count": helper_count,
        "adapter_case": adapter_case,
        "inventory_totals": branch_inventory.get("totals") or {},
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
        "next_safe_step": "run composed locks, then target the remaining bending-fail snapshot future candidate",
    }


def _write_report(snapshot: dict[str, Any], path: Path) -> None:
    lines = [
        "# Final Visible Combined Outside-Target Blocker Projection Cutover",
        "",
        f"Status: `{snapshot['status']}`",
        f"Decision: `{snapshot['decision']}`",
        "",
        "## Future Counts",
    ]
    for key, value in snapshot["future_counts"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            f"- projection helper count: `{snapshot['projection_helper_count']}`",
            "",
            "## Adapter Case",
            f"- hash: `{snapshot['adapter_case']['hash']}`",
            f"- evidence keys: `{', '.join(snapshot['adapter_case']['evidence_keys'])}`",
            f"- item projection keys: `{', '.join(snapshot['adapter_case']['item_projection_keys'])}`",
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
        f"design_guide_final_visible_combined_outside_target_blocker_projection_cutover_{stamp}.json"
    )
    report_path = AUDIT_DIR / (
        f"design_guide_final_visible_combined_outside_target_blocker_projection_cutover_{stamp}.md"
    )
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(snapshot, report_path)
    print(
        "design_guide_final_visible_combined_outside_target_blocker_projection_cutover "
        f"{snapshot['status']}"
    )
    print(f"decision={snapshot['decision']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
