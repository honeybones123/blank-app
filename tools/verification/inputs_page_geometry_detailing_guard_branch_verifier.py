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
    json_path = ARTIFACT_DIR / f"inputs_page_geometry_detailing_guard_branch_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_geometry_detailing_guard_branch_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals: dict[str, Any] = {
        "_geometry_detailing_governs_guidance_item": inputs_page._geometry_detailing_governs_guidance_item,
        "_design_guide_apply_button_contracts_to_items": inputs_page._design_guide_apply_button_contracts_to_items,
        "_design_guide_apply_display_truth_to_items": inputs_page._design_guide_apply_display_truth_to_items,
        "_design_guide_button_contract_enabled": inputs_page._design_guide_button_contract_enabled,
    }
    calls: list[str] = []
    failures: list[str] = []
    cases: list[dict[str, Any]] = []

    def _restore() -> None:
        for name, value in originals.items():
            setattr(inputs_page, name, value)

    def _install(*, geometry_item: dict | None) -> None:
        calls.clear()

        def _geometry(state, overview, *, debug_sink=None):
            calls.append("geometry_item")
            if isinstance(debug_sink, dict):
                debug_sink["seed_marker"] = "from_geometry_item"
            return dict(geometry_item or {})

        def _apply_contracts(items, *, state=None):
            calls.append("apply_contracts")
            out = [dict(item) for item in list(items or [])]
            if out:
                contract = dict(out[0].get("button_contract") or {})
                contract.setdefault("updates", {"b": 450})
                out[0]["button_contract"] = contract
            return out

        def _apply_display(items, *, state=None, overview=None, mode_config=None):
            calls.append("apply_display")
            out = [dict(item) for item in list(items or [])]
            if out:
                out[0]["display_truth_applied"] = True
            return out

        inputs_page._geometry_detailing_governs_guidance_item = _geometry
        inputs_page._design_guide_apply_button_contracts_to_items = _apply_contracts
        inputs_page._design_guide_apply_display_truth_to_items = _apply_display
        inputs_page._design_guide_button_contract_enabled = lambda contract: bool(contract.get("enabled"))

    def _run_case(
        name: str,
        *,
        render_governing_classifier: dict,
        primary_guard_key: str,
        geometry_item: dict | None,
        guidance_items: list[dict],
    ) -> dict[str, Any]:
        try:
            _install(geometry_item=geometry_item)
            result = inputs_page.render_design_guide_geometry_detailing_guard_branch(
                render_governing_classifier=render_governing_classifier,
                guidance_debug={},
                active_fail_keys_for_render={"bending"},
                primary_for_active_guard=dict(guidance_items[0] if guidance_items else {}),
                primary_guard_key=primary_guard_key,
                guidance_items=[dict(item) for item in guidance_items],
                guidance_items_raw=[dict(item) for item in guidance_items],
                guidance_disp_state={"D": 400, "b": 300},
                dg_overview={"statuses": {"geometry": "FAIL"}},
                dg_mode_cfg={"goal": "balanced"},
            )
        finally:
            case_calls = list(calls)
            _restore()
        case = {"name": name, "result": result, "calls": case_calls}
        cases.append(case)
        return case

    geometry = _run_case(
        "geometry_governs_republishes_cta",
        render_governing_classifier={"governing_state": "GEOMETRY_DETAILING_GOVERNS"},
        primary_guard_key="bending",
        geometry_item={
            "reasoning": "Width ratio limit is exceeded.",
            "candidate_search_evidence": {"source": "geometry"},
        },
        guidance_items=[{"family": "bending", "title": "Bending capacity is low"}],
    )
    (
        geometry_debug,
        geometry_items,
        geometry_items_raw,
        geometry_active_keys,
        geometry_primary,
        geometry_key,
    ) = geometry["result"]
    geometry_contract = dict(geometry_primary.get("button_contract") or {})
    if geometry_active_keys != set():
        failures.append(f"geometry_active_keys_not_cleared:{geometry_active_keys}")
    if geometry_key != "geometry_detailing":
        failures.append(f"geometry_primary_key_mismatch:{geometry_key}")
    if geometry_primary.get("title_main") != "Geometry needs correction":
        failures.append(f"geometry_title_mismatch:{geometry_primary}")
    if geometry_primary.get("primary_action") != "Apply geometry correction":
        failures.append(f"geometry_cta_label_mismatch:{geometry_primary}")
    if geometry_contract.get("enabled") is not True or geometry_contract.get("actionable") is not True:
        failures.append(f"geometry_contract_not_enabled:{geometry_contract}")
    if geometry_contract.get("action_type") != "apply_resolved_candidate":
        failures.append(f"geometry_contract_action_type_mismatch:{geometry_contract}")
    for key in ("selected_family_id", "published_family_id", "cta_family_id", "apply_payload_family_id"):
        if geometry_contract.get(key) != "GEOMETRY_DETAILING_GOVERNS":
            failures.append(f"geometry_contract_family_mismatch:{key}:{geometry_contract}")
    if geometry_debug.get("guidance_branch") != "geometry_detailing_family_render_publication":
        failures.append(f"geometry_guidance_branch_mismatch:{geometry_debug}")
    if geometry_debug.get("geometry_detailing_render_publication_used") is not True:
        failures.append(f"geometry_publication_flag_missing:{geometry_debug}")
    if geometry_debug.get("button_contract_enabled") is not True:
        failures.append(f"geometry_debug_contract_enabled_mismatch:{geometry_debug}")
    if geometry_debug.get("seed_marker") != "from_geometry_item":
        failures.append(f"geometry_seed_not_merged:{geometry_debug}")
    if geometry_items_raw != geometry_items:
        failures.append("geometry_items_raw_not_updated")
    if geometry["calls"] != ["geometry_item", "apply_contracts", "apply_display"]:
        failures.append(f"geometry_call_order_mismatch:{geometry['calls']}")

    ratio = _run_case(
        "ratio_blocker_clears_active_keys_without_item",
        render_governing_classifier={"geometry_ratio_blocker": {"blocked": True}},
        primary_guard_key="bending",
        geometry_item={},
        guidance_items=[{"family": "bending"}],
    )
    if ratio["result"][3] != set():
        failures.append(f"ratio_active_keys_not_cleared:{ratio['result'][3]}")
    if ratio["result"][0].get("active_failure_visible_truth_suppressed_by_geometry_detailing") is not True:
        failures.append(f"ratio_suppression_flag_missing:{ratio['result'][0]}")
    if ratio["result"][5] != "bending":
        failures.append(f"ratio_primary_key_changed_without_item:{ratio['result'][5]}")

    already = _run_case(
        "already_geometry_preserves_existing_primary",
        render_governing_classifier={"governing_state": "GEOMETRY_DETAILING_GOVERNS"},
        primary_guard_key="geometry_detailing",
        geometry_item={"title": "Should not be used"},
        guidance_items=[{"family": "geometry_detailing", "title": "Existing geometry card"}],
    )
    if already["calls"]:
        failures.append(f"already_geometry_republished_unexpectedly:{already['calls']}")
    if already["result"][1][0].get("title") != "Existing geometry card":
        failures.append(f"already_geometry_item_changed:{already['result'][1]}")
    if already["result"][3] != set():
        failures.append(f"already_geometry_active_keys_not_cleared:{already['result'][3]}")

    payload = {
        "verifier": "inputs_page_geometry_detailing_guard_branch_verifier",
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
                "# Inputs Page Geometry Detailing Guard Branch Verifier",
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
