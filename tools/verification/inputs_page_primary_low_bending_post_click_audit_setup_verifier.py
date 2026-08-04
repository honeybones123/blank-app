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
    json_path = ARTIFACT_DIR / f"inputs_page_primary_low_bending_post_click_audit_setup_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_primary_low_bending_post_click_audit_setup_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    calls: list[dict] = []

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    original_family = inputs_page._design_guide_candidate_family

    def family(item):
        calls.append({"event": "family", "item": dict(item or {})})
        return str((item or {}).get("family") or "")

    try:
        inputs_page._design_guide_candidate_family = family
        overview, audit = inputs_page.render_design_guide_primary_low_bending_post_click_audit_setup(
            guidance_debug={
                "overview": {"utils": {"bending": 0.72, "shear": 0.8, "serviceability": 0.4}},
                "post_click_exact_blockers_by_family": {"serviceability": {"reason": "keep"}},
            },
            dg_overview={"utils": {"bending": 0.95}},
            post_cleanup_render_audit={"existing": "audit"},
            primary_last_apply_route={"route": "last"},
            primary_post_click_item={
                "family": "bending",
                "exact_blockers_by_family": {"shear": {"reason": "item exact"}},
            },
        )
        preserved_overview, preserved_audit = (
            inputs_page.render_design_guide_primary_low_bending_post_click_audit_setup(
                guidance_debug={},
                dg_overview={"utils": {}},
                post_cleanup_render_audit={
                    "post_click_exact_blockers_by_family": {"bending": {"reason": "preexisting"}}
                },
                primary_last_apply_route={"route": "empty"},
                primary_post_click_item={
                    "family": "bending",
                    "exact_blockers_by_family": {"shear": {"reason": "ignored without utils"}},
                },
            )
        )
    finally:
        inputs_page._design_guide_candidate_family = original_family

    expect(
        "overview_and_route",
        overview == {"utils": {"bending": 0.72, "shear": 0.8, "serviceability": 0.4}}
        and audit.get("existing") == "audit"
        and audit.get("last_apply_route") == {"route": "last"},
        f"overview={overview} audit={audit}",
    )
    expect(
        "below_family_filtering",
        audit.get("post_click_family_utils")
        == {"bending": 0.72, "shear": 0.8, "serviceability": 0.4}
        and audit.get("post_click_families_below_final_threshold") == ["bending"]
        and audit.get("post_click_unresolved_low_util_families") == ["bending"],
        f"audit={audit}",
    )
    expect(
        "exact_precedence",
        audit.get("post_click_exact_blockers_by_family") == {"shear": {"reason": "item exact"}},
        f"audit={audit}",
    )
    expect(
        "empty_utils_path",
        preserved_overview == {"utils": {}}
        and preserved_audit
        == {
            "post_click_exact_blockers_by_family": {"bending": {"reason": "preexisting"}},
            "last_apply_route": {"route": "empty"},
        },
        f"preserved_overview={preserved_overview} preserved_audit={preserved_audit}",
    )
    expect(
        "call_coverage",
        any(call["event"] == "family" for call in calls),
        f"calls={calls}",
    )

    result = {
        "verdict": "PASS" if not failures else "FAIL",
        "json": str(json_path),
        "report": str(report_path),
        "failures": failures,
        "overview": overview,
        "audit": audit,
        "preserved_overview": preserved_overview,
        "preserved_audit": preserved_audit,
        "calls": calls,
    }
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Primary Low Bending Post Click Audit Setup Verifier",
                "",
                f"Verdict: `{result['verdict']}`",
                "",
                f"JSON: `{json_path}`",
                "",
                "## Failures",
                "",
                *(failures or ["None."]),
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
