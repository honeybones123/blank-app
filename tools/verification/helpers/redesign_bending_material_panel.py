from pathlib import Path
import textwrap

path = Path("bending_page_runtime.py")
text = path.read_text(encoding="utf-8")

start_marker = "            with matcurves_placeholder.container():\n"
end_marker = '                render_timing_mark("bending_page.runtime.material_model.end")\n'

if "How do strain, stress and force relate?" in text and "From stress to internal force and equilibrium" in text:
    print("Bending material teaching panel already redesigned.")
    raise SystemExit(0)

start = text.find(start_marker)
if start < 0:
    raise SystemExit("Could not find material-panel start marker")
end = text.find(end_marker, start)
if end < 0:
    raise SystemExit("Could not find material-panel end marker")
end += len(end_marker)

replacement = textwrap.dedent(r'''
with matcurves_placeholder.container():
    st.markdown("**State:**")
    st.radio(
        "State:",
        state_options,
        key="bending_state_main",
        horizontal=True,
        index=state_options.index(main_state),
        label_visibility="collapsed",
    )
    st.session_state["bending_state"] = st.session_state.get(
        "bending_state_main", main_state
    )

    def _render_material_model_content():
        selected_state = str(
            st.session_state.get("bending_state_main", main_state) or main_state
        )
        state_low = selected_state.strip().lower()
        is_uls = state_low.startswith("uls")
        is_sls = "sls" in state_low
        is_uncracked = "uncracked" in state_low

        # Major teaching section 1: read top-to-bottom. Keep this full width so
        # the panel reads like an engineering explanation, not a poster.
        with st.container(border=True):
            st.markdown("### How do strain, stress and force relate?")
            st.markdown(
                "When a reinforced-concrete beam bends, different parts of the section "
                "shorten or elongate by different amounts. We describe this deformation "
                "using **strain**. The calculation then converts strain into stress, and "
                "stress into the internal forces carried by the section."
            )

            stage_cols = st.columns(3, gap="medium")
            with stage_cols[0]:
                with st.container(border=True):
                    st.markdown("**Strain**")
                    st.caption("How much the material deforms.")
            with stage_cols[1]:
                with st.container(border=True):
                    st.markdown("**Stress**")
                    st.caption("The internal intensity of force developed by that deformation.")
            with stage_cols[2]:
                with st.container(border=True):
                    st.markdown("**Force**")
                    st.caption("The total internal action produced when stress acts over an area.")

            st.markdown("#### 1 — Where does the strain come from?")
            st.markdown(
                "For normal beam bending, **plane sections are assumed to remain plane**. "
                "The longitudinal strain therefore varies linearly through the section depth. "
                "The Section / Strain / Stress diagram above shows this compatible linear "
                "strain profile for the selected state."
            )
            st.markdown(
                "Once the neutral axis is known, strain is zero at the neutral axis and the "
                "strain at any other depth follows directly from the geometry of that linear profile."
            )
            st.latex(r"\varepsilon_{s,i}=-\varepsilon_{cu}\frac{y_i-d_n}{d_n}")
            st.info(
                "Strain is determined from the section geometry and the assumed neutral-axis "
                "depth $d_n$."
            )

            st.markdown("#### 2 — How does strain become stress?")
            st.markdown(
                "Knowing the strain does not yet tell us the force carried by the material. "
                "We first convert strain into **stress**. Within the elastic range, stress is "
                "related to strain by **Hooke's law**:"
            )
            st.latex(r"\sigma=E\varepsilon")
            st.markdown(
                "Here, $\sigma$ is stress, $E$ is the elastic modulus (material stiffness), "
                "and $\varepsilon$ is strain. For the same strain, a material with a larger "
                "$E$ develops a larger stress. This is why the strain profile must be combined "
                "with the material stress–strain relationship before internal forces can be found."
            )
            hooke_cols = st.columns(2, gap="large")
            with hooke_cols[0]:
                st.markdown("**Concrete — approximately elastic range**")
                st.latex(r"f_c\approx E_c\varepsilon_c")
            with hooke_cols[1]:
                st.markdown("**Reinforcement — elastic range**")
                st.latex(r"f_s=E_s\varepsilon_s")

            st.markdown(f"#### Selected state — {selected_state}")
            if is_uls:
                st.markdown(
                    "At ULS the section is taken to its ultimate flexural condition. The extreme "
                    "concrete compression strain is taken as $\varepsilon_{cu}=0.003$. "
                    "Reinforcement stress is obtained from strain and is limited to the applicable "
                    "yield strength $f_{sy}$. Concrete compression for section strength is represented "
                    "by the AS 3600 equivalent rectangular stress block."
                )
                st.latex(r"\varepsilon_{cu}=0.003\qquad |f_s|\leq f_{sy}")
            elif is_sls:
                st.markdown(
                    "At cracked SLS the section is analysed under service actions after flexural "
                    "cracking. Tensile concrete is neglected in the cracked flexural section analysis, "
                    "while concrete compression and reinforcement stresses follow the compatible "
                    "service strain profile."
                )
            elif is_uncracked:
                st.markdown(
                    "In the uncracked state the concrete section remains effective in tension and "
                    "compression. The elastic material relationships are therefore directly useful "
                    "for converting the compatible strain profile into concrete and steel stresses."
                )

            fig_mat = _plot_material_stress_strain_curves()
            try:
                render_plotly_diagram(
                    fig_mat,
                    key="bending_material_stress_strain_curves",
                    title="Material stress-strain curves",
                    config={"displayModeBar": False},
                )
            except Exception:
                st.warning(
                    "Material curves view failed to render (browser/graphics). Try refreshing the page."
                )

            behaviour_cols = st.columns(2, gap="large")
            with behaviour_cols[0]:
                with st.container(border=True):
                    st.markdown("**Concrete behaviour**")
                    st.markdown(
                        "Concrete is approximately elastic at low stress but becomes increasingly "
                        "nonlinear as compression increases."
                    )
                    if is_uls:
                        st.markdown(
                            "At ULS, AS 3600 represents the concrete compression zone using an "
                            "equivalent rectangular stress block for section-strength calculations."
                        )
                        st.info(
                            "The material stress–strain curve describes concrete behaviour; the ULS "
                            "rectangular stress block is the code representation used for section strength."
                        )
            with behaviour_cols[1]:
                with st.container(border=True):
                    st.markdown("**Reinforcement behaviour**")
                    st.markdown(
                        "Reinforcement behaves approximately linear-elastically up to yield. The "
                        "initial slope of the steel stress–strain relationship is $E_s$."
                    )
                    st.latex(r"f_s=E_s\varepsilon_s")
                    if is_uls:
                        st.markdown(
                            "Once yield is reached, the ULS section calculation limits reinforcement "
                            "stress to the applicable steel yield strength."
                        )
                        st.latex(r"|f_s|\leq f_{sy}")

        # Major teaching section 2: deliberately stacked directly below section 1.
        with st.container(border=True):
            st.markdown("### From stress to internal force and equilibrium")
            st.markdown(
                "Stress is force per unit area. Once the stress and the area over which it acts "
                "are known, the corresponding internal force can be calculated."
            )
            st.latex(r"F=\sigma A")

            force_cols = st.columns(2, gap="large")
            with force_cols[0]:
                with st.container(border=True):
                    st.markdown("**Concrete compression**")
                    if is_uls:
                        st.markdown(
                            "For ULS, the equivalent concrete stress $\alpha_2 f'_c$ acts over the "
                            "rectangular compression-block area $ba$, where $a=\gamma d_n$."
                        )
                        st.latex(r"a=\gamma d_n")
                        st.latex(r"C_c=\alpha_2 f'_cba")
                    elif is_sls:
                        st.markdown(
                            "For cracked SLS, the concrete compression stress distribution acting over "
                            "the cracked compression zone produces the concrete compression resultant."
                        )
                    else:
                        st.markdown(
                            "For the uncracked state, the concrete stress distribution acting over the "
                            "effective concrete section produces the concrete resultant."
                        )
            with force_cols[1]:
                with st.container(border=True):
                    st.markdown("**Reinforcement layer $i$**")
                    st.markdown(
                        "The stress in each reinforcement layer acts over that layer's steel area."
                    )
                    st.latex(r"F_{s,i}=A_{s,i}f_{s,i}")

            st.markdown("#### Why do we need these forces?")
            st.markdown(
                "The internal concrete and reinforcement forces must balance to satisfy section "
                "equilibrium. If they do not balance, the assumed section state — including the "
                "neutral-axis position where applicable — is not the equilibrium solution."
            )
            st.latex(r"\sum C=\sum T")
            st.markdown(
                "Changing the neutral-axis depth changes the strain profile, which changes the "
                "material stresses and therefore the internal forces. The section solution therefore "
                "closes the loop:"
            )
            st.markdown(
                "**Neutral axis → Strain → Stress → Force → Equilibrium**"
            )

    render_lazy_expander(
        "ℹ️ From strain to stress to internal force",
        _render_material_model_content,
        key="bending_material_model_expander",
    )
    render_timing_mark("bending_page.runtime.material_model.end")
''').strip("\n")
replacement = textwrap.indent(replacement, "            ") + "\n"

new_text = text[:start] + replacement + text[end:]
path.write_text(new_text, encoding="utf-8")
print("Updated bending material teaching panel.")
