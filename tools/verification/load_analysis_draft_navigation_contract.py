"""An unpublished Load Analysis load must survive leaving and returning."""

from pathlib import Path

import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs_application.load_analysis_state_store import LoadAnalysisStateStore


def main() -> None:
    state: dict[str, object] = {
        "active_beam_id": "beam_1",
        "load_g_udl": 10.0,
        "g_udl_kNm_per_m": 0.0,
    }
    store = LoadAnalysisStateStore(state)
    captured = store.capture_widgets()
    assert captured.to_dict()["load_g_udl"] == 10.0

    # Simulate Beam Inputs temporarily hydrating the shared widget key. The
    # unpublished Analysis draft remains beam-owned and does not mutate the
    # main beam's committed load/action state.
    state["load_g_udl"] = 0.0
    assert state["g_udl_kNm_per_m"] == 0.0

    restored = store.restore_widgets(route_token="return-to-load-analysis")
    assert restored.to_dict()["load_g_udl"] == 10.0
    assert state["load_g_udl"] == 10.0
    assert state["g_udl_kNm_per_m"] == 0.0
    print("load analysis draft navigation contract: PASS")


if __name__ == "__main__":
    main()
