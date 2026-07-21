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
        f"inputs_page_post_cleanup_invalid_render_shear_exact_blocker_reset_{timestamp}.json"
    )
    report_path = AUDIT_DIR / (
        f"inputs_page_post_cleanup_invalid_render_shear_exact_blocker_reset_{timestamp}.md"
    )
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    original_resolver = inputs_page._resolve_recommendation_updates
    calls: list[dict] = []
    failures: list[str] = []

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    def resolve_updates(item, *, state):
        calls.append({"item": dict(item or {}), "state": dict(state or {})})
        return dict((item or {}).get("updates") or {})

    try:
        inputs_page._resolve_recommendation_updates = resolve_updates
        reset_result = inputs_page.render_design_guide_post_cleanup_invalid_render_shear_exact_blocker_reset(
            blocked_render_item={"family": "bending", "title": "Bending blocker"},
            guidance_disp_state={"b": 300},
            post_cleanup_render_audit={
                "post_click_exact_blockers_by_family": {"shear": {"reason": "exact"}}
            },
            post_cleanup_low_families=["shear"],
        )
        keep_shear_result = inputs_page.render_design_guide_post_cleanup_invalid_render_shear_exact_blocker_reset(
            blocked_render_item={"family": "shear", "title": "Shear blocker"},
            guidance_disp_state={"b": 300},
            post_cleanup_render_audit={
                "post_click_exact_blockers_by_family": {"shear": {"reason": "exact"}}
            },
            post_cleanup_low_families=["shear"],
        )
        keep_updates_result = inputs_page.render_design_guide_post_cleanup_invalid_render_shear_exact_blocker_reset(
            blocked_render_item={
                "family": "bending",
                "title": "Bending action",
                "updates": {"b": 250},
            },
            guidance_disp_state={"b": 300},
            post_cleanup_render_audit={
                "post_click_exact_blockers_by_family": {"shear": {"reason": "exact"}}
            },
            post_cleanup_low_families=["shear"],
        )
    finally:
        inputs_page._resolve_recommendation_updates = original_resolver

    expect("reset_case", reset_result is None, f"reset_result={reset_result}")
    expect(
        "keep_shear_case",
        keep_shear_result == {"family": "shear", "title": "Shear blocker"},
        f"keep_shear_result={keep_shear_result}",
    )
    expect(
        "keep_updates_case",
        keep_updates_result
        == {"family": "bending", "title": "Bending action", "updates": {"b": 250}},
        f"keep_updates_result={keep_updates_result}",
    )
    expect(
        "resolver_called_for_dict_cases",
        len(calls) == 3
        and calls[0]["item"]["family"] == "bending"
        and calls[1]["item"]["family"] == "shear"
        and calls[2]["item"]["updates"] == {"b": 250},
        f"calls={calls}",
    )

    payload = {
        "verdict": "PASS" if not failures else "FAIL",
        "calls": calls,
        "reset_result": reset_result,
        "keep_shear_result": keep_shear_result,
        "keep_updates_result": keep_updates_result,
        "failures": failures,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Post Cleanup Invalid Render Shear Exact Blocker Reset Verifier",
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
