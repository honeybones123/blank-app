from tools.verification.helpers.browser_state_overlay import (
    merge_fragment_browser_state_overlay,
    select_browser_state_candidate,
    select_fragment_browser_state_overlay,
)


def test_outer_selection_prefers_complete_post_render_probe():
    selected = select_browser_state_candidate(
        [
            {"probe_phase": "pre_page_render", "results_version": 9},
            {
                "browser_probe_phase": "post_page_render",
                "results_version": 8,
                "summary_state_probe": {"b": 300},
            },
        ]
    )
    assert selected["summary_state_probe"] == {"b": 300}


def test_fragment_selection_uses_newest_fresh_revision_not_dom_order():
    selected = select_fragment_browser_state_overlay(
        [
            {
                "workspace_revision": 7,
                "fragment_emitted_at_ms": 200,
                "browser_state_overlay": {
                    "fragment_fresh": True,
                    "summary_state_probe": {"b": 325},
                },
            },
            {
                "workspace_revision": 6,
                "fragment_emitted_at_ms": 300,
                "browser_state_overlay": {
                    "fragment_fresh": True,
                    "summary_state_probe": {"b": 300},
                },
            },
        ],
        base_state={},
    )
    assert selected["summary_state_probe"] == {"b": 325}


def test_stale_fragment_is_never_selected_or_merged():
    overlay = select_fragment_browser_state_overlay(
        [{"browser_state_overlay": {"fragment_fresh": False, "value": 2}}],
        base_state={"value": 1},
    )
    assert overlay == {}
    assert merge_fragment_browser_state_overlay({"value": 1}, overlay) == {
        "value": 1,
        "fragment_fresh": False,
    }


def test_merge_replaces_fragment_owned_evidence():
    merged = merge_fragment_browser_state_overlay(
        {"summary_state_probe": {"b": 250}, "page_slug": "inputs"},
        {"fragment_fresh": True, "summary_state_probe": {"b": 300}},
    )
    assert merged == {
        "summary_state_probe": {"b": 300},
        "page_slug": "inputs",
        "fragment_fresh": True,
    }
