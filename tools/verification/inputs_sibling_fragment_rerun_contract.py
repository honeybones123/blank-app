"""Focused runtime proof for the coupled Inputs workspace rerun boundary."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs_application.engineering_workspace import (
    render_inputs_widget_fragment_section,
)
from inputs_application.workspace_rerun_policy import (
    request_inputs_workspace_refresh,
)


class _FakeStreamlit:
    def __init__(self) -> None:
        self.session_state: dict = {
            "_inputs_workspace_revision": 4,
            "_inputs_workspace_authoritative_revision": 4,
        }
        self.rerun_scopes: list[str] = []

    def rerun(self, *, scope: str = "app") -> None:
        self.rerun_scopes.append(scope)


def main() -> int:
    fake = _FakeStreamlit()
    events: list[str] = []
    runtime = SimpleNamespace(
        render_widgets=lambda **kwargs: events.append("widgets") or False,
        render_divider=lambda: events.append("divider"),
    )
    page_context = {
        "sync_callbacks": {},
        "inputs_render_audit": {},
        "fast_focus_section": None,
        "fast_get_param": lambda *args, **kwargs: None,
        "corrected_invalid_shear_state": False,
        "mark": lambda *args, **kwargs: None,
        "sub_mark": lambda *args, **kwargs: None,
    }

    render_inputs_widget_fragment_section(
        st_module=fake,
        runtime=runtime,
        page_context=page_context,
        inputs_detailed_mode=False,
    )
    assert fake.rerun_scopes == []

    request = request_inputs_workspace_refresh(
        fake.session_state,
        "inputs_D",
    )
    assert request is not None and request.revision == 5
    render_inputs_widget_fragment_section(
        st_module=fake,
        runtime=runtime,
        page_context=page_context,
        inputs_detailed_mode=False,
    )
    # The workspace fragment itself owns the rerun. The widget section must
    # never promote an engineering edit to an app-scope rerun.
    assert fake.rerun_scopes == []
    assert fake.session_state["_inputs_workspace_revision"] == 5

    revision_before_local = fake.session_state["_inputs_workspace_revision"]
    local = request_inputs_workspace_refresh(
        fake.session_state,
        "inputs_fast_mode_show_3d_toggle",
    )
    assert local is None
    assert fake.session_state["_inputs_workspace_revision"] == revision_before_local
    print("inputs sibling fragment rerun contract PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
