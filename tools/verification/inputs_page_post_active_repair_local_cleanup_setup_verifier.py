from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def main() -> int:
    import inputs_page

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"inputs_page_post_active_repair_local_cleanup_setup_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_post_active_repair_local_cleanup_setup_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals: dict[str, Any] = {
        "_passing_guidance_item": inputs_page._passing_guidance_item,
        "_parse_util_value": inputs_page._parse_util_value,
        "_overview_required_checks_acceptable": inputs_page._overview_required_checks_acceptable,
        "FINAL_ACCEPTED_MIN_FAMILY_UTIL": inputs_page.FINAL_ACCEPTED_MIN_FAMILY_UTIL,
    }
    calls: list[str] = []
    failures: list[str] = []
    cases: list[dict[str, Any]] = []

    def _restore() -> None:
        for name, value in originals.items():
            setattr(inputs_page, name, value)

    def _install(*, required_checks_ok: bool = True) -> None:
        calls.clear()
        inputs_page.FINAL_ACCEPTED_MIN_FAMILY_UTIL = 0.85

        def _passing(state, overview):
            calls.append("passing_guidance_item")
            return {"title": "Passing design", "family": "passing"}

        def _parse(value):
            calls.append(f"parse:{value}")
            if value is None:
                return None
            return float(value)

        inputs_page._passing_guidance_item = _passing
        inputs_page._parse_util_value = _parse
        inputs_page._overview_required_checks_acceptable = lambda overview: bool(required_checks_ok)

    def _run_case(
        name: str,
        *,
        guidance_debug: dict | None = None,
        guidance_items: list[dict] | None = None,
        last_apply_route: dict | None = None,
        overview: dict | None = None,
        required_checks_ok: bool = True,
    ) -> tuple[dict, bool, list, object, bool, bool]:
        try:
            _install(required_checks_ok=required_checks_ok)
            result = inputs_page.render_design_guide_post_active_repair_local_cleanup_setup(
                guidance_debug=dict(guidance_debug or {}),
                guidance_items=[dict(item) for item in list(guidance_items or [])],
                guidance_disp_state={"D": 400},
                dg_overview=dict(overview or {}),
                last_apply_route=dict(last_apply_route or {}),
            )
        finally:
            case_calls = list(calls)
            _restore()
        cases.append({"name": name, "calls": case_calls, "result": result})
        return result

    active_repair = _run_case(
        "post_active_repair_skips_adapter",
        guidance_items=[{"title": "Existing card"}],
        last_apply_route={
            "post_apply_resolved_candidate_attempted": True,
            "resolved_candidate_family_tag": "bending",
            "resolved_candidate_label": "Increase bending capacity",
        },
        overview={"utils": {"shear": 1.1}, "any_fail": True},
    )
    if active_repair[1] is not True:
        failures.append(f"active_repair_flag_mismatch:{active_repair}")
    if active_repair[5] is not True:
        failures.append(f"active_repair_skip_mismatch:{active_repair}")
    if active_repair[0].get("post_active_failure_repair_render") is not True:
        failures.append(f"active_repair_debug_flag_missing:{active_repair[0]}")

    cleanup_label = _run_case(
        "cleanup_label_does_not_count_as_active_repair",
        guidance_items=[{"title": "Existing card"}],
        last_apply_route={
            "post_apply_resolved_candidate_attempted": True,
            "resolved_candidate_family_tag": "bending",
            "resolved_candidate_label": "Cleanup overdesign reinforcement",
        },
        overview={"utils": {"shear": 1.1}, "any_fail": True},
    )
    if cleanup_label[1] is not False or cleanup_label[5] is not False:
        failures.append(f"cleanup_label_not_suppressed:{cleanup_label}")

    fallback_seed = _run_case(
        "empty_guidance_items_uses_passing_fallback_seed",
        guidance_items=[],
        last_apply_route={},
        overview={"utils": {"shear": 1.1}, "any_fail": False},
    )
    if fallback_seed[2] != [{"title": "Passing design", "family": "passing"}]:
        failures.append(f"fallback_seed_mismatch:{fallback_seed[2]}")
    if "passing_guidance_item" not in cases[-1]["calls"]:
        failures.append(f"fallback_seed_not_called:{cases[-1]['calls']}")

    shear_contract = _run_case(
        "shear_overdesign_contract_cleanup_skips_adapter",
        guidance_debug={},
        guidance_items=[{"title": "Existing card"}],
        last_apply_route={},
        overview={"utils": {"shear": 0.2}, "any_fail": False},
        required_checks_ok=True,
    )
    if shear_contract[3] != 0.2:
        failures.append(f"shear_util_mismatch:{shear_contract[3]}")
    if shear_contract[4] is not True or shear_contract[5] is not True:
        failures.append(f"shear_contract_skip_mismatch:{shear_contract}")
    if shear_contract[0].get("legacy_local_cleanup_adapter_skipped_for_contract_runtime") is not True:
        failures.append(f"shear_contract_debug_flag_missing:{shear_contract[0]}")
    if (
        shear_contract[0].get("legacy_local_cleanup_adapter_skip_reason")
        != "SHEAR_OVERDESIGN_GOVERNS contract runtime owns shear cleanup candidate selection"
    ):
        failures.append(f"shear_contract_reason_mismatch:{shear_contract[0]}")

    fast_path = _run_case(
        "target_band_active_shear_fast_path_skips_adapter",
        guidance_debug={"guidance_branch": "target_band_active_shear_local_cleanup_fast_path"},
        guidance_items=[{"title": "Existing card"}],
        last_apply_route={},
        overview={"utils": {"shear": 1.1}, "any_fail": True},
    )
    if fast_path[5] is not True:
        failures.append(f"fast_path_skip_mismatch:{fast_path}")
    if fast_path[4] is not False:
        failures.append(f"fast_path_shear_contract_unexpected:{fast_path}")

    payload = {
        "verifier": "inputs_page_post_active_repair_local_cleanup_setup_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "case_count": len(cases),
        "cases": [
            {"name": case["name"], "calls": case["calls"]}
            for case in cases
        ],
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Post Active Repair Local Cleanup Setup Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                "## Cases",
                "",
                *(f"- `{case['name']}` calls={case['calls']}" for case in cases),
                "",
                "## Failures",
                "",
                *(f"- `{failure}`" for failure in failures),
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(payload["status"])
    print(f"json={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ";".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
