"""Focused structural and transaction proof for typed popover recommendation Apply."""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs_application.popover_recommendation_apply import (  # noqa: E402
    execute_popover_recommendation_apply,
    plan_popover_recommendation_mutation,
)


def main() -> int:
    bottom = {
        "arrangement": {
            "bot1_count": 4,
            "bot2_count": 2,
            "db_bot_1": 20,
            "db_bot_2": 16,
        }
    }
    bottom_mutation = plan_popover_recommendation_mutation(bottom, kind="bottom")
    geometry_mutation = plan_popover_recommendation_mutation(
        {"updates": {"D": 650.0, "_debug": "drop"}},
        kind="geometry",
    )
    empty_mutation = plan_popover_recommendation_mutation(None, kind="shear")

    session: dict = {}
    writes: list[tuple[str, object, str]] = []
    publishes: list[dict] = []
    invalidations: list[dict] = []
    reruns: list[bool] = []

    def set_shared(key, value, *, source):
        session[key] = value
        writes.append((key, value, source))

    applied = execute_popover_recommendation_apply(
        kind="shear",
        source="fast_mode:shear_recommendation",
        session_state=session,
        recommendation={"updates": {"lig_d": 12, "lig_legs": 2, "s_lig": 150.0}},
        set_shared=set_shared,
        finalize_publish=lambda **kwargs: publishes.append(dict(kwargs)),
        persist_active_beam=lambda: session.__setitem__(
            "persisted_lig_d", session["lig_d"]
        ),
        invalidate_caches=lambda **kwargs: invalidations.append(dict(kwargs)),
        rerun=lambda: reruns.append(True),
    )

    route_text = (
        ROOT / "inputs_application" / "page_runtime" / "widgets.py"
    ).read_text(encoding="utf-8")
    panel_text = (ROOT / "inputs_page_modules" / "recommendation_panels.py").read_text(
        encoding="utf-8"
    )
    checks = {
        "bottom_projection_matches_legacy_contract": bottom_mutation.updates
        == {
            "bot1_layout_mode": "Count",
            "bot1_count": 4,
            "db_bot_1": 20,
            "bot2_layout_mode": "Count",
            "bot2_count": 2,
            "db_bot_2": 16,
            "bot_row_count": 2,
            "bot_row_1_mode": "Count",
            "bot_row_1_bars": 4,
            "bot_row_1_spacing": 0.0,
            "bot_row_1_dia": 20,
            "bot_row_2_mode": "Count",
            "bot_row_2_bars": 2,
            "bot_row_2_spacing": 0.0,
            "bot_row_2_dia": 16,
        },
        "private_updates_filtered": geometry_mutation.updates == {"D": 650.0},
        "empty_recommendation_fails_closed": empty_mutation.status == "failed",
        "typed_commit_applied": applied
        and session.get("lig_d") == 12
        and session.get("lig_legs") == 2
        and session.get("s_lig") == 150.0
        and session.get("persisted_lig_d") == 12,
        "canonical_writer_used": len(writes) == 3
        and all(row[2] == "fast_mode:shear_recommendation" for row in writes),
        "popover_does_not_claim_primary_post_apply_acceptance": (
            "_typed_inputs_post_apply_acceptance_fp" not in session
        ),
        "publish_invalidate_rerun_order_surfaces_present": len(publishes) == 1
        and len(invalidations) == 1
        and reruns == [True],
        "route_has_no_legacy_apply_callbacks": all(
            token not in route_text
            for token in (
                "_legacy_inputs_page._apply_bottom_reo_recommendation",
                "_legacy_inputs_page._apply_shear_recommendation",
                "_legacy_inputs_page._apply_geometry_recommendation",
            )
        ),
        "panels_apply_displayed_recommendation": panel_text.count(
            "recommendation=recommendation, source=source"
        )
        == 3,
    }
    result = {
        "contract_version": "inputs_popover_recommendation_apply_cutover.v1",
        "checks": checks,
        "status": "PASS" if all(checks.values()) else "FAIL",
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
