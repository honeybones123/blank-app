"""Verify application-owned shear candidate diagnostic behavior."""

from __future__ import annotations

import contextlib
import copy
import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
        io.StringIO()
    ):
        import inputs_page_app_contract_bridge as bridge
        import inputs_application.recommendation_diagnostics as diagnostics
        from inputs_page_modules.recommendation_compute import (
            ShearRecommendationRuntime,
        )

    state = {"lig_d": 12, "lig_legs": 4, "s_lig": 150.0}
    candidate = {"score": 42.5}
    preview = {
        "results": SimpleNamespace(phi_Vu=300.0, V_eq=240.0),
        "util": 0.8,
    }
    calls = {"compatibility": [], "application": [], "disabled": []}
    originals = {
        "st": bridge.st,
        "logger": bridge._agent_debug_log,
        "preview": bridge._evaluate_shear_with_state,
        "owned_preview": diagnostics.evaluate_shear_with_state,
    }
    try:
        bridge.st = SimpleNamespace(session_state={"_dev_mode": True})
        bridge._agent_debug_log = lambda *args, **kwargs: calls[
            "compatibility"
        ].append((copy.deepcopy(args), copy.deepcopy(kwargs)))
        bridge._evaluate_shear_with_state = lambda value: copy.deepcopy(preview)
        diagnostics.evaluate_shear_with_state = lambda value: copy.deepcopy(preview)
        bridge._log_shear_candidate_debug(
            source="parity",
            candidate_state=copy.deepcopy(state),
            candidate=copy.deepcopy(candidate),
        )
        diagnostics.log_shear_candidate_debug(
            source="parity",
            candidate_state=copy.deepcopy(state),
            candidate=copy.deepcopy(candidate),
            agent_debug_log=lambda *args, **kwargs: calls[
                "application"
            ].append((copy.deepcopy(args), copy.deepcopy(kwargs))),
            enabled=True,
        )
        diagnostics.log_shear_candidate_debug(
            source="parity",
            candidate_state=copy.deepcopy(state),
            candidate=copy.deepcopy(candidate),
            agent_debug_log=lambda *args, **kwargs: calls["disabled"].append(
                (copy.deepcopy(args), copy.deepcopy(kwargs))
            ),
            enabled=False,
        )
    finally:
        bridge.st = originals["st"]
        bridge._agent_debug_log = originals["logger"]
        bridge._evaluate_shear_with_state = originals["preview"]
        diagnostics.evaluate_shear_with_state = originals["owned_preview"]

    runtime_fields = set(ShearRecommendationRuntime.__dataclass_fields__)
    checks = {
        "enabled_payload_matches_exactly": (
            calls["compatibility"] == calls["application"]
        ),
        "disabled_emits_nothing": calls["disabled"] == [],
        "bridge_callback_removed_from_typed_runtime": (
            "_log_shear_candidate_debug" not in runtime_fields
        ),
    }
    payload = {
        "contract_version": "inputs_shear_candidate_diagnostics_application_owner.v1",
        "checks": checks,
        "status": "PASS" if all(checks.values()) else "FAIL",
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
