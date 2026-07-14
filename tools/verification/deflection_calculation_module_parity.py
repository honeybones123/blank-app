from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import deflection
import deflection_checks_helpers
import deflection_core
import state_and_helpers
from calculations import deflection as deflection_calc
from calculations import materials


def _near(actual: float, expected: float, tol: float = 1e-12) -> None:
    assert abs(float(actual) - float(expected)) <= tol, (actual, expected)


def test_page_names_delegate_to_shared_module() -> None:
    assert deflection.calc_ief_simplified is deflection_calc.calc_ief_simplified
    assert deflection.calc_deflection_as3600 is deflection_calc.calc_deflection_as3600
    assert deflection.calc_span_depth_limit is deflection_calc.calc_span_depth_limit
    assert (
        deflection.compression_to_tension_steel_ratio
        is deflection_calc.compression_to_tension_steel_ratio
    )
    assert deflection.simplified_ief_k1_factor is deflection_calc.simplified_ief_k1_factor
    assert deflection.effective_flange_width_ratio is deflection_calc.effective_flange_width_ratio
    assert deflection.tension_reinforcement_ratio is deflection_calc.tension_reinforcement_ratio
    assert deflection.effective_design_load_from_shear is deflection_calc.effective_design_load_from_shear
    assert (
        deflection.deflection_multispan_load_split_values
        is deflection_calc.deflection_multispan_load_split_values
    )
    assert deflection.deflection_limit_check_values is deflection_calc.deflection_limit_check_values
    assert deflection.span_depth_display_values is deflection_calc.span_depth_display_values
    assert deflection.span_to_depth_ratio is deflection_calc.span_to_depth_ratio
    assert (
        deflection_core.effective_design_load_from_shear
        is deflection_calc.effective_design_load_from_shear
    )
    assert (
        deflection.deflection_sustained_load_factor
        is deflection_calc.deflection_sustained_load_factor
    )
    assert (
        deflection.effective_stiffness_coefficient_k1
        is deflection_calc.effective_stiffness_coefficient_k1
    )
    assert (
        deflection.effective_flexural_rigidity_kNm2
        is deflection_calc.effective_flexural_rigidity_kNm2
    )
    assert (
        deflection.span_deflection_utilisation_values
        is deflection_calc.span_deflection_utilisation_values
    )
    assert (
        deflection._normalize_deflection_support_type
        is deflection_calc.normalize_deflection_support_type
    )
    assert (
        deflection._defl_support_type_from_design_selection
        is deflection_calc.defl_support_type_from_design_selection
    )
    assert (
        deflection._deflection_support_options_for_value
        is deflection_calc.deflection_support_options_for_value
    )
    assert (
        deflection._calc_is_design_multispan_mode
        is deflection_calc.design_multispan_mode_from_state
    )
    assert (
        deflection._calc_active_multispan_lengths_m
        is deflection_calc.active_multispan_lengths_m
    )
    assert (
        deflection._calc_multispan_design_elastic_loads
        is deflection_calc.multispan_design_elastic_loads
    )
    assert (
        deflection.multispan_deflection_metric_values
        is deflection_calc.multispan_deflection_metric_values
    )
    assert (
        deflection._derive_equiv_udl_from_actions
        is deflection_calc.derive_equiv_udl_from_actions
    )
    assert deflection.has_udl_line_loads is deflection_calc.has_udl_line_loads
    assert (
        deflection.resolve_deflection_equiv_loads_from_inputs
        is deflection_calc.resolve_deflection_equiv_loads_from_inputs
    )
    assert (
        deflection._deflection_from_sfd_case
        is deflection_calc.deflection_from_sfd_case
    )
    assert (
        deflection._pick_controlling_span_index
        is deflection_calc.pick_controlling_span_index
    )
    assert (
        deflection._governing_span_support_pair
        is deflection_calc.governing_span_support_pair
    )
    assert deflection._support_props is deflection_calc.support_props
    assert (
        deflection._support_type_from_sfd_case
        is deflection_calc.support_type_from_sfd_case
    )
    assert (
        state_and_helpers.get_deflection_limit_ratio
        is deflection_calc.get_deflection_limit_ratio
    )
    assert (
        state_and_helpers.get_deflection_limit_label_from_ratio
        is deflection_calc.get_deflection_limit_label_from_ratio
    )
    assert (
        state_and_helpers.get_deflection_limit_ratio_from_label
        is deflection_calc.get_deflection_limit_ratio_from_label
    )
    assert (
        state_and_helpers.derive_concrete_modulus_from_fc
        is deflection_calc.derive_concrete_modulus_from_fc
    )
    assert deflection_calc.derive_concrete_modulus_from_fc is materials.derive_concrete_modulus_from_fc
    assert (
        state_and_helpers.derive_effective_concrete_modulus
        is deflection_calc.derive_effective_concrete_modulus
    )
    assert (
        state_and_helpers.derive_sustained_stress_ratio
        is deflection_calc.derive_sustained_stress_ratio
    )
    assert (
        deflection_checks_helpers._format_deflection_allowable_limit_mm
        is deflection_calc.format_deflection_allowable_limit_mm
    )
    assert deflection.format_L_over_delta is deflection_calc.format_L_over_delta
    checks_source = Path(deflection_checks_helpers.__file__).read_text(encoding="utf-8")
    assert "def _format_deflection_allowable_limit_mm(" not in checks_source
    assert "format_deflection_allowable_limit_mm as _format_deflection_allowable_limit_mm" in checks_source
    page_source = Path(deflection.__file__).read_text(encoding="utf-8")
    calc_source = Path(deflection_calc.__file__).read_text(encoding="utf-8")
    assert "def format_L_over_delta(" not in page_source
    assert "kcs_line = deflection_sustained_load_factor(Asc, Ast)" in calc_source
    assert "kcs_line = max(0.8, 2.0 - 1.2 * ratio_asc)" not in page_source
    assert "ratio_Asc_Ast = compression_to_tension_steel_ratio(Asc, Ast)" in page_source
    assert "ratio_Asc_Ast = (Asc / Ast) if Ast > 0 else 0.0" not in page_source
    assert "effective_stiffness_coefficient_k1(Ief_selected, beff, d)" in page_source
    assert "Ief_selected / (beff * (d**3))" not in page_source
    assert "simplified_ief_k1_factor(fc_display, beta_display, p_display, p_lim_display)" in page_source
    assert "beta = effective_flange_width_ratio(beff, bw)" in page_source
    assert "p = tension_reinforcement_ratio(Ast, beff, d)" in page_source
    assert "beta = beff / bw if (bw is not None and bw > 0) else 1.0" not in page_source
    assert "Ast / (beff * d)" not in page_source
    assert "(5.0 - 0.04 * fc_display) * p_display + 0.002" not in page_source
    assert "0.055 * (fc_display ** (1.0 / 3.0))" not in page_source
    assert "effective_design_load_from_shear(" in page_source
    assert "fd_ef_used = 2.0 * V_kN / L_m_value" not in page_source
    assert "fd_ef_used = V_kN / L_m_value" not in page_source
    assert "load_split = deflection_multispan_load_split_values(" in page_source
    assert 'w_source = "actions"' not in page_source
    assert 'w_source = "g+q"' not in page_source
    assert "g_ratio = g / (g + q)" not in page_source
    assert "return _calc_is_design_multispan_mode(" in page_source
    assert "return _calc_active_multispan_lengths_m(state)" in page_source
    assert "return _calc_multispan_design_elastic_loads(" in page_source
    assert "metrics = multispan_deflection_metric_values(" in page_source
    assert "node_positions_m.append(node_positions_m[-1] + max(0.0, li))" not in page_source
    assert "pl_char.append({" not in page_source
    assert "udl_sust.append({" not in page_source
    multispan_adapter_source = page_source.split(
        "def compute_and_store_multispan_deflection_metrics",
        1,
    )[1].split("def get_deflection_diagram_support_condition", 1)[0]
    assert "np.asarray(" not in multispan_adapter_source
    assert "calc_deflection_as3600(" not in multispan_adapter_source
    assert "span_deflection_utilisation_values(" not in multispan_adapter_source
    assert "ei_knm2 = effective_flexural_rigidity_kNm2(Ec, Ief)" in calc_source
    assert "max(float(Ec) * float(Ief) / 1e9, 1e-12)" not in page_source
    assert "span_deflection_utilisation_values(" in calc_source
    assert "limit_mm = (float(span_len_m) * 1000.0) / ratio" not in page_source
    assert "util = (delta_abs / limit_mm) if limit_mm > 0 else 0.0" not in page_source
    assert "span_depth_display = span_depth_display_values(" in page_source
    assert "L_over_d = span_to_depth_ratio(L_mm, d)" in page_source
    assert "short_limit_check = deflection_limit_check_values(" in page_source
    assert "total_limit_check = deflection_limit_check_values(" in page_source
    assert "L_over_d / L_over_d_limit" not in page_source
    assert "L_over_d = (L_mm / d) if d > 0 else 0.0" not in page_source
    assert "span_passes = L_over_d <= L_over_d_limit" not in page_source
    assert 'span_defl_status = "pass" if span_passes else "fail"' not in page_source
    assert 'limit_text = f"{L_over_d_limit:.1f}"' not in page_source
    assert "limit_delta_mm = L_mm / defl_limit_ratio" not in page_source
    assert "delta_short_total /" not in page_source
    assert "delta_total / limit_delta_mm" not in page_source
    assert "util_total is not None and util_total <= 1.0" not in page_source
    core_source = Path(deflection_core.__file__).read_text(encoding="utf-8")
    assert "effective_design_load_from_shear(" in core_source
    assert "Fdef_kNm = 2.0 * V_kN / L_m_for_fd" not in core_source
    assert "Fdef_kNm = V_kN / L_m_for_fd" not in core_source


def test_support_table_contract() -> None:
    assert deflection.SUPPORT_DEFLECTION_MAP == deflection_calc.SUPPORT_DEFLECTION_MAP
    assert (
        deflection.DEFLECTION_SUPPORT_OPTIONS_BASE
        == deflection_calc.DEFLECTION_SUPPORT_OPTIONS_BASE
    )
    assert deflection_calc.support_props("Fixed-ended") == {
        "k2": 1.0 / 384.0,
        "diagram": "fixed_fixed_udl",
    }
    assert deflection_calc.support_props("missing") == {
        "k2": 5.0 / 384.0,
        "diagram": "simply_supported_udl",
    }


def test_deflection_limit_and_material_helper_contracts() -> None:
    assert (
        state_and_helpers.DEFLECTION_LIMIT_OPTIONS
        == deflection_calc.DEFLECTION_LIMIT_OPTIONS
    )
    assert deflection_calc.DEFLECTION_LIMIT_DEFAULT_LABEL == "L/250"
    assert deflection_calc.DEFLECTION_LIMIT_DEFAULT_RATIO == 250
    assert deflection_calc.get_deflection_limit_ratio(250.0) == 250
    assert deflection_calc.get_deflection_limit_ratio("250") == 250
    assert deflection_calc.get_deflection_limit_ratio(251) == 250
    assert deflection_calc.get_deflection_limit_ratio("bad") == 250
    assert deflection_calc.get_deflection_limit_label_from_ratio(250) == "L/250"
    assert deflection_calc.get_deflection_limit_label_from_ratio(251) == "L/250"
    assert deflection_calc.get_deflection_limit_ratio_from_label("L/500") == 500
    assert deflection_calc.get_deflection_limit_ratio_from_label("missing") == 250
    assert (
        deflection_calc.format_deflection_allowable_limit_mm(24.0, 250.0)
        == "δlim = 24.00 mm (L/250)"
    )
    assert deflection_calc.format_deflection_allowable_limit_mm(0.0, 250.0) == "—"
    assert deflection_calc.format_L_over_delta(24.0, 6000.0) == "L/250"
    assert deflection_calc.format_L_over_delta(2.5, 10000.0) == "L/4,000"
    assert deflection_calc.format_L_over_delta(0.0, 6000.0) == "–"
    assert deflection_calc.format_L_over_delta(-1.0, 6000.0) == "–"

    _near(deflection_calc.effective_flexural_rigidity_kNm2(30000.0, 8.0e9), 240000.0)
    _near(deflection_calc.effective_flexural_rigidity_kNm2(0.0, 8.0e9), 1e-12)
    assert deflection_calc.span_deflection_utilisation_values(
        delta_abs_mm=12.0,
        span_len_m=6.0,
        ratio=250.0,
    ) == {
        "limit_mm": 24.0,
        "util": 0.5,
    }

    _near(deflection_calc.derive_concrete_modulus_from_fc(40.0), 29725.410005582766)
    _near(deflection_calc.derive_concrete_modulus_from_fc(-1.0), 0.0)
    _near(materials.derive_concrete_modulus_from_fc(40.0), 29725.410005582766)
    _near(deflection_calc.derive_effective_concrete_modulus(30000.0, 2.0), 10000.0)
    _near(deflection_calc.derive_effective_concrete_modulus(0.0, 2.0), 3.3333333333333334e-10)

    sagging = deflection_calc.derive_sustained_stress_ratio(
        fc_mpa=40.0,
        sls_m_pos_kNm=50.0,
        sls_m_neg_kNm=20.0,
        z_top_mm3=42187500.0,
        z_bot_mm3=42187500.0,
    )
    assert sagging == {
        "stress_ratio": 0.029629629629629627,
        "sigma_cs_mpa": 1.1851851851851851,
        "M_sust_kNm": 50.0,
        "Z_comp_mm3": 42187500.0,
        "compression_fibre": "top",
    }

    hogging = deflection_calc.derive_sustained_stress_ratio(
        fc_mpa=40.0,
        sls_m_pos_kNm=20.0,
        sls_m_neg_kNm=50.0,
        z_top_mm3=42187500.0,
        z_bot_mm3=40000000.0,
    )
    assert hogging == {
        "stress_ratio": 0.03125,
        "sigma_cs_mpa": 1.25,
        "M_sust_kNm": 50.0,
        "Z_comp_mm3": 40000000.0,
        "compression_fibre": "bottom",
    }


def test_support_resolution_helper_contracts() -> None:
    assert deflection_calc.normalize_deflection_support_type(None) == "Simply supported"
    assert (
        deflection_calc.normalize_deflection_support_type("Fixed-Fixed")
        == "Fixed-ended"
    )
    assert (
        deflection_calc.normalize_deflection_support_type("Fixed-Pinned")
        == "Fixed–Pinned"
    )
    assert (
        deflection_calc.normalize_deflection_support_type("Pinned-Fixed")
        == "Pinned–Fixed"
    )
    assert (
        deflection_calc.normalize_deflection_support_type("Continuous beam")
        == "Continuous – interior span"
    )
    assert (
        deflection_calc.normalize_deflection_support_type("fixed_fixed")
        == "Simply supported"
    )
    assert (
        deflection_calc.defl_support_type_from_design_selection(
            "Cantilever beam with UDL",
            "Pinned-Pinned",
        )
        == "Cantilever"
    )
    assert (
        deflection_calc.defl_support_type_from_design_selection(
            "Simple beam with UDL",
            "Fixed-Pinned",
        )
        == "Fixed–Pinned"
    )
    assert deflection_calc.deflection_support_options_for_value(
        "Fixed–Pinned"
    ) == deflection_calc.DEFLECTION_SUPPORT_OPTIONS_BASE + ["Fixed–Pinned"]
    assert deflection_calc.deflection_support_options_for_value(
        "Simply supported"
    ) == deflection_calc.DEFLECTION_SUPPORT_OPTIONS_BASE


def test_controlling_span_helper_contracts() -> None:
    design_multispan_state = {
        "actions_mode": "design",
        "sfd_beam_system_mode": "Multi-span",
        "sfd_span_count": 2,
        "sfd_span_len_1": 4.0,
        "sfd_span_len_2": "5.5",
    }
    assert deflection_calc.design_multispan_mode_from_state(design_multispan_state)
    assert deflection_calc.active_multispan_lengths_m(design_multispan_state) == [4.0, 5.5]
    assert not deflection_calc.design_multispan_mode_from_state(
        {**design_multispan_state, "actions_mode": "manual"}
    )
    assert deflection_calc.design_multispan_mode_from_state(
        {
            "sfd_case": "Multi-span continuous beam - uniform loads",
        },
        actions_mode_default="design",
    )
    loads = deflection_calc.multispan_design_elastic_loads(
        {
            "sfd_span_count": 2,
            "sfd_span_len_1": 4.0,
            "sfd_span_len_2": 5.0,
            "sfd_support_type_1": "Fixed",
            "sfd_support_type_2": "Pinned",
            "sfd_support_type_3": "Roller",
            "sfd_ms_point_count": 1,
            "load_ms_G_1": 10.0,
            "load_ms_Q_1": 5.0,
            "load_ms_x_1": 12.0,
            "sfd_ms_udl_count": 1,
            "load_ms_g_1": 2.0,
            "load_ms_q_1": 3.0,
            "load_ms_x0_1": -1.0,
            "load_ms_x1_1": 6.0,
        },
        psi_point_default=0.4,
        psi_udl_default=0.5,
    )
    assert loads == (
        [0.0, 4.0, 9.0],
        ["Fixed", "Pinned", "Roller"],
        [{"x_m": 9.0, "P_kN": 15.0}],
        [{"x_start_m": 0.0, "x_end_m": 6.0, "w_kN_per_m": 5.0}],
        [{"x_m": 9.0, "P_kN": 12.0}],
        [{"x_start_m": 0.0, "x_end_m": 6.0, "w_kN_per_m": 3.5}],
    )

    assert deflection_calc.pick_controlling_span_index(
        {"defl_span_utilisations": [0.2, 0.7, 0.4]}
    ) == (1, "highest deflection utilisation")
    assert deflection_calc.pick_controlling_span_index(
        {"defl_span_deflections_mm": [2.0, -4.5, 3.0]}
    ) == (1, "largest absolute deflection")
    assert deflection_calc.pick_controlling_span_index(
        {"sfd_span_count": 3, "sfd_span_len_1": 4.0, "sfd_span_len_2": 7.0, "sfd_span_len_3": 5.0}
    ) == (1, "longest active span")
    assert deflection_calc.pick_controlling_span_index({}) == (0, "fallback")


def test_multispan_deflection_metric_values_contract() -> None:
    state = {
        "actions_mode": "design",
        "sfd_beam_system_mode": "Multi-span",
        "sfd_span_count": 2,
        "sfd_span_len_1": 2.0,
        "sfd_span_len_2": 3.0,
        "sfd_support_type_1": "Pinned",
        "sfd_support_type_2": "Pinned",
        "sfd_support_type_3": "Pinned",
    }
    responses = [
        {"x": [0.0, 1.0, 2.0, 3.0, 4.0, 5.0], "w_mm": [0.0, -1.0, -2.0, -1.0, -3.0, -1.0]},
        {"x": [0.0, 1.0, 2.0, 3.0, 4.0, 5.0], "w_mm": [0.0, -0.5, -1.0, -0.5, -1.5, -0.5]},
    ]
    calls = []

    def fake_solver(*args, **kwargs):
        calls.append((args, kwargs))
        return responses[len(calls) - 1]

    metrics = deflection_calc.multispan_deflection_metric_values(
        state=state,
        Ec=30000.0,
        Ief=8.0e9,
        g_kNm=2.0,
        q_kNm=3.0,
        psi_s=0.4,
        defl_limit_ratio=250.0,
        Ast=1000.0,
        Asc=0.0,
        solve_beam_structure_fn=fake_solver,
    )
    assert metrics["available"] is True
    assert metrics["metrics_source"] == "multispan_fem_elastic"
    assert metrics["span_deflections_mm"] == [4.0, 6.0]
    assert metrics["span_utilisations"] == [0.5, 0.5]
    assert len(calls) == 2
    assert calls[0][1]["n_points_per_span"] == 96
    _near(calls[0][1]["ei_knm2_for_deflection"], 240000.0)

    fallback = deflection_calc.multispan_deflection_metric_values(
        state={
            **state,
            "load_ms_g_1": 0.0,
            "load_ms_q_1": 0.0,
            "load_ms_g_2": 1.0,
            "load_ms_q_2": 2.0,
        },
        Ec=30000.0,
        Ief=8.0e9,
        g_kNm=2.0,
        q_kNm=3.0,
        psi_s=0.4,
        defl_limit_ratio=250.0,
        Ast=1000.0,
        Asc=0.0,
        solve_beam_structure_fn=None,
    )
    assert fallback["available"] is True
    assert fallback["metrics_source"] == "per_span_k2_approx"
    assert len(fallback["span_deflections_mm"]) == 2
    assert len(fallback["span_utilisations"]) == 2

    assert deflection_calc.multispan_deflection_metric_values(
        state={**state, "actions_mode": "manual"},
        Ec=30000.0,
        Ief=8.0e9,
        g_kNm=2.0,
        q_kNm=3.0,
        psi_s=0.4,
        defl_limit_ratio=250.0,
    ) == {"available": False, "reason": "not design multispan mode"}


def test_multispan_page_adapter_preserves_session_key_contract() -> None:
    state = {
        "actions_mode": "design",
        "sfd_beam_system_mode": "Multi-span",
        "sfd_span_count": 2,
        "sfd_span_len_1": 2.0,
        "sfd_span_len_2": 3.0,
        "sfd_support_type_1": "Pinned",
        "sfd_support_type_2": "Pinned",
        "sfd_support_type_3": "Pinned",
    }
    responses = [
        {"x": [0.0, 1.0, 2.0, 3.0, 4.0, 5.0], "w_mm": [0.0, -1.0, -2.0, -1.0, -3.0, -1.0]},
        {"x": [0.0, 1.0, 2.0, 3.0, 4.0, 5.0], "w_mm": [0.0, -0.5, -1.0, -0.5, -1.5, -0.5]},
    ]
    calls = []

    def fake_solver(*args, **kwargs):
        calls.append((args, kwargs))
        return responses[len(calls) - 1]

    old_beam_analysis = sys.modules.get("beam_analysis")
    old_get_param = deflection.get_param
    sys.modules["beam_analysis"] = SimpleNamespace(solve_beam_structure=fake_solver)
    deflection.get_param = lambda name, default=None: default
    try:
        out = deflection.compute_and_store_multispan_deflection_metrics(
            state=state,
            Ec=30000.0,
            Ief=8.0e9,
            g_kNm=2.0,
            q_kNm=3.0,
            psi_s=0.4,
            defl_limit_ratio=250.0,
            Ast=1000.0,
            Asc=0.0,
        )
        assert out == {
            "available": True,
            "span_deflections_mm": [4.0, 6.0],
            "span_utilisations": [0.5, 0.5],
        }
        assert state["defl_span_deflections_mm"] == [4.0, 6.0]
        assert state["defl_span_utilisations"] == [0.5, 0.5]
        assert state["defl_multispan_metrics_source"] == "multispan_fem_elastic"

        state["actions_mode"] = "manual"
        out = deflection.compute_and_store_multispan_deflection_metrics(
            state=state,
            Ec=30000.0,
            Ief=8.0e9,
            g_kNm=2.0,
            q_kNm=3.0,
            psi_s=0.4,
            defl_limit_ratio=250.0,
        )
        assert out == {"available": False, "reason": "not design multispan mode"}
        assert "defl_span_deflections_mm" not in state
        assert "defl_span_utilisations" not in state
        assert "defl_multispan_metrics_source" not in state
    finally:
        deflection.get_param = old_get_param
        if old_beam_analysis is None:
            sys.modules.pop("beam_analysis", None)
        else:
            sys.modules["beam_analysis"] = old_beam_analysis


def test_governing_span_support_pair_contract() -> None:
    state = {
        "sfd_span_count": 3,
        "sfd_support_type_1": "Fixed",
        "sfd_support_type_2": "Pinned",
        "sfd_support_type_3": "Roller",
        "sfd_support_type_4": "Fixed",
    }
    assert deflection_calc.governing_span_support_pair(
        state,
        {"mode": "design", "multi_span": True, "controlling_span_idx": 1},
    ) == ("Pinned", "Roller")
    assert (
        deflection_calc.governing_span_support_pair(
            state,
            {"mode": "manual", "multi_span": True, "controlling_span_idx": 1},
        )
        is None
    )
    assert (
        deflection_calc.governing_span_support_pair(
            state,
            {"mode": "design", "multi_span": False, "controlling_span_idx": 1},
        )
        is None
    )


def test_equivalent_load_helper_contracts() -> None:
    assert deflection_calc.effective_design_load_from_shear(
        V_kN=50.0,
        L_m=4.0,
        support_type="Simply supported",
    ) == (25.0, "2V/L")
    assert deflection_calc.effective_design_load_from_shear(
        V_kN=50.0,
        L_m=4.0,
        support_type="Pinnedâ€“Pinned",
    ) == (25.0, "2V/L")
    assert deflection_calc.effective_design_load_from_shear(
        V_kN=50.0,
        L_m=4.0,
        support_type="Cantilever",
    ) == (12.5, "V/L")
    assert deflection_calc.effective_design_load_from_shear(
        V_kN=None,
        L_m=4.0,
        support_type="Simply supported",
    ) == (None, None)

    missing = deflection_calc.derive_equiv_udl_from_actions(None, None, None, "")
    assert missing == {
        "w_kN_per_m": None,
        "w_from_M": None,
        "w_from_V": None,
        "consistent": None,
        "note": "L_m missing",
    }

    consistent = deflection_calc.derive_equiv_udl_from_actions(
        M_kNm=50.0,
        V_kN=50.0,
        L_m=4.0,
        support_type="Simply supported",
    )
    _near(consistent["w_kN_per_m"], 25.0)
    _near(consistent["w_from_M"], 25.0)
    _near(consistent["w_from_V"], 25.0)
    assert consistent["consistent"] is True
    assert "using average(wM, wV)" in consistent["note"]

    conservative = deflection_calc.derive_equiv_udl_from_actions(
        M_kNm=100.0,
        V_kN=10.0,
        L_m=4.0,
        support_type="Simply supported",
    )
    _near(conservative["w_kN_per_m"], 50.0)
    _near(conservative["w_from_M"], 50.0)
    _near(conservative["w_from_V"], 5.0)
    assert conservative["consistent"] is False
    assert "using max(wM, wV)" in conservative["note"]

    cantilever = deflection_calc.derive_equiv_udl_from_actions(
        M_kNm=20.0,
        V_kN=10.0,
        L_m=4.0,
        support_type="Cantilever",
    )
    _near(cantilever["w_kN_per_m"], 2.5)
    assert cantilever["consistent"] is True

    too_long = deflection_calc.derive_equiv_udl_from_actions(
        M_kNm=1.0,
        V_kN=1.0,
        L_m=5000.0,
        support_type="Simply supported",
    )
    assert too_long["w_kN_per_m"] is None
    assert "looks like mm" in too_long["note"]

    assert deflection_calc.has_udl_line_loads(2.0, 0.0) is True
    assert deflection_calc.has_udl_line_loads(None, 0.0) is False

    assert deflection_calc.resolve_deflection_equiv_loads_from_inputs(
        derived=consistent,
        w_sls=None,
        g_udl=3.0,
        q_udl=2.0,
    ) == (15.0, 10.0)
    assert deflection_calc.resolve_deflection_equiv_loads_from_inputs(
        derived={"w_kN_per_m": None},
        w_sls=6.0,
        g_udl=None,
        q_udl=None,
    ) == (6.0, 0.0)
    assert deflection_calc.resolve_deflection_equiv_loads_from_inputs(
        derived={"w_kN_per_m": None},
        w_sls=None,
        g_udl=3.0,
        q_udl=2.0,
    ) == (3.0, 2.0)

    split_actions = deflection_calc.deflection_multispan_load_split_values(
        derived={"w_kN_per_m": 12.0},
        g_kNm=3.0,
        q_kNm=1.0,
    )
    assert split_actions == {
        "w_used": 12.0,
        "w_source": "actions",
        "g_used": 9.0,
        "q_used": 3.0,
    }
    split_stored = deflection_calc.deflection_multispan_load_split_values(
        derived={"w_kN_per_m": None},
        g_kNm=3.0,
        q_kNm=1.0,
    )
    assert split_stored == {
        "w_used": 4.0,
        "w_source": "g+q",
        "g_used": 3.0,
        "q_used": 1.0,
    }
    split_missing = deflection_calc.deflection_multispan_load_split_values(
        derived={"w_kN_per_m": None},
        g_kNm=None,
        q_kNm=1.0,
    )
    assert split_missing == {
        "w_used": 0.0,
        "w_source": "g+q",
        "g_used": None,
        "q_used": 1.0,
    }


def test_sfd_closed_form_deflection_contracts() -> None:
    simple_udl = deflection_calc.deflection_from_sfd_case(
        "Simple beam – UDL over entire span",
        6000.0,
        7.0,
        None,
        30000.0,
        8e9,
    )
    _near(simple_udl[0], 0.4921875)
    assert simple_udl[1] == (
        r"\delta_{\max} = \frac{5 w L^4}{384 E I}"
        r"\quad\text{(simply supported, full UDL, midspan)}"
    )
    assert simple_udl[2] == "At midspan (x = L/2)"

    simple_point = deflection_calc.deflection_from_sfd_case(
        "Simple beam – point load at centre",
        6000.0,
        None,
        10.0,
        30000.0,
        8e9,
    )
    _near(simple_point[0], 0.0001875)
    assert simple_point[2] == "At midspan (x = L/2)"

    cantilever_point = deflection_calc.deflection_from_sfd_case(
        "Cantilever – point load at free end",
        6000.0,
        None,
        10.0,
        30000.0,
        8e9,
    )
    _near(cantilever_point[0], 0.003)
    assert cantilever_point[2] == "At free end (x = L)"

    cantilever_udl = deflection_calc.deflection_from_sfd_case(
        "Cantilever – UDL over entire span",
        6000.0,
        7.0,
        None,
        30000.0,
        8e9,
    )
    _near(cantilever_udl[0], 4.725)
    assert cantilever_udl[2] == "At free end (x = L)"

    no_match = deflection_calc.deflection_from_sfd_case(
        "Unsupported case",
        6000.0,
        7.0,
        10.0,
        30000.0,
        8e9,
    )
    assert no_match == (
        None,
        r"\text{No closed-form deflection linked for this case yet.}",
        "—",
    )


def test_ief_contract() -> None:
    _near(deflection_calc.effective_flange_width_ratio(400.0, 300.0), 1.3333333333333333)
    _near(deflection_calc.effective_flange_width_ratio(400.0, 0.0), 1.0)
    _near(deflection_calc.effective_flange_width_ratio(400.0, None), 1.0)
    _near(deflection_calc.tension_reinforcement_ratio(1800.0, 400.0, 550.0), 0.008181818181818182)
    _near(deflection_calc.tension_reinforcement_ratio(1800.0, None, 550.0), 0.0)
    _near(deflection_calc.tension_reinforcement_ratio(1800.0, 400.0, 0.0), 0.0)
    _near(
        deflection_calc.simplified_ief_k1_factor(
            32.0,
            1.3333333333333333,
            0.008181818181818182,
            0.0026207413942088966,
        ),
        0.03243636363636364,
    )
    _near(
        deflection_calc.simplified_ief_k1_factor(
            32.0,
            1.3333333333333333,
            0.001,
            0.0026207413942088966,
        ),
        0.0941407766814893,
    )

    ief, beta, p, p_lim, ief_max, k1 = deflection_calc.calc_ief_simplified(
        32.0,
        400.0,
        300.0,
        550.0,
        1800.0,
    )
    _near(ief, 2158640000.0)
    _near(beta, 1.3333333333333333)
    _near(p, 0.008181818181818182)
    _near(p_lim, 0.0026207413942088966)
    _near(ief_max, 5493581460.348435)
    _near(k1, 0.03243636363636364)


def test_deflection_contract() -> None:
    _near(deflection_calc.compression_to_tension_steel_ratio(600.0, 1800.0), 1.0 / 3.0)
    assert deflection_calc.compression_to_tension_steel_ratio(600.0, 0.0) == 0.0
    _near(deflection_calc.deflection_sustained_load_factor(600.0, 1800.0), 1.6)
    _near(deflection_calc.deflection_sustained_load_factor(2400.0, 1800.0), 0.8)
    _near(deflection_calc.deflection_sustained_load_factor(0.0, 0.0), 2.0)
    _near(
        deflection_calc.effective_stiffness_coefficient_k1(8e9, 400.0, 550.0),
        0.12021036814425244,
    )
    assert deflection_calc.effective_stiffness_coefficient_k1(8e9, 0.0, 550.0) == 0.0

    result = deflection_calc.calc_deflection_as3600(
        L_m=6.0,
        Ec=30000.0,
        Ief=8e9,
        g_kNm=5.0,
        q_kNm=2.0,
        psi_s=0.4,
        support_type="Simply supported",
        Ast=1800.0,
        Asc=600.0,
    )
    _near(result["L_mm"], 6000.0)
    _near(result["k2"], 0.013020833333333334)
    _near(result["w_total"], 7.0)
    _near(result["w_sust"], 5.8)
    _near(result["delta_short_total"], 0.49218750000000006)
    _near(result["delta_short_sust"], 0.4078125)
    _near(result["kcs"], 1.6)
    _near(result["delta_long_add"], 0.6525000000000001)
    _near(result["delta_total"], 1.1446875)

    assert deflection_calc.calc_deflection_as3600(None, 1, 1, 1, 1, 1, "", 1, 1) == {
        "ok": False,
        "error": "Effective span is missing (L_m is None).",
    }


def test_span_depth_contract() -> None:
    _near(deflection_calc.span_to_depth_ratio(6000.0, 300.0), 20.0)
    assert deflection_calc.span_to_depth_ratio(6000.0, 0.0) == 0.0

    limit, k1, k2 = deflection_calc.calc_span_depth_limit(
        8e9,
        400.0,
        300.0,
        550.0,
        32.0,
        30000.0,
        12.0,
        "Simply supported",
        250.0,
    )
    _near(limit, 33.30077796518783)
    _near(k1, 0.12021036814425244)
    _near(k2, 0.013020833333333334)

    no_limit, _, _ = deflection_calc.calc_span_depth_limit(
        8e9,
        400.0,
        300.0,
        550.0,
        32.0,
        30000.0,
        0.0,
        "Simply supported",
        250.0,
    )
    assert no_limit is None

    passing_display = deflection_calc.span_depth_display_values(18.0, 20.0)
    _near(passing_display["util_span"], 0.9)
    assert passing_display["span_passes"] is True
    assert passing_display["span_defl_status"] == "pass"
    assert passing_display["result_text"] == "PASS"
    assert passing_display["limit_text"] == "20.0"

    failing_display = deflection_calc.span_depth_display_values(22.0, 20.0)
    _near(failing_display["util_span"], 1.1)
    assert failing_display["span_passes"] is False
    assert failing_display["span_defl_status"] == "fail"
    assert failing_display["result_text"] == "FAIL"
    assert failing_display["limit_text"] == "20.0"

    zero_ratio_display = deflection_calc.span_depth_display_values(0.0, 20.0)
    assert zero_ratio_display["util_span"] == 0.0
    assert zero_ratio_display["span_passes"] is None
    assert zero_ratio_display["span_defl_status"] is None
    assert zero_ratio_display["result_text"] == "—"
    assert zero_ratio_display["limit_text"] == "20.0"

    missing_limit_display = deflection_calc.span_depth_display_values(18.0, None)
    assert missing_limit_display["util_span"] is None
    assert missing_limit_display["span_passes"] is None
    assert missing_limit_display["span_defl_status"] is None
    assert missing_limit_display["result_text"] == "—"
    assert missing_limit_display["limit_text"] == "—"

    short_pass = deflection_calc.deflection_limit_check_values(6.0, 6000.0, 250.0)
    assert short_pass == {
        "limit_delta_mm": 24.0,
        "utilisation": 0.25,
        "status": "pass",
        "result_text": "PASS",
        "limit_delta_mm_display": 24.0,
        "utilisation_display": 0.25,
    }

    total_fail = deflection_calc.deflection_limit_check_values(30.0, 6000.0, 250.0)
    assert total_fail == {
        "limit_delta_mm": 24.0,
        "utilisation": 1.25,
        "status": "fail",
        "result_text": "FAIL",
        "limit_delta_mm_display": 24.0,
        "utilisation_display": 1.25,
    }

    no_limit = deflection_calc.deflection_limit_check_values(6.0, 6000.0, 0.0)
    assert no_limit == {
        "limit_delta_mm": None,
        "utilisation": None,
        "status": None,
        "result_text": "—",
        "limit_delta_mm_display": 0.0,
        "utilisation_display": 0.0,
    }


def main() -> int:
    test_page_names_delegate_to_shared_module()
    test_support_table_contract()
    test_deflection_limit_and_material_helper_contracts()
    test_support_resolution_helper_contracts()
    test_controlling_span_helper_contracts()
    test_multispan_deflection_metric_values_contract()
    test_multispan_page_adapter_preserves_session_key_contract()
    test_governing_span_support_pair_contract()
    test_equivalent_load_helper_contracts()
    test_sfd_closed_form_deflection_contracts()
    test_ief_contract()
    test_deflection_contract()
    test_span_depth_contract()
    print("deflection_calculation_module_parity: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
