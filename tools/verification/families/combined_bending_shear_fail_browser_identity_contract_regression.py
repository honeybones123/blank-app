"""Regression for combined active-fail browser publication identity.

This locks the screenshot failure where the visible card says combined bending
and shear, but the browser publication/CTA probe is stamped as shear or blank.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification.run_family_10_fuzz_audit import _browser_family_identity_contract


FAMILY = "COMBINED_BENDING_SHEAR_FAIL"
FINAL_CARD = {
    "text_sample": (
        "Design Guide\nBLOCKED\nBending and shear repair blocked\n"
        "No validated one-click update is available for this state."
    )
}


def _contract(publication_probe: dict) -> dict:
    return _browser_family_identity_contract(
        family=FAMILY,
        publication_probe=publication_probe,
        final_card_probe=FINAL_CARD,
        visual_snapshot={"checks": {"visible_design_guide_cards": {"titles": ["Bending and shear repair blocked"]}}},
    )


def main() -> int:
    good = _contract(
        {
            "selected_family_id": "COMBINED_BENDING_SHEAR_FAIL",
            "cta": {"family_id": "COMBINED_BENDING_SHEAR_FAIL"},
        }
    )
    wrong_family = _contract(
        {
            "selected_family_id": "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS",
            "cta": {"family_id": "SHEAR"},
        }
    )
    missing_publication = _contract({"selected_family_id": None, "cta": {}})
    checks = {
        "good_combined_identity_passes": bool(good.get("passes_contract")),
        "shear_stamped_publication_fails": not bool(wrong_family.get("passes_contract")),
        "blank_publication_identity_fails": not bool(missing_publication.get("passes_contract")),
        "wrong_family_records_mismatches": bool(wrong_family.get("mismatched_roles")),
        "blank_publication_records_missing_roles": bool(missing_publication.get("missing_roles")),
    }
    payload = {
        "schema": "combined_bending_shear_fail_browser_identity_contract_regression.v1",
        "passed": all(checks.values()),
        "checks": checks,
        "good": good,
        "wrong_family": wrong_family,
        "missing_publication": missing_publication,
    }
    out_dir = ROOT / "artifacts" / "verification"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "combined_bending_shear_fail_browser_identity_contract_regression.json"
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    if not payload["passed"]:
        print(json.dumps(payload, indent=2, sort_keys=True), file=sys.stderr)
        return 1
    print("combined_bending_shear_fail_browser_identity_contract_regression PASS")
    print(f"JSON: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
