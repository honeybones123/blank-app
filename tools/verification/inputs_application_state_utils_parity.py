from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import inputs_page_app_contract_bridge as bridge  # noqa: E402
from inputs_application.state_utils import (  # noqa: E402
    bottom_reo_state_label,
    float_from_state,
    guidance_state_snapshot,
    shared_state_snapshot,
    shear_state_label,
    updates_match_state,
)


def main() -> int:
    state = {
        "b": 300,
        "D": 500,
        "bot1_layout_mode": "Count",
        "bot2_layout_mode": "Count",
        "bot1_count": 4,
        "bot2_count": 2,
        "db_bot_1": 20,
        "lig_legs": 2,
        "lig_d": 10,
        "s_lig": 200.0,
        "_solver_result": {"stale": True},
    }
    original_st = bridge.st
    try:
        bridge.st = SimpleNamespace(session_state=dict(state))
        assert shared_state_snapshot(state) == bridge._shared_state_snapshot()
        assert guidance_state_snapshot(state) == bridge._guidance_state_snapshot(state)
        assert bottom_reo_state_label(state) == bridge._bottom_reo_state_label(state)
        assert shear_state_label(state) == bridge._shear_state_label(state)
        assert float_from_state(state, "b", 0.0) == bridge._float_from_state(state, "b", 0.0)
        assert updates_match_state(state, {"b": 300.0, "D": 500}) == bridge._updates_match_state(
            state,
            {"b": 300.0, "D": 500},
        )
    finally:
        bridge.st = original_st
    print("inputs application state utils parity PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
