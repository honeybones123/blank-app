"""Verify the application-owned shear ladder diagnostic payload."""

from __future__ import annotations

import contextlib
import copy
import io
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
        io.StringIO()
    ):
        import inputs_page_app_contract_bridge as bridge
        from inputs_application.recommendation_diagnostics import (
            log_shear_ladder_attempt,
        )
        from inputs_page_modules.recommendation_compute import (
            ShearRecommendationRuntime,
        )

    calls = {"compatibility": [], "application": [], "disabled": []}
    kwargs = {
        "ladder_mode": "strengthening",
        "branch": "spacing",
        "lig_legs": 2,
        "s_lig": 200.0,
        "proposed_updates": {"s_lig": 150.0},
        "expected_util_after": 0.94,
        "decision": "accepted",
        "reason": "target_band",
    }
    original_logger = bridge._agent_debug_log
    original_enabled = bridge.DEBUG_DESIGN_GUIDANCE_PROBE
    try:
        bridge._agent_debug_log = lambda *args, **named: calls[
            "compatibility"
        ].append((copy.deepcopy(args), copy.deepcopy(named)))
        bridge.DEBUG_DESIGN_GUIDANCE_PROBE = True
        bridge._log_shear_ladder_attempt({}, **copy.deepcopy(kwargs))
    finally:
        bridge._agent_debug_log = original_logger
        bridge.DEBUG_DESIGN_GUIDANCE_PROBE = original_enabled

    log_shear_ladder_attempt(
        {},
        agent_debug_log=lambda *args, **named: calls["application"].append(
            (copy.deepcopy(args), copy.deepcopy(named))
        ),
        enabled=True,
        **copy.deepcopy(kwargs),
    )
    log_shear_ladder_attempt(
        {},
        agent_debug_log=lambda *args, **named: calls["disabled"].append(
            (copy.deepcopy(args), copy.deepcopy(named))
        ),
        enabled=False,
        **copy.deepcopy(kwargs),
    )
    runtime_fields = set(ShearRecommendationRuntime.__dataclass_fields__)
    checks = {
        "enabled_payload_matches_exactly": (
            calls["compatibility"] == calls["application"]
        ),
        "disabled_emits_nothing": calls["disabled"] == [],
        "bridge_callback_removed_from_typed_runtime": (
            "_log_shear_ladder_attempt" not in runtime_fields
        ),
    }
    payload = {
        "contract_version": "inputs_shear_ladder_diagnostics_application_owner.v1",
        "checks": checks,
        "status": "PASS" if all(checks.values()) else "FAIL",
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
