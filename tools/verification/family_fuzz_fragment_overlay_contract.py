"""Prove the family browser loader prefers fragment-fresh authority."""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification.helpers.browser_one_click_regression import (
    _load_browser_state,
)


class _FakePage:
    def __init__(self, candidates: list[dict[str, object]]) -> None:
        self._candidates = candidates

    def evaluate(self, _script: str) -> list[str]:
        return [json.dumps(candidate) for candidate in self._candidates]


def main() -> int:
    fresh_overlay_state = _load_browser_state(
        _FakePage(
            [
                {
                    "browser_probe_phase": "post_page_render",
                    "render_timing_probe": {
                        "rerun_seq": 1,
                        "started_at_ms": 100,
                    },
                    "browser_shared_probe": {
                        "lig_legs": 2,
                        "s_lig": 300.0,
                    },
                    "summary_overview_probe": {
                        "all_key_pass": False,
                        "any_fail": True,
                    },
                },
                {
                    "fragment_emitted_at_ms": 200,
                    "workspace_revision": 1,
                    "workspace_fragment_render_count": 2,
                    "browser_state_overlay": {
                        "fragment_fresh": True,
                        "browser_shared_probe": {
                            "lig_legs": 6,
                            "s_lig": 100.0,
                        },
                        "summary_overview_probe": {
                            "all_key_pass": True,
                            "any_fail": False,
                        },
                        "selected_family_id": "TARGET_BAND_REACHED",
                    },
                },
            ]
        )
    )
    assert fresh_overlay_state["browser_shared_probe"] == {
        "lig_legs": 6,
        "s_lig": 100.0,
    }
    assert fresh_overlay_state["summary_overview_probe"] == {
        "all_key_pass": True,
        "any_fail": False,
    }
    assert fresh_overlay_state["selected_family_id"] == "TARGET_BAND_REACHED"
    assert fresh_overlay_state["browser_probe_phase"] == "post_page_render"

    stale_overlay_state = _load_browser_state(
        _FakePage(
            [
                {
                    "browser_probe_phase": "post_page_render",
                    "render_timing_probe": {
                        "rerun_seq": 2,
                        "started_at_ms": 300,
                    },
                    "browser_shared_probe": {
                        "lig_legs": 6,
                        "s_lig": 100.0,
                    },
                    "summary_overview_probe": {
                        "all_key_pass": True,
                        "any_fail": False,
                    },
                    "selected_family_id": "TARGET_BAND_REACHED",
                },
                {
                    "fragment_emitted_at_ms": 200,
                    "workspace_revision": 1,
                    "workspace_fragment_render_count": 1,
                    "browser_state_overlay": {
                        "fragment_fresh": True,
                        "browser_shared_probe": {
                            "lig_legs": 2,
                            "s_lig": 300.0,
                        },
                        "summary_overview_probe": {
                            "all_key_pass": False,
                            "any_fail": True,
                        },
                        "selected_family_id": "SHEAR_FAIL_GOVERNS",
                    },
                },
            ]
        )
    )
    assert stale_overlay_state["browser_shared_probe"] == {
        "lig_legs": 6,
        "s_lig": 100.0,
    }
    assert stale_overlay_state["summary_overview_probe"] == {
        "all_key_pass": True,
        "any_fail": False,
    }
    assert stale_overlay_state["selected_family_id"] == "TARGET_BAND_REACHED"

    post_apply_state = _load_browser_state(
        _FakePage(
            [
                {
                    "browser_probe_phase": "post_page_render",
                    "render_timing_probe": {
                        "rerun_seq": 2,
                        "started_at_ms": 300,
                    },
                    "browser_shared_probe": {
                        "lig_legs": 6,
                        "s_lig": 100.0,
                    },
                    "summary_overview_probe": {
                        "all_key_pass": True,
                        "any_fail": False,
                    },
                    "selected_family_id": "TARGET_BAND_REACHED",
                },
                {
                    # The fragment may be emitted during the current rerun
                    # while still carrying the previous authoritative result.
                    "fragment_emitted_at_ms": 350,
                    "workspace_revision": 2,
                    "workspace_fragment_render_count": 2,
                    "browser_state_overlay": {
                        "fragment_fresh": True,
                        "browser_shared_probe": {
                            "lig_legs": 2,
                            "s_lig": 300.0,
                        },
                        "summary_overview_probe": {
                            "all_key_pass": False,
                            "any_fail": True,
                        },
                        "selected_family_id": "SHEAR_FAIL_GOVERNS",
                    },
                },
            ]
        ),
        preferred_updates={"lig_legs": 6, "s_lig": 100.0},
    )
    assert post_apply_state["browser_shared_probe"] == {
        "lig_legs": 6,
        "s_lig": 100.0,
    }
    assert post_apply_state["summary_overview_probe"] == {
        "all_key_pass": True,
        "any_fail": False,
    }
    assert post_apply_state["selected_family_id"] == "TARGET_BAND_REACHED"
    print("family fuzz fragment overlay contract PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
