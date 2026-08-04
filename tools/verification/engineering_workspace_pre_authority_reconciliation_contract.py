"""Prove widget reconciliation precedes authoritative engineering refresh."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs_application.engineering_workspace import (
    EngineeringWorkspaceRuntime,
    render_engineering_workspace,
)
from inputs_page_modules.summaries.pipeline import (
    InputsSummaryCalculationSource,
)


class _FakeStreamlit:
    def __init__(self) -> None:
        self.session_state: dict = {}

    def container(self):
        return object()

    def empty(self):
        return object()


def main() -> int:
    events: list[str] = []
    fake = _FakeStreamlit()

    runtime = EngineeringWorkspaceRuntime(
        reconcile_design_actions=lambda: (
            events.append("reconcile") or ["uls_Vstar"]
        ),
        refresh_authoritative_result=lambda: events.append("refresh"),
        render_summary=lambda **kwargs: (
            events.append("summary")
            or InputsSummaryCalculationSource(
                bending_rows=(),
                shear_rows=(),
                crack_rows=(),
                deflection_rows=(),
                results_version=0,
                summary_action_fp=None,
            )
        ),
        render_calculation=lambda **kwargs: events.append("calculation"),
        render_mode_selector=lambda **kwargs: (
            events.append("mode") or False
        ),
        render_batch=lambda **kwargs: events.append("batch"),
        render_design_guide=lambda **kwargs: events.append("design_guide"),
        render_widgets=lambda **kwargs: (
            events.append("widgets") or False
        ),
        render_divider=lambda: events.append("divider"),
    )
    page_context = {
        "sync_callbacks": {},
        "mark": lambda *args, **kwargs: None,
        "pre_widget_trace": lambda *args, **kwargs: None,
        "beam_labels": {},
        "beam_order": [],
        "active_beam_id": None,
        "inputs_render_audit": {},
        "fast_focus_section": None,
        "fast_get_param": lambda *args, **kwargs: None,
        "corrected_invalid_shear_state": False,
        "sub_mark": lambda *args, **kwargs: None,
    }
    render_engineering_workspace(
        st_module=fake,
        runtime=runtime,
        page_context=page_context,
    )
    assert events[:4] == [
        "reconcile",
        "refresh",
        "summary",
        "calculation",
    ], events
    assert fake.session_state[
        "_inputs_workspace_pre_authority_reconciled_keys"
    ] == ["uls_Vstar"]
    print("engineering workspace pre-authority reconciliation contract PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
