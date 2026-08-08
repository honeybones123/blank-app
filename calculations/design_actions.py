from __future__ import annotations

from typing import Any, Mapping

from application.contracts.design_actions import (
    DESIGN_ACTIONS_SNAPSHOT_SCHEMA_VERSION,
    DesignActionsSnapshot,
)


RESOLVED_DESIGN_ACTIONS_SCHEMA_VERSION = DESIGN_ACTIONS_SNAPSHOT_SCHEMA_VERSION
ResolvedDesignActions = DesignActionsSnapshot


def _state_read_mapping(source_state):
    return source_state if hasattr(source_state, "get") else {}


def _state_working_dict(source_state) -> dict:
    if isinstance(source_state, dict):
        return dict(source_state)
    if hasattr(source_state, "items"):
        return dict(source_state.items())
    if hasattr(source_state, "keys") and hasattr(source_state, "get"):
        return {key: source_state.get(key) for key in source_state.keys()}
    return {}


def resolve_design_actions_from_state(source_state: dict | None) -> dict:
    """Resolve canonical design actions from an explicit state mapping."""
    state = _state_read_mapping(source_state)
    actions_source = str(state.get("actions_source") or "")
    actions_mode = str(state.get("actions_mode") or "")
    if (
        str(state.get("actions_mode") or "").strip().lower() == "manual"
        or str(state.get("actions_source") or "").strip()
        == "Manual design actions (inputs below)"
    ):
        Mu_signed_fallback = float(state.get("uls_Mstar", 0.0) or 0.0)
        Mu_pos = float(
            state.get(
                "uls_Mstar_pos_manual",
                state.get("Mu_star_pos_manual", max(0.0, Mu_signed_fallback)),
            )
            or 0.0
        )
        Mu_neg = float(
            state.get(
                "uls_Mstar_neg_manual",
                state.get("Mu_star_neg_manual", max(0.0, -Mu_signed_fallback)),
            )
            or 0.0
        )
        Mu_pos = max(0.0, Mu_pos)
        Mu_neg = max(0.0, Mu_neg)
        Mu_signed = Mu_pos - Mu_neg
        Mu = float(max(Mu_pos, Mu_neg))
        Vu = float(state.get("uls_Vstar", 0.0) or 0.0)
        Nu = float(state.get("uls_Nstar", 0.0) or 0.0)
        SLS_M_signed_fallback = float(state.get("sls_Mstar", 0.0) or 0.0)
        SLS_M_pos = float(
            state.get("sls_Mstar_pos_manual", max(0.0, SLS_M_signed_fallback))
            or 0.0
        )
        SLS_M_neg = float(
            state.get("sls_Mstar_neg_manual", max(0.0, -SLS_M_signed_fallback))
            or 0.0
        )
        SLS_M_pos = max(0.0, SLS_M_pos)
        SLS_M_neg = max(0.0, SLS_M_neg)
        SLS_M_signed = SLS_M_pos - SLS_M_neg
        SLS_M = float(max(SLS_M_pos, SLS_M_neg))
        SLS_V = float(state.get("sls_Vstar", 0.0) or 0.0)
        assert abs(Vu - float(state.get("uls_Vstar", 0.0) or 0.0)) < 1e-9
        assert abs(Nu - float(state.get("uls_Nstar", 0.0) or 0.0)) < 1e-9

        return {
            "Mu": Mu,
            "Mu_signed": Mu_signed,
            "Mu_pos": Mu_pos,
            "Mu_neg": Mu_neg,
            "has_sagging_case": Mu_pos > 1e-9,
            "has_hogging_case": Mu_neg > 1e-9,
            "Vu": Vu,
            "Nu": Nu,
            "SLS_M": SLS_M,
            "SLS_M_signed": SLS_M_signed,
            "SLS_M_pos": SLS_M_pos,
            "SLS_M_neg": SLS_M_neg,
            "SLS_V": SLS_V,
            "Tu": float(state.get("Tu_star", 0.0) or 0.0),
            "Pu": float(state.get("P_star", 0.0) or 0.0),
            "source": "manual_uls",
            "actions_source": str(state.get("actions_source") or ""),
            "actions_mode": str(state.get("actions_mode") or ""),
            "signature": (
                Mu,
                Vu,
                Nu,
                SLS_M,
                SLS_V,
                "manual_uls",
                str(state.get("actions_source") or ""),
                str(state.get("actions_mode") or ""),
            ),
        }

    design_source = str(state.get("design_actions_source") or "max")
    if design_source == "section":
        Mu_signed = float(
            state.get(
                "design_M_uls_kNm_signed",
                state.get("design_M_uls_kNm", state.get("Mu_star", 0.0)),
            )
            or 0.0
        )
        Mu_pos = max(0.0, Mu_signed)
        Mu_neg = max(0.0, -Mu_signed)
        Mu = float(max(Mu_pos, Mu_neg))
        Vu = float(state.get("design_V_uls_kN", state.get("Vu_star", 0.0)) or 0.0)
        SLS_M_signed = float(
            state.get(
                "design_M_sls_kNm_signed",
                state.get("design_M_sls_kNm", state.get("sls_Mstar", 0.0)),
            )
            or 0.0
        )
        SLS_M_pos = max(0.0, SLS_M_signed)
        SLS_M_neg = max(0.0, -SLS_M_signed)
        SLS_M = float(max(SLS_M_pos, SLS_M_neg))
        SLS_V = float(state.get("design_V_sls_kN", state.get("sls_Vstar", 0.0)) or 0.0)
    else:
        Mu_pos = float(
            state.get(
                "M_pos_max_uls_kNm",
                state.get("uls_Mstar_pos_manual", state.get("Mu_star_pos_manual", 0.0)),
            )
            or 0.0
        )
        Mu_neg = float(
            abs(
                min(
                    0.0,
                    float(
                        state.get(
                            "M_neg_min_uls_kNm",
                            -float(
                                state.get(
                                    "uls_Mstar_neg_manual",
                                    state.get("Mu_star_neg_manual", 0.0),
                                )
                                or 0.0
                            ),
                        )
                        or 0.0
                    ),
                )
            )
        )
        if abs(Mu_pos) <= 1e-9 and abs(Mu_neg) <= 1e-9:
            Mu_pos = float(
                state.get(
                    "uls_Mstar_pos_manual",
                    state.get("Mu_star_pos_manual", 0.0),
                )
                or 0.0
            )
            Mu_neg = float(
                state.get(
                    "uls_Mstar_neg_manual",
                    state.get("Mu_star_neg_manual", 0.0),
                )
                or 0.0
            )
        Mu_abs_raw = state.get("sfd_Mmax_abs_kNm", None)
        Mu_from_extremes = float(max(Mu_pos, Mu_neg))
        Mu = float(
            Mu_abs_raw
            if Mu_abs_raw not in (None, "")
            else state.get("Mu_star", 0.0) or 0.0
        )
        if abs(Mu) <= 1e-9 and Mu_from_extremes > 1e-9:
            Mu = Mu_from_extremes
        Mu_signed = float(Mu_pos) if Mu_pos >= Mu_neg else -float(Mu_neg)
        Vu = float(state.get("sfd_Vmax_abs_kN", state.get("Vu_star", 0.0)) or 0.0)
        SLS_M_pos = float(state.get("M_pos_max_sls_kNm", 0.0) or 0.0)
        SLS_M_neg = float(abs(min(0.0, float(state.get("M_neg_min_sls_kNm", 0.0) or 0.0))))
        SLS_M_abs_raw = state.get("sfd_Msls_max_kNm", None)
        SLS_M_from_extremes = float(max(SLS_M_pos, SLS_M_neg))
        SLS_M = float(
            SLS_M_abs_raw
            if SLS_M_abs_raw not in (None, "")
            else state.get("sls_Mstar", 0.0) or 0.0
        )
        if abs(SLS_M) <= 1e-9 and SLS_M_from_extremes > 1e-9:
            SLS_M = SLS_M_from_extremes
        SLS_M_signed = float(SLS_M_pos) if SLS_M_pos >= SLS_M_neg else -float(SLS_M_neg)
        SLS_V = float(state.get("sfd_Vsls_max_kN", state.get("sls_Vstar", 0.0)) or 0.0)
    Nu = float(state.get("Nu_star", state.get("N_star", state.get("uls_Nstar", 0.0))) or 0.0)

    actions = {
        "Mu": float(Mu),
        "Mu_signed": float(Mu_signed),
        "Mu_pos": float(Mu_pos),
        "Mu_neg": float(Mu_neg),
        "has_sagging_case": float(Mu_pos) > 1e-9,
        "has_hogging_case": float(Mu_neg) > 1e-9,
        "Vu": float(Vu),
        "Nu": float(Nu),
        "SLS_M": float(SLS_M),
        "SLS_M_signed": float(SLS_M_signed),
        "SLS_M_pos": float(SLS_M_pos),
        "SLS_M_neg": float(SLS_M_neg),
        "SLS_V": float(SLS_V),
        "Tu": float(state.get("Tu_star", 0.0) or 0.0),
        "Pu": float(state.get("P_star", 0.0) or 0.0),
        "source": "design",
        "actions_source": actions_source,
        "actions_mode": actions_mode,
    }
    actions["signature"] = (
        actions["Mu"],
        actions["Vu"],
        actions["Nu"],
        actions["SLS_M"],
        actions["SLS_V"],
        actions["source"],
        actions["actions_source"],
        actions["actions_mode"],
    )
    return actions


def resolve_design_actions_contract_from_state(
    source_state: Mapping[str, Any] | None,
) -> ResolvedDesignActions:
    """Resolve one immutable contract from an explicit state mapping."""

    working = _state_working_dict(source_state)
    if not str(working.get("actions_mode") or "").strip():
        working["actions_mode"] = "manual"
    actions = resolve_design_actions_from_state(working)
    return ResolvedDesignActions(
        mu=float(actions.get("Mu", 0.0) or 0.0),
        mu_signed=float(actions.get("Mu_signed", actions.get("Mu", 0.0)) or 0.0),
        mu_pos=float(actions.get("Mu_pos", 0.0) or 0.0),
        mu_neg=float(actions.get("Mu_neg", 0.0) or 0.0),
        has_sagging_case=bool(actions.get("has_sagging_case", False)),
        has_hogging_case=bool(actions.get("has_hogging_case", False)),
        vu=float(actions.get("Vu", 0.0) or 0.0),
        nu=float(actions.get("Nu", 0.0) or 0.0),
        sls_m=float(actions.get("SLS_M", 0.0) or 0.0),
        sls_m_signed=float(
            actions.get("SLS_M_signed", actions.get("SLS_M", 0.0)) or 0.0
        ),
        sls_m_pos=float(actions.get("SLS_M_pos", 0.0) or 0.0),
        sls_m_neg=float(actions.get("SLS_M_neg", 0.0) or 0.0),
        sls_v=float(actions.get("SLS_V", 0.0) or 0.0),
        sls_n=float(working.get("sls_Nstar", actions.get("Nu", 0.0)) or 0.0),
        tu=float(actions.get("Tu", 0.0) or 0.0),
        pu=float(actions.get("Pu", 0.0) or 0.0),
        source=str(actions.get("source") or ""),
        actions_source=str(actions.get("actions_source") or ""),
        actions_mode=str(actions.get("actions_mode") or ""),
        design_actions_source=str(working.get("design_actions_source") or "max"),
        sls_line_load=float(working.get("w_sls_kNm_per_m", 0.0) or 0.0),
        sls_point_load=float(working.get("P_sls_kN", 0.0) or 0.0),
    )


def derive_design_action_session_updates(source_state: dict | None) -> dict:
    """
    Calculate the session-state writes performed by derive_design_actions().

    The returned mapping preserves the legacy write contract; callers still own
    applying these values to their session state.
    """
    state = _state_read_mapping(source_state)
    working = _state_working_dict(state)
    updates: dict[str, float] = {}

    raw_mode = working.get("actions_mode", "manual")
    actions_mode = str(raw_mode or "manual").strip().lower()
    if actions_mode not in ("manual", "design"):
        actions_mode = "manual"

    if actions_mode == "design":
        source = working.get("design_actions_source", "max")
        if source == "section":
            uls_M_signed = float(
                working.get(
                    "design_M_uls_kNm_signed",
                    working.get("design_M_uls_kNm", 0.0),
                )
                or 0.0
            )
            uls_pos = max(0.0, uls_M_signed)
            uls_neg = max(0.0, -uls_M_signed)
            uls_V = float(working.get("design_V_uls_kN", 0.0) or 0.0)
            sls_M_signed = float(
                working.get(
                    "design_M_sls_kNm_signed",
                    working.get("design_M_sls_kNm", 0.0),
                )
                or 0.0
            )
            sls_pos = max(0.0, sls_M_signed)
            sls_neg = max(0.0, -sls_M_signed)
            sls_V = float(working.get("design_V_sls_kN", 0.0) or 0.0)
        else:
            uls_pos = float(
                working.get(
                    "M_pos_max_uls_kNm",
                    working.get(
                        "uls_Mstar_pos_manual",
                        working.get("Mu_star_pos_manual", 0.0),
                    ),
                )
                or 0.0
            )
            uls_neg = float(
                abs(
                    min(
                        0.0,
                        float(
                            working.get(
                                "M_neg_min_uls_kNm",
                                -float(
                                    working.get(
                                        "uls_Mstar_neg_manual",
                                        working.get("Mu_star_neg_manual", 0.0),
                                    )
                                    or 0.0
                                ),
                            )
                            or 0.0
                        ),
                    )
                )
            )
            if abs(uls_pos) <= 1e-9 and abs(uls_neg) <= 1e-9:
                uls_pos = float(
                    working.get(
                        "uls_Mstar_pos_manual",
                        working.get("Mu_star_pos_manual", 0.0),
                    )
                    or 0.0
                )
                uls_neg = float(
                    working.get(
                        "uls_Mstar_neg_manual",
                        working.get("Mu_star_neg_manual", 0.0),
                    )
                    or 0.0
                )
            uls_M_signed = uls_pos if uls_pos >= uls_neg else -uls_neg
            uls_V = float(working.get("sfd_Vmax_abs_kN", 0.0) or 0.0)
            sls_pos = float(working.get("M_pos_max_sls_kNm", 0.0) or 0.0)
            sls_neg = float(abs(min(0.0, float(working.get("M_neg_min_sls_kNm", 0.0) or 0.0))))
            sls_M_signed = sls_pos if sls_pos >= sls_neg else -sls_neg
            sls_V = float(working.get("sfd_Vsls_max_kN", 0.0) or 0.0)

        shared_N = float(working.get("N_star", 0.0) or 0.0)
        updates.update(
            {
                "uls_Mstar": float(uls_M_signed),
                "uls_Mstar_pos_manual": float(max(0.0, uls_pos)),
                "uls_Mstar_neg_manual": float(max(0.0, uls_neg)),
                "uls_Vstar": float(uls_V),
                "uls_Nstar": shared_N,
                "sls_Mstar": float(sls_M_signed),
                "sls_Mstar_pos_manual": float(max(0.0, sls_pos)),
                "sls_Mstar_neg_manual": float(max(0.0, sls_neg)),
                "sls_Vstar": float(sls_V),
                "sls_Nstar": shared_N,
            }
        )
        working.update(updates)

    actions = resolve_design_actions_from_state(working)
    updates.update(
        {
            "Mu_star_manual": float(working.get("uls_Mstar", 0.0) or 0.0),
            "Mu_star_pos_manual": float(
                working.get(
                    "uls_Mstar_pos_manual",
                    max(0.0, working.get("uls_Mstar", 0.0) or 0.0),
                )
                or 0.0
            ),
            "Mu_star_neg_manual": float(
                working.get(
                    "uls_Mstar_neg_manual",
                    max(0.0, -(working.get("uls_Mstar", 0.0) or 0.0)),
                )
                or 0.0
            ),
            "Mu_star": float(actions["Mu"]),
            "Mu_star_kNm": float(actions["Mu"]),
            "Mu_star_kNm_signed": float(actions.get("Mu_signed", actions["Mu"])),
            "Vu_star": float(actions["Vu"]),
            "N_star": float(actions["Nu"]),
        }
    )
    return updates


__all__ = [
    "RESOLVED_DESIGN_ACTIONS_SCHEMA_VERSION",
    "ResolvedDesignActions",
    "derive_design_action_session_updates",
    "resolve_design_actions_contract_from_state",
    "resolve_design_actions_from_state",
]
