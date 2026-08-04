from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _base_state(**updates: Any) -> dict[str, Any]:
    state = {
        "lig_legs": 2,
        "lig_d": 10,
        "s_lig": 200.0,
    }
    state.update(updates)
    return state


def _run_case(name: str, initial_state: dict[str, Any]) -> dict[str, Any]:
    import inputs_page_app_contract_bridge as bridge
    from inputs_page_modules.session.shear_normalization import (
        run_inputs_pre_hydrate_shear_normalization,
    )

    original_bridge_st = bridge.st
    original_bridge_set_shared = bridge.set_shared
    legacy_calls: list[dict[str, Any]] = []
    bridge_calls: list[dict[str, Any]] = []

    try:
        legacy_session: dict[str, Any] = dict(initial_state)
        bridge_session: dict[str, Any] = dict(initial_state)

        def legacy_set_shared(key: str, value: Any, *, source: str = "") -> None:
            legacy_calls.append({"key": key, "value": value, "source": source})
            legacy_session[key] = value

        def bridge_set_shared(key: str, value: Any, *, source: str = "") -> None:
            bridge_calls.append({"key": key, "value": value, "source": source})
            bridge_session[key] = value

        bridge.st = SimpleNamespace(session_state=bridge_session)
        bridge.set_shared = bridge_set_shared
        legacy_value = bool(
            run_inputs_pre_hydrate_shear_normalization(
                legacy_session,
                set_shared_fn=legacy_set_shared,
            )
        )
        legacy_flag = legacy_session.get("_inputs_shear_shared_normalised_this_run")

        bridge_value = bool(bridge.run_inputs_layer4_pre_hydrate_shear_normalisation())
        bridge_flag = bridge_session.get("_inputs_shear_shared_normalised_this_run")
    finally:
        bridge.st = original_bridge_st
        bridge.set_shared = original_bridge_set_shared

    return {
        "case": name,
        "initial_state": dict(initial_state),
        "legacy_value": legacy_value,
        "bridge_value": bridge_value,
        "legacy_flag": legacy_flag,
        "bridge_flag": bridge_flag,
        "legacy_final_state": legacy_session,
        "bridge_final_state": bridge_session,
        "legacy_calls": legacy_calls,
        "bridge_calls": bridge_calls,
        "match": (
            legacy_value == bridge_value
            and legacy_flag == bridge_flag
            and legacy_calls == bridge_calls
            and legacy_session == bridge_session
        ),
    }


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    rows = [
        _run_case("valid_active_links", _base_state()),
        _run_case("inactive_links_canonicalised", _base_state(lig_legs=0, lig_d=10, s_lig=175.0)),
        _run_case("active_links_missing_diameter", _base_state(lig_legs=2, lig_d=0, s_lig=200.0)),
        _run_case("active_links_missing_spacing", _base_state(lig_legs=2, lig_d=10, s_lig=0.0)),
    ]
    failures = [
        f"{row['case']}_layer4_shear_normalisation_mismatch"
        for row in rows
        if not bool(row["match"])
    ]
    payload = {
        "audit": "inputs_page_app_bridge_layer4_shear_normalisation_parity",
        "timestamp": timestamp,
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "samples": rows,
        "wrapper_note": "bridge wrapper delegates legacy normalisation implementation and preserves app-facing flag behavior",
    }

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_DIR / f"inputs_page_app_bridge_layer4_shear_normalisation_parity_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_app_bridge_layer4_shear_normalisation_parity_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page App Bridge Layer 4 Shear Normalisation Parity",
                "",
                f"Status: `{payload['status']}`",
                "",
                "## Samples",
                "",
                *(f"- `{row['case']}` match: `{row['match']}`" for row in rows),
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
