"""Prove Design Guide replacement occurs inside its fragment boundary."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from application.design_result_store import AuthoritativeDesignResultStore
from design_brain.authority import (
    EngineeringInputSnapshot,
    build_authoritative_design_result,
)
from inputs_application.design_guide_fragment_store import (
    DesignGuideFragmentStore,
)
from inputs_application.engineering_workspace import (
    prepare_engineering_workspace_transaction,
    render_inputs_design_guide_fragment_section,
)
from inputs_page_modules.design_guide.render_coordinators import (
    render_design_guide_component_cta,
)


def _result(*, width: float, title: str):
    return build_authoritative_design_result(
        engineering_snapshot=EngineeringInputSnapshot(
            geometry={"b": width}
        ),
        final_publication={"display": {"title": title}},
    )


class _FakeStreamlit:
    def __init__(self, session_state: dict) -> None:
        self.session_state = session_state
        self.rerun_scopes: list[str | None] = []

    def empty(self):
        return object()

    def rerun(self, *, scope: str | None = None) -> None:
        self.rerun_scopes.append(scope)


def main() -> int:
    design_guide_page_source = (
        ROOT / "design_guide_page.py"
    ).read_text(encoding="utf-8")
    assert '"_inputs_design_guide_fragment_mode"' in design_guide_page_source
    assert (
        '"_inputs_engineering_workspace_fragment_mode"'
        in design_guide_page_source
    )

    session = {"_inputs_workspace_revision": 2}
    fake = _FakeStreamlit(session)
    first = _result(width=300.0, title="First")
    second = _result(width=350.0, title="Second")
    result_store = AuthoritativeDesignResultStore(session)
    fragment_store = DesignGuideFragmentStore(session)
    result_store.store(first)
    fragment_store.publish(first)

    def refresh():
        return result_store.store(second)

    transaction_runtime = SimpleNamespace(
        reconcile_design_actions=lambda: [],
        refresh_authoritative_result=refresh,
    )
    prepare_engineering_workspace_transaction(
        st_module=fake,
        runtime=transaction_runtime,
    )
    pending = fragment_store.current()
    assert pending.status == "refreshing"
    assert pending.active_engineering_hash == first.engineering_hash
    assert pending.active_publication == first.final_publication

    rendered_states: list[dict] = []
    fragment_runtime = SimpleNamespace(
        handle_pending_apply=lambda: None,
        render_design_guide=lambda **kwargs: rendered_states.append(
            dict(kwargs["fragment_state"])
        )
    )
    render_inputs_design_guide_fragment_section(
        st_module=fake,
        runtime=fragment_runtime,
        page_context={
            "sync_callbacks": {},
            "inputs_render_audit": {},
            "fast_focus_section": None,
            "mark": lambda *args, **kwargs: None,
        },
        inputs_detailed_mode=False,
    )
    ready = fragment_store.current()
    assert ready.status == "ready"
    assert ready.active_engineering_hash == second.engineering_hash
    assert ready.active_publication == second.final_publication
    assert rendered_states[-1]["active_engineering_hash"] == (
        second.engineering_hash
    )
    cta_events: list[tuple[str, object]] = []

    class _FakeCtaStreamlit:
        session_state = {}

        @staticmethod
        def button(label, **kwargs):
            cta_events.append(("button", {"label": label, **kwargs}))
            return True

    pressed = render_design_guide_component_cta(
        st_module=_FakeCtaStreamlit(),
        apply_label="Apply recommendation",
        rec={"candidate_id": "candidate_1"},
        primary_route_target="handle_apply_buttons",
        button_contract={"enabled": True},
        queue_primary_button_action_fn=lambda *args: cta_events.append(
            ("queue", args)
        ),
    )
    assert pressed is True
    assert [event[0] for event in cta_events] == ["button"]
    assert cta_events[0][1]["on_click"] is not None
    assert cta_events[0][1]["args"][1] == "handle_apply_buttons"
    print("inputs Design Guide local replacement contract PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
