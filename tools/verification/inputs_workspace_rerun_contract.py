"""Lock widget classification and sibling-fragment engineering commit contract."""

from __future__ import annotations

import ast
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def main() -> None:
    from inputs_application.workspace_rerun_policy import (
        DISPLAY_LOCAL_WIDGET_KEYS,
        InputsWidgetRerunClass,
        classify_inputs_widget,
        request_inputs_workspace_refresh,
    )
    from state_and_helpers import TAB_KEYS

    classifications = {
        key: classify_inputs_widget(key)
        for key in TAB_KEYS
        if str(key).startswith("inputs_")
    }
    assert classifications
    assert all(
        value is not InputsWidgetRerunClass.APP_NAVIGATION
        for value in classifications.values()
    )
    for key in DISPLAY_LOCAL_WIDGET_KEYS:
        assert (
            classify_inputs_widget(key)
            is InputsWidgetRerunClass.DISPLAY_LOCAL
        )

    state: dict = {}
    first = request_inputs_workspace_refresh(state, "inputs_b")
    second = request_inputs_workspace_refresh(state, "inputs_D")
    local = request_inputs_workspace_refresh(
        state,
        "inputs_fast_mode_show_3d_toggle",
    )
    assert first is not None and first.revision == 1
    assert second is not None and second.revision == 2
    assert local is None
    assert state["_inputs_workspace_revision"] == 2
    assert len(state["_inputs_workspace_rerun_events"]) == 2
    assert "_inputs_engineering_commit_requested" not in state

    page_source = (ROOT / "inputs_page.py").read_text(encoding="utf-8")
    state_source = (ROOT / "state_and_helpers.py").read_text(encoding="utf-8")
    ast.parse(page_source)
    ast.parse(state_source)
    workspace_source = (
        ROOT / "inputs_application" / "engineering_workspace.py"
    ).read_text(encoding="utf-8")
    assert 'fragment_name="engineering_workspace"' not in page_source
    assert "_render_engineering_workspace(page_context=page_context)" in page_source
    assert 'fragment_name="input"' in workspace_source
    assert 'fragment_name="summary"' in workspace_source
    assert 'fragment_name="calculation"' in workspace_source
    assert 'fragment_name="design_guide"' in workspace_source
    assert "rerun_inputs_app_scope_if_requested" not in page_source
    assert "def rerun_inputs_app_scope_if_requested" not in state_source
    assert "_inputs_engineering_commit_requested" not in state_source
    request_body = state_source[
        state_source.index("def _request_inputs_engineering_commit"):
        state_source.index("def _compose_sync_callback")
    ]
    assert "_inputs_engineering_commit_requested" not in request_body
    assert "st.rerun" not in request_body
    widget_section = workspace_source[
        workspace_source.index("def render_inputs_widget_fragment_section"):
        workspace_source.index("def render_engineering_workspace")
    ]
    design_guide_section = workspace_source[
        workspace_source.index("def render_inputs_design_guide_fragment_section"):
        workspace_source.index("def render_inputs_widget_fragment_section")
    ]
    assert "_inputs_workspace_authoritative_revision" in widget_section
    assert "workspace_revision > authoritative_revision" in widget_section
    assert 'st_module.rerun(scope="app")' in widget_section
    assert "runtime.handle_pending_apply()" in design_guide_section
    callback_body = state_source[
        state_source.index("def _compose_sync_callback"):
        state_source.index("def _make_sync_callback")
    ]
    # Geometry/material/reinforcement widgets use this callback.  They must
    # invalidate the same summary/compute state as design-action callbacks so
    # the diagram, summary packs, and Design Brain cannot consume stale data.
    for required in (
        "_classify_inputs_widget(widget_key)",
        "_InputsWidgetRerunClass.ENGINEERING_WORKSPACE",
        "_invalidate_inputs_summary_packs(",
        'st.session_state["cached_results"] = None',
        'st.session_state["_cached_compute_results"] = None',
        'st.session_state["_last_compute_fp"] = None',
        'st.session_state["inputs_dirty"] = True',
        'st.session_state["run_design_clicked"] = True',
    ):
        assert required in callback_body, required
    assert "_InputsWidgetRerunClass.DISPLAY_LOCAL" not in callback_body

    print(
        "PASS: all "
        f"{len(classifications)} Inputs widget callbacks have a rerun class; "
        "engineering edits advance one workspace revision and the Input "
        "fragment promotes stale truth to one app-scope transaction rerun"
    )


if __name__ == "__main__":
    main()
