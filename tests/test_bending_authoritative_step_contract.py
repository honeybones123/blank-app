import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_authoritative_bending_uls_uses_the_nine_step_explanatory_sequence() -> None:
    source = (ROOT / "bending_tabs.py").read_text(encoding="utf-8")

    expected_titles = (
        "Check 1 — Stress-block parameters",
        "Check 2 — Neutral-axis solution method",
        "Check 3 — Neutral-axis equilibrium",
        "Check 4 — Reinforcement strains and stresses",
        "Check 5 — Internal force resultants",
        "Check 6 — Force-equilibrium verification",
        "Check 7 — Neutral-axis ratio, ductility and strength factor",
        "Check 8 — Nominal and design moment capacity",
        "Check 9 — Final flexural capacity check",
    )
    for title in expected_titles:
        assert title in source

    renderer = (ROOT / "widgets_helpers.py").read_text(encoding="utf-8")
    assert 'uid == "bending_uls_authoritative_strains"' in renderer
    assert 'uid == "bending_uls_authoritative_equilibrium"' in renderer
    assert "_rendering_deferred_bending_uls_check_2" in renderer


def test_authoritative_bending_diagrams_follow_the_equations_they_explain() -> None:
    source = (ROOT / "bending_tabs.py").read_text(encoding="utf-8")

    assert 'uid="bending_uls_authoritative_strains"' in source
    assert "diagram_fn=strain_diagram" in source
    assert '"bending_uls_authoritative_equilibrium_diagram", "Neutral axis and block depth"' in source
    assert '"bending_uls_authoritative_4_diagram", "Internal force resultants"' in source
    assert '"bending_uls_authoritative_7_diagram", "ULS force model and capacity"' in source


def test_authoritative_force_resultant_explanation_uses_rectangular_stress_block() -> None:
    source = (ROOT / "bending_tabs.py").read_text(encoding="utf-8")
    force_box = source[source.index('uid="bending_uls_authoritative_4"'):source.index('uid="bending_uls_authoritative_5"')]

    assert r"C_c=\int_A" not in force_box
    assert r"C_c=\alpha_2f'_cba" in force_box
    assert r"y_{{C_c}}=\frac{{a}}{{2}}" in source
    assert r"R=C-T" in force_box
    assert "concrete_kn + compression_steel_kn" in force_box
    assert "steel_layer_areas_mm2" in source


def test_authoritative_strain_explanation_identifies_and_classifies_each_layer() -> None:
    source = (ROOT / "bending_tabs.py").read_text(encoding="utf-8")

    assert "steel_layer_labels" in source
    assert "zip(layer_areas, steel_depths, stresses, layer_forces)" in source
    assert r"\varepsilon_{{s,i}}=-\varepsilon_{{cu}}" in source
    assert r"\operatorname{{sign}}(\varepsilon_{{s,i}})" in source
    assert 'role = "tension" if stress < 0.0' in source
    assert '"yielded" if yielded else "elastic"' in source
    assert "not from the" in source and "words “top” or “bottom”" in source


def test_neutral_axis_checks_split_method_from_converged_equilibrium() -> None:
    source = (ROOT / "bending_tabs.py").read_text(encoding="utf-8")

    assert "neutral_axis_method_md" in source
    assert "neutral_axis_equilibrium_md" in source
    assert "Direct single-layer solution" in source
    assert "General multi-layer solution" in source
    assert "geometry_table_md" in source
    assert "relative_to_na_md" in source
    assert "Authoritative equilibrium iterations" in source
    assert "iteration_table_md" in source
    assert "active_indices = tuple(index for index, area in enumerate(layer_areas) if area > 1e-9)" in source
    assert "A zero-bar top row is a UI configuration aid" in source


def test_app_prefers_its_own_authoritative_inputs_package() -> None:
    source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert 'LOCAL_INPUTS_SRC = os.path.join(ROOT, "packages", "beamapp-inputs-v2", "src")' in source
    assert "sys.path.insert(0, LOCAL_INPUTS_SRC)" in source


def test_advanced_neutral_axis_math_uses_single_line_display_blocks() -> None:
    source = (ROOT / "bending_tabs.py").read_text(encoding="utf-8")

    assert "$$K_c=\\alpha_2f'_cb\\gamma=({alpha2:.3f})" in source
    assert "$$K_cd_n^2+\\left({b_symbolic}\\right)d_n-\\sum_" in source
    assert "$$\\boxed{{A=K_c=\\alpha_2f'_cb\\gamma}}=" in source
    assert "$$\\boxed{{B={b_symbolic}}}=" in source
    assert "$$\\boxed{{C=-\\sum_" in source
    assert "$$({na_teaching['A'] / 1000.0:.9f})d_n^2+" in source
    assert "$$K_c=\\alpha_2f'_cb\\gamma\n" not in source


def test_authoritative_bending_info_preserves_detailed_heading_and_references() -> None:
    source = (ROOT / "bending_tabs.py").read_text(encoding="utf-8")

    assert 'st.markdown(f"### {heading}\\n\\n{body}")' in source
    assert "#### Why this check matters" in source
    assert "#### References" in source
    assert "[1] AS 3600:2018" in source
    assert "[2] AS 3600:2018" in source


def test_authoritative_bending_info_cites_each_numbered_reference_inline() -> None:
    source = (ROOT / "bending_tabs.py").read_text(encoding="utf-8")
    authoritative = source[source.index("def _render_authoritative_uls_steps("):]
    info_bodies = authoritative.split("content_before=info_control(")[1:10]

    assert len(info_bodies) == 9
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
