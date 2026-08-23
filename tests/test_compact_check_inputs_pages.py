from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

PAGE_CONTRACTS = {
    "engineering_page_sections/bending_inputs.py": {
        "categories": (
            "design_actions",
            "section_material",
            "reinforcement",
        ),
        "widgets": (
            "bending_b",
            "bending_D",
            "bending_fc",
            "bending_cover_{face}",
        ),
    },
    "shear_page_runtime.py": {
        "categories": (
            "design_actions",
            "section_material",
            "shear_reinforcement",
            "method_parameters",
        ),
        "widgets": ("shear_b", "shear_D", "shear_lig_d", "shear_lig_legs", "shear_s_lig"),
    },
    "creep.py": {
        "categories": ("section_member", "material_environment", "time_loading"),
        "widgets": ("cr_b", "cr_D", "cr_faces", "cr_env", "inputs_t_creep", "inputs_age_at_loading"),
    },
    "shrinkage.py": {
        "categories": ("method", "section_member", "material_environment", "time_drying"),
        "widgets": ("sh_method", "sh_b", "sh_D", "sh_faces", "inputs_t_shrink"),
    },
    "crack_page_runtime.py": {
        "categories": (
            "method",
            "section_material",
            "reinforcement",
            "criteria",
            "wall_reinforcement",
            "restraint_parameters",
        ),
        "widgets": ("crack_fc", "crack_b", "crack_D", "crack_cover_bot", "inputs_crack_k1"),
    },
    "deflection_page_runtime.py": {
        "categories": (
            "section_geometry",
            "material_long_term",
            "serviceability_actions",
            "bottom_reinforcement",
            "top_reinforcement",
        ),
        "widgets": ("defl_b", "defl_D", "defl_L", "defl_fc", "defl_support_type"),
    },
}


def test_all_calculation_pages_use_the_shared_panel_and_no_old_rail():
    for filename, contract in PAGE_CONTRACTS.items():
        source = (ROOT / filename).read_text(encoding="utf-8")
        assert "compact_check_input" in source, filename
        assert "render_specialized_widget_rail" not in source, filename
        assert "specialized_widget_rail_columns" not in source, filename
        for category in contract["categories"]:
            assert f'"{category}"' in source, (filename, category)


def test_shared_panel_enforces_two_column_widget_grid():
    source = (
        ROOT / "engineering_page_sections" / "compact_check_inputs" / "renderer.py"
    ).read_text(encoding="utf-8")
    assert "grid-template-columns: repeat(2, minmax(0, 1fr))" in source
    assert "grid-template-columns: minmax(0, 1fr)" in source


def test_bending_combines_top_and_bottom_reinforcement_in_one_card():
    source = (
        ROOT / "engineering_page_sections" / "bending_inputs.py"
    ).read_text(encoding="utf-8")
    assert '"reinforcement",' in source
    assert '"Reinforcement",' in source
    assert '"bottom_reinforcement", "Bottom reinforcement"' not in source
    assert '"top_reinforcement", "Top reinforcement"' not in source
    assert "col_bottom, col_top = st.columns(2" in source


def test_migrated_pages_retain_their_established_widget_keys():
    for filename, contract in PAGE_CONTRACTS.items():
        source = (ROOT / filename).read_text(encoding="utf-8")
        for widget_key in contract["widgets"]:
            assert widget_key in source, (filename, widget_key)


def test_inputs_load_analysis_and_start_do_not_import_the_component():
    for filename in ("inputs_page.py", "design_page_runtime.py", "start_page.py"):
        source = (ROOT / filename).read_text(encoding="utf-8")
        assert "compact_check_inputs" not in source, filename


def test_all_crack_methods_are_owned_by_the_shared_panel():
    source = (ROOT / "crack_page_runtime.py").read_text(encoding="utf-8")
    assert 'page_slug="crack"' in source
    assert 'page_slug="crack_as5100"' in source
    assert 'page_slug="crack_c766"' in source
    assert source.count('key="crack_method"') == 1


def test_shrinkage_alternate_method_keeps_its_own_complete_result_contract():
    source = (ROOT / "shrinkage.py").read_text(encoding="utf-8")
    assert "eps_csd_final = method_result.nominal_drying_shrinkage" in source
    assert "if shrinkage_method == ShrinkageMethod.EXISTING_AS3600.value" in source
    assert "else dict(shrinkage_fallback)" in source
