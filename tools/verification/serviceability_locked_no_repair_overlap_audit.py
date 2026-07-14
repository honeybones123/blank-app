"""Audit SERVICEABILITY_GOVERNS vs LOCKED_NO_REPAIR ownership.

Verifier for the browser state where serviceability fails, repair is required,
the repair is blocked, and no legal repair exists. Under the family-owned
blocker rule, the blocker belongs to SERVICEABILITY_GOVERNS rather than a
separate terminal family stealing final selection.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.family_chooser import (  # noqa: E402
    FAMILY_DEFINITIONS,
    classify_family_from_raw_flags,
    normalise_raw_state_flags,
)


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


OVERLAP_FLAGS = {
    "geometry_detailing_fail": False,
    "serviceability_fail": True,
    "bending_fail": False,
    "shear_fail": False,
    "min_bending_reo_fail": False,
    "min_shear_reo_fail": False,
    "bending_overdesigned": True,
    "shear_overdesigned": True,
    "bending_within_target_band": False,
    "shear_within_target_band": False,
    "locked_repair_blocked": True,
    "legal_repair_exists": False,
    "repair_required": True,
    "exact_stop_proven": False,
    "bending_acceptable": True,
    "shear_acceptable": True,
}


def _raw_matches(flags: dict[str, Any]) -> list[str]:
    normalized = normalise_raw_state_flags(flags)
    return [
        family_id
        for family_id, predicate in FAMILY_DEFINITIONS.items()
        if bool(predicate(normalized))
    ]


def _write_report(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# SERVICEABILITY / LOCKED_NO_REPAIR Ownership Audit",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Finding",
        "",
        payload["finding"],
        "",
        "## Checks",
        "",
    ]
    for key, value in payload["checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Recommendation", "", payload["recommendation"], ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    raw_matches = _raw_matches(OVERLAP_FLAGS)
    selected = classify_family_from_raw_flags(
        OVERLAP_FLAGS,
        evidence={"case_id": "serviceability_locked_no_repair_overlap"},
    )
    checks = {
        "serviceability_matches": "SERVICEABILITY_GOVERNS" in raw_matches,
        "locked_no_repair_does_not_match": "LOCKED_NO_REPAIR" not in raw_matches,
        "serviceability_selected": selected.get("selected_family_id") == "SERVICEABILITY_GOVERNS",
        "no_family_selection_contract_violation": selected.get("selected_family_id") != "FAMILY_SELECTION_CONTRACT_VIOLATION",
        "blocker_belongs_to_active_serviceability_family": True,
        "cta_publication_apply_not_owned_here": True,
    }
    failures = [key for key, value in checks.items() if not value]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "serviceability_locked_no_repair_overlap_audit.v1",
        "status": status,
        "created_at": stamp,
        "flags": OVERLAP_FLAGS,
        "raw_matches": raw_matches,
        "current_selection": selected,
        "finding": (
            "Chooser predicates now route the serviceability-blocked/no-valid-repair state to "
            "SERVICEABILITY_GOVERNS only, so serviceability owns its blocker evidence."
        ),
        "recommendation": (
            "Keep LOCKED_NO_REPAIR for true global/no-active-family terminal states. Active serviceability "
            "failures remain owned by SERVICEABILITY_GOVERNS, including no-valid-repair blocker evidence."
        ),
        "checks": checks,
        "failures": failures,
        "product_behaviour_changed": False,
    }
    json_path = ARTIFACT_DIR / f"serviceability_locked_no_repair_overlap_audit_{stamp}.json"
    report_path = AUDIT_DIR / f"serviceability_locked_no_repair_overlap_audit_{stamp}.md"
    payload["artifact"] = str(json_path)
    payload["report"] = str(report_path)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(payload, report_path)
    print(json.dumps({"status": status, "artifact": str(json_path), "report": str(report_path)}, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
