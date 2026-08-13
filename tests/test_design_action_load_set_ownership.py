from __future__ import annotations

from inputs_page_modules.widgets.design_action_sync import (
    make_design_action_widget_callback,
)
from inputs_application.v2_design_guide_renderer import (
    _commit_v2_design_guide_apply,
)


def test_reused_action_widget_resolves_sls_owner_when_callback_executes() -> None:
    selected = {"prefix": "uls"}
    writes: list[tuple[str, str, str | None, bool]] = []

    callback = make_design_action_widget_callback(
        "inputs_load_Mstar_pos_proxy",
        "uls_Mstar_pos_manual",
        "load_Mstar_pos_proxy",
        selected_prefix_fn=lambda: selected["prefix"],
        sync_design_action_widget_to_shared_fn=lambda widget, shared, proxy, *, trigger_rerun: writes.append(
            (widget, shared, proxy, trigger_rerun)
        ),
    )

    # The same Streamlit widget/callback survives the load-set switch.
    selected["prefix"] = "sls"
    callback()

    assert writes == [
        (
            "inputs_load_Mstar_pos_proxy",
            "sls_Mstar_pos_manual",
            "load_Mstar_pos_proxy",
            False,
        )
    ]


def test_reused_shear_action_widget_resolves_uls_owner_after_switch_back() -> None:
    selected = {"prefix": "sls"}
    writes: list[str] = []
    callback = make_design_action_widget_callback(
        "inputs_load_Vstar_proxy",
        "manual_sls_Vstar",
        "load_Vstar_proxy",
        selected_prefix_fn=lambda: selected["prefix"],
        sync_design_action_widget_to_shared_fn=lambda _widget, shared, _proxy, *, trigger_rerun: writes.append(
            shared
        ),
    )

    selected["prefix"] = "uls"
    callback()

    assert writes == ["manual_uls_Vstar"]


def test_load_set_handoff_uses_last_rendered_prefix_not_eager_global_mode() -> None:
    source = (
        __import__("pathlib").Path(__file__).resolve().parents[1]
        / "inputs_page_modules"
        / "widgets"
        / "render_coordinators.py"
    ).read_text(encoding="utf-8")

    assert "_inputs_design_actions_rendered_prefix" in source
    assert "commit_design_action_widgets_to_shared_fn(rendered_prefix)" in source
    assert "mirror_design_action_proxies_from_shared_fn(new_prefix)" in source


def test_apply_callback_commits_queued_payload_before_automatic_render() -> None:
    class FakeStreamlit:
        def __init__(self) -> None:
            self.session_state: dict[str, object] = {}

    st_module = FakeStreamlit()
    observed: list[dict[str, object]] = []

    _commit_v2_design_guide_apply(
        st_module,
        {"recommendation_id": "serviceability-1", "updates": {"D": 700.0}},
        lambda: observed.append(dict(st_module.session_state)),
    )

    assert observed
    assert observed[0]["_inputs_action_apply_recommendation"] is True
    assert observed[0]["pending_recommendation"] == {
        "recommendation_id": "serviceability-1",
        "updates": {"D": 700.0},
    }
