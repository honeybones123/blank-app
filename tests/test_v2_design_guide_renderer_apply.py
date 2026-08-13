from __future__ import annotations

from pathlib import Path

from application.contracts.design_brain import AuthoritativeDesignResult
from inputs_application.v2_design_guide_renderer import render_v2_design_guide_card


class _Context:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class _Slot:
    def container(self):
        return _Context()


class _ClickedStreamlit:
    def __init__(self) -> None:
        self.session_state: dict = {}

    def markdown(self, *_args, **_kwargs) -> None:
        return None

    def expander(self, *_args, **_kwargs):
        return _Context()

    def container(self, *_args, **_kwargs):
        return _Context()

    def button(self, *_args, **kwargs) -> bool:
        callback = kwargs.get("on_click")
        if callback is not None:
            callback(*tuple(kwargs.get("args") or ()))
        return True


def test_card_contains_scoped_morning_transaction_shell() -> None:
    source = Path(__file__).parents[1].joinpath(
        "inputs_application", "v2_design_guide_renderer.py"
    ).read_text(encoding="utf-8-sig")

    assert "inputs-v2-design-brain-runtime-loading" in source
    assert "Updating Design Brain" in source
    assert 'stStatusWidget' in source
    assert 'st-key-v2_design_guide_apply_scope' in source
    assert "stAppViewContainer" in source


def test_apply_click_commits_before_workspace_fragment_renders() -> None:
    st_module = _ClickedStreamlit()
    handled: list[dict] = []
    result = AuthoritativeDesignResult(
        engineering_hash="engineering-v1",
        governing_family="BENDING_OVERDESIGN_GOVERNS",
        display_model={
            "v2_badge": "ACTION",
            "v2_heading": "Verified bending optimisation",
            "v2_state_class": "action",
            "v2_governing_utilisation": 0.97,
            "v2_advice_text": "Reduce the bottom reinforcement.",
        },
        cta_model={"enabled": True, "label": "Apply recommendation"},
        final_publication={"publication_hash": "publication-v1"},
        apply_payload={"updates": {"bot_bar_dia": 20}},
    )

    render_v2_design_guide_card(
        st_module=st_module,
        design_guide_slot=_Slot(),
        result=result,
        apply_handler=lambda: handled.append(
            dict(st_module.session_state["pending_recommendation"])
        ),
    )

    assert st_module.session_state["_inputs_action_apply_recommendation"] is True
    assert st_module.session_state["pending_recommendation"]["updates"] == {
        "bot_bar_dia": 20
    }
    assert "_defer_scoped_apply_rerun" not in st_module.session_state[
        "pending_recommendation"
    ]
    assert handled == [st_module.session_state["pending_recommendation"]]
