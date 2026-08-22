from __future__ import annotations

import inspect

from inputs_application import engineering_workspace
from inputs_application.v2_design_guide_renderer import (
    _commit_v2_design_guide_apply,
)


class _MarkdownProbe:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def markdown(self, body: str, **_kwargs) -> None:
        self.calls.append(body)


class _ApplyProbe:
    def __init__(self) -> None:
        self.session_state: dict[str, object] = {}


def test_design_brain_apply_arms_atomic_revision_gate_after_commit() -> None:
    st_probe = _ApplyProbe()
    handler_observations: list[bool] = []

    def _handler() -> None:
        handler_observations.append(
            bool(st_probe.session_state.get("_inputs_atomic_revision_guard_pending"))
        )

    _commit_v2_design_guide_apply(
        st_probe,
        {"updates": {"b": 300.0, "D": 600.0}},
        _handler,
    )

    assert handler_observations == [False]
    assert st_probe.session_state["_inputs_atomic_revision_guard_pending"] is True


def test_atomic_workspace_markers_bind_revision_and_expected_controls() -> None:
    st_probe = _MarkdownProbe()

    engineering_workspace._render_atomic_workspace_start(
        st_module=st_probe,
        beam_id="beam_2",
        revision=17,
        guard_required=True,
    )
    engineering_workspace._render_atomic_workspace_complete(
        st_module=st_probe,
        beam_id="beam_2",
        revision=17,
        expected_width_mm=325.0,
        expected_depth_mm=650.0,
    )

    rendered = "\n".join(st_probe.calls)
    assert 'data-inputs-workspace-revision-start="17"' in rendered
    assert 'data-inputs-workspace-identity-start="beam_2:17"' in rendered
    assert 'data-atomic-guard="1"' in rendered
    assert "data-inputs-workspace-revision-complete='17'" in rendered
    assert "data-inputs-workspace-identity-complete='beam_2:17'" in rendered
    assert "data-expected-width-mm='325'" in rendered
    assert "data-expected-depth-mm='650'" in rendered
    # Visibility is released by the server's final revision marker. Browser
    # scroll preservation may enhance the transition, but it must never be a
    # prerequisite for revealing an otherwise complete Inputs workspace.
    assert ":not(:has([data-inputs-workspace-identity-complete=\"beam_2:17\"]))" in rendered


def test_atomic_scroll_bridge_is_one_shot_and_user_cancellable() -> None:
    source = inspect.getsource(
        engineering_workspace._render_atomic_workspace_browser_runtime
    )

    assert source.count("main.scrollTop = pending.scrollTop") == 1
    assert "requestAnimationFrame(function ()" in source
    assert "wheel" in source
    assert "touchmove" in source
    assert "PageDown" in source
    assert "onScrollbar" in source
    assert "setInterval" not in source
    assert "while (" not in source
    assert "data-expected-width-mm" in source
    assert "data-expected-depth-mm" in source
    assert "beamSelector" in source
    assert "previousIdentity" in source
    assert "identity === pending.previousIdentity) return" in source
    assert "if (!doc || !doc.body) return;" in source
