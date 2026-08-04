from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import inputs_page_app_contract_bridge as bridge  # noqa: E402
from inputs_page_modules.design_guide.post_apply_acceptance import (  # noqa: E402
    build_local_cleanup_acceptance_fingerprint,
    local_cleanup_post_apply_acceptance_matches,
)


def main() -> int:
    state = {
        "b": 300,
        "D": 500,
        "bot1_count": 4,
        "db_bot_1": 20,
        "lig_d": 10,
        "lig_legs": 2,
        "s_lig": 200,
    }
    expected = build_local_cleanup_acceptance_fingerprint(state)
    original_st = bridge.st
    try:
        bridge.st = SimpleNamespace(
            session_state={"_design_guide_post_cleanup_acceptance_fp": expected}
        )
        assert bridge._local_cleanup_acceptance_fingerprint(state) == expected
        assert bridge._local_cleanup_post_apply_acceptance_matches(state)
        assert local_cleanup_post_apply_acceptance_matches(
            state,
            expected_fingerprint=expected,
        )
        assert not local_cleanup_post_apply_acceptance_matches(
            {**state, "D": 525},
            expected_fingerprint=expected,
        )
    finally:
        bridge.st = original_st
    print("inputs post-Apply acceptance parity PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
