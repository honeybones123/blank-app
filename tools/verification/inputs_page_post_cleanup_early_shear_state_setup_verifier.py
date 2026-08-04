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
    json_path = ARTIFACT_DIR / f"inputs_page_post_cleanup_early_shear_state_setup_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_post_cleanup_early_shear_state_setup_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    original_snapshot = inputs_page._guidance_state_snapshot
    original_shared = inputs_page._shared_state_snapshot

    failures: list[str] = []
    cases: list[dict] = []
    should_raise = False

    def fake_shared_state_snapshot():
        return {"D": 600, "shared": True}

    def fake_guidance_state_snapshot(state):
        if should_raise:
            raise RuntimeError("snapshot unavailable")
        return {"snapshot": True, **dict(state or {})}

    def run_case(
        name: str,
        *,
        raise_snapshot: bool,
        guidance_debug: dict,
        dg_overview: dict,
        expected_state: dict,
        expected_overview: dict,
    ) -> None:
        nonlocal should_raise
        should_raise = raise_snapshot
        state, overview = inputs_page.render_design_guide_post_cleanup_early_shear_state_setup(
            guidance_debug=guidance_debug,
            dg_overview=dg_overview,
            guidance_disp_state={"D": 500, "fallback": True},
        )
        cases.append({"name": name, "state": state, "overview": overview})
        if state != expected_state:
            failures.append(f"{name}:state:expected={expected_state}:actual={state}")
        if overview != expected_overview:
            failures.append(f"{name}:overview:expected={expected_overview}:actual={overview}")

    try:
        inputs_page._shared_state_snapshot = fake_shared_state_snapshot
        inputs_page._guidance_state_snapshot = fake_guidance_state_snapshot

        run_case(
            "shared_snapshot_success_uses_guidance_debug_overview",
            raise_snapshot=False,
            guidance_debug={"overview": {"any_fail": False, "utils": {"shear": 0.7}}},
            dg_overview={"any_fail": True},
            expected_state={"snapshot": True, "D": 600, "shared": True},
            expected_overview={"any_fail": False, "utils": {"shear": 0.7}},
        )
        run_case(
            "snapshot_exception_falls_back_to_display_state",
            raise_snapshot=True,
            guidance_debug={"overview": {"any_fail": False}},
            dg_overview={"any_fail": True},
            expected_state={"D": 500, "fallback": True},
            expected_overview={"any_fail": False},
        )
        run_case(
            "missing_guidance_debug_overview_uses_dg_overview",
            raise_snapshot=False,
            guidance_debug={},
            dg_overview={"any_fail": False, "utils": {"shear": 0.9}},
            expected_state={"snapshot": True, "D": 600, "shared": True},
            expected_overview={"any_fail": False, "utils": {"shear": 0.9}},
        )
        run_case(
            "missing_overviews_returns_empty_dict",
            raise_snapshot=False,
            guidance_debug={},
            dg_overview={},
            expected_state={"snapshot": True, "D": 600, "shared": True},
            expected_overview={},
        )
    finally:
        inputs_page._guidance_state_snapshot = original_snapshot
        inputs_page._shared_state_snapshot = original_shared

    payload_out = {
        "verifier": "inputs_page_post_cleanup_early_shear_state_setup_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "case_count": len(cases),
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload_out, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Post Cleanup Early Shear State Setup Verifier",
                "",
                f"Status: `{payload_out['status']}`",
                "",
                "## Cases",
                "",
                *(f"- `{case['name']}`" for case in cases),
                "",
                "## Failures",
                "",
                *(f"- `{failure}`" for failure in failures),
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(payload_out["status"])
    print(f"json={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ";".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
