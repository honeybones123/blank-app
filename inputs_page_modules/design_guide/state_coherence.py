"""Design Guide state/coherence helper projections.

These helpers are exact page-extracted utilities used by the remaining Inputs
Design Guide compute coordinator. They hold no page rendering authority.
"""

from __future__ import annotations

from typing import Any

from state_and_helpers import effective_depth_with_links_mm


def _canonical_pack_is_valid(pack: dict | None) -> bool:
    p = dict(pack or {})
    if "canonical_pack_valid" in p:
        return bool(p.get("canonical_pack_valid"))
    return bool(p.get("canonical_pack_built", False))


def _design_state_coherence_check(state: dict) -> dict:
    """Compact coherence checker for raw vs derived/resolved reinforcement state."""
    s = dict(state or {})
    hard_invalid_issues: list[str] = []
    soft_mismatch_issues: list[str] = []

    def _append_issue(bucket: list[str], issue: str | None) -> None:
        label = str(issue or "").strip()
        if label and label not in bucket:
            bucket.append(label)

    canonical_pack_error = str(s.get("canonical_pack_error") or "").strip()
    if "canonical_pack_valid" in s and not _canonical_pack_is_valid(s):
        _append_issue(hard_invalid_issues, canonical_pack_error or "canonical_pack_invalid")
    elif canonical_pack_error:
        _append_issue(hard_invalid_issues, canonical_pack_error)

    positive_required_fields = (
        ("b", "missing_or_invalid_b"),
        ("D", "missing_or_invalid_D"),
        ("fc", "missing_or_invalid_fc"),
        ("fsy", "missing_or_invalid_fsy"),
    )
    for field_name, issue_name in positive_required_fields:
        try:
            field_value = float(s.get(field_name, 0.0) or 0.0)
        except (TypeError, ValueError):
            field_value = 0.0
        if field_value <= 0.0:
            _append_issue(hard_invalid_issues, issue_name)

    nonnegative_required_fields = (
        ("cover_top", "negative_cover_top"),
        ("cover_bot", "negative_cover_bot"),
        ("lig_d", "negative_lig_d"),
    )
    for field_name, issue_name in nonnegative_required_fields:
        try:
            field_value = float(s.get(field_name, 0.0) or 0.0)
        except (TypeError, ValueError):
            field_value = 0.0
        if field_value < 0.0:
            _append_issue(hard_invalid_issues, issue_name)

    raw_bottom_signature = {
        "bot1_count": int(s.get("bot1_count", 0) or 0),
        "bot2_count": int(s.get("bot2_count", 0) or 0),
        "db_bot_1": float(s.get("db_bot_1", 0.0) or 0.0),
        "db_bot_2": float(s.get("db_bot_2", s.get("db_bot_1", 0.0)) or 0.0),
        "raw_total_bars": int(s.get("bot1_count", 0) or 0) + int(s.get("bot2_count", 0) or 0),
    }
    raw_top_signature = {
        "top1_count": int(s.get("top1_count", 0) or 0),
        "top2_count": int(s.get("top2_count", 0) or 0),
        "db_top_1": float(s.get("db_top_1", 0.0) or 0.0),
        "db_top_2": float(s.get("db_top_2", s.get("db_top_1", 0.0)) or 0.0),
        "raw_total_bars": int(s.get("top1_count", 0) or 0) + int(s.get("top2_count", 0) or 0),
    }
    bot_rows = list(s.get("bot_rows_resolved") or [])
    top_rows = list(s.get("top_rows_resolved") or [])
    resolved_total = int(sum(int((r or {}).get("bar_count_resolved", 0) or 0) for r in bot_rows))
    resolved_top_total = int(sum(int((r or {}).get("bar_count_resolved", 0) or 0) for r in top_rows))
    resolved_bottom_signature = {
        "resolved_total_bars": resolved_total,
        "resolved_dias": [
            float((r or {}).get("dia", 0.0) or 0.0)
            for r in bot_rows
            if int((r or {}).get("bar_count_resolved", 0) or 0) > 0
        ],
        "Ast_bot": float(s.get("Ast_bot", 0.0) or 0.0),
    }
    resolved_top_signature = {
        "resolved_total_bars": resolved_top_total,
        "resolved_dias": [
            float((r or {}).get("dia", 0.0) or 0.0)
            for r in top_rows
            if int((r or {}).get("bar_count_resolved", 0) or 0) > 0
        ],
        "Ast_top": float(s.get("Ast_top", 0.0) or 0.0),
    }
    is_canonical_state = bool(s.get("canonical_pack_built")) or ("canonical_pack_valid" in s) or bool(canonical_pack_error)
    if is_canonical_state:
        has_any_resolved_bars = bool(
            list(s.get("resolved_longitudinal_bars") or [])
            or resolved_total > 0
            or resolved_top_total > 0
        )
        if not has_any_resolved_bars:
            _append_issue(hard_invalid_issues, "no_bars_resolved")
    if raw_bottom_signature["raw_total_bars"] > 0 and resolved_total != raw_bottom_signature["raw_total_bars"]:
        _append_issue(soft_mismatch_issues, "bottom_bar_count_mismatch_raw_vs_resolved")
    if raw_top_signature["raw_total_bars"] > 0 and resolved_top_total != raw_top_signature["raw_total_bars"]:
        _append_issue(soft_mismatch_issues, "top_bar_count_mismatch_raw_vs_resolved")
    bars = list(s.get("resolved_longitudinal_bars") or [])
    bottom_bars = [bar for bar in bars if str(bar.get("face")) == "bottom"]
    top_bars = [bar for bar in bars if str(bar.get("face")) == "top"]
    resolved_ast = float(sum(float(bar.get("area_mm2", 0.0) or 0.0) for bar in bottom_bars))
    resolved_ast_top = float(sum(float(bar.get("area_mm2", 0.0) or 0.0) for bar in top_bars))
    if bottom_bars and abs(float(s.get("Ast_bot", 0.0) or 0.0) - resolved_ast) > 1e-3:
        _append_issue(soft_mismatch_issues, "Ast_bot_mismatch_vs_resolved_longitudinal_bars")
    if top_bars and abs(float(s.get("Ast_top", 0.0) or 0.0) - resolved_ast_top) > 1e-3:
        _append_issue(soft_mismatch_issues, "Ast_top_mismatch_vs_resolved_longitudinal_bars")
    if bars and bot_rows and resolved_total != len(bottom_bars):
        _append_issue(soft_mismatch_issues, "resolved_longitudinal_bars_mismatch_vs_row_model")
    if bars and top_rows and resolved_top_total != len(top_bars):
        _append_issue(soft_mismatch_issues, "resolved_top_longitudinal_bars_mismatch_vs_row_model")
    expected_d = effective_depth_with_links_mm(
        D_mm=float(s.get("D", 0.0) or 0.0),
        cover_to_ligs_mm=float(s.get("cover_bot", 0.0) or 0.0),
        lig_diameter_mm=float(s.get("lig_d", 0.0) or 0.0),
        bar_diameter_mm=float(s.get("db_bot_1", 0.0) or 0.0),
    )
    try:
        actual_d = float(s.get("d", 0.0) or 0.0)
    except (TypeError, ValueError):
        actual_d = 0.0
    if actual_d <= 0.0:
        _append_issue(hard_invalid_issues, "missing_or_invalid_effective_depth_d")
    if abs(actual_d - expected_d) > 1.0:
        _append_issue(soft_mismatch_issues, "effective_depth_d_inconsistent")
    D = float(s.get("D", 0.0) or 0.0)
    primary_top_y = next((float((r or {}).get("y_position", 0.0) or 0.0) for r in top_rows if (r or {}).get("active")), None)
    if primary_top_y is not None:
        expected_do = float(D - primary_top_y)
    else:
        expected_do = float(D - float(s.get("cover_top", 0.0) or 0.0) - float(s.get("db_top_1", 0.0) or 0.0) / 2.0)
    try:
        actual_do = float(s.get("do", 0.0) or 0.0)
    except (TypeError, ValueError):
        actual_do = 0.0
    if actual_do <= 0.0:
        _append_issue(hard_invalid_issues, "missing_or_invalid_do")
    if abs(actual_do - expected_do) > 1.0:
        _append_issue(soft_mismatch_issues, "do_inconsistent")
    issues = list(hard_invalid_issues) + list(soft_mismatch_issues)
    return {
        "coherence_ok": len(issues) == 0,
        "issues": issues,
        "hard_invalid_issues": list(hard_invalid_issues),
        "soft_mismatch_issues": list(soft_mismatch_issues),
        "coherence_blocking_issues": list(hard_invalid_issues),
        "coherence_nonblocking_issues": list(soft_mismatch_issues),
        "coherence_should_block": len(hard_invalid_issues) > 0,
        "state_coherence_warning": len(soft_mismatch_issues) > 0,
        "state_coherence_warning_issues": list(soft_mismatch_issues),
        "raw_bottom_signature": raw_bottom_signature,
        "resolved_bottom_signature": resolved_bottom_signature,
        "raw_top_signature": raw_top_signature,
        "resolved_top_signature": resolved_top_signature,
    }


def _coherence_debug_fields(coherence: dict | None) -> dict[str, Any]:
    c = dict(coherence or {})
    blocking_issues = list(c.get("coherence_blocking_issues") or [])
    nonblocking_issues = list(c.get("coherence_nonblocking_issues") or [])
    should_block = bool(c.get("coherence_should_block"))
    return {
        "state_coherence_ok": bool(c.get("coherence_ok")),
        "state_coherence_issues": list(c.get("issues") or []),
        "hard_invalid_issues": list(c.get("hard_invalid_issues") or blocking_issues),
        "soft_mismatch_issues": list(c.get("soft_mismatch_issues") or nonblocking_issues),
        "coherence_blocking_issues": blocking_issues,
        "coherence_nonblocking_issues": nonblocking_issues,
        "coherence_should_block": should_block,
        "state_coherence_warning": bool(nonblocking_issues),
        "state_coherence_warning_issues": list(c.get("state_coherence_warning_issues") or nonblocking_issues),
        "blocked_state_class": "hard_invalid" if should_block else None,
        "raw_bottom_signature": dict(c.get("raw_bottom_signature") or {}),
        "resolved_bottom_signature": dict(c.get("resolved_bottom_signature") or {}),
        "raw_top_signature": dict(c.get("raw_top_signature") or {}),
        "resolved_top_signature": dict(c.get("resolved_top_signature") or {}),
    }


__all__ = [
    "_canonical_pack_is_valid",
    "_coherence_debug_fields",
    "_design_state_coherence_check",
]
