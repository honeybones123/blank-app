"""Independent Design Guide blocker truth probes.

These helpers are intentionally verifier-side: they do not change solver
maths, formulas, target bands, or app ranking.  They build small executor-shaped
candidate inventories from the browser/current state and evaluate them through
the app's existing candidate preview path.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _float_or_none(value: Any) -> float | None:
    try:
        if value is None:
            return None
        out = float(value)
        if not math.isfinite(out):
            return None
        return out
    except Exception:
        return None


def _int_or_none(value: Any) -> int | None:
    out = _float_or_none(value)
    return int(round(out)) if out is not None else None


def _state_from_browser(browser_state: dict[str, Any] | None) -> dict[str, Any]:
    browser_state = browser_state if isinstance(browser_state, dict) else {}
    state: dict[str, Any] = {}
    for source_name in (
        "browser_recipe_applied_state",
        "browser_shared_probe",
        "summary_state_probe",
        "active_beam_record_probe",
    ):
        source = browser_state.get(source_name)
        if isinstance(source, dict):
            state.update(
                {
                    key: value
                    for key, value in source.items()
                    if value is not None and not str(key).startswith("_")
                }
            )
    return state


def _overview(browser_state: dict[str, Any] | None) -> dict[str, Any]:
    browser_state = browser_state if isinstance(browser_state, dict) else {}
    return dict(
        browser_state.get("summary_overview_probe")
        or browser_state.get("browser_overview_support")
        or {}
    )


def _status_failures(overview: dict[str, Any]) -> list[str]:
    statuses = dict(overview.get("statuses") or {})
    return [
        str(family)
        for family, status in statuses.items()
        if str(status or "").strip().upper() == "FAIL"
    ]


def _failed_subchecks(overview: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for key in ("checks", "check_results", "required_checks", "subchecks", "details"):
        value = overview.get(key)
        rows: list[Any]
        if isinstance(value, dict):
            rows = list(value.values())
        elif isinstance(value, list):
            rows = list(value)
        else:
            rows = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            status = str(row.get("status") or row.get("result") or "").strip().upper()
            util = _float_or_none(row.get("util") or row.get("utilisation") or row.get("ratio"))
            failed = status == "FAIL" or (util is not None and util > 1.0 + 1e-9)
            if failed:
                out.append(
                    {
                        "name": row.get("name") or row.get("check") or row.get("label"),
                        "family": row.get("family") or row.get("check_key"),
                        "status": status or None,
                        "util": util,
                        "demand": row.get("demand") or row.get("demand_label"),
                        "capacity_or_limit": row.get("capacity") or row.get("limit") or row.get("capacity_or_limit"),
                    }
                )
    return out


def _evaluate_updates(base_state: dict[str, Any], updates: dict[str, Any], *, candidate_id: str, family: str, kind: str) -> dict[str, Any]:
    import inputs_page as app  # noqa: WPS433 - lazy import keeps tool startup light.

    candidate_state = dict(base_state)
    candidate_state.update(dict(updates))
    row: dict[str, Any] = {
        "candidate_id": candidate_id,
        "candidate_type": kind,
        "family": family,
        "updates": dict(updates),
        "executor_backed": True,
    }
    try:
        evaluated = app.evaluate_candidate_full(candidate_state, source=f"blocker_truth_probe:{kind}:{family}")
        ov = dict((evaluated or {}).get("overview") or {})
        utils = dict(ov.get("utils") or {})
        statuses = dict(ov.get("statuses") or {})
        all_pass = bool(ov.get("all_key_pass")) and not bool(ov.get("any_fail"))
        failures = _status_failures(ov)
        subchecks = _failed_subchecks(ov)
        row.update(
            {
                "bending_util": _float_or_none(utils.get("bending")),
                "shear_util": _float_or_none(utils.get("shear")),
                "crack_util": _float_or_none(utils.get("crack")),
                "deflection_util": _float_or_none(utils.get("deflection")),
                "statuses": statuses,
                "all_required_checks_pass": bool(all_pass),
                "failed_family": failures[0] if failures else None,
                "failed_check": failures[0] if failures else (subchecks[0].get("name") if subchecks else None),
                "failed_subchecks": subchecks,
                "failed_value": subchecks[0].get("util") if subchecks else None,
                "failed_limit_or_capacity": subchecks[0].get("capacity_or_limit") if subchecks else None,
            }
        )
    except Exception as exc:
        row.update({"error": f"{type(exc).__name__}: {exc}", "all_required_checks_pass": False})
    return row


def _bar_diameters() -> list[int]:
    return [10, 12, 16, 20, 24, 28, 32, 36, 40]


def _link_diameters() -> list[int]:
    return [10, 12, 16, 20]


def _unique_update_rows(rows: list[tuple[str, str, dict[str, Any]]]) -> list[tuple[str, str, dict[str, Any]]]:
    seen: set[tuple[tuple[str, str], ...]] = set()
    out: list[tuple[str, str, dict[str, Any]]] = []
    for family, label, updates in rows:
        key = tuple(sorted((str(k), repr(v)) for k, v in dict(updates).items()))
        if key in seen:
            continue
        seen.add(key)
        out.append((family, label, dict(updates)))
    return out


def build_bending_repair_candidates(state: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    rows: list[tuple[str, str, dict[str, Any]]] = []
    count = _int_or_none(state.get("bot1_count") or state.get("bot_row_1_bars")) or 0
    dia = _int_or_none(state.get("db_bot_1") or state.get("bot_row_1_dia")) or 0
    depth = _float_or_none(state.get("D")) or 0.0
    width = _float_or_none(state.get("b") or state.get("bw")) or 0.0
    for new_count in range(max(count + 1, 2), 9):
        rows.append(("bending", f"bottom_count_{new_count}", {"bot1_count": new_count, "bot_row_1_bars": new_count}))
    for new_dia in _bar_diameters():
        if new_dia > dia:
            rows.append(("bending", f"bottom_dia_{new_dia}", {"db_bot_1": new_dia, "bot_row_1_dia": new_dia}))
    if count > 0 and dia > 0:
        rows.append(
            (
                "bending",
                "add_second_bottom_row",
                {
                    "bot_row_count": 2,
                    "bot2_count": max(2, min(count, 4)),
                    "bot_row_2_bars": max(2, min(count, 4)),
                    "db_bot_2": dia,
                    "bot_row_2_dia": dia,
                },
            )
        )
    for new_depth in (depth + 50, depth + 100, depth + 150, depth + 200, depth + 300):
        if new_depth > depth:
            rows.append(("geometry", f"depth_{int(new_depth)}", {"D": float(new_depth)}))
    for new_width in (width + 50, width + 100, width + 150, width + 200):
        if new_width > width:
            rows.append(("geometry", f"width_{int(new_width)}", {"b": float(new_width), "bw": float(new_width)}))
    return _unique_update_rows(rows)


def build_shear_repair_candidates(state: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    rows: list[tuple[str, str, dict[str, Any]]] = []
    lig_d = _int_or_none(state.get("lig_d")) or 0
    legs = _int_or_none(state.get("lig_legs")) or 0
    spacing = _float_or_none(state.get("s_lig")) or 200.0
    depth = _float_or_none(state.get("D")) or 0.0
    width = _float_or_none(state.get("b") or state.get("bw")) or 0.0
    if lig_d <= 0 or legs <= 0:
        rows.append(("shear", "turn_links_on", {"lig_d": 10, "lig_legs": 2, "s_lig": min(spacing, 200.0)}))
    for new_d in _link_diameters():
        if new_d > lig_d:
            rows.append(("shear", f"link_dia_{new_d}", {"lig_d": new_d, "lig_legs": max(legs, 2), "s_lig": spacing}))
    for new_legs in (2, 3, 4, 6, 8):
        if new_legs > legs:
            rows.append(("shear", f"link_legs_{new_legs}", {"lig_d": max(lig_d, 10), "lig_legs": new_legs, "s_lig": spacing}))
    for new_spacing in (300, 250, 200, 175, 150, 125, 100, 75):
        if new_spacing < spacing or lig_d <= 0 or legs <= 0:
            rows.append(("shear", f"spacing_{new_spacing}", {"lig_d": max(lig_d, 10), "lig_legs": max(legs, 2), "s_lig": float(new_spacing)}))
    for new_depth in (depth + 50, depth + 100, depth + 150, depth + 200, depth + 300):
        if new_depth > depth:
            rows.append(("geometry", f"depth_shear_{int(new_depth)}", {"D": float(new_depth)}))
    for new_width in (width + 50, width + 100, width + 150, width + 200):
        if new_width > width:
            rows.append(("geometry", f"width_shear_{int(new_width)}", {"b": float(new_width), "bw": float(new_width)}))
    return _unique_update_rows(rows)


def build_combined_repair_candidates(state: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    bending = build_bending_repair_candidates(state)[:12]
    shear = build_shear_repair_candidates(state)[:16]
    rows: list[tuple[str, str, dict[str, Any]]] = []
    for _, bend_label, bend_updates in bending:
        for _, shear_label, shear_updates in shear:
            updates = dict(bend_updates)
            updates.update(shear_updates)
            rows.append(("combined", f"{bend_label}+{shear_label}", updates))
    return _unique_update_rows(rows)


def build_bending_cleanup_candidates(state: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    rows: list[tuple[str, str, dict[str, Any]]] = []
    count = _int_or_none(state.get("bot1_count") or state.get("bot_row_1_bars")) or 0
    dia = _int_or_none(state.get("db_bot_1") or state.get("bot_row_1_dia")) or 0
    for new_count in range(max(1, count - 1), 0, -1):
        if new_count < count:
            rows.append(("bending", f"bottom_count_{new_count}", {"bot1_count": new_count, "bot_row_1_bars": new_count}))
    for new_dia in reversed(_bar_diameters()):
        if 0 < new_dia < dia:
            rows.append(("bending", f"bottom_dia_{new_dia}", {"db_bot_1": new_dia, "bot_row_1_dia": new_dia}))
    if (_int_or_none(state.get("bot2_count") or state.get("bot_row_2_bars")) or 0) > 0:
        rows.append(("bending", "remove_second_bottom_row", {"bot2_count": 0, "bot_row_2_bars": 0, "bot_row_count": 1}))
    return _unique_update_rows(rows)


def build_shear_cleanup_candidates(state: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    rows: list[tuple[str, str, dict[str, Any]]] = []
    lig_d = _int_or_none(state.get("lig_d")) or 0
    legs = _int_or_none(state.get("lig_legs")) or 0
    spacing = _float_or_none(state.get("s_lig")) or 200.0
    if lig_d > 0 and legs > 0:
        for new_spacing in (spacing + 25, spacing + 50, 200, 250, 300, 400):
            if new_spacing > spacing:
                rows.append(("shear", f"spacing_{int(new_spacing)}", {"s_lig": float(new_spacing)}))
        for new_d in reversed(_link_diameters()):
            if 0 < new_d < lig_d:
                rows.append(("shear", f"link_dia_{new_d}", {"lig_d": new_d}))
        for new_legs in (legs - 1, legs - 2, 2):
            if 0 < new_legs < legs:
                rows.append(("shear", f"link_legs_{new_legs}", {"lig_legs": int(new_legs)}))
        rows.append(("shear", "remove_links", {"lig_d": 0, "lig_legs": 0}))
    return _unique_update_rows(rows)


def _evaluate_inventory(state: dict[str, Any], rows: list[tuple[str, str, dict[str, Any]]], *, kind: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for family, label, updates in rows:
        out.append(
            _evaluate_updates(
                state,
                updates,
                candidate_id=f"{kind}:{family}:{label}",
                family=family,
                kind=kind,
            )
        )
    return out


def probe_active_fail_repair_truth(browser_state: dict[str, Any] | None, summary: dict[str, Any] | None = None) -> dict[str, Any]:
    state = _state_from_browser(browser_state)
    rows = _evaluate_inventory(
        state,
        build_bending_repair_candidates(state)
        + build_shear_repair_candidates(state)
        + build_combined_repair_candidates(state),
        kind="repair",
    )
    passing = [row for row in rows if bool(row.get("all_required_checks_pass")) and bool(row.get("executor_backed"))]
    return {
        "probe_type": "active_fail_repair_truth",
        "candidate_count": len(rows),
        "passing_candidate_count": len(passing),
        "passing_candidates": passing[:12],
        "best_passing_candidate": passing[0] if passing else None,
        "candidate_rows": rows[:120],
    }


def probe_overdesign_cleanup_truth(browser_state: dict[str, Any] | None, summary: dict[str, Any] | None = None) -> dict[str, Any]:
    state = _state_from_browser(browser_state)
    ov = _overview(browser_state)
    utils = dict(ov.get("utils") or {})
    current_bending = _float_or_none(utils.get("bending"))
    current_shear = _float_or_none(utils.get("shear"))
    rows = _evaluate_inventory(
        state,
        build_bending_cleanup_candidates(state) + build_shear_cleanup_candidates(state),
        kind="cleanup",
    )
    improving: list[dict[str, Any]] = []
    for row in rows:
        if not bool(row.get("all_required_checks_pass")):
            continue
        family = str(row.get("family") or "")
        util_key = "bending_util" if family == "bending" else "shear_util" if family == "shear" else None
        before = current_bending if family == "bending" else current_shear if family == "shear" else None
        after = _float_or_none(row.get(util_key)) if util_key else None
        if before is not None and after is not None and after > before + 1e-6:
            row = dict(row)
            row["improves_utilisation"] = True
            improving.append(row)
    return {
        "probe_type": "overdesign_cleanup_truth",
        "candidate_count": len(rows),
        "safe_improving_candidate_count": len(improving),
        "safe_improving_candidates": improving[:12],
        "best_safe_improving_candidate": improving[0] if improving else None,
        "candidate_rows": rows[:120],
    }


def probe_green_secondary_blocker_truth(browser_state: dict[str, Any] | None, summary: dict[str, Any] | None = None) -> dict[str, Any]:
    cleanup = probe_overdesign_cleanup_truth(browser_state, summary)
    return {
        "probe_type": "green_secondary_blocker_truth",
        **cleanup,
    }


def blocker_family_util_mismatches(browser_state: dict[str, Any] | None, blockers: dict[str, Any] | None) -> list[dict[str, Any]]:
    ov = _overview(browser_state)
    utils = dict(ov.get("utils") or {})
    blockers = blockers if isinstance(blockers, dict) else {}
    out: list[dict[str, Any]] = []
    for family in ("bending", "shear"):
        blocker = blockers.get(family)
        if not isinstance(blocker, dict):
            continue
        truth = _float_or_none(utils.get(family))
        if truth is None:
            continue
        for field in ("current_util",):
            value = _float_or_none(blocker.get(field))
            if value is not None and abs(value - truth) > 0.03:
                out.append({"family": family, "field": field, "value": value, "truth": truth})
        failed_util = _float_or_none(blocker.get("failed_check_util"))
        failed_name = str(blocker.get("failed_check_name") or "").lower()
        if failed_util is not None and family in failed_name and abs(failed_util - truth) > 0.25:
            out.append({"family": family, "field": "failed_check_util", "value": failed_util, "truth": truth})
    return out

