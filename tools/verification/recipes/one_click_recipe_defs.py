"""Shared frozen recipe definitions for one-click regression tooling.

This module is intentionally dependency-light so both the solver harness and
dev-only browser tooling can consume the exact same frozen recipes.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from optimisation_config import get_target_utilisation_band

_TARGET_LOW, _TARGET_HIGH = get_target_utilisation_band("balanced")
TARGET_BAND = {"min": _TARGET_LOW, "max": _TARGET_HIGH}


def _manual_actions(mu: float, vu: float) -> dict[str, Any]:
    return {
        "uls_Mstar": float(mu),
        "load_Mstar_proxy": float(mu),
        "load_Mstar_pos_proxy": float(mu),
        "uls_Mstar_pos_manual": float(mu),
        "uls_Mstar_neg_manual": 0.0,
        "Mu_star": float(mu),
        "Mu_star_manual": float(mu),
        "load_Mstar_neg_proxy": 0.0,
        "uls_Vstar": float(vu),
        "load_Vstar_proxy": float(vu),
        "Vu_star": float(vu),
        "Vu_star_manual": float(vu),
        "uls_Nstar": 0.0,
        "load_Nstar_proxy": 0.0,
        "N_star": 0.0,
        "sls_Mstar": 0.0,
        "sls_Vstar": 0.0,
        "sls_Nstar": 0.0,
    }


BASE_BEAM: dict[str, Any] = {
    "design_optimisation_goal": "balanced",
    "actions_mode": "manual",
    "actions_source": "Manual design actions (inputs below)",
    "design_actions_source": "max",
    "sec_shape": "RECT",
    "design_support_condition": "Simply supported",
    "design_beam_system_mode": "Single span",
    "span_L_m": 6.0,
    "b": 300.0,
    "bw": 300.0,
    "D": 400.0,
    "bf": 600.0,
    "tf": 120.0,
    "bf_bot": 600.0,
    "tf_bot": 120.0,
    "cover_top": 40.0,
    "cover_bot": 40.0,
    "cover_side": 40.0,
    "rowgap_top": 60.0,
    "rowgap_bot": 60.0,
    "fc": 40.0,
    "fsy": 500.0,
    "phi_bend": 0.85,
    "phi_shear": 0.75,
    "top1_count": 2,
    "db_top_1": 10.0,
    "top2_count": 0,
    "db_top_2": 0.0,
    "top_row_count": 1,
    "top_row_1_mode": "Count",
    "top_row_1_bars": 2,
    "top_row_1_spacing": 200.0,
    "top_row_1_dia": 10.0,
    "top_row_2_mode": "Count",
    "top_row_2_bars": 0,
    "top_row_2_spacing": 200.0,
    "top_row_2_dia": 10.0,
    "top1_layout_mode": "Count",
    "top2_layout_mode": "Count",
    "top1_spacing": 200.0,
    "top2_spacing": 200.0,
    "nb_top": 2,
    "db_top": 10.0,
    "top_entry": 2.0,
    "s_top": 0.0,
    "bot1_count": 4,
    "db_bot_1": 16.0,
    "bot2_count": 0,
    "db_bot_2": 0.0,
    "bot_row_count": 1,
    "bot_row_1_mode": "Count",
    "bot_row_1_bars": 4,
    "bot_row_1_spacing": 200.0,
    "bot_row_1_dia": 16.0,
    "bot_row_2_mode": "Count",
    "bot_row_2_bars": 0,
    "bot_row_2_spacing": 200.0,
    "bot_row_2_dia": 16.0,
    "bot1_layout_mode": "Count",
    "bot2_layout_mode": "Count",
    "bot1_spacing": 200.0,
    "bot2_spacing": 200.0,
    "nb_bot": 4,
    "db_bot": 16.0,
    "bot_entry": 4.0,
    "s_bot": 0.0,
    "lig_d": 10,
    "lig_legs": 2,
    "s_lig": 150.0,
    "shear_auto_design": False,
    "shear_optimize_reinforcement": False,
    "shear_zone_enabled": True,
    "loads_edit_mode": "ULS",
    **_manual_actions(0.0, 0.0),
}


FROZEN_RECIPES: list[dict[str, Any]] = [
    {
        "name": "R1_bending_under_only",
        "purpose": "Verify bending-only underdesign rescue lands the final governing utilisation inside the target band.",
        "clean_start_required": True,
        "subcases": [
            {"name": "R1A_M300_V0", "changes": _manual_actions(300.0, 0.0)},
            {"name": "R1B_M600_V0", "changes": _manual_actions(600.0, 0.0)},
        ],
        "expected_starting_condition": "Bending is the controlling failed domain; shear is not the reason optimisation is triggered.",
        "expected_optimisation_direction": "Strengthen bending only as needed and finish with the true governing utilisation in band.",
        "acceptable_stop_condition": "None unless a real enforced upper bound prevents valid rescue.",
        "must_not_happen": [
            "shear becomes a required target domain in a zero-shear case",
            "stale bending truth is published as final",
            "target-band success is claimed without final recompute",
        ],
    },
    {
        "name": "R2_shear_under_only",
        "purpose": "Verify shear-only underdesign rescue lands the final governing utilisation inside the target band.",
        "clean_start_required": True,
        "subcases": [
            {"name": "R2A_M0_V400", "changes": _manual_actions(0.0, 400.0)},
            {"name": "R2B_M0_V600", "changes": _manual_actions(0.0, 600.0)},
        ],
        "expected_starting_condition": "Shear is the controlling failed domain; bending is not the reason optimisation is triggered.",
        "expected_optimisation_direction": "Strengthen shear only as needed and finish with the true governing utilisation in band.",
        "acceptable_stop_condition": "None unless a real enforced upper bound prevents valid rescue.",
        "must_not_happen": [
            "bending becomes a required target domain in a zero-moment case",
            "stale shear truth is published as final",
            "detailed shear passes but the final state is still treated as failing",
        ],
    },
    {
        "name": "R3_combined_underdesign",
        "purpose": "Verify combined bending + shear underdesign is solved as a true combined problem.",
        "clean_start_required": True,
        "subcases": [
            {"name": "R3A_M300_V400", "changes": _manual_actions(300.0, 400.0)},
            {"name": "R3B_M600_V600", "changes": _manual_actions(600.0, 600.0)},
        ],
        "expected_starting_condition": "Both bending and shear are materially part of the governing picture.",
        "expected_optimisation_direction": "Recompute both domains and finish with the true governing utilisation in band.",
        "acceptable_stop_condition": "None unless a genuine enforced limit makes target unreachable.",
        "must_not_happen": [
            "bending is fixed while shear stays stale",
            "shear is fixed while bending stays stale",
            "single-domain truth is reported as the combined final result",
        ],
    },
    {
        "name": "R4_bending_overdesign",
        "purpose": "Verify bending-only overdesign optimisation returns toward the target band from a clean start.",
        "clean_start_required": True,
        "subcases": [
            {"name": "R4A_M45_V0", "changes": _manual_actions(45.0, 0.0)},
            {"name": "R4B_M55_V0", "changes": _manual_actions(55.0, 0.0)},
        ],
        "expected_starting_condition": "Bending is the controlling overdesigned domain; shear is not the optimisation driver.",
        "expected_optimisation_direction": "Reduce excess bending conservatism toward the target band.",
        "acceptable_stop_condition": "Only if further reduction would violate minimum beam/reo geometry or constructability rules already enforced.",
        "must_not_happen": [
            "shear is optimised instead of bending",
            "stale final bending value is reported as governing",
            "preview and committed truths diverge",
        ],
    },
    {
        "name": "R5_shear_overdesign",
        "purpose": "Verify shear-only overdesign optimisation returns toward the target band from a clean start.",
        "clean_start_required": True,
        "subcases": [
            {"name": "R5A_M0_V150", "changes": _manual_actions(0.0, 150.0)},
            {"name": "R5B_M0_V200", "changes": _manual_actions(0.0, 200.0)},
        ],
        "expected_starting_condition": "Shear is the controlling overdesigned domain; bending is not the optimisation driver.",
        "expected_optimisation_direction": "Reduce excess shear conservatism toward the target band.",
        "acceptable_stop_condition": "Only if minimum shear reinforcement/detailing/spacing-leg rules block further valid reduction.",
        "must_not_happen": [
            "bending is optimised instead of shear",
            "stale committed shear truth drives the result",
            "target-band success is claimed without post-commit shear recompute",
        ],
    },
    {
        "name": "R6_combined_overdesign",
        "purpose": "Verify combined overdesign optimisation reduces conservatism without solving the wrong domain.",
        "clean_start_required": True,
        "subcases": [
            {"name": "R6A_M45_V150", "changes": _manual_actions(45.0, 150.0)},
        ],
        "expected_starting_condition": "Combined overdesign with both bending and shear already passing below the target band.",
        "expected_optimisation_direction": "Reduce excess conservatism while keeping the true governing final value honest.",
        "acceptable_stop_condition": "Only if minimum shear detailing or minimum valid beam/reo rules block further valid reduction.",
        "must_not_happen": [
            "wrong-domain optimisation",
            "fake target-band success",
            "stale recommendation/card state diverging from committed truth",
        ],
    },
]


REGRESSION_CASES: list[dict[str, Any]] = [
    {"name": "A_bending_under_only", "changes": _manual_actions(300.0, 0.0)},
    {"name": "B_shear_under_only", "changes": _manual_actions(0.0, 400.0)},
    {"name": "C_combined_underdesign", "changes": _manual_actions(300.0, 400.0)},
    {"name": "D_bending_overdesign", "changes": _manual_actions(45.0, 0.0)},
    {"name": "E_shear_overdesign", "changes": _manual_actions(0.0, 150.0)},
    {"name": "F_combined_overdesign", "changes": _manual_actions(45.0, 150.0)},
]


DEBUG_CASES: list[dict[str, Any]] = [
    {
        "name": "SO_BASE_HEAVY_LINKS_CONSERVATIVE",
        "changes": {
            "b": 450.0,
            "bw": 450.0,
            "D": 500.0,
            "cover_top": 40.0,
            "cover_bot": 40.0,
            "cover_side": 40.0,
            "bot1_count": 4,
            "db_bot_1": 16.0,
            "bot_row_count": 1,
            "bot_row_1_bars": 4,
            "bot_row_1_dia": 16.0,
            "top1_count": 2,
            "db_top_1": 10.0,
            "top_row_count": 1,
            "top_row_1_bars": 2,
            "top_row_1_dia": 10.0,
            "lig_d": 24,
            "lig_legs": 4,
            "s_lig": 125.0,
            "actions_source": "Manual design actions (inputs below)",
            "actions_mode": "manual",
            **_manual_actions(0.0, 0.0),
        },
    },
    {
        "name": "BENDING_ONLY_OVERDESIGN_LOCKED_SHEAR_BASE",
        "changes": {
            "bot1_count": 5,
            "db_bot_1": 16.0,
            "bot_row_count": 1,
            "bot_row_1_bars": 5,
            "bot_row_1_dia": 16.0,
            "nb_bot": 5,
            "bot_entry": 5.0,
            "lig_d": 0,
            "lig_legs": 0,
            "s_lig": 0.0,
            "actions_source": "Manual design actions (inputs below)",
            "actions_mode": "manual",
            **_manual_actions(100.0, 0.0),
        },
    },
      {
          "name": "BENDING_LOW_SHEAR_IN_TARGET_TERMINAL_SNAPSHOT",
          "changes": {
            "b": 350.0,
            "bw": 350.0,
            "D": 420.0,
            "cover_top": 40.0,
            "cover_bot": 40.0,
            "cover_side": 40.0,
            "side_cover_bot": 40.0,
            "side_cover_top": 40.0,
            "bot1_layout_mode": "Count",
            "bot1_count": 5,
            "bot1_spacing": 200.0,
            "db_bot_1": 24.0,
            "bot2_layout_mode": "Count",
            "bot2_count": 0,
            "bot2_spacing": 200.0,
            "db_bot_2": 24.0,
            "bot_row_count": 1,
            "bot_row_1_mode": "Count",
            "bot_row_1_bars": 5,
            "bot_row_1_spacing": 0.0,
            "bot_row_1_dia": 24.0,
            "bot_row_2_mode": "Count",
            "bot_row_2_bars": 0,
            "bot_row_2_spacing": 0.0,
            "bot_row_2_dia": 24.0,
            "nb_or_s_bot_1": 5.0,
            "nb_or_s_bot_2": 0.0,
            "nb_bot": 5,
            "db_bot": 24.0,
            "bot_entry": 5.0,
            "top1_count": 2,
            "db_top_1": 10.0,
            "top_row_count": 1,
            "top_row_1_bars": 2,
            "top_row_1_dia": 10.0,
            "lig_d": 10,
            "lig_legs": 2,
            "s_lig": 300.0,
            "actions_source": "Manual design actions (inputs below)",
            "actions_mode": "manual",
              **_manual_actions(20.0, 200.0),
          },
      },
      {
          "name": "TERMINAL_EFFICIENT_NO_CLEANUP_SNAPSHOT",
          "changes": {
              "b": 375.0,
              "bw": 375.0,
              "D": 550.0,
              "cover_top": 40.0,
              "cover_bot": 40.0,
              "cover_side": 40.0,
              "side_cover_bot": 40.0,
              "side_cover_top": 40.0,
              "bot1_layout_mode": "Count",
              "bot1_count": 4,
              "bot1_spacing": 200.0,
              "db_bot_1": 24.0,
              "bot2_layout_mode": "Count",
              "bot2_count": 4,
              "bot2_spacing": 200.0,
              "db_bot_2": 24.0,
              "bot_row_count": 2,
              "bot_row_1_mode": "Count",
              "bot_row_1_bars": 4,
              "bot_row_1_spacing": 0.0,
              "bot_row_1_dia": 24.0,
              "bot_row_2_mode": "Count",
              "bot_row_2_bars": 4,
              "bot_row_2_spacing": 0.0,
              "bot_row_2_dia": 24.0,
              "nb_or_s_bot_1": 4.0,
              "nb_or_s_bot_2": 4.0,
              "nb_bot": 4,
              "db_bot": 24.0,
              "bot_entry": 4.0,
              "top1_count": 2,
              "db_top_1": 10.0,
              "top_row_count": 1,
              "top_row_1_bars": 2,
              "top_row_1_dia": 10.0,
              "lig_d": 0,
              "lig_legs": 0,
              "s_lig": 0.0,
              "actions_source": "Manual design actions (inputs below)",
              "actions_mode": "manual",
              **_manual_actions(600.0, 0.0),
          },
      },
      {
          "name": "TERMINAL_EXACT_STOP_PROVEN_SNAPSHOT",
          "changes": {
              "b": 375.0,
              "bw": 375.0,
              "D": 550.0,
              "cover_top": 40.0,
              "cover_bot": 40.0,
              "cover_side": 40.0,
              "side_cover_bot": 40.0,
              "side_cover_top": 40.0,
              "bot1_layout_mode": "Count",
              "bot1_count": 4,
              "bot1_spacing": 200.0,
              "db_bot_1": 24.0,
              "bot2_layout_mode": "Count",
              "bot2_count": 4,
              "bot2_spacing": 200.0,
              "db_bot_2": 24.0,
              "bot_row_count": 2,
              "bot_row_1_mode": "Count",
              "bot_row_1_bars": 4,
              "bot_row_1_spacing": 0.0,
              "bot_row_1_dia": 24.0,
              "bot_row_2_mode": "Count",
              "bot_row_2_bars": 4,
              "bot_row_2_spacing": 0.0,
              "bot_row_2_dia": 24.0,
              "nb_or_s_bot_1": 4.0,
              "nb_or_s_bot_2": 4.0,
              "nb_bot": 4,
              "db_bot": 24.0,
              "bot_entry": 4.0,
              "top1_count": 2,
              "db_top_1": 10.0,
              "top_row_count": 1,
              "top_row_1_bars": 2,
              "top_row_1_dia": 10.0,
              "lig_d": 0,
              "lig_legs": 0,
              "s_lig": 0.0,
              "exact_stop_available": True,
              "exact_stop_proven": True,
              "exact_stop_proof": {
                  "family_id": "EXACT_STOP_PROVEN",
                  "exact_stop_proven": True,
                  "target_band_reached": True,
                  "exhaustive_search_proven": True,
                  "repair_payload_available": False,
              },
              "actions_source": "Manual design actions (inputs below)",
              "actions_mode": "manual",
              **_manual_actions(600.0, 0.0),
          },
      },
      {
        "name": "BENDING_LOW_SHEAR_IN_TARGET_LOCAL_CLEANUP_SNAPSHOT",
        "changes": {
            "b": 350.0,
            "bw": 350.0,
            "D": 500.0,
            "cover_top": 40.0,
            "cover_bot": 40.0,
            "cover_side": 40.0,
            "side_cover_bot": 40.0,
            "side_cover_top": 40.0,
            "bot1_layout_mode": "Count",
            "bot1_count": 4,
            "bot1_spacing": 200.0,
            "db_bot_1": 28.0,
            "bot2_layout_mode": "Count",
            "bot2_count": 0,
            "bot2_spacing": 200.0,
            "db_bot_2": 28.0,
            "bot_row_count": 1,
            "bot_row_1_mode": "Count",
            "bot_row_1_bars": 4,
            "bot_row_1_spacing": 0.0,
            "bot_row_1_dia": 28.0,
            "bot_row_2_mode": "Count",
            "bot_row_2_bars": 0,
            "bot_row_2_spacing": 0.0,
            "bot_row_2_dia": 28.0,
            "nb_or_s_bot_1": 4.0,
            "nb_or_s_bot_2": 0.0,
            "nb_bot": 4,
            "db_bot": 28.0,
            "bot_entry": 4.0,
            "top1_count": 2,
            "db_top_1": 10.0,
            "top_row_count": 1,
            "top_row_1_bars": 2,
            "top_row_1_dia": 10.0,
            "lig_d": 10,
            "lig_legs": 2,
            "s_lig": 300.0,
            "actions_source": "Manual design actions (inputs below)",
            "actions_mode": "manual",
            **_manual_actions(100.0, 200.0),
        },
    },
    {
        "name": "SHEAR_LOW_BENDING_IN_TARGET_LOCAL_CLEANUP_SNAPSHOT",
        "changes": {
            "b": 350.0,
            "bw": 350.0,
            "D": 500.0,
            "cover_top": 40.0,
            "cover_bot": 40.0,
            "cover_side": 40.0,
            "side_cover_bot": 40.0,
            "side_cover_top": 40.0,
            "bot1_layout_mode": "Count",
            "bot1_count": 4,
            "bot1_spacing": 200.0,
            "db_bot_1": 28.0,
            "bot2_layout_mode": "Count",
            "bot2_count": 0,
            "bot2_spacing": 200.0,
            "db_bot_2": 28.0,
            "bot_row_count": 1,
            "bot_row_1_mode": "Count",
            "bot_row_1_bars": 4,
            "bot_row_1_spacing": 0.0,
            "bot_row_1_dia": 28.0,
            "bot_row_2_mode": "Count",
            "bot_row_2_bars": 0,
            "bot_row_2_spacing": 0.0,
            "bot_row_2_dia": 28.0,
            "nb_or_s_bot_1": 4.0,
            "nb_or_s_bot_2": 0.0,
            "nb_bot": 4,
            "db_bot": 28.0,
            "bot_entry": 4.0,
            "top1_count": 2,
            "db_top_1": 10.0,
            "top_row_count": 1,
            "top_row_1_bars": 2,
            "top_row_1_dia": 10.0,
            "lig_d": 16,
            "lig_legs": 4,
            "s_lig": 125.0,
            "actions_source": "Manual design actions (inputs below)",
            "actions_mode": "manual",
            **_manual_actions(360.0, 20.0),
        },
    },
    {
        "name": "SERVICEABILITY_LOW_BENDING_IN_TARGET_LOCAL_CLEANUP_SNAPSHOT",
        "changes": {
            "b": 350.0,
            "bw": 350.0,
            "D": 500.0,
            "cover_top": 40.0,
            "cover_bot": 40.0,
            "cover_side": 40.0,
            "side_cover_bot": 40.0,
            "side_cover_top": 40.0,
            "bot1_layout_mode": "Count",
            "bot1_count": 4,
            "bot1_spacing": 200.0,
            "db_bot_1": 28.0,
            "bot2_layout_mode": "Count",
            "bot2_count": 0,
            "bot2_spacing": 200.0,
            "db_bot_2": 28.0,
            "bot_row_count": 1,
            "bot_row_1_mode": "Count",
            "bot_row_1_bars": 4,
            "bot_row_1_spacing": 0.0,
            "bot_row_1_dia": 28.0,
            "bot_row_2_mode": "Count",
            "bot_row_2_bars": 0,
            "bot_row_2_spacing": 0.0,
            "bot_row_2_dia": 28.0,
            "nb_or_s_bot_1": 4.0,
            "nb_or_s_bot_2": 0.0,
            "nb_bot": 4,
            "db_bot": 28.0,
            "bot_entry": 4.0,
            "top1_count": 2,
            "db_top_1": 10.0,
            "top_row_count": 1,
            "top_row_1_bars": 2,
            "top_row_1_dia": 10.0,
            "lig_d": 10,
            "lig_legs": 2,
            "s_lig": 300.0,
            "actions_source": "Manual design actions (inputs below)",
            "actions_mode": "manual",
            **_manual_actions(360.0, 20.0),
        },
    },
    {
        "name": "GEOMETRY_LOW_REO_OR_SHEAR_IN_TARGET_LOCAL_CLEANUP_SNAPSHOT",
        "changes": {
            "b": 400.0,
            "bw": 400.0,
            "D": 560.0,
            "cover_top": 40.0,
            "cover_bot": 40.0,
            "cover_side": 40.0,
            "side_cover_bot": 40.0,
            "side_cover_top": 40.0,
            "bot1_layout_mode": "Count",
            "bot1_count": 4,
            "bot1_spacing": 200.0,
            "db_bot_1": 28.0,
            "bot2_layout_mode": "Count",
            "bot2_count": 0,
            "bot2_spacing": 200.0,
            "db_bot_2": 28.0,
            "bot_row_count": 1,
            "bot_row_1_mode": "Count",
            "bot_row_1_bars": 4,
            "bot_row_1_spacing": 0.0,
            "bot_row_1_dia": 28.0,
            "bot_row_2_mode": "Count",
            "bot_row_2_bars": 0,
            "bot_row_2_spacing": 0.0,
            "bot_row_2_dia": 28.0,
            "nb_or_s_bot_1": 4.0,
            "nb_or_s_bot_2": 0.0,
            "nb_bot": 4,
            "db_bot": 28.0,
            "bot_entry": 4.0,
            "top1_count": 2,
            "db_top_1": 10.0,
            "top_row_count": 1,
            "top_row_1_bars": 2,
            "top_row_1_dia": 10.0,
            "lig_d": 10,
            "lig_legs": 2,
            "s_lig": 300.0,
            "actions_source": "Manual design actions (inputs below)",
            "actions_mode": "manual",
            **_manual_actions(360.0, 20.0),
        },
    },
    {
        "name": "MANUAL_SCREENSHOT_BENDING_IN_BAND_SHEAR_LOW_AFTER_CLICK_SNAPSHOT",
        "changes": {
            "b": 250.0,
            "bw": 250.0,
            "D": 520.0,
            "cover_top": 40.0,
            "cover_bot": 40.0,
            "cover_side": 40.0,
            "side_cover_bot": 40.0,
            "side_cover_top": 40.0,
            "bot1_layout_mode": "Count",
            "bot1_count": 3,
            "bot1_spacing": 200.0,
            "db_bot_1": 20.0,
            "bot2_layout_mode": "Count",
            "bot2_count": 3,
            "bot2_spacing": 200.0,
            "db_bot_2": 20.0,
            "bot_row_count": 2,
            "bot_row_1_mode": "Count",
            "bot_row_1_bars": 3,
            "bot_row_1_spacing": 0.0,
            "bot_row_1_dia": 20.0,
            "bot_row_2_mode": "Count",
            "bot_row_2_bars": 3,
            "bot_row_2_spacing": 0.0,
            "bot_row_2_dia": 20.0,
            "nb_or_s_bot_1": 3.0,
            "nb_or_s_bot_2": 3.0,
            "nb_bot": 6,
            "db_bot": 20.0,
            "bot_entry": 3.0,
            "top1_count": 2,
            "db_top_1": 10.0,
            "top_row_count": 1,
            "top_row_1_bars": 2,
            "top_row_1_dia": 10.0,
            "lig_d": 16,
            "lig_legs": 4,
            "s_lig": 100.0,
            "actions_source": "Manual design actions (inputs below)",
            "actions_mode": "manual",
            **_manual_actions(300.0, 200.0),
        },
    },
    {
        "name": "CONTRACT_DIRECT_STATE_SEED",
        "changes": {
            "b": 250.0,
            "bw": 250.0,
            "D": 580.0,
            "cover_top": 40.0,
            "cover_bot": 40.0,
            "cover_side": 40.0,
            "bot1_layout_mode": "Count",
            "bot1_count": 2,
            "bot1_spacing": 200.0,
            "db_bot_1": 28.0,
            "bot2_layout_mode": "Count",
            "bot2_count": 0,
            "bot2_spacing": 200.0,
            "db_bot_2": 28.0,
            "bot_row_count": 1,
            "bot_row_1_mode": "Count",
            "bot_row_1_bars": 2,
            "bot_row_1_spacing": 0.0,
            "bot_row_1_dia": 28.0,
            "bot_row_2_mode": "Count",
            "bot_row_2_bars": 0,
            "bot_row_2_spacing": 0.0,
            "bot_row_2_dia": 28.0,
            "nb_or_s_bot_1": 2.0,
            "nb_or_s_bot_2": 0.0,
            "nb_bot": 2,
            "db_bot": 28.0,
            "bot_entry": 2.0,
            "top1_count": 2,
            "db_top_1": 10.0,
            "top_row_count": 1,
            "top_row_1_bars": 2,
            "top_row_1_dia": 10.0,
            "lig_d": 10,
            "lig_legs": 2,
            "s_lig": 75.0,
            "actions_source": "Manual design actions (inputs below)",
            "actions_mode": "manual",
            **_manual_actions(0.0, 0.0),
        },
    },
    {
        "name": "CONTRACT_DIRECT_STATE_SEED_H_ALREADY_EFFICIENT_BENDING",
        "changes": {
            "b": 250.0,
            "bw": 250.0,
            "D": 580.0,
            "cover_top": 40.0,
            "cover_bot": 40.0,
            "cover_side": 40.0,
            "bot1_layout_mode": "Count",
            "bot1_count": 2,
            "bot1_spacing": 200.0,
            "db_bot_1": 28.0,
            "bot2_layout_mode": "Count",
            "bot2_count": 0,
            "bot2_spacing": 200.0,
            "db_bot_2": 28.0,
            "bot_row_count": 1,
            "bot_row_1_mode": "Count",
            "bot_row_1_bars": 2,
            "bot_row_1_spacing": 0.0,
            "bot_row_1_dia": 28.0,
            "bot_row_2_mode": "Count",
            "bot_row_2_bars": 0,
            "bot_row_2_spacing": 0.0,
            "bot_row_2_dia": 28.0,
            "nb_or_s_bot_1": 2.0,
            "nb_or_s_bot_2": 0.0,
            "nb_bot": 2,
            "db_bot": 28.0,
            "bot_entry": 2.0,
            "top1_count": 2,
            "db_top_1": 10.0,
            "top_row_count": 1,
            "top_row_1_bars": 2,
            "top_row_1_dia": 10.0,
            "lig_d": 10,
            "lig_legs": 2,
            "s_lig": 75.0,
            "actions_source": "Manual design actions (inputs below)",
            "actions_mode": "manual",
            **_manual_actions(230.0, 0.0),
        },
    },
]


def _manual_actions_with_input_proxies(mu: float, vu: float) -> dict[str, Any]:
    actions = _manual_actions(mu, vu)
    actions.update(
        {
            "inputs_load_Mstar_pos_proxy": float(mu),
            "inputs_load_Mstar_neg_proxy": 0.0,
            "inputs_load_Vstar_proxy": float(vu),
        }
    )
    return actions


def _manual_actions_with_sls(mu: float, vu: float, sls_mu: float, sls_vu: float = 0.0) -> dict[str, Any]:
    actions = _manual_actions_with_input_proxies(mu, vu)
    actions.update(
        {
            "sls_Mstar": float(sls_mu),
            "sls_Mstar_pos_manual": max(0.0, float(sls_mu)),
            "sls_Mstar_neg_manual": max(0.0, -float(sls_mu)),
            "sls_Vstar": float(sls_vu),
        }
    )
    return actions


def _matrix_strength_serviceability_base(mu: float, vu: float, sls_mu: float, *, sls_vu: float = 0.0) -> dict[str, Any]:
    changes = {
        "b": 250.0,
        "bw": 250.0,
        "D": 320.0,
        "span_L_m": 7.5,
        "defl_limit_ratio": 500.0,
        "bot1_count": 2,
        "db_bot_1": 16.0,
        "bot_row_count": 1,
        "bot_row_1_bars": 2,
        "bot_row_1_dia": 16.0,
        "nb_bot": 2,
        "db_bot": 16.0,
        "bot_entry": 2.0,
        "lig_d": 10,
        "lig_legs": 2,
        "s_lig": 200.0,
    }
    changes.update(_manual_actions_with_sls(mu, vu, sls_mu, sls_vu))
    return changes


def _matrix_crack_only_fail_base() -> dict[str, Any]:
    changes = _matrix_strength_serviceability_base(80.0, 20.0, 500.0)
    changes.update(
        {
            "b": 450.0,
            "bw": 450.0,
            "D": 520.0,
            "bot1_count": 6,
            "db_bot_1": 20.0,
            "bot2_count": 6,
            "db_bot_2": 20.0,
            "bot_row_count": 2,
            "bot_row_1_bars": 6,
            "bot_row_1_dia": 20.0,
            "bot_row_2_bars": 6,
            "bot_row_2_dia": 20.0,
            "nb_bot": 12,
            "db_bot": 20.0,
            "bot_entry": 12.0,
        }
    )
    return changes


def _matrix_crack_serviceability_only_fail_base() -> dict[str, Any]:
    changes = _matrix_strength_serviceability_base(20.0, 10.0, 500.0)
    changes.update(
        {
            "b": 250.0,
            "bw": 250.0,
            "D": 350.0,
            "span_L_m": 8.0,
            "L": 8000.0,
            "defl_L_eff": 8.0,
            "defl_limit_ratio": 250.0,
            "fc": 40.0,
            "fsy": 500.0,
            "bot1_count": 6,
            "db_bot_1": 16.0,
            "bot2_count": 0,
            "db_bot_2": 16.0,
            "bot_row_count": 1,
            "bot_row_1_mode": "Count",
            "bot_row_1_bars": 6,
            "bot_row_1_dia": 16.0,
            "bot_row_2_mode": "Count",
            "bot_row_2_bars": 0,
            "bot_row_2_dia": 16.0,
            "nb_bot": 6,
            "db_bot": 16.0,
            "bot_entry": 6.0,
            "top1_count": 2,
            "db_top_1": 12.0,
            "top2_count": 0,
            "db_top_2": 0.0,
            "top_row_count": 1,
            "top_row_1_mode": "Count",
            "top_row_1_bars": 2,
            "top_row_1_dia": 12.0,
            "lig_d": 12,
            "lig_legs": 4,
            "s_lig": 150.0,
        }
    )
    return changes


def _matrix_deflection_only_fail_base(mu: float = 80.0, vu: float = 20.0) -> dict[str, Any]:
    changes = _matrix_strength_serviceability_base(mu, vu, 250.0)
    changes.update(
        {
            "b": 450.0,
            "bw": 450.0,
            "D": 520.0,
            "L": 20000.0,
            "span_L_m": 20.0,
            "defl_L_eff": 20.0,
            "defl_limit_ratio": 1000.0,
            "defl_support_type": "Simply supported",
            "g_udl_kNm_per_m": 5.0,
            "q_udl_kNm_per_m": 0.0,
            "w_sls_kNm_per_m": 5.0,
            "bot1_count": 6,
            "db_bot_1": 20.0,
            "bot2_count": 6,
            "db_bot_2": 20.0,
            "bot_row_count": 2,
            "bot_row_1_bars": 6,
            "bot_row_1_dia": 20.0,
            "bot_row_2_bars": 6,
            "bot_row_2_dia": 20.0,
            "nb_bot": 12,
            "db_bot": 20.0,
            "bot_entry": 12.0,
            "lig_d": 16,
            "lig_legs": 4,
            "s_lig": 125.0,
        }
    )
    return changes


def _golden_serviceability_blocked_base() -> dict[str, Any]:
    changes = _matrix_deflection_only_fail_base(190.0, 90.0)
    changes.update(
        {
            "sec_shape": "RECT",
            "optimisation_lock_geometry": True,
            "b": 250.0,
            "bw": 250.0,
            "D": 300.0,
            "L": 9000.0,
            "span_L_m": 9.0,
            "sfd_span_L_m": 9.0,
            "defl_L_eff": 9.0,
            "fc": 32.0,
            "fsy": 500.0,
            "bot1_count": 2,
            "db_bot_1": 12.0,
            "bot2_count": 0,
            "db_bot_2": 0.0,
            "bot_row_count": 1,
            "bot_row_1_bars": 2,
            "bot_row_1_dia": 12.0,
            "bot_row_2_bars": 0,
            "bot_row_2_dia": 12.0,
            "nb_bot": 2,
            "db_bot": 12.0,
            "bot_entry": 2.0,
            "top1_count": 2,
            "db_top_1": 10.0,
            "top2_count": 0,
            "db_top_2": 0.0,
            "top_row_count": 1,
            "top_row_1_bars": 2,
            "top_row_1_dia": 10.0,
            "top_row_2_bars": 0,
            "top_row_2_dia": 10.0,
            "nb_top": 2,
            "db_top": 10.0,
            "top_entry": 2.0,
            "lig_d": 10,
            "lig_legs": 2,
            "s_lig": 250.0,
        }
    )
    return changes


def _matrix_shear_and_crack_fail_base() -> dict[str, Any]:
    changes = _matrix_crack_only_fail_base()
    changes.update(_manual_actions_with_sls(80.0, 600.0, 500.0))
    changes.update(
        {
            "lig_d": 10,
            "lig_legs": 2,
            "s_lig": 300.0,
        }
    )
    return changes


def _matrix_bending_target_shear_fail_base() -> dict[str, Any]:
    changes = _matrix_strength_serviceability_base(300.0, 600.0, 0.0)
    changes.update(
        {
            "b": 450.0,
            "bw": 450.0,
            "D": 470.0,
            "bot1_count": 7,
            "db_bot_1": 20.0,
            "bot_row_count": 1,
            "bot_row_1_bars": 7,
            "bot_row_1_dia": 20.0,
            "nb_bot": 7,
            "db_bot": 20.0,
            "bot_entry": 7.0,
            "lig_d": 10,
            "lig_legs": 2,
            "s_lig": 300.0,
        }
    )
    return changes


def _matrix_shear_target_bending_low_base() -> dict[str, Any]:
    changes = _matrix_bending_target_shear_fail_base()
    changes.update(_manual_actions_with_input_proxies(120.0, 135.0))
    return changes


def _matrix_shear_safe_bending_fail_base() -> dict[str, Any]:
    return _so_base_heavy_links_with_actions(600.0, 1260.0)


def _so_base_heavy_links_with_actions(mu: float, vu: float) -> dict[str, Any]:
    changes = deepcopy(DEBUG_CASES[0]["changes"])
    changes.update(_manual_actions_with_input_proxies(mu, vu))
    return changes


def _base_with_active_links_and_actions(mu: float, vu: float) -> dict[str, Any]:
    changes = {
        "lig_d": 24,
        "lig_legs": 4,
        "s_lig": 125.0,
    }
    changes.update(_manual_actions_with_input_proxies(mu, vu))
    return changes


def _base_without_links_and_actions(mu: float, vu: float) -> dict[str, Any]:
    changes = {
        "lig_d": 0,
        "lig_legs": 0,
        "s_lig": 200.0,
    }
    changes.update(_manual_actions_with_input_proxies(mu, vu))
    return changes


def _bending_only_overdesign_locked_shear_base() -> dict[str, Any]:
    changes = {
        "bot1_count": 5,
        "db_bot_1": 16.0,
        "bot_row_count": 1,
        "bot_row_1_bars": 5,
        "bot_row_1_dia": 16.0,
        "nb_bot": 5,
        "bot_entry": 5.0,
        "lig_d": 0,
        "lig_legs": 0,
        "s_lig": 0.0,
    }
    changes.update(_manual_actions_with_input_proxies(100.0, 0.0))
    return changes


def _bending_overdesign_shear_probe_base(mu: float, vu: float) -> dict[str, Any]:
    changes = {
        "bot1_count": 5,
        "db_bot_1": 16.0,
        "bot_row_count": 1,
        "bot_row_1_bars": 5,
        "bot_row_1_dia": 16.0,
        "nb_bot": 5,
        "bot_entry": 5.0,
        "lig_d": 10,
        "lig_legs": 2,
        "s_lig": 150.0,
    }
    changes.update(_manual_actions_with_input_proxies(mu, vu))
    return changes


def _combined_safe_overdesigned_base(mu: float, vu: float) -> dict[str, Any]:
    changes = {
        "b": 350.0,
        "bw": 350.0,
        "D": 600.0,
        "cover_top": 40.0,
        "cover_bot": 40.0,
        "cover_side": 40.0,
        "fc": 40.0,
        "fsy": 500.0,
        "bot1_count": 6,
        "db_bot_1": 24.0,
        "bot2_count": 0,
        "db_bot_2": 24.0,
        "bot_row_count": 1,
        "bot_row_1_mode": "Count",
        "bot_row_1_bars": 6,
        "bot_row_1_spacing": 200.0,
        "bot_row_1_dia": 24.0,
        "bot_row_2_mode": "Count",
        "bot_row_2_bars": 0,
        "bot_row_2_spacing": 200.0,
        "bot_row_2_dia": 24.0,
        "nb_bot": 6,
        "db_bot": 24.0,
        "bot_entry": 6.0,
        "top1_count": 4,
        "db_top_1": 12.0,
        "top2_count": 0,
        "db_top_2": 12.0,
        "top_row_count": 1,
        "top_row_1_mode": "Count",
        "top_row_1_bars": 4,
        "top_row_1_spacing": 200.0,
        "top_row_1_dia": 12.0,
        "top_row_2_mode": "Count",
        "top_row_2_bars": 0,
        "top_row_2_spacing": 200.0,
        "top_row_2_dia": 12.0,
        "nb_top": 4,
        "db_top": 12.0,
        "top_entry": 4.0,
        "lig_d": 12,
        "lig_legs": 4,
        "s_lig": 150.0,
        "actions_source": "Manual design actions (inputs below)",
        "actions_mode": "manual",
    }
    changes.update(_manual_actions_with_input_proxies(mu, vu))
    return changes


DEBUG_CASES.extend(
    [
        {"name": "MATRIX_CRACK_ONLY_FAIL", "changes": _matrix_crack_only_fail_base()},
        {"name": "MATRIX_CRACK_SERVICEABILITY_ONLY_FAIL", "changes": _matrix_crack_serviceability_only_fail_base()},
        {"name": "MATRIX_DEFLECTION_ONLY_FAIL", "changes": _matrix_deflection_only_fail_base(80.0, 20.0)},
        {"name": "GOLDEN_SERVICEABILITY_BLOCKED", "changes": _golden_serviceability_blocked_base()},
        {"name": "MATRIX_BENDING_AND_CRACK_FAIL", "changes": _matrix_strength_serviceability_base(600.0, 20.0, 420.0)},
        {"name": "MATRIX_BENDING_AND_DEFLECTION_FAIL", "changes": _matrix_deflection_only_fail_base(650.0, 20.0)},
        {"name": "MATRIX_SHEAR_AND_CRACK_FAIL", "changes": _matrix_shear_and_crack_fail_base()},
        {"name": "MATRIX_SHEAR_AND_DEFLECTION_FAIL", "changes": _matrix_deflection_only_fail_base(80.0, 1400.0)},
        {"name": "MATRIX_CRACK_AND_DEFLECTION_FAIL", "changes": _matrix_deflection_only_fail_base(80.0, 20.0) | {"sls_Mstar": 500.0, "sls_Mstar_pos_manual": 500.0}},
        {"name": "MATRIX_OVERDESIGNED_STRENGTH_DEFLECTION_FAIL", "changes": _matrix_deflection_only_fail_base(80.0, 20.0)},
        {"name": "MATRIX_OVERDESIGNED_STRENGTH_CRACK_FAIL", "changes": _matrix_crack_only_fail_base()},
        {"name": "MATRIX_BENDING_OVERPROVIDED_DEFLECTION_FAIL", "changes": _matrix_deflection_only_fail_base(20.0, 120.0)},
        {"name": "MATRIX_SHEAR_OVERPROVIDED_DEFLECTION_FAIL", "changes": _matrix_deflection_only_fail_base(120.0, 20.0)},
        {"name": "MATRIX_BENDING_AND_SHEAR_SAFE_DEFLECTION_FAIL", "changes": _matrix_deflection_only_fail_base(120.0, 120.0)},
        {
            "name": "MATRIX_BENDING_SHEAR_SERVICEABILITY_FAIL",
            "changes": _matrix_deflection_only_fail_base(650.0, 1400.0) | {"sls_Mstar": 500.0, "sls_Mstar_pos_manual": 500.0},
        },
        {
            "name": "MATRIX_BENDING_IN_TARGET_SHEAR_FAIL",
            "changes": _matrix_bending_target_shear_fail_base(),
        },
        {
            "name": "SHEAR_TARGET_BENDING_LOW_NOT_ACCEPTED_SNAPSHOT",
            "changes": _matrix_shear_target_bending_low_base(),
        },
        {
            "name": "MATRIX_SHEAR_IN_TARGET_BENDING_FAIL",
            "changes": _matrix_shear_safe_bending_fail_base(),
        },
        {
            "name": "MATRIX_ACTIVE_FAILURE_TERMINAL_PROOF_PRESENT",
            "changes": _so_base_heavy_links_with_actions(600.0, 20.0),
        },
        {
            "name": "MATRIX_ACTIVE_FAILURE_CLEANUP_IDEA_PRESENT",
            "changes": _so_base_heavy_links_with_actions(600.0, 20.0),
        },
    ]
)


DEBUG_CASES.extend(
    [
        {
            "name": "OPT_EXPECT_BENDING_SAFE_OVERDESIGNED",
            "changes": _base_without_links_and_actions(45.0, 0.0),
        },
        {
            "name": "OPT_EXPECT_SHEAR_SAFE_OVERDESIGNED",
            "changes": _manual_actions_with_input_proxies(0.0, 150.0),
        },
        {
            "name": "OPT_EXPECT_COMBINED_SAFE_OVERDESIGNED",
            "changes": _combined_safe_overdesigned_base(55.0, 20.0),
        },
        {
            "name": "OPT_EXPECT_ALREADY_TARGET",
            "changes": _base_without_links_and_actions(100.0, 0.0),
        },
        {
            "name": "OPT_EXPECT_IN_BAND_ZERO_SHEAR_ACTIVE_LINKS",
            "changes": _base_with_active_links_and_actions(95.0, 0.0),
        },
        {
            "name": "ZERO_DEMAND_SHEAR_OVERPROVIDED_N10_3LEG_250",
            "changes": {
                "section_shape": "RECT",
                "b": 300.0,
                "bw": 300.0,
                "D": 500.0,
                "cover_top": 40.0,
                "cover_bot": 40.0,
                "cover_side": 40.0,
                "bot1_count": 3,
                "db_bot_1": 20.0,
                "bot_row_count": 1,
                "bot_row_1_bars": 3,
                "bot_row_1_dia": 20.0,
                "top1_count": 2,
                "db_top_1": 10.0,
                "top_row_count": 1,
                "top_row_1_bars": 2,
                "top_row_1_dia": 10.0,
                "lig_d": 10,
                "lig_legs": 3,
                "s_lig": 250.0,
                **_manual_actions_with_input_proxies(135.0, 0.0),
            },
        },
        {
            "name": "PRODUCT_KU_ONLY_DUCTILITY_FAIL",
            "changes": {
                "section_shape": "RECT",
                "sec_shape": "RECT",
                "b": 300.0,
                "bw": 300.0,
                "D": 300.0,
                "fc": 32.0,
                "fsy": 500.0,
                "cover_top": 40.0,
                "cover_bot": 40.0,
                "cover_side": 40.0,
                "lig_d": 0,
                "lig_legs": 0,
                "s_lig": 200.0,
                "bot1_count": 4,
                "db_bot_1": 20.0,
                "bot2_count": 0,
                "db_bot_2": 0.0,
                "bot_row_count": 1,
                "bot_row_1_bars": 4,
                "bot_row_1_dia": 20.0,
                "bot_row_2_bars": 0,
                "bot_row_2_dia": 0.0,
                "nb_bot": 4,
                "db_bot": 20.0,
                "bot_entry": 4.0,
                "top1_count": 2,
                "db_top_1": 10.0,
                "top_row_count": 1,
                "top_row_1_bars": 2,
                "top_row_1_dia": 10.0,
                **_manual_actions_with_input_proxies(50.0, 0.0),
            },
        },
        {
            "name": "PRODUCT_INVALID_LONGITUDINAL_REO_SPACING",
            "changes": {
                "section_shape": "RECT",
                "sec_shape": "RECT",
                "b": 200.0,
                "bw": 200.0,
                "D": 500.0,
                "fc": 40.0,
                "fsy": 500.0,
                "cover_top": 40.0,
                "cover_bot": 40.0,
                "cover_side": 40.0,
                "lig_d": 10,
                "lig_legs": 2,
                "s_lig": 200.0,
                "bot1_count": 6,
                "db_bot_1": 20.0,
                "bot2_count": 0,
                "db_bot_2": 0.0,
                "bot_row_count": 1,
                "bot_row_1_bars": 6,
                "bot_row_1_dia": 20.0,
                "bot_row_2_bars": 0,
                "bot_row_2_dia": 0.0,
                "nb_bot": 6,
                "db_bot": 20.0,
                "bot_entry": 6.0,
                "top1_count": 2,
                "db_top_1": 10.0,
                "top_row_count": 1,
                "top_row_1_bars": 2,
                "top_row_1_dia": 10.0,
                **_manual_actions_with_input_proxies(80.0, 40.0),
            },
        },
        {
            "name": "PRODUCT_INVALID_LONGITUDINAL_REO_SPACING_NO_ACTIONS",
            "changes": {
                "section_shape": "RECT",
                "sec_shape": "RECT",
                "b": 200.0,
                "bw": 200.0,
                "D": 500.0,
                "fc": 40.0,
                "fsy": 500.0,
                "cover_top": 40.0,
                "cover_bot": 40.0,
                "cover_side": 40.0,
                "lig_d": 10,
                "lig_legs": 2,
                "s_lig": 200.0,
                "bot1_count": 6,
                "db_bot_1": 20.0,
                "bot2_count": 0,
                "db_bot_2": 0.0,
                "bot_row_count": 1,
                "bot_row_1_bars": 6,
                "bot_row_1_dia": 20.0,
                "bot_row_2_bars": 0,
                "bot_row_2_dia": 0.0,
                "nb_bot": 6,
                "db_bot": 20.0,
                "bot_entry": 6.0,
                "top1_count": 2,
                "db_top_1": 10.0,
                "top_row_count": 1,
                "top_row_1_bars": 2,
                "top_row_1_dia": 10.0,
                **_manual_actions_with_input_proxies(0.0, 0.0),
            },
        },
        {
            "name": "PRODUCT_ZERO_VU_INVALID_PRESENT_SHEAR_LINKS",
            "changes": {
                "section_shape": "RECT",
                "sec_shape": "RECT",
                "b": 300.0,
                "bw": 300.0,
                "D": 500.0,
                "fc": 40.0,
                "fsy": 500.0,
                "cover_top": 40.0,
                "cover_bot": 40.0,
                "cover_side": 40.0,
                "bot1_count": 3,
                "db_bot_1": 20.0,
                "bot_row_count": 1,
                "bot_row_1_bars": 3,
                "bot_row_1_dia": 20.0,
                "top1_count": 2,
                "db_top_1": 10.0,
                "top_row_count": 1,
                "top_row_1_bars": 2,
                "top_row_1_dia": 10.0,
                "lig_d": 10,
                "lig_legs": 2,
                "s_lig": 1000.0,
                **_manual_actions_with_input_proxies(80.0, 0.0),
            },
        },
        {
            "name": "PRODUCT_LOCKED_GEOMETRY_LOW_BENDING_CLEANUP_PROOF",
            "changes": {
                "section_shape": "RECT",
                "sec_shape": "RECT",
                "optimisation_lock_geometry": True,
                "geometry_lock": True,
                "b": 350.0,
                "bw": 350.0,
                "D": 500.0,
                "fc": 40.0,
                "fsy": 500.0,
                "cover_top": 40.0,
                "cover_bot": 40.0,
                "cover_side": 40.0,
                "lig_d": 10,
                "lig_legs": 2,
                "s_lig": 200.0,
                "bot1_count": 6,
                "db_bot_1": 16.0,
                "bot2_count": 0,
                "db_bot_2": 0.0,
                "bot_row_count": 1,
                "bot_row_1_bars": 6,
                "bot_row_1_dia": 16.0,
                "bot_row_2_bars": 0,
                "bot_row_2_dia": 0.0,
                "nb_bot": 6,
                "db_bot": 16.0,
                "bot_entry": 6.0,
                "top1_count": 2,
                "db_top_1": 10.0,
                "top_row_count": 1,
                "top_row_1_bars": 2,
                "top_row_1_dia": 10.0,
                **_manual_actions_with_input_proxies(80.0, 80.0),
            },
        },
        {
            "name": "PRODUCT_LOCKED_NO_REPAIR_SHEAR_FAIL",
            "changes": {
                "section_shape": "RECT",
                "sec_shape": "RECT",
                "optimisation_lock_geometry": True,
                "inputs_optimisation_lock_geometry": True,
                "optimisation_lock_width": True,
                "inputs_optimisation_lock_width": True,
                "optimisation_lock_depth": True,
                "inputs_optimisation_lock_depth": True,
                "geometry_lock": True,
                "reinforcement_lock": True,
                "reo_locked": True,
                "shear_lock": True,
                "locked_no_repair": True,
                "locked_repair_blocked": True,
                "all_repair_paths_locked": True,
                "no_valid_repair_available": True,
                "repair_required": True,
                "b": 250.0,
                "bw": 250.0,
                "D": 350.0,
                "fc": 40.0,
                "fsy": 500.0,
                "cover_top": 40.0,
                "cover_bot": 40.0,
                "cover_side": 40.0,
                "lig_d": 10,
                "lig_legs": 2,
                "s_lig": 300.0,
                "bot1_count": 4,
                "db_bot_1": 16.0,
                "bot2_count": 0,
                "db_bot_2": 0.0,
                "bot_row_count": 1,
                "bot_row_1_bars": 4,
                "bot_row_1_dia": 16.0,
                "bot_row_2_bars": 0,
                "bot_row_2_dia": 0.0,
                "nb_bot": 4,
                "db_bot": 16.0,
                "bot_entry": 4.0,
                "top1_count": 2,
                "db_top_1": 10.0,
                "top_row_count": 1,
                "top_row_1_bars": 2,
                "top_row_1_dia": 10.0,
                **_manual_actions_with_input_proxies(0.0, 500.0),
            },
        },
        {
            "name": "OPT_EXPECT_IN_BAND_TINY_SHEAR_ACTIVE_LINKS",
            "changes": _base_with_active_links_and_actions(95.0, 10.0),
        },
        {
            "name": "OPT_EXPECT_MINIMUM_GEOMETRY_BLOCKED",
            "changes": _manual_actions_with_input_proxies(40.0, 0.0),
        },
    ]
)


def _live_fuzz_rect(
    *,
    mu: float,
    vu: float,
    b: float = 300.0,
    D: float = 400.0,
    bot_count: int = 4,
    bot_dia: float = 16.0,
    top_count: int = 2,
    top_dia: float = 10.0,
    lig_d: int = 10,
    lig_legs: int = 2,
    s_lig: float = 150.0,
    span_m: float = 6.0,
    sls_mu: float = 0.0,
    defl_limit_ratio: float | None = None,
    geometry_locked: bool = False,
    reo_locked: bool = False,
) -> dict[str, Any]:
    changes = {
        "section_shape": "RECT",
        "sec_shape": "RECT",
        "b": float(b),
        "bw": float(b),
        "D": float(D),
        "L": float(span_m) * 1000.0,
        "span_L_m": float(span_m),
        "defl_L_eff": float(span_m),
        "fc": 40.0,
        "fsy": 500.0,
        "cover_top": 40.0,
        "cover_bot": 40.0,
        "cover_side": 40.0,
        "side_cover_bot": 40.0,
        "side_cover_top": 40.0,
        "bot1_count": max(2, int(bot_count)),
        "db_bot_1": float(bot_dia),
        "bot2_count": 0,
        "db_bot_2": 0.0,
        "bot_row_count": 1,
        "bot_row_1_mode": "Count",
        "bot_row_1_bars": max(2, int(bot_count)),
        "bot_row_1_spacing": 200.0,
        "bot_row_1_dia": float(bot_dia),
        "bot_row_2_mode": "Count",
        "bot_row_2_bars": 0,
        "bot_row_2_spacing": 200.0,
        "bot_row_2_dia": 0.0,
        "nb_or_s_bot_1": float(max(2, int(bot_count))),
        "nb_or_s_bot_2": 0.0,
        "nb_bot": max(2, int(bot_count)),
        "db_bot": float(bot_dia),
        "bot_entry": float(max(2, int(bot_count))),
        "top1_count": max(2, int(top_count)),
        "db_top_1": float(top_dia),
        "top2_count": 0,
        "db_top_2": 0.0,
        "top_row_count": 1,
        "top_row_1_mode": "Count",
        "top_row_1_bars": max(2, int(top_count)),
        "top_row_1_spacing": 200.0,
        "top_row_1_dia": float(top_dia),
        "top_row_2_mode": "Count",
        "top_row_2_bars": 0,
        "top_row_2_spacing": 200.0,
        "top_row_2_dia": 0.0,
        "nb_top": max(2, int(top_count)),
        "db_top": float(top_dia),
        "top_entry": float(max(2, int(top_count))),
        "lig_d": int(lig_d),
        "lig_legs": int(lig_legs),
        "s_lig": float(s_lig),
        "actions_source": "Manual design actions (inputs below)",
        "actions_mode": "manual",
        **_manual_actions_with_sls(mu, vu, sls_mu),
    }
    if defl_limit_ratio is not None:
        changes["defl_limit_ratio"] = float(defl_limit_ratio)
    if geometry_locked:
        changes.update(
            {
                "optimisation_lock_geometry": True,
                "inputs_optimisation_lock_geometry": True,
                "geometry_lock": True,
            }
        )
    if reo_locked:
        changes.update(
            {
                "reinforcement_lock": True,
                "reo_locked": True,
            }
        )
    return changes


def _live_fuzz_cases_for_family(family: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "name": f"LIVE_FUZZ_{family}_{index:02d}",
            "changes": changes,
        }
        for index, changes in enumerate(rows, start=1)
    ]


DEBUG_CASES.extend(
    _live_fuzz_cases_for_family(
        "BENDING_FAIL_GOVERNS",
        [_matrix_shear_safe_bending_fail_base() for _ in range(10)],
    )
)

DEBUG_CASES.extend(
    _live_fuzz_cases_for_family(
        "SHEAR_FAIL_GOVERNS",
        [_matrix_bending_target_shear_fail_base() for _ in range(10)],
    )
)

DEBUG_CASES.extend(
    _live_fuzz_cases_for_family(
        "COMBINED_BENDING_SHEAR_FAIL_GOVERNS",
        [_manual_actions_with_input_proxies(300.0, 400.0) for _ in range(10)],
    )
)

DEBUG_CASES.extend(
    _live_fuzz_cases_for_family(
        "BENDING_OVERDESIGN_GOVERNS",
        [_bending_overdesign_shear_probe_base(100.0, 250.0) for _ in range(10)],
    )
)

DEBUG_CASES.extend(
    [
        {"name": "BENDING_OVERDESIGN_PROBE_V100", "changes": _bending_overdesign_shear_probe_base(100.0, 100.0)},
        {"name": "BENDING_OVERDESIGN_PROBE_V150", "changes": _bending_overdesign_shear_probe_base(100.0, 150.0)},
        {"name": "BENDING_OVERDESIGN_PROBE_V200", "changes": _bending_overdesign_shear_probe_base(100.0, 200.0)},
        {"name": "BENDING_OVERDESIGN_PROBE_V250", "changes": _bending_overdesign_shear_probe_base(100.0, 250.0)},
        {"name": "BENDING_OVERDESIGN_PROBE_V300", "changes": _bending_overdesign_shear_probe_base(100.0, 300.0)},
    ]
)

DEBUG_CASES.extend(
    _live_fuzz_cases_for_family(
        "SHEAR_OVERDESIGN_GOVERNS",
        [_manual_actions_with_input_proxies(0.0, 150.0) for _ in range(10)],
    )
)

DEBUG_CASES.extend(
    _live_fuzz_cases_for_family(
        "COMBINED_OVERDESIGN_GOVERNS",
        [
            _live_fuzz_rect(mu=30, vu=10, b=375, D=525, bot_count=6, bot_dia=24, lig_d=12, lig_legs=4, s_lig=125)
            for _ in range(10)
        ],
    )
)

DEBUG_CASES.extend(
    _live_fuzz_cases_for_family(
        "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS",
        [
            _live_fuzz_rect(mu=300, vu=0, b=350, D=420, bot_count=2, bot_dia=16, lig_d=16, lig_legs=3, s_lig=125)
            for _ in range(10)
        ],
    )
)

DEBUG_CASES.extend(
    _live_fuzz_cases_for_family(
        "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS",
        [
            _live_fuzz_rect(mu=20, vu=360, b=350, D=420, bot_count=6, bot_dia=20, lig_d=10, lig_legs=2, s_lig=300)
            for _ in range(10)
        ],
    )
)

DEBUG_CASES.extend(
    _live_fuzz_cases_for_family(
        "SERVICEABILITY_GOVERNS",
        [
            _live_fuzz_rect(mu=20, vu=10, b=250, D=320, bot_count=2, bot_dia=16, lig_d=10, s_lig=250, span_m=8.0, sls_mu=500, defl_limit_ratio=250),
            _live_fuzz_rect(mu=40, vu=20, b=275, D=340, bot_count=2, bot_dia=16, lig_d=10, s_lig=250, span_m=8.5, sls_mu=540, defl_limit_ratio=250),
            _live_fuzz_rect(mu=60, vu=30, b=300, D=360, bot_count=3, bot_dia=16, lig_d=10, s_lig=250, span_m=9.0, sls_mu=580, defl_limit_ratio=250),
            _live_fuzz_rect(mu=80, vu=40, b=325, D=380, bot_count=3, bot_dia=16, lig_d=10, s_lig=225, span_m=9.5, sls_mu=620, defl_limit_ratio=250),
            _live_fuzz_rect(mu=100, vu=50, b=350, D=400, bot_count=4, bot_dia=16, lig_d=10, s_lig=225, span_m=10.0, sls_mu=660, defl_limit_ratio=250),
            _live_fuzz_rect(mu=120, vu=60, b=375, D=420, bot_count=4, bot_dia=20, lig_d=10, s_lig=225, span_m=10.5, sls_mu=700, defl_limit_ratio=250),
            _live_fuzz_rect(mu=140, vu=70, b=400, D=440, bot_count=4, bot_dia=20, lig_d=12, s_lig=200, span_m=11.0, sls_mu=740, defl_limit_ratio=250),
            _live_fuzz_rect(mu=160, vu=80, b=425, D=460, bot_count=5, bot_dia=20, lig_d=12, s_lig=200, span_m=11.5, sls_mu=780, defl_limit_ratio=250),
            _live_fuzz_rect(mu=180, vu=90, b=450, D=480, bot_count=5, bot_dia=20, lig_d=12, s_lig=200, span_m=12.0, sls_mu=820, defl_limit_ratio=250),
            _live_fuzz_rect(mu=200, vu=100, b=475, D=500, bot_count=6, bot_dia=20, lig_d=12, s_lig=175, span_m=12.5, sls_mu=860, defl_limit_ratio=250),
        ],
    )
)


def flatten_frozen_recipe_runs() -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    for recipe in FROZEN_RECIPES:
        base_payload = {
            "recipe_name": recipe["name"],
            "purpose": recipe["purpose"],
        }
        for subcase in list(recipe.get("subcases") or []):
            payload = dict(base_payload)
            payload["name"] = subcase["name"]
            payload["changes"] = deepcopy(subcase["changes"])
            runs.append(payload)
    return runs


RUNNABLE_RECIPES = flatten_frozen_recipe_runs()


def build_state(changes: dict[str, Any] | None = None) -> dict[str, Any]:
    state = deepcopy(BASE_BEAM)
    if changes:
        state.update(deepcopy(changes))
    return state


def find_named_case(name: str) -> dict[str, Any] | None:
    for case in REGRESSION_CASES:
        if case["name"] == name:
            return {"kind": "case", **deepcopy(case)}
    for case in DEBUG_CASES:
        if case["name"] == name:
            return {"kind": "debug_case", **deepcopy(case)}
    for recipe in RUNNABLE_RECIPES:
        if recipe["name"] == name:
            return {"kind": "recipe", **deepcopy(recipe)}
    return None
