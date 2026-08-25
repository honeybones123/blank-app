"""Pure Bending calculation-report projection.

This module consumes already-computed Bending results and report parameters.
It does not render the Streamlit page or own engineering publication state.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from calculations.bending import (
    minimum_moment_capacity_kNm,
    sls_report_display_values,
    uls_bending_report_values,
)
from state_and_helpers import debug_print


@dataclass(frozen=True)
class BendingReportState:
    """Small immutable report-only projection of published page state."""

    sls_dn: float | None
    sls_kappa: float | None
    sls_eps_top: float | None
    sls_fs_outer: float | None
    nb_top: int
    db_top: float
    cover_top: float

    @classmethod
    def from_mapping(cls, state: Mapping[str, Any]) -> "BendingReportState":
        return cls(
            sls_dn=state.get("bending_sls_dn"),
            sls_kappa=state.get("bending_sls_kappa"),
            sls_eps_top=state.get("bending_sls_eps_top"),
            sls_fs_outer=state.get("bending_sls_fs_outer"),
            nb_top=state.get("nb_top", 0) or 0,
            db_top=state.get("db_top", 0.0) or 0.0,
            cover_top=state.get("cover_top", 0.0) or 0.0,
        )


def build_bending_report(
    top_results: dict,
    params: dict,
    *,
    state: BendingReportState,
) -> dict:
    """
    Build the bending report structure (tabs + calc boxes) from computed values.

    This function replicates the authoritative check outputs without invoking
    any of the UI renderers.

    Args:
        top_results: Dict from _compute_bending_capacity() with all calculated values
        params: Dict with inputs: b, D, fc, fsy, Ast, d, phi, Mu_star, Ec, Es, etc.
        state: Immutable projection of the published SLS and reinforcement state.

    Returns:
        dict with module_title, summary, and tabs structure
    """
    from reporting.report_content import make_calc_box, make_tab, make_module_report
    import math

    # Extract parameters
    b = params.get("b", 400.0)
    D = params.get("D", 600.0)
    fc = params.get("fc", 32.0)
    fsy = params.get("fsy", 500.0)
    Ast = params.get("Ast", 0.0)
    d = params.get("d", 560.0)
    phi = params.get("phi", 0.85)
    Mu_star = params.get("Mu_star_uls", params.get("Mu_star", 0.0))
    Mu_star_sls = params.get("Mu_star_sls", None)
    Ec = params.get("Ec", 30000.0)
    Es = params.get("Es", 200000.0)
    report_moment_sign = str(params.get("moment_sign", "positive") or "positive").strip().lower()

    # Extract results
    phi_Mu_cap = top_results.get("phi_Mu_cap", 0.0)
    Mu_util = top_results.get("Mu_util", 0.0)

    # Build summary
    outcome = "PASS" if (Mu_util is not None and Mu_util <= 1.0) else "FAIL" if Mu_util is not None else "N/A"
    summary = [
        ("Demand", f"{Mu_star:.1f} kNm"),
        ("Capacity", f"{phi_Mu_cap:.1f} kNm"),
        ("Utilisation", f"{Mu_util:.2f}" if Mu_util is not None and not math.isnan(Mu_util) else "N/A"),
        ("Outcome", outcome),
    ]

    # ULS check calculations matching the authoritative presentation.
    uls_boxes = []
    if phi_Mu_cap > 0 and d and Ast:
        uls_report_values = uls_bending_report_values(
            b=b,
            d=d,
            fc=fc,
            fsy=fsy,
            Ast=Ast,
            phi=phi,
            Mu_star=Mu_star,
            Es=Es,
        )
        alpha2_uls = uls_report_values["alpha2"]
        gamma_uls = uls_report_values["gamma"]
        T = uls_report_values["T_N"]
        T_kN = uls_report_values["T_kN"]
        dn = uls_report_values["dn"]
        a_uls = uls_report_values["a"]
        z_uls = uls_report_values["z"]
        Mu_nom_uls = uls_report_values["Mu_nom"]
        phi_Mu_cap_uls = uls_report_values["phi_Mu_cap"]
        C_N = uls_report_values["C_N"]
        C_kN = uls_report_values["C_kN"]

        # 1.1 Stress-block parameters
        # Create diagram callable for box 1.1
        def diagram_1_1_fn():
            from bending_diagrams import _make_uls_stress_block_figure
            return _make_uls_stress_block_figure(
                b_mm=b or 0.0,
                D_mm=D or 0.0,
                d_mm=d,
                dn_mm=dn,
                a_mm=a_uls,
                alpha2=alpha2_uls,
                gamma=gamma_uls,
                fc=fc,
                fsy=fsy,
                show_lever_arm=False,
                show_dn=False,
                show_alpha_label=True,
                show_C=False,
                C_N=None,
                variant="11",
                moment_sign=report_moment_sign,
            )

        uls_boxes.append(make_calc_box(
            "1.1",
            "Stress-block parameters (alpha2 and gamma)",
            "info",
            f"alpha2 = {alpha2_uls:.3f}, gamma = {gamma_uls:.3f}",
            "AS 3600:2018 Cl. 8.1.3",
            [
                {"label": "Stress block factor alpha2", "eq": "alpha2 = 0.85 - 0.0015*f'c (>= 0.67)", "sub": f"= 0.85 - 0.0015*{fc:.1f} = {alpha2_uls:.3f}"},
                {"label": "Stress block factor gamma", "eq": "gamma = 0.97 - 0.0025*f'c (>= 0.67)", "sub": f"= 0.97 - 0.0025*{fc:.1f} = {gamma_uls:.3f}"},
            ],
            diagram=diagram_1_1_fn,  # Store callable for later export
        ))

        # 1.2 Concrete compressive force C
        uls_boxes.append(make_calc_box(
            "1.2",
            "Concrete compressive force C",
            "info",
            f"C = {C_kN:.1f} kN",
            "AS 3600:2018 Cl. 8.1.3",
            [
                {"label": "Compression force", "eq": "C = alpha2*f'c*b*a/1000", "sub": f"= {alpha2_uls:.3f}*{fc:.1f}*{b:.0f}*{a_uls:.1f}/1000 = {C_kN:.1f} kN"},
            ],
        ))

        # 1.3 Steel area and tension force T
        uls_boxes.append(make_calc_box(
            "1.3",
            "Steel area and tension force T",
            "info",
            f"T = {T_kN:.1f} kN",
            "AS 3600:2018 Cl. 8.1.3",
            [
                {"label": "Tension force", "eq": "T = Ast*fsy/1000", "sub": f"= {Ast:.0f}*{fsy:.0f}/1000 = {T_kN:.1f} kN"},
            ],
        ))

        # 1.4 Neutral axis depth d_n and block depth a
        def diagram_1_4_fn():
            from bending_diagrams import _make_uls_stress_block_figure
            return _make_uls_stress_block_figure(
                b_mm=b or 0.0,
                D_mm=D or 0.0,
                d_mm=d,
                dn_mm=dn,
                a_mm=a_uls,
                alpha2=alpha2_uls,
                gamma=gamma_uls,
                fc=fc,
                fsy=fsy,
                show_lever_arm=False,
                show_dn=True,
                show_alpha_label=False,
                show_C=True,
                C_N=C_N,
                variant="13",
                moment_sign=report_moment_sign,
            )

        uls_boxes.append(make_calc_box(
            "1.4",
            "Neutral axis depth d_n and block depth a",
            "info",
            f"d_n = {dn:.1f} mm, a = {a_uls:.1f} mm",
            "AS 3600:2018 Cl. 8.1.3",
            [
                {"label": "Equilibrium", "eq": "T = alpha2*f'c*b*gamma*c/1000", "sub": "Rearrange for c"},
                {"label": "Neutral axis", "eq": "c = T*1000/(alpha2*f'c*b*gamma)", "sub": f"= {T_kN:.1f}*1000/({alpha2_uls:.3f}*{fc:.1f}*{b:.0f}*{gamma_uls:.3f}) = {dn:.1f} mm"},
                {"label": "Block depth", "eq": "a = gamma*c", "sub": f"= {gamma_uls:.3f}*{dn:.1f} = {a_uls:.1f} mm"},
            ],
            diagram=diagram_1_4_fn,
        ))

        # 1.4A Strain compatibility (εcu and εs) — same formula as ULS tab calc card
        eps_cu_rep = uls_report_values["eps_cu"]
        eps_s_rep = uls_report_values["eps_s"]
        eps_sy_rep = uls_report_values["eps_sy"]
        yield_note = ""
        if not math.isnan(eps_s_rep) and not math.isnan(eps_sy_rep):
            yield_note = f"; ε_sy = {eps_sy_rep:.5f} → {'ε_s ≥ ε_sy' if eps_s_rep >= eps_sy_rep else 'ε_s < ε_sy'}"

        uls_boxes.append(make_calc_box(
            "1.4A",
            "Strain compatibility (εcu and εs)",
            "info",
            f"ε_s = {eps_s_rep:.5f}{yield_note}" if not math.isnan(eps_s_rep) else "ε_s = —",
            "AS 3600:2018 — strain compatibility (diagram support)",
            [
                {"label": "Assumption", "eq": "εcu = 0.003 at extreme compression fibre", "sub": "ULS concrete strain limit"},
                {"label": "Compatibility", "eq": "εs = εcu * (d - d_n) / d_n", "sub": f"= {eps_cu_rep:.3f} * ({d:.1f} - {dn:.1f}) / {dn:.1f}" + (f" = {eps_s_rep:.5f}" if not math.isnan(eps_s_rep) else "")},
            ],
        ))

        # 1.5 Neutral axis ratio k_u
        ku = uls_report_values["ku"]
        ku_lim = uls_report_values["ku_limit"]
        ku_ok = uls_report_values["ku_ok"]
        ku_status = "pass" if ku_ok is True else "fail" if ku_ok is False else "info"
        uls_boxes.append(make_calc_box(
            "1.5",
            "Neutral axis ratio k_u",
            ku_status,
            f"k_u = {ku:.3f} vs k_u,lim = {ku_lim:.2f} → {'PASS' if ku_ok else 'FAIL' if ku_ok is False else '—'}",
            "AS 3600:2018 Cl. 8.1.3",
            [
                {"label": "Ratio", "eq": "k_u = c/d", "sub": f"= {dn:.1f}/{d:.1f} = {ku:.3f}"},
            ],
        ))

        # 1.6 Lever arm z and moment capacity
        def diagram_1_6_fn():
            from bending_diagrams import _make_uls_force_model_figure
            from reporting.fig_export import call_with_supported_kwargs
            # Use signature-safe call - function expects D_mm, d_mm, a_mm, C_N, T_N
            return call_with_supported_kwargs(
                _make_uls_force_model_figure,
                D_mm=D or 0.0,
                d_mm=d,
                a_mm=a_uls,
                C_N=C_N,
                T_N=T,
                moment_sign=report_moment_sign,
                dn_mm=dn,
                # Also pass aliases in case function accepts different names
                b_mm=b or 0.0,
                b=b or 0.0,
                z_mm=z_uls,
                alpha2=alpha2_uls,
                gamma=gamma_uls,
                fc=fc,
                fsy=fsy,
            )

        uls_boxes.append(make_calc_box(
            "1.6",
            "Lever arm z and moment capacity",
            "info",
            f"phiM_u,cap = {phi_Mu_cap_uls:.2f} kNm",
            "AS 3600:2018 Cl. 8.1.3, 2.2",
            [
                {"label": "Lever arm", "eq": "z = d - a/2", "sub": f"= {d:.1f} - {a_uls:.1f}/2 = {z_uls:.1f} mm"},
                {"label": "Nominal", "eq": "M_u = T*z/1000/1000", "sub": f"= {T_kN:.1f}*{z_uls:.1f}/1000 = {Mu_nom_uls:.2f} kNm"},
                {"label": "Design", "eq": "phiM_u = phi*M_u", "sub": f"= {phi:.2f}*{Mu_nom_uls:.2f} = {phi_Mu_cap_uls:.2f} kNm"},
            ],
            diagram=diagram_1_6_fn,
        ))

        # 1.7 Flexural capacity check
        Mu_ok = uls_report_values["Mu_ok"]
        Mu_status = "pass" if Mu_ok is True else "fail" if Mu_ok is False else "info"
        Mu_util_val = uls_report_values["Mu_util"]
        uls_boxes.append(make_calc_box(
            "1.7",
            "Flexural capacity check",
            Mu_status,
            f"M_u* = {Mu_star:.2f} kNm vs phiM_u,cap = {phi_Mu_cap_uls:.2f} kNm → {'PASS' if Mu_ok else 'FAIL' if Mu_ok is False else 'N/A'}",
            "AS 3600:2018 Cl. 2.2",
            [
                {"label": "Utilisation", "eq": "Util = M_u*/phiM_u,cap", "sub": f"= {Mu_star:.2f}/{phi_Mu_cap_uls:.2f} = {Mu_util_val:.2f}"},
            ],
        ))

    # Minimum-strength calculations matching the authoritative presentation.
    min_boxes = []
    if phi_Mu_cap > 0:
        fctf = top_results.get("fctf", 0.0)
        Z_gross = top_results.get("Z_gross", 0.0)
        Mcr = top_results.get("Mcr", 0.0)
        As_min = top_results.get("As_min", 0.0)

        fctf_as = fctf
        Zg = Z_gross
        Mcr_as = Mcr
        Mu_min_as = minimum_moment_capacity_kNm(Mcr_as)
        Ast_min_as = As_min

        # 2.1 f_ct,f
        min_boxes.append(make_calc_box(
            "2.1",
            "Concrete flexural tensile strength f_ct,f",
            "info",
            f"f_ct,f = {fctf_as:.3f} MPa",
            "AS 3600:2018 (simplified)",
            [
                {"label": "Tensile strength", "eq": "f_ct,f = 0.6*sqrt(f'c)", "sub": f"= 0.6*sqrt({fc:.1f}) = {fctf_as:.3f} MPa"},
            ],
        ))

        # 2.2 Z_g
        min_boxes.append(make_calc_box(
            "2.2",
            "Gross section modulus Z_g",
            "info",
            f"Z_g = {Zg:.3e} mm³",
            "AS 3600:2018",
            [
                {"label": "Section modulus", "eq": "Z_g = b*D^2/6", "sub": f"= {b:.0f}*{D:.0f}^2/6 = {Zg:.3e} mm³"},
            ],
        ))

        # 2.3 M_cr
        min_boxes.append(make_calc_box(
            "2.3",
            "Cracking moment M_cr",
            "info",
            f"M_cr = {Mcr_as:.2f} kNm",
            "AS 3600:2018",
            [
                {"label": "Cracking moment", "eq": "M_cr = f_ct,f*Z_g/10^6", "sub": f"= {fctf_as:.3f}*{Zg:.3e}/10^6 = {Mcr_as:.2f} kNm"},
            ],
        ))

        # 2.4 Minimum required capacity
        Mu_min_ok = phi_Mu_cap >= Mu_min_as if (phi_Mu_cap > 0 and Mu_min_as > 0) else None
        Mu_min_status = "pass" if Mu_min_ok is True else "fail" if Mu_min_ok is False else "info"
        min_boxes.append(make_calc_box(
            "2.4",
            "Minimum required design capacity (M_u,cap)_min",
            Mu_min_status,
            f"phiM_u,cap = {phi_Mu_cap:.2f} kNm vs (M_u,cap)_min = {Mu_min_as:.2f} kNm → {'PASS' if Mu_min_ok else 'FAIL' if Mu_min_ok is False else 'N/A'}",
            "AS 3600:2018 (teaching)",
            [
                {"label": "Minimum capacity", "eq": "(M_u,cap)_min = 1.2*M_cr", "sub": f"= 1.2*{Mcr_as:.2f} = {Mu_min_as:.2f} kNm"},
            ],
        ))

        # 2.5 Minimum tensile reinforcement
        As_ok = Ast >= Ast_min_as if (Ast is not None and Ast_min_as is not None and not math.isnan(Ast_min_as)) else None
        As_status = "pass" if As_ok is True else "fail" if As_ok is False else "info"
        min_boxes.append(make_calc_box(
            "2.5",
            "Minimum tensile reinforcement A_st,min",
            As_status,
            f"A_st = {Ast:.1f} mm² vs A_st,min = {Ast_min_as:.1f} mm² → {'PASS' if As_ok else 'FAIL' if As_ok is False else 'N/A'}",
            "AS 3600:2018 (simplified)",
            [
                {"label": "Minimum steel", "eq": "A_st,min = 0.4*(f_ct,f/f_sy)*b*d", "sub": f"= 0.4*({fctf_as:.3f}/{fsy:.0f})*{b:.0f}*{d:.0f} = {Ast_min_as:.1f} mm²"},
            ],
        ))

    # SLS values are read from the authoritative publication when available.
    sls_boxes = []
    Ms = params.get("Mu_star_sls", Mu_star)  # service moment (kNm)
    if Mu_star_sls is not None:
        try:
            debug_print(f"[BENDING_REPORT_ACTIONS] uls_M={Mu_star} sls_M={Mu_star_sls}")
        except Exception:
            pass

    dn_sls = state.sls_dn
    kappa_sls = state.sls_kappa
    eps_top_sls = state.sls_eps_top
    fs_outer = state.sls_fs_outer

    if dn_sls is not None and kappa_sls is not None and Ec > 0 and Es > 0 and b > 0 and Ast > 0 and d > 0:
        # SLS values are available - build calc boxes
        sls_report_values = sls_report_display_values(
            Ms_kNm=Ms,
            Ec=Ec,
            Es=Es,
            d=d,
            dn_sls=dn_sls,
            kappa_sls=kappa_sls,
            eps_top_sls=eps_top_sls,
        )
        n_sls = sls_report_values["n_sls"]

        # 3.1 Modular ratio
        sls_boxes.append(make_calc_box(
            "3.1",
            "Modular ratio n = E_s / E_c",
            "info",
            f"n = {n_sls:.2f}",
            "AS 3600:2018 SLS",
            [
                {"label": "Modular ratio", "eq": "n = E_s / E_c", "sub": f"= {Es:.0f} / {Ec:.0f} = {n_sls:.2f}"},
            ],
        ))

        # 3.2 Neutral axis depth d_n
        def diagram_3_2_fn():
            from bending_diagrams import _make_sls_stress_block_figure
            from reporting.fig_export import call_with_supported_kwargs
            # Get bar layout info for diagram
            nb_top = state.nb_top
            db_top = state.db_top
            cover_top = state.cover_top
            include_comp = (nb_top > 0)
            d_comp = cover_top + db_top/2.0 if (nb_top > 0 and db_top > 0) else None
            # Use signature-safe call
            return call_with_supported_kwargs(
                _make_sls_stress_block_figure,
                D_mm=D or 0.0,
                d_mm=d,
                dn_mm=dn_sls,
                include_comp=include_comp,
                d_comp_mm=d_comp,
                moment_sign=report_moment_sign,
                # Also pass aliases
                D=D or 0.0,
                d=d,
                dn=dn_sls,
            )

        sls_boxes.append(make_calc_box(
            "3.2",
            "Neutral axis depth d_n (cracked section)",
            "info",
            f"d_n = {dn_sls:.1f} mm",
            "AS 3600:2018 SLS",
            [
                {"label": "Cracked section", "eq": "Equilibrium: C = T (transformed areas)", "sub": "Solved numerically"},
                {"label": "Result", "eq": "d_n", "sub": f"= {dn_sls:.1f} mm"},
            ],
            diagram=diagram_3_2_fn,
        ))

        # 3.3 Cracked moment of inertia I_cr
        Icr = sls_report_values["Icr"]

        sls_boxes.append(make_calc_box(
            "3.3",
            "Cracked moment of inertia I_cr",
            "info",
            f"I_cr = {Icr:,.2f} mm⁴",
            "AS 3600:2018 SLS",
            [
                {"label": "Formula", "eq": "I_cr = b*d_n^3/3 + Σ(n*A_s*(d_i - d_n)^2)", "sub": "Includes all steel layers"},
                {"label": "Result", "eq": "I_cr", "sub": f"= {Icr:,.2f} mm⁴"},
            ],
        ))

        # 3.4 Curvature
        sls_boxes.append(make_calc_box(
            "3.4",
            "Curvature at service moment",
            "info",
            f"κ = {kappa_sls:.3e} mm⁻¹",
            "AS 3600:2018 SLS",
            [
                {"label": "Curvature", "eq": "κ = M_s / (E_c * I_cr)", "sub": f"= {Ms:.2f}*10^6 / ({Ec:.0f} * {Icr:,.2f}) = {kappa_sls:.3e} mm⁻¹"},
            ],
        ))

        # 3.5 Strain distribution (top fibre)
        if eps_top_sls is not None:
            sls_boxes.append(make_calc_box(
                "3.5",
                "Strain distribution ε(y) = κ(y − d_n)",
                "info",
                f"ε_top = {eps_top_sls:.5f}",
                "AS 3600:2018 SLS",
                [
                    {"label": "Top fibre strain", "eq": "ε_top = κ*(0 - d_n)", "sub": f"= {kappa_sls:.3e}*({-dn_sls:.1f}) = {eps_top_sls:.5f}"},
                ],
            ))
        else:
            eps_top_computed = sls_report_values["eps_top"]
            sls_boxes.append(make_calc_box(
                "3.5",
                "Strain distribution ε(y) = κ(y − d_n)",
                "info",
                f"ε_top = {eps_top_computed:.5f}",
                "AS 3600:2018 SLS",
                [
                    {"label": "Top fibre strain", "eq": "ε_top = κ*(0 - d_n)", "sub": f"= {kappa_sls:.3e}*({-dn_sls:.1f}) = {eps_top_computed:.5f}"},
                ],
            ))

        # 3.6 Steel stresses (outermost tension layer if available)
        if fs_outer is not None:
            sls_boxes.append(make_calc_box(
                "3.6",
                "Steel stresses at SLS",
                "info",
                f"f_s,outer = {fs_outer:.1f} MPa",
                "AS 3600:2018 SLS",
                [
                    {"label": "Outermost tension layer", "eq": "f_s = E_s * ε_s", "sub": f"= {fs_outer:.1f} MPa"},
                ],
            ))
        else:
            eps_s_computed = sls_report_values["eps_s"]
            fs_computed = sls_report_values["fs"]
            sls_boxes.append(make_calc_box(
                "3.6",
                "Steel stresses at SLS",
                "info",
                f"f_s ≈ {fs_computed:.1f} MPa",
                "AS 3600:2018 SLS",
                [
                    {"label": "Steel strain", "eq": "ε_s = κ*(d - d_n)", "sub": f"= {kappa_sls:.3e}*({d:.1f} - {dn_sls:.1f}) = {eps_s_computed:.5f}"},
                    {"label": "Steel stress", "eq": "f_s = E_s * ε_s", "sub": f"= {Es:.0f} * {eps_s_computed:.5f} = {fs_computed:.1f} MPa"},
                ],
            ))
    else:
        # SLS values not available - show warning box
        sls_boxes.append(make_calc_box(
            "SLS",
            "SLS checks not available",
            "warn",
            "Run SLS checks (or Run all checks) before exporting.",
            "",
            [
                {"label": "Note", "eq": "", "sub": "SLS cracked-section analysis requires running the SLS tab in the app."},
            ],
        ))

    # Build tabs
    tabs = [
        make_tab("ULS Checks", uls_boxes),
        make_tab("SLS Checks", sls_boxes),
        make_tab("Minimum strength checks", min_boxes),
    ]

    # Build module report
    report = make_module_report("Bending (ULS)", tabs)
    report["summary"] = summary  # Add summary to report
    return report
