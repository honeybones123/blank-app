"""Lock the extracted guidance helper to its injected session dependency."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs_page_modules import guidance_compute


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
    expected = guidance_compute._local_cleanup_acceptance_fingerprint(state)
    original = guidance_compute._GUIDANCE_COMPUTE_SESSION_STATE
    try:
        guidance_compute._GUIDANCE_COMPUTE_SESSION_STATE = {
            "_design_guide_post_cleanup_acceptance_fp": expected
        }
        assert guidance_compute._local_cleanup_post_apply_acceptance_matches(state)
        assert not guidance_compute._local_cleanup_post_apply_acceptance_matches(
            {**state, "D": 525}
        )
    finally:
        guidance_compute._GUIDANCE_COMPUTE_SESSION_STATE = original

    source = Path(guidance_compute.__file__).read_text(encoding="utf-8")
    runtime_source = source.split("def build_guidance_compute_runtime", 1)[1].split(
        "def _build_auto_design_runtime", 1
    )[0]
    assert 'globals()["st"] = namespace.st' in runtime_source
    helper_source = source.split(
        "def _local_cleanup_post_apply_acceptance_matches", 1
    )[1].split("def _build_design_actions_context", 1)[0]
    assert "st.session_state" not in helper_source
    assert "_local_cleanup_acceptance_matches_owned(" in helper_source
    print("guidance_compute_session_dependency: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
