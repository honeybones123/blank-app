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
    json_path = ARTIFACT_DIR / f"inputs_page_displayed_primary_update_family_link_state_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_displayed_primary_update_family_link_state_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals: dict[str, Any] = {
        "_resolve_recommendation_updates": inputs_page._resolve_recommendation_updates,
        "_compound_subfamilies_from_updates": inputs_page._compound_subfamilies_from_updates,
        "_optimisation_candidate_family": inputs_page._optimisation_candidate_family,
        "_governing_focus_from_overview": inputs_page._governing_focus_from_overview,
        "_normalise_invalid_shear_state_updates": inputs_page._normalise_invalid_shear_state_updates,
        "_shear_reinforcement_is_active": inputs_page._shear_reinforcement_is_active,
        "_int_from_state": inputs_page._int_from_state,
        "_float_from_state": inputs_page._float_from_state,
    }
    failures: list[str] = []
    cases: list[dict[str, Any]] = []

    def _restore() -> None:
        for name, value in originals.items():
            setattr(inputs_page, name, value)

    def _run_case(
        name: str,
        *,
        item: dict | None,
        updates: dict,
        subfamilies: list[str],
        fallback_family: str,
        state: dict,
        normalised_updates: dict,
        active: bool,
        debug: dict | None = None,
        overview: dict | None = None,
    ) -> dict[str, Any]:
        events: list[dict[str, Any]] = []

        def _updates(item_arg, state_arg):
            events.append({"event": "updates", "item": dict(item_arg or {}), "state": dict(state_arg or {})})
            return dict(updates)

        def _families(updates_arg):
            events.append({"event": "families", "updates": dict(updates_arg or {})})
            return list(subfamilies)

        def _fallback(item_arg, state_arg):
            events.append({"event": "fallback_family", "item": dict(item_arg or {})})
            return fallback_family

        def _governing(overview_arg):
            events.append({"event": "governing_focus", "overview": dict(overview_arg or {})})
            return "overview_focus"

        def _normalise(state_arg, updates_arg, *, source):
            events.append({"event": "normalise", "state": dict(state_arg or {}), "source": source})
            return dict(normalised_updates)

        def _active(state_arg):
            events.append({"event": "active", "state": dict(state_arg or {})})
            return bool(active)

        def _int_state(state_arg, key, default=0):
            events.append({"event": "int", "key": key})
            return int(dict(state_arg or {}).get(key, default) or 0)

        def _float_state(state_arg, key, default=0.0):
            events.append({"event": "float", "key": key})
            return float(dict(state_arg or {}).get(key, default) or 0.0)

        try:
            inputs_page._resolve_recommendation_updates = _updates
            inputs_page._compound_subfamilies_from_updates = _families
            inputs_page._optimisation_candidate_family = _fallback
            inputs_page._governing_focus_from_overview = _governing
            inputs_page._normalise_invalid_shear_state_updates = _normalise
            inputs_page._shear_reinforcement_is_active = _active
            inputs_page._int_from_state = _int_state
            inputs_page._float_from_state = _float_state
            result = inputs_page.render_design_guide_displayed_primary_update_family_and_link_state(
                displayed_primary_item=None if item is None else dict(item),
                guidance_disp_state=dict(state),
                guidance_debug=dict(debug or {}),
                overview=dict(overview or {}),
            )
        finally:
            _restore()

        (
            displayed_primary_updates,
            displayed_primary_update_families,
            displayed_primary_governing_action,
            optimisation_eval_state,
            optimisation_normalized_link_state,
        ) = result
        case = {
            "name": name,
            "events": events,
            "displayed_primary_updates": displayed_primary_updates,
            "displayed_primary_update_families": displayed_primary_update_families,
            "displayed_primary_governing_action": displayed_primary_governing_action,
            "optimisation_eval_state": optimisation_eval_state,
            "optimisation_normalized_link_state": optimisation_normalized_link_state,
        }
        cases.append(case)
        return case

    direct = _run_case(
        "direct_update_families_active_links",
        item={"id": "primary", "check_key": "item_check"},
        updates={"bot_dia": 20},
        subfamilies=["bending"],
        fallback_family="shear",
        state={"lig_d": 10, "lig_legs": 2, "s_lig": 200},
        normalised_updates={"s_lig": 180},
        active=True,
    )
    if direct["displayed_primary_updates"] != {"bot_dia": 20}:
        failures.append(f"direct_updates_mismatch:{direct}")
    if direct["displayed_primary_update_families"] != ["bending"]:
        failures.append(f"direct_families_mismatch:{direct}")
    if direct["displayed_primary_governing_action"] != "item_check":
        failures.append(f"direct_governing_mismatch:{direct}")
    if direct["optimisation_normalized_link_state"] != {
        "lig_d": 10,
        "lig_legs": 2,
        "s_lig": 180.0,
        "shear_reinforcement_active": True,
        "normalization_source": "guidance_resolved_state",
    }:
        failures.append(f"direct_link_state_mismatch:{direct['optimisation_normalized_link_state']}")

    fallback = _run_case(
        "fallback_family_inactive_links",
        item={"id": "primary"},
        updates={},
        subfamilies=[],
        fallback_family="shear",
        state={"lig_d": 12, "lig_legs": 3, "s_lig": 150},
        normalised_updates={},
        active=False,
        debug={"governing_action": "debug_governing"},
    )
    if fallback["displayed_primary_update_families"] != ["shear"]:
        failures.append(f"fallback_family_mismatch:{fallback}")
    if fallback["displayed_primary_governing_action"] != "debug_governing":
        failures.append(f"fallback_governing_mismatch:{fallback}")
    if fallback["optimisation_eval_state"].get("lig_d") != 0 or fallback["optimisation_eval_state"].get("s_lig") != 0.0:
        failures.append(f"fallback_inactive_state_mismatch:{fallback['optimisation_eval_state']}")
    if fallback["optimisation_normalized_link_state"].get("shear_reinforcement_active") is not False:
        failures.append(f"fallback_active_flag_mismatch:{fallback['optimisation_normalized_link_state']}")

    overview = _run_case(
        "overview_governing_no_item",
        item=None,
        updates={"D": 500},
        subfamilies=["geometry"],
        fallback_family="other",
        state={},
        normalised_updates={},
        active=False,
        overview={"governing_check": "overview_check"},
    )
    if overview["displayed_primary_updates"] != {}:
        failures.append(f"overview_no_item_updates_mismatch:{overview}")
    if overview["displayed_primary_governing_action"] is not None:
        failures.append(f"overview_no_item_governing_mismatch:{overview}")
    if any(event.get("event") == "updates" for event in overview["events"]):
        failures.append(f"overview_no_item_updates_called:{overview['events']}")

    focus = _run_case(
        "overview_focus_fallback",
        item={"id": "primary"},
        updates={},
        subfamilies=[],
        fallback_family="general",
        state={},
        normalised_updates={},
        active=False,
        overview={},
    )
    if focus["displayed_primary_update_families"] != []:
        failures.append(f"focus_general_family_unexpected:{focus}")
    if focus["displayed_primary_governing_action"] != "overview_focus":
        failures.append(f"focus_governing_mismatch:{focus}")

    payload = {
        "verifier": "inputs_page_displayed_primary_update_family_link_state_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Displayed Primary Update Family Link State Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                "## Evidence",
                "",
                *(
                    f"- `{case['name']}` families: `{case['displayed_primary_update_families']}`, governing: `{case['displayed_primary_governing_action']}`"
                    for case in cases
                ),
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
