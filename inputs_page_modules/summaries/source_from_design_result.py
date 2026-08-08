"""Shared summary projection from one authoritative Design Brain result."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from application.contracts.design_actions import DesignActionsSnapshot
from application.contracts.design_brain import AuthoritativeDesignResult
from inputs_page_modules.summaries.models import (
    InputsSummaryCardSource,
    InputsSummarySourceSnapshot,
)
from inputs_page_modules.summaries.rows_from_packs import (
    render_inputs_summary_rows_from_packs,
)


@dataclass(frozen=True)
class DesignResultSummaryProjection:
    source: InputsSummarySourceSnapshot
    rows_by_family: dict[str, tuple[dict[str, Any], ...]]


def _primary_row(rows, *, preferred_title: str = "") -> dict[str, Any]:
    materialised = [dict(row) for row in rows]
    preferred = str(preferred_title or "").strip().lower()
    return next(
        (
            row
            for row in materialised
            if preferred and preferred in str(row.get("title") or "").lower()
        ),
        next(
            (row for row in materialised if row.get("is_primary")),
            next(
                (row for row in materialised if not row.get("is_informational")),
                {},
            ),
        ),
    )


def _card(
    *,
    family: str,
    title: str,
    rows,
    capacity_label: str,
    action_label: str,
    preferred_title: str = "",
) -> InputsSummaryCardSource:
    materialised = tuple(dict(row) for row in rows)
    primary = _primary_row(materialised, preferred_title=preferred_title)
    return InputsSummaryCardSource(
        family=family,
        title=title,
        capacity=str(primary.get("capacity") or primary.get("limit") or "—"),
        action=str(primary.get("action") or primary.get("value") or "—"),
        utilisation=str(primary.get("util") or "—"),
        status=str(primary.get("status") or "INFO"),
        rows=materialised,
        capacity_label=capacity_label,
        action_label=action_label,
    )


def build_summary_source_from_design_result(
    *,
    result: AuthoritativeDesignResult,
    actions: DesignActionsSnapshot,
    st_module,
    scenario_id: str,
    scenario_label: str,
) -> DesignResultSummaryProjection:
    """Project cards and detail rows without recalculating engineering truth."""

    packs = dict(result.current_calculations or {}).get("packs", {})
    bend_pack = dict(packs.get("bending") or {})
    shear_pack = dict(packs.get("shear") or {})
    crack_pack = dict(packs.get("crack") or {})
    defl_pack = dict(packs.get("deflection") or {})
    bending, shear, crack, deflection, *_ = render_inputs_summary_rows_from_packs(
        st_module=st_module,
        bend_pack=bend_pack or None,
        shear_pack=shear_pack or None,
        crack_pack=crack_pack or None,
        defl_pack=defl_pack or None,
    )
    rows_by_family = {
        "bending": tuple(dict(row) for row in bending),
        "shear": tuple(dict(row) for row in shear),
        "crack": tuple(dict(row) for row in crack),
        "deflection": tuple(dict(row) for row in deflection),
    }
    source = InputsSummarySourceSnapshot(
        scenario_id=str(scenario_id),
        scenario_label=str(scenario_label),
        bending=_card(
            family="bending",
            title="Bending &mdash; ULS check",
            rows=rows_by_family["bending"],
            capacity_label="Calculated capacity",
            action_label="Applied design action",
        ),
        shear=_card(
            family="shear",
            title="Shear &mdash; ULS check",
            rows=rows_by_family["shear"],
            capacity_label="Calculated capacity",
            action_label="Applied design action",
        ),
        crack=_card(
            family="crack",
            title="Crack control &mdash; SLS check",
            rows=rows_by_family["crack"],
            capacity_label="Allowable limit",
            action_label="Calculated crack width",
            preferred_title="Direct crack width check",
        ),
        deflection=_card(
            family="deflection",
            title="Deflection &mdash; SLS check",
            rows=rows_by_family["deflection"],
            capacity_label="Allowable limit",
            action_label="Calculated deflection",
        ),
        geometry={},
        actions=actions.to_legacy_mapping(),
        run_state={
            "source": "authoritative_design_result",
            "engineering_hash": result.engineering_hash,
        },
    )
    return DesignResultSummaryProjection(source=source, rows_by_family=rows_by_family)


__all__ = [
    "DesignResultSummaryProjection",
    "build_summary_source_from_design_result",
]
