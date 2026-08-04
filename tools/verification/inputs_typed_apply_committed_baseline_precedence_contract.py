"""Lock typed Apply precedence over the previous committed beam baseline."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs_application.engineering_input_store import (  # noqa: E402
    should_reuse_committed_engineering_baseline,
)


def main() -> int:
    common = {
        "committed_state_present": True,
        "active_beam_id": "beam_1",
        "committed_beam_id": "beam_1",
        "shared_only_mode": False,
        "same_beam_route_return": False,
    }
    assert should_reuse_committed_engineering_baseline(
        **common,
        snapshot_update_pending=False,
    )
    assert not should_reuse_committed_engineering_baseline(
        **common,
        snapshot_update_pending=True,
    )
    assert should_reuse_committed_engineering_baseline(
        **{
            **common,
            "shared_only_mode": True,
            "same_beam_route_return": True,
        },
        snapshot_update_pending=False,
    )
    assert not should_reuse_committed_engineering_baseline(
        **{
            **common,
            "committed_beam_id": "beam_2",
        },
        snapshot_update_pending=False,
    )
    print("inputs typed Apply committed-baseline precedence contract PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
