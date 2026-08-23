import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_authoritative_bending_uls_uses_the_eight_step_explanatory_sequence() -> None:
    source = (ROOT / "engineering_page_sections" / "bending_uls_checks.py").read_text(encoding="utf-8")

    expected_titles = (
        "Check 1 — Concrete stress block",
        "Check 2 — Neutral-axis solution method",
        "Check 3 — Neutral-axis equilibrium",
        "Check 4 — Reinforcement strains and stresses",
        "Check 5 — Internal force resultants",
        "Check 6 — Neutral-axis ratio, ductility and strength factor",
        "Check 7 — Nominal and design moment capacity",
        "Check 8 — Final flexural capacity check",
    )
    for title in expected_titles:
        assert title in source
    assert "Check 6 — Force-equilibrium verification" not in source

    renderer = (ROOT / "widgets_helpers.py").read_text(encoding="utf-8")
    assert 'uid == "bending_uls_authoritative_strains"' in renderer
    assert 'uid == "bending_uls_authoritative_equilibrium"' in renderer
    assert "_rendering_deferred_bending_uls_check_2" in renderer
    forbidden_teaching_text = (
        "Hand derivation verified against authoritative solver",
        "Authoritative production result",
        "Hand-equation result",
        "Authoritative solver verification",
    )
    assert not any(text in source for text in forbidden_teaching_text)


def test_authoritative_bending_diagrams_follow_the_equations_they_explain() -> None:
    source = (ROOT / "engineering_page_sections" / "bending_uls_checks.py").read_text(encoding="utf-8")

    assert 'uid="bending_uls_authoritative_strains"' in source
    assert "bending_uls_authoritative_check4_strain_{moment_sign}" in source
    assert '"bending_uls_authoritative_equilibrium_diagram", "Neutral axis and block depth"' in source
    assert '"bending_uls_authoritative_4_diagram", "Internal force resultants"' in source
    assert '"bending_uls_authoritative_7_diagram", "ULS force model and capacity"' in source


def test_authoritative_force_resultant_explanation_uses_rectangular_stress_block() -> None:
    source = (ROOT / "engineering_page_sections" / "bending_uls_checks.py").read_text(encoding="utf-8")
    force_box = source[source.index('uid="bending_uls_authoritative_4"'):source.index('uid="bending_uls_authoritative_6"')]

    assert r"C_c=\int_A" not in force_box
    assert r"C_c=\alpha_2f'_cba" in force_box
    assert r"y_{{C_c}}=\frac{{a}}{{2}}" in source
    assert "Neutral-axis equilibrium\nwas already established in Check 3" in force_box
    assert r"R=C-T" not in force_box
    assert "concrete_kn + compression_steel_kn" in force_box
    assert "steel_layer_areas_mm2" in source


def test_authoritative_strain_explanation_identifies_and_classifies_each_layer() -> None:
    source = (ROOT / "engineering_page_sections" / "bending_uls_checks.py").read_text(encoding="utf-8")
    check_4 = source[
        source.index('uid="bending_uls_authoritative_strains"'):
        source.index('uid="bending_uls_authoritative_method"')
    ]

    assert "steel_layer_labels" in source
    assert "zip(layer_areas, steel_depths, stresses, layer_forces)" in source
    assert r"\varepsilon_{{s,i}}=-\varepsilon_{{cu}}" in check_4
    assert r"\operatorname{{sign}}(\varepsilon_{{s,i}})" in check_4
    assert 'role = "tension" if stress < 0.0' in source
    assert "_teaching_steel_response_state" in source
    assert "Final reinforcement strain and stress state" in check_4
    assert "{final_layer_table_md}" in check_4
    assert "Elastic trial stress" in source
    assert "Final steel stress" in source
    assert r"F_{{s,i}}=A_{{s,i}}f_{{s,i}}" not in check_4
    assert "Representative equilibrium steps" not in check_4
    assert "words “top” or “bottom”" not in check_4


def test_force_resultant_calculation_is_owned_by_check_5() -> None:
    source = (ROOT / "engineering_page_sections" / "bending_uls_checks.py").read_text(encoding="utf-8")
    check_5 = source[
        source.index('uid="bending_uls_authoritative_4"'):
        source.index('uid="bending_uls_authoritative_6"')
    ]

    assert "Using the final steel stresses from Check 4" in check_5
    assert r"F_{{s,i}}=A_{{s,i}}f_{{s,i}}" in check_5
    assert "Tension-steel resultant" in check_5
    assert "Concrete compression resultant" in check_5
    assert "Compression-steel resultant" in check_5


def test_neutral_axis_checks_split_method_from_converged_equilibrium() -> None:
    source = (ROOT / "engineering_page_sections" / "bending_uls_checks.py").read_text(encoding="utf-8")
    check_2 = source[
        source.index('uid="bending_uls_authoritative_method"'):
        source.index('uid="bending_uls_authoritative_equilibrium"')
    ]
    check_3 = source[
        source.index('neutral_axis_equilibrium_md = rf"""'):
        source.index('na_table_lines = [')
    ]

    assert "neutral_axis_method_md" in source
    assert "neutral_axis_equilibrium_md" in source
    assert "Direct single-layer solution" in source
    assert "General multi-layer equilibrium solution" in source
    assert "geometry_table_md" in source
    assert "**Step 1 — Concrete compression**" in source
    assert r"R(d_n)=\sum C-\sum T" in source
    assert "Representative equilibrium steps" not in check_2
    assert "iteration_table_md" not in check_2
    assert "Final neutral-axis depth" not in check_2
    assert "Final neutral-axis depth" in check_3
    assert "iteration_table_md" in check_3
    assert "active_indices = tuple(index for index, area in enumerate(layer_areas) if area > 1e-9)" in source
    assert "A zero-bar top row is a UI configuration aid" in source


def test_multi_layer_neutral_axis_method_uses_a_six_step_calcbox() -> None:
    source = (ROOT / "engineering_page_sections" / "bending_uls_checks.py").read_text(encoding="utf-8")
    method_card = source[
        source.index("neutral_axis_method_md = rf\"\"\""):
        source.index("# These are deliberately authored display blocks")
    ]

    assert method_card.count("**Step ") == 6
    assert "Calculate the concrete compression force" in method_card
    assert "Convert the steel strain into stress" in method_card
    assert "Accept the neutral-axis depth" in method_card
    assert r"\operatorname{{sign}}(\varepsilon_{{s,i}})" in method_card
    assert r"\displaystyle" not in method_card


def test_check_2_diagram_is_an_explicit_trial_not_the_converged_result() -> None:
    source = (ROOT / "engineering_page_sections" / "bending_uls_checks.py").read_text(encoding="utf-8")

    assert '"Trial stress block"' in source
    assert "trial_neutral_axis=True" in source
    assert '"Trial neutral axis d<sub>n</sub>"' in source
    assert '"a = γ d<sub>n</sub>"' in source


def test_app_prefers_its_own_authoritative_inputs_package() -> None:
    source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert 'LOCAL_INPUTS_SRC = os.path.join(ROOT, "packages", "beamapp-inputs-v2", "src")' in source
    assert "sys.path.insert(0, LOCAL_INPUTS_SRC)" in source


def test_advanced_neutral_axis_math_uses_single_line_display_blocks() -> None:
    source = (ROOT / "engineering_page_sections" / "bending_uls_checks.py").read_text(encoding="utf-8")

    assert "$$K_c=\\alpha_2f'_cb\\gamma=({alpha2:.3f})" in source
    assert "$$K_cd_n^2+\\left({b_symbolic}\\right)d_n-\\sum_" in source
    assert "$$\\boxed{{A=K_c=\\alpha_2f'_cb\\gamma}}=" in source
    assert "$$\\boxed{{B={b_symbolic}}}=" in source
    assert "$$\\boxed{{C=-\\sum_" in source
    assert "$$({na_teaching['A'] / 1000.0:.9f})d_n^2+" in source
    assert "$$K_c=\\alpha_2f'_cb\\gamma\n" not in source


def test_authoritative_bending_info_preserves_detailed_heading_and_references() -> None:
    source = (ROOT / "engineering_page_sections" / "bending_uls_checks.py").read_text(encoding="utf-8")

    assert 'st.markdown(f"### {heading}\\n\\n{body}")' in source
    assert "#### Why this check matters" in source
    assert "#### References" in source
    assert "[1] AS 3600:2018" in source
    assert "[2] AS 3600:2018" in source


def test_authoritative_bending_info_cites_each_numbered_reference_inline() -> None:
    source = (ROOT / "engineering_page_sections" / "bending_uls_checks.py").read_text(encoding="utf-8")
    authoritative = source[source.index("def _render_authoritative_uls_steps("):]
    info_bodies = authoritative.split("content_before=info_control(")[1:9]

    assert len(info_bodies) == 8
    for index, body in enumerate(info_bodies, start=1):
        prose, references = body.split("#### References", 1)
        references = references.split('""",', 1)[0]
        numbers = re.findall(
            r"^\[([0-9]+)\] AS 3600:2018", references, re.MULTILINE
        )
        assert numbers, f"Check 1.{index} has no numbered reference list"
        for number in numbers:
            assert f"[{number}]" in prose, (
                f"Check 1.{index} does not cite reference [{number}] inline"
            )


def test_shared_info_button_hides_current_streamlit_material_caret() -> None:
    source = (ROOT / "widgets_helpers.py").read_text(encoding="utf-8")

    assert '[data-testid="stIconMaterial"]' in source
    assert ".material-symbols-rounded" in source
    assert 'div[data-testid="stPopoverBody"] h3' in source
