from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs_page_modules.design_guide.apply_trace_session import (  # noqa: E402
    DESIGN_GUIDE_APPLY_TRACE_RUN_ID_KEY,
    begin_design_guide_apply_trace,
    end_design_guide_apply_trace,
    set_design_guide_live_breadcrumb,
)
from inputs_page_app_contracts import DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY  # noqa: E402


def main() -> int:
    session: dict = {}
    set_design_guide_live_breadcrumb(session, "apply_clicked", {"candidate": "c1"})
    assert DESIGN_GUIDE_APPLY_TRACE_RUN_ID_KEY == "_design_guide_apply_trace_run_id"
    assert session["_dg_live_breadcrumb"]["label"] == "apply_clicked"
    assert session["_dg_live_breadcrumb"]["extra"] == {"candidate": "c1"}
    assert session["_dg_live_breadcrumb"]["ts"]

    events: list[dict] = []

    def append_trace(event: str, data: dict, **meta) -> None:
        events.append({"event": event, "data": dict(data), **dict(meta)})

    begin_design_guide_apply_trace(
        session,
        recommendation={
            "action_type": "apply_resolved_candidate",
            "title": "Apply recommendation",
        },
        source="primary_apply_button",
        append_trace=append_trace,
    )
    session[DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY] = {
        "typed_apply_canonical_candidate_preverified": True,
        "post_apply_all_key_pass": True,
        "post_apply_any_fail": False,
        "payload_binding_match": True,
        "payload_update_match": True,
        "applied_updates": {"D": 470.0, "canonical_alias": 1},
        "post_apply_preview_worst_util": 0.93,
    }
    end_design_guide_apply_trace(
        session,
        stop_reason="typed_apply_committed",
        final_updates={"D": 470.0},
        winner_label="Apply recommendation",
        append_trace=append_trace,
    )
    run_end = events[-1]
    assert run_end["event"] == "run_end"
    assert run_end["data"]["status"] == "pass"
    assert run_end["data"]["all_key_pass"] is True
    assert run_end["data"]["final_live_worst_util"] == 0.93
    assert run_end["data"]["post_commit_live_statuses"] == {
        "canonical_candidate_preverified": "PASS"
    }
    assert run_end["data"]["typed_apply_commit_proof"]["proven"] is True
    assert run_end["data"]["last_apply_route"]["applied_updates"] == {
        "D": 470.0,
        "canonical_alias": 1,
    }
    print("inputs Apply trace session contract PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
