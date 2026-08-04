"""Regression for visible combined bending/shear blocker reason specificity."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs_page_modules.design_guide.current_coordinators import (  # noqa: E402
    _render_exact_blocker_from_item,
)


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _blocked_combined_item() -> dict:
    return {
        "title_main": "Bending and shear repair blocked",
        "guidance_intent": "specific_blocker",
        "selected_family_id": "COMBINED_BENDING_SHEAR_FAIL",
        "candidate_search_evidence": {
            "selected_family_id": "COMBINED_BENDING_SHEAR_FAIL",
            "repair_search_exhaustive": True,
            "exact_blockers_by_family": {
                "bending": {
                    "reason": (
                        "Bending repair is blocked by reinforcement, geometry, "
                        "ductility, or detailing limits."
                    ),
                    "repair_search_exhaustive": True,
                    "safe_candidate_count": 0,
                    "attempted_updates": {"D": 750.0, "b": 600.0, "bot1_count": 8},
                    "failed_check_status": "FAIL",
                    "failed_check_util": 2.74,
                },
                "shear": {
                    "reason": "Shear repair is blocked by shear/detailing limits.",
                    "repair_search_exhaustive": True,
                    "safe_candidate_count": 0,
                    "attempted_updates": {"lig_d": 16.0, "lig_legs": 4, "s_lig": 75.0},
                    "failed_check_status": "FAIL",
                    "failed_check_util": 2.8,
                },
            },
        },
        "button_contract": {
            "enabled": False,
            "actionable": False,
            "preview_pass": False,
            "blocking_reason": "candidate_preview_has_fail_status",
        },
    }


def _write(snapshot: dict) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"combined_bending_shear_fail_visible_blocker_reason_regression_{stamp}.json"
    report_path = AUDIT_DIR / f"combined_bending_shear_fail_visible_blocker_reason_regression_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Combined Bending/Shear Visible Blocker Reason Regression",
                "",
                f"Result: `{snapshot['result']}`",
                "",
                "## Checks",
                "",
                *[f"- `{key}`: `{value}`" for key, value in snapshot["checks"].items()],
                "",
                "## Visible Reason",
                "",
                snapshot["visible_reason"],
                "",
                "## Failures",
                "",
                *([f"- `{failure}`" for failure in snapshot["failures"]] or ["- none"]),
                "",
            ]
        ),
        encoding="utf-8",
    )
    return json_path, report_path


def main() -> int:
    rendered = _render_exact_blocker_from_item(_blocked_combined_item())
    reason = str(rendered.get("reason") or "")
    proof = str(rendered.get("proof_summary") or "")
    reason_l = reason.lower()
    proof_l = proof.lower()
    checks = {
        "combined_family_rendered": rendered.get("family") == "combined",
        "visible_mentions_bending": "bending repair blocked" in reason_l,
        "visible_mentions_shear": "shear repair blocked" in reason_l,
        "visible_has_exhaustive_search_proof": "repair search exhausted" in reason_l,
        "visible_has_zero_safe_candidate_proof": "safe executable candidates: 0" in reason_l,
        "visible_has_attempted_moves_proof": "attempted moves:" in reason_l,
        "proof_summary_keeps_combined_family": "combined family" in proof_l,
    }
    failures = sorted(key for key, passed in checks.items() if not passed)
    snapshot = {
        "schema": "combined_bending_shear_fail_visible_blocker_reason_regression.v1",
        "result": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "visible_reason": reason,
        "proof_summary": proof,
        "rendered": rendered,
    }
    json_path, report_path = _write(snapshot)
    if failures:
        print("combined bending/shear visible blocker reason regression FAIL")
        print(f"JSON: {json_path}")
        print(f"Report: {report_path}")
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        return 1
    print("combined bending/shear visible blocker reason regression PASS")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
