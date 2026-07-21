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


def _run_blocker_case(
    *,
    name: str,
    state: dict | None,
    overview: dict | None,
    variants: list[dict],
    candidate_by_updates: dict[tuple[tuple[str, str], ...], dict | None],
    threshold: float,
) -> dict[str, Any]:
    import inputs_page as legacy_inputs_page
    import inputs_page_app_contract_bridge as bridge

    original_legacy_variants = legacy_inputs_page.generate_less_shear_reo_variants
    original_legacy_evaluate = legacy_inputs_page._evaluate_auto_design_candidate
    original_bridge_variants = bridge._generate_less_shear_reo_variants_for_app_bridge
    original_bridge_evaluate = bridge._evaluate_auto_design_candidate_for_app_bridge
    legacy_calls: list[dict[str, Any]] = []
    bridge_calls: list[dict[str, Any]] = []

    def _key(updates: dict) -> tuple[tuple[str, str], ...]:
        return tuple((str(k), str(updates[k])) for k in sorted(dict(updates or {})))

    def legacy_variants(current_candidate: dict, mode_config: dict) -> list[dict]:
        legacy_calls.append({"fn": "variants", "current_candidate": current_candidate})
        return list(variants)

    def bridge_variants(current_candidate: dict, mode_config: dict) -> list[dict]:
        bridge_calls.append({"fn": "variants", "current_candidate": current_candidate})
        return list(variants)

    def legacy_evaluate(
        eval_state: dict,
        *,
        updates: dict,
        source: str,
        label: str,
        action_type: str,
    ) -> dict | None:
        legacy_calls.append(
            {
                "fn": "evaluate",
                "updates": dict(updates),
                "source": source,
                "label": label,
                "action_type": action_type,
            }
        )
        candidate = candidate_by_updates.get(_key(updates))
        return None if candidate is None else dict(candidate)

    def bridge_evaluate(
        eval_state: dict,
        *,
        updates: dict,
        source: str,
        label: str,
        action_type: str,
    ) -> dict | None:
        bridge_calls.append(
            {
                "fn": "evaluate",
                "updates": dict(updates),
                "source": source,
                "label": label,
                "action_type": action_type,
            }
        )
        candidate = candidate_by_updates.get(_key(updates))
        return None if candidate is None else dict(candidate)

    try:
        legacy_inputs_page.generate_less_shear_reo_variants = legacy_variants
        legacy_inputs_page._evaluate_auto_design_candidate = legacy_evaluate
        bridge._generate_less_shear_reo_variants_for_app_bridge = bridge_variants
        bridge._evaluate_auto_design_candidate_for_app_bridge = bridge_evaluate
        legacy_value = legacy_inputs_page._shear_low_util_active_links_exact_blocker(
            None if state is None else dict(state),
            None if overview is None else dict(overview),
            threshold=threshold,
        )
        bridge_value = bridge._shear_low_util_active_links_exact_blocker(
            None if state is None else dict(state),
            None if overview is None else dict(overview),
            threshold=threshold,
        )
    finally:
        legacy_inputs_page.generate_less_shear_reo_variants = original_legacy_variants
        legacy_inputs_page._evaluate_auto_design_candidate = original_legacy_evaluate
        bridge._generate_less_shear_reo_variants_for_app_bridge = original_bridge_variants
        bridge._evaluate_auto_design_candidate_for_app_bridge = original_bridge_evaluate

    return {
        "case": name,
        "legacy_value": legacy_value,
        "bridge_value": bridge_value,
        "legacy_calls": legacy_calls,
        "bridge_calls": bridge_calls,
        "match": legacy_value == bridge_value and legacy_calls == bridge_calls,
    }


def _variant_identity_rows(states: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "lig_d": item.get("lig_d"),
            "lig_legs": item.get("lig_legs"),
            "s_lig": item.get("s_lig"),
            "D": item.get("D"),
            "b": item.get("b"),
            "bw": item.get("bw"),
        }
        for item in states
    ]


def _run_variant_case(
    *,
    name: str,
    state: dict[str, Any],
    shear_cleanup_possible: bool,
    shear_state_eligible_for_no_links: bool,
) -> dict[str, Any]:
    import inputs_page as legacy_inputs_page
    import inputs_page_app_contract_bridge as bridge

    original_legacy_possible = legacy_inputs_page._shear_cleanup_possible
    original_legacy_no_links = legacy_inputs_page._shear_state_eligible_for_no_links
    original_bridge_possible = bridge._shear_cleanup_possible
    original_bridge_no_links = bridge._shear_state_eligible_for_no_links
    try:
        legacy_inputs_page._shear_cleanup_possible = lambda _state: bool(shear_cleanup_possible)
        legacy_inputs_page._shear_state_eligible_for_no_links = (
            lambda _state: bool(shear_state_eligible_for_no_links)
        )
        bridge._shear_cleanup_possible = lambda _state: bool(shear_cleanup_possible)
        bridge._shear_state_eligible_for_no_links = lambda _state: bool(shear_state_eligible_for_no_links)
        legacy_rows = _variant_identity_rows(
            list(legacy_inputs_page.generate_less_shear_reo_variants({"state": dict(state)}, {}) or [])
        )
        bridge_rows = _variant_identity_rows(
            list(bridge._generate_less_shear_reo_variants_for_app_bridge({"state": dict(state)}, {}) or [])
        )
    finally:
        legacy_inputs_page._shear_cleanup_possible = original_legacy_possible
        legacy_inputs_page._shear_state_eligible_for_no_links = original_legacy_no_links
        bridge._shear_cleanup_possible = original_bridge_possible
        bridge._shear_state_eligible_for_no_links = original_bridge_no_links
    return {
        "case": name,
        "legacy_rows": legacy_rows,
        "bridge_rows": bridge_rows,
        "legacy_count": len(legacy_rows),
        "bridge_count": len(bridge_rows),
        "match": legacy_rows == bridge_rows,
    }


def main() -> int:
    import inputs_page as legacy_inputs_page
    import inputs_page_app_contract_bridge as bridge

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    original_compute = legacy_inputs_page._compute_design_guidance_items
    compute_calls: list[dict[str, Any]] = []
    guidance_state = {"b": 300, "D": 600, "uls_Vstar": 0}
    sentinel_payload = {"guidance_items": [{"title_main": "stub"}], "debug_trace": {"source": "legacy"}}

    def fake_compute_design_guidance_items(
        state: dict,
        *,
        guidance_debug_verbose: bool | None = None,
        debug_enabled: bool = False,
        request_kind: str = "design_guide",
    ) -> dict:
        compute_calls.append(
            {
                "state": state,
                "guidance_debug_verbose": guidance_debug_verbose,
                "debug_enabled": debug_enabled,
                "request_kind": request_kind,
            }
        )
        return sentinel_payload

    try:
        legacy_inputs_page._compute_design_guidance_items = fake_compute_design_guidance_items
        guidance_payload = bridge._compute_design_guidance_items(
            guidance_state,
            guidance_debug_verbose=True,
            debug_enabled=True,
            request_kind="browser_probe",
        )
    finally:
        legacy_inputs_page._compute_design_guidance_items = original_compute

    blocker_state = {
        "design_optimisation_goal": "balanced",
        "lig_d": 10,
        "lig_legs": 2,
        "s_lig": 200,
    }
    blocker_overview = {"utils": {"shear": 0.41}, "Vu_star": 120}
    variant = {**blocker_state, "s_lig": 250}
    update_key = (("s_lig", "250"),)
    blocker_rows = [
        _run_blocker_case(
            name="inactive_links_returns_none",
            state={**blocker_state, "lig_legs": 0},
            overview=blocker_overview,
            variants=[variant],
            candidate_by_updates={},
            threshold=0.7,
        ),
        _run_blocker_case(
            name="already_above_threshold_returns_none",
            state=blocker_state,
            overview={"utils": {"shear": 0.72}},
            variants=[variant],
            candidate_by_updates={},
            threshold=0.7,
        ),
        _run_blocker_case(
            name="safe_candidate_reaches_threshold_returns_none",
            state=blocker_state,
            overview=blocker_overview,
            variants=[variant],
            candidate_by_updates={
                update_key: {
                    "overview": {
                        "all_key_pass": True,
                        "any_fail": False,
                        "utils": {"shear": 0.72},
                        "packs": {"shear": {"summary_util": 0.72}},
                    }
                }
            },
            threshold=0.7,
        ),
        _run_blocker_case(
            name="safe_candidate_still_below_threshold_blocks",
            state=blocker_state,
            overview=blocker_overview,
            variants=[variant],
            candidate_by_updates={
                update_key: {
                    "overview": {
                        "all_key_pass": True,
                        "any_fail": False,
                        "utils": {"shear": 0.55},
                        "packs": {
                            "shear": {
                                "summary_util": 0.55,
                                "summary_governing_demand_kN": 120,
                                "summary_governing_capacity_kN": 220,
                            }
                        },
                    }
                }
            },
            threshold=0.7,
        ),
        _run_blocker_case(
            name="failed_candidate_blocks",
            state=blocker_state,
            overview=blocker_overview,
            variants=[variant],
            candidate_by_updates={
                update_key: {
                    "overview": {
                        "all_key_pass": False,
                        "any_fail": True,
                        "utils": {"shear": 1.12},
                        "statuses": {"shear": "FAIL"},
                        "packs": {
                            "shear": {
                                "summary_util": 1.12,
                                "summary_governing_demand_kN": 120,
                                "summary_governing_capacity_kN": 107,
                                "summary_governing_check_name": "shear strength",
                            }
                        },
                    }
                }
            },
            threshold=0.7,
        ),
    ]
    variant_rows = [
        _run_variant_case(
            name="cleanup_not_possible",
            state={"lig_d": 0, "lig_legs": 0, "s_lig": 300.0, "D": 650.0, "b": 400.0},
            shear_cleanup_possible=False,
            shear_state_eligible_for_no_links=False,
        ),
        _run_variant_case(
            name="active_links_no_link_eligible",
            state={"lig_d": 10, "lig_legs": 2, "s_lig": 200.0, "D": 650.0, "b": 400.0},
            shear_cleanup_possible=True,
            shear_state_eligible_for_no_links=True,
        ),
        _run_variant_case(
            name="active_links_no_link_not_eligible",
            state={"lig_d": 12, "lig_legs": 3, "s_lig": 225.0, "D": 650.0, "b": 400.0},
            shear_cleanup_possible=True,
            shear_state_eligible_for_no_links=False,
        ),
        _run_variant_case(
            name="larger_current_links",
            state={"lig_d": 16, "lig_legs": 4, "s_lig": 175.0, "D": 650.0, "b": 400.0},
            shear_cleanup_possible=True,
            shear_state_eligible_for_no_links=True,
        ),
    ]
    bridge_source = (ROOT / "inputs_page_app_contract_bridge.py").read_text(
        encoding="utf-8",
        errors="replace",
    )

    checks = {
        "compute_delegates_exact_value": guidance_payload is sentinel_payload,
        "compute_forwards_state_and_keywords": compute_calls
        == [
            {
                "state": guidance_state,
                "guidance_debug_verbose": True,
                "debug_enabled": True,
                "request_kind": "browser_probe",
            }
        ],
        "blocker_branch_parity": all(bool(row["match"]) for row in blocker_rows),
        "less_shear_variant_parity": all(bool(row["match"]) for row in variant_rows),
        "less_shear_generator_uses_local_controller": (
            "_legacy_inputs_page.generate_less_shear_reo_variants" not in bridge_source
            and "build_design_guide_shear_low_util_raw_variant_states(" in bridge_source
        ),
    }
    failures = [name for name, passed in checks.items() if not passed]
    payload = {
        "audit": "inputs_page_app_bridge_guidance_compute_blocker_contract_parity",
        "timestamp": timestamp,
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "blocker_branch_samples": blocker_rows,
        "less_shear_variant_samples": variant_rows,
        "wrapper_note": "bridge wrappers preserve app-facing dispatch for compute-heavy legacy helpers without moving implementation ownership",
    }

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_DIR / f"inputs_page_app_bridge_guidance_compute_blocker_contract_parity_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_app_bridge_guidance_compute_blocker_contract_parity_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page App Bridge Guidance Compute/Blocker Contract Parity",
                "",
                f"Status: `{payload['status']}`",
                "",
                "## Checks",
                "",
                *(f"- `{name}`: `{passed}`" for name, passed in checks.items()),
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
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
