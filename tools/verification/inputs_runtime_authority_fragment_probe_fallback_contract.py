from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification import inputs_runtime_authority_replay as replay


def test_workspace_probe_survives_outer_probe_failure() -> None:
    original_outer = replay._load_browser_state
    original_overlay = replay._state_with_workspace_probe
    try:
        def fail_outer(*args, **kwargs):
            raise RuntimeError("outer page probe replaced during fragment rerun")

        def load_workspace(page, state):
            assert state == {}
            return {
                "browser_probe_phase": "post_page_render",
                "engineering_snapshot_probe": {
                    "engineering_hash": "fragment-current-hash"
                },
            }

        replay._load_browser_state = fail_outer
        replay._state_with_workspace_probe = load_workspace

        state = replay._load_current_replay_state(object())
        assert state["engineering_snapshot_probe"]["engineering_hash"] == (
            "fragment-current-hash"
        )
    finally:
        replay._load_browser_state = original_outer
        replay._state_with_workspace_probe = original_overlay


def main() -> int:
    test_workspace_probe_survives_outer_probe_failure()
    print("inputs_runtime_authority_fragment_probe_fallback_contract: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
