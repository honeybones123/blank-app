"""Verify application ownership of the lightweight Design Guide state."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    import inputs_page_app_contract_bridge as bridge
    from inputs_application.state_utils import guidance_state_snapshot
    from inputs_application.summary_state_runtime import (
        InputsSummaryStateRuntime,
        resolve_design_guide_lightweight_state,
    )
    from state_and_helpers import SHARED_DEFAULTS

    original_st = bridge.st
    cases = (
        {
            "b": 400.0,
            "D": 600.0,
            "L": 6000.0,
            "Ast_bot": 1500.0,
            "nb_bot": 4,
            "db_bot": 20.0,
            "lig_legs": 2,
            "lig_d": 10.0,
            "s_lig": 200.0,
        },
        {
            "sec_shape": "T",
            "bw": 300.0,
            "D": 700.0,
            "L": 7000.0,
            "page_slug": "inputs",
            "inputs_lig_legs": 4,
            "inputs_lig_d": 12.0,
            "inputs_s_lig": 150.0,
            "exact_stop_proven": True,
            "exact_stop_proof": {"source": "verification"},
        },
        {
            "b": 450.0,
            "D": 750.0,
            "L": 8000.0,
            "_applying_auto_design": True,
            "page_slug": "inputs",
            "inputs_lig_legs": 4,
            "inputs_lig_d": 12.0,
            "inputs_s_lig": 125.0,
            "lig_legs": 2,
            "lig_d": 10.0,
            "s_lig": 200.0,
        },
        {
            "b": 350.0,
            "D": 550.0,
            "L": 5000.0,
            "reinforcement_lock": True,
            "geometry_lock": True,
            "shear_lock": True,
        },
    )
    checks = 0
    try:
        for session_case in cases:
            session = {
                key: deepcopy(default)
                for key, default in SHARED_DEFAULTS.items()
            }
            session.update(deepcopy(session_case))
            bridge.st = SimpleNamespace(session_state=session)
            incoming = deepcopy(session_case)
            expected = bridge._design_guide_lightweight_guidance_state(incoming)
            actual = resolve_design_guide_lightweight_state(
                InputsSummaryStateRuntime(
                    design_guide_fingerprint=lambda state: str(sorted(state)),
                    guidance_state_snapshot=guidance_state_snapshot,
                    session_state=session,
                    shared_state_snapshot=lambda: {
                        key: session.get(key, default)
                        for key, default in SHARED_DEFAULTS.items()
                    },
                    ux_probe_record=lambda *args, **kwargs: None,
                ),
                incoming,
            )
            assert actual == expected
            checks += 1
    finally:
        bridge.st = original_st

    source = (
        ROOT / "inputs_application" / "summary_state_runtime.py"
    ).read_text(encoding="utf-8")
    assert "inputs_page_app_contract_bridge" not in source
    assert "inputs_page_route_coordinators" not in source
    print(f"PASS exact lightweight Design Guide state parity {checks}/{checks}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
