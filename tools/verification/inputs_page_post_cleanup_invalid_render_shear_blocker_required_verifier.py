from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def main() -> int:
    import inputs_page

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / (
        f"inputs_page_post_cleanup_invalid_render_shear_blocker_required_{timestamp}.json"
    )
    report_path = AUDIT_DIR / (
        f"inputs_page_post_cleanup_invalid_render_shear_blocker_required_{timestamp}.md"
    )
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    cases = {
        "required": inputs_page.render_design_guide_post_cleanup_invalid_render_shear_blocker_required(
            blocked_render_item=None,
            post_cleanup_render_audit={
                "post_click_exact_blockers_by_family": {"shear": {"reason": "exact"}}
            },
            post_cleanup_low_families=["shear"],
        ),
        "blocked_item_exists": inputs_page.render_design_guide_post_cleanup_invalid_render_shear_blocker_required(
            blocked_render_item={"family": "shear"},
            post_cleanup_render_audit={
                "post_click_exact_blockers_by_family": {"shear": {"reason": "exact"}}
            },
            post_cleanup_low_families=["shear"],
        ),
        "no_shear_low_family": inputs_page.render_design_guide_post_cleanup_invalid_render_shear_blocker_required(
            blocked_render_item=None,
            post_cleanup_render_audit={
                "post_click_exact_blockers_by_family": {"shear": {"reason": "exact"}}
            },
            post_cleanup_low_families=["bending"],
        ),
        "no_shear_exact": inputs_page.render_design_guide_post_cleanup_invalid_render_shear_blocker_required(
            blocked_render_item=None,
            post_cleanup_render_audit={
                "post_click_exact_blockers_by_family": {"bending": {"reason": "exact"}}
            },
            post_cleanup_low_families=["shear"],
        ),
    }
    failures = [
        f"{name}: expected {expected}, got {cases[name]}"
        for name, expected in {
            "required": True,
            "blocked_item_exists": False,
            "no_shear_low_family": False,
            "no_shear_exact": False,
        }.items()
        if cases[name] is not expected
    ]

    payload = {
        "verdict": "PASS" if not failures else "FAIL",
        "cases": cases,
        "failures": failures,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Post Cleanup Invalid Render Shear Blocker Required Verifier",
                "",
                f"Verdict: `{payload['verdict']}`",
                "",
                f"JSON: `{json_path}`",
                "",
                "## Failures",
                "",
                *(f"- {failure}" for failure in failures),
            ]
        ),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "verdict": payload["verdict"],
                "json": str(json_path),
                "report": str(report_path),
                "failures": failures,
            },
            indent=2,
        )
    )
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
