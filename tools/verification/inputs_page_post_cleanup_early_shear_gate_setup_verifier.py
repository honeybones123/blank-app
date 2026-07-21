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
    json_path = ARTIFACT_DIR / f"inputs_page_post_cleanup_early_shear_gate_setup_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_post_cleanup_early_shear_gate_setup_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    patched_names = [
        "_resolved_efficiency_target_band",
        "_design_mode_config",
        "_design_optimisation_goal",
        "_float_from_state",
        "_overview_active_failure_keys",
    ]
    originals = {name: getattr(inputs_page, name) for name in patched_names}

    failures: list[str] = []
    cases: list[dict] = []
    target_band_raises = False
    active_failures: set[str] = set()

    def fake_goal(state):
        return "balanced"

    def fake_mode_config(goal):
        return {"goal": goal}

    def fake_target_band(mode_config, *, goal):
        if target_band_raises:
            raise RuntimeError("target band unavailable")
        return 0.75, 0.95, "fake"

    def fake_float_from_state(state, key, default):
        return dict(state or {}).get(key, default)

    def fake_active_failure_keys(overview):
        return set(active_failures)

    def run_case(
        name: str,
        *,
        overview: dict,
        state: dict,
        target_raises: bool,
        failure_keys: set[str],
        expected_allowed: bool,
        expected_target_low: float,
        expected_target_high: float,
        expected_vu: float,
    ) -> None:
        nonlocal target_band_raises, active_failures
        target_band_raises = target_raises
        active_failures = set(failure_keys)
        (
            utils,
            util,
            target_low,
            target_high,
            vu,
            failures_found,
            allowed,
        ) = inputs_page.render_design_guide_post_cleanup_early_shear_gate_setup(
            early_shear_cleanup_state=state,
            early_shear_cleanup_overview=overview,
        )
        cases.append(
            {
                "name": name,
                "util": util,
                "target_low": target_low,
                "target_high": target_high,
                "vu": vu,
                "failures_found": sorted(failures_found),
                "allowed": allowed,
            }
        )
        if utils != dict(overview.get("utils") or {}):
            failures.append(f"{name}:utils_mismatch:{utils}")
        if allowed is not expected_allowed:
            failures.append(f"{name}:allowed:expected={expected_allowed}:actual={allowed}")
        if target_low != expected_target_low or target_high != expected_target_high:
            failures.append(
                f"{name}:target_band:expected={(expected_target_low, expected_target_high)}:actual={(target_low, target_high)}"
            )
        if vu != expected_vu:
            failures.append(f"{name}:vu:expected={expected_vu}:actual={vu}")
        expected_failures_found = set(failure_keys) & {"bending", "shear"}
        if failures_found != expected_failures_found:
            failures.append(
                f"{name}:failure_keys:expected={expected_failures_found}:actual={failures_found}"
            )

    try:
        inputs_page._resolved_efficiency_target_band = fake_target_band
        inputs_page._design_mode_config = fake_mode_config
        inputs_page._design_optimisation_goal = fake_goal
        inputs_page._float_from_state = fake_float_from_state
        inputs_page._overview_active_failure_keys = fake_active_failure_keys

        run_case(
            "allowed_low_shear_with_demand_and_no_failures",
            overview={"utils": {"shear": "0.70"}},
            state={"uls_Vstar": 120.0, "load_Vstar_proxy": 0.0},
            target_raises=False,
            failure_keys=set(),
            expected_allowed=True,
            expected_target_low=0.75,
            expected_target_high=0.95,
            expected_vu=120.0,
        )
        run_case(
            "missing_shear_util_blocks",
            overview={"utils": {}},
            state={"uls_Vstar": 120.0, "load_Vstar_proxy": 0.0},
            target_raises=False,
            failure_keys=set(),
            expected_allowed=False,
            expected_target_low=0.75,
            expected_target_high=0.95,
            expected_vu=120.0,
        )
        run_case(
            "zero_shear_demand_blocks",
            overview={"utils": {"shear": "0.70"}},
            state={"uls_Vstar": 0.0, "load_Vstar_proxy": 0.0},
            target_raises=False,
            failure_keys=set(),
            expected_allowed=False,
            expected_target_low=0.75,
            expected_target_high=0.95,
            expected_vu=0.0,
        )
        run_case(
            "active_shear_failure_blocks",
            overview={"utils": {"shear": "0.70"}},
            state={"uls_Vstar": 120.0, "load_Vstar_proxy": 0.0},
            target_raises=False,
            failure_keys={"shear", "spacing"},
            expected_allowed=False,
            expected_target_low=0.75,
            expected_target_high=0.95,
            expected_vu=120.0,
        )
        run_case(
            "target_band_exception_uses_default_band",
            overview={"utils": {"shear": "0.70"}},
            state={"uls_Vstar": 0.0, "load_Vstar_proxy": -80.0},
            target_raises=True,
            failure_keys=set(),
            expected_allowed=True,
            expected_target_low=float(inputs_page.EFFICIENCY_TARGET_UTIL_MIN),
            expected_target_high=float(inputs_page.GUIDANCE_TARGET_UTIL_MAX),
            expected_vu=80.0,
        )
    finally:
        for name, value in originals.items():
            setattr(inputs_page, name, value)

    payload_out = {
        "verifier": "inputs_page_post_cleanup_early_shear_gate_setup_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "case_count": len(cases),
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload_out, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Post Cleanup Early Shear Gate Setup Verifier",
                "",
                f"Status: `{payload_out['status']}`",
                "",
                "## Cases",
                "",
                *(f"- `{case['name']}`: `{case['allowed']}`" for case in cases),
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
