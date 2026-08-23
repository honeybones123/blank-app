from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def _top_level_function(path: str, name: str) -> str:
    text = _read(path)
    marker = f"def {name}("
    start = text.index(marker)
    end = text.find("\ndef ", start + len(marker))
    return text[start:] if end < 0 else text[start:end]


def test_registry_defines_the_six_production_calculation_pages():
    text = _read("application/page_module_registry.py")
    expected = {"bending", "shear", "creep", "shrinkage", "crack", "deflection"}
    for slug in expected:
        assert f'"{slug}": PageModuleSpec(' in text
    assert text.count("PageModuleSpec(") == len(expected)


def test_bending_summary_renders_before_explainer_inputs_diagram_and_checks():
    text = _top_level_function("bending_page_runtime.py", "render_bending")
    summary = text.index("summary_result = render_bending_summary(")
    summary_mark = text.index("bending_page.runtime.summary_table.rendered")
    explainer = text.index("render_page_explainer_expander(_render_bending_explainer)")
    inputs = text.index("with inputs_placeholder.container():")
    diagram = text.index("_render_bending_diagram_bundle_panel(")
    checks = text.index("render_bending_checks(st_module=st, checks=checks_snapshot)")
    authority = text.index("build_bending_check_rows_from_state(st.session_state)")

    assert authority < summary < summary_mark < explainer
    assert summary < inputs
    assert summary < diagram
    assert summary < checks


def test_shear_summary_renders_before_explainer_inputs_visualisation_and_checks():
    text = _top_level_function("shear_page_runtime.py", "render_shear")
    authority = text.index("build_shear_check_rows_from_state(st.session_state)")
    snapshot = text.index("shear_page_snapshot = build_shear_page_snapshot(")
    summary = text.index("render_shear_summary(", authority)
    explainer = text.index("render_explainer=lambda: render_shear_explainer(")
    visualisation = text.index(
        "shear_page_shell = ShearPageShell.reserve_after_summary("
    )
    inputs = text.index('render_timing_mark("shear_page.runtime.inputs.start")')
    checks = text.index('render_timing_mark("shear_page.runtime.checks.start")')

    assert authority < snapshot < summary < explainer
    assert summary < visualisation
    assert summary < inputs
    assert summary < checks


def test_creep_summary_renders_before_explainer_inputs_and_diagram_placeholder():
    text = _top_level_function("creep_page_runtime.py", "render_creep")
    authority = text.index("summary_values = compute_creep_results(publish=True)")
    summary = text.index("render_creep_summary(", authority)
    explainer = text.index(
        "render_page_explainer_expander(lambda: render_creep_explainer(st))"
    )
    inputs = text.index("render_creep_inputs(")
    diagram = text.index("CreepPageShell.reserve_visualisation(st)")

    assert authority < summary < explainer
    assert summary < inputs
    assert summary < diagram
    assert 'current_authoritative_family(st.session_state, "creep")' in _read(
        "creep_page_runtime.py"
    )


def test_shrinkage_summary_renders_before_explainer_inputs_and_diagram_placeholder():
    text = _top_level_function("shrinkage_page_runtime.py", "render_shrinkage")
    authority = text.index("summary_values = compute_shrinkage_results(publish=True)")
    summary = text.index("render_shrinkage_summary(", authority)
    explainer = text.index("render_page_explainer_expander(")
    inputs = text.index("render_shrinkage_inputs(")
    diagram = text.index("ShrinkagePageShell.reserve_visualisation(st)")

    assert authority < summary < explainer
    assert summary < inputs
    assert summary < diagram
    assert 'current_authoritative_family(st.session_state, "shrinkage")' in _read(
        "shrinkage_page_runtime.py"
    )


def test_deflection_summary_renders_before_explainer_inputs_and_diagram_placeholder():
    text = _top_level_function("deflection_page_runtime.py", "render_deflection")
    authority = text.index("build_deflection_check_rows_from_state(st.session_state)")
    summary = text.index("render_deflection_summary(", authority)
    inputs = text.index('render_timing_mark("deflection_page.runtime.inputs.start")')
    diagram = text.index("diagram_placeholder = st.empty()")

    assert authority < summary
    assert summary < inputs
    assert summary < diagram

    summary_source = _read("engineering_page_sections/deflection_summary.py")
    assert summary_source.index("render_clickable_summary_table(") < summary_source.index(
        "render_page_explainer_expander("
    )


def test_crack_as3600_summary_renders_before_explainer_and_inputs():
    text = _top_level_function("crack_page_runtime.py", "render_crack")
    authority = text.index("build_crack_check_rows_from_state(st.session_state)")
    summary = text.index("render_crack_summary(", authority)
    inputs = text.index('render_timing_mark("crack_page.runtime.inputs.start")', authority)

    assert authority < summary < inputs


def test_crack_alternate_method_summary_helper_is_result_first():
    text = _top_level_function(
        "engineering_page_sections/crack_summary.py", "render_crack_summary"
    )
    summary = text.index("clicked_uid = render_clickable_summary_table(")
    explainer = text.index("render_page_explainer_expander(")
    assert summary < explainer


def test_summary_first_migration_keeps_existing_input_card_and_lazy_boundaries():
    shear = _top_level_function("shear_page_runtime.py", "render_shear")
    crack = _top_level_function("crack_page_runtime.py", "render_crack")
    deflection = _top_level_function("deflection_page_runtime.py", "render_deflection")
    creep = _top_level_function("creep_page_runtime.py", "render_creep")
    shrinkage = _top_level_function("shrinkage_page_runtime.py", "render_shrinkage")

    assert "render_shear_inputs(" in shear
    assert "render_as3600_inputs(" in crack
    assert "compact_check_input_columns(" in deflection
    assert "render_creep_inputs(" in creep
    assert "render_shrinkage_inputs(" in shrinkage
    assert "shear_page_shell = ShearPageShell.reserve_after_summary(" in shear
    assert "shear_page_shell.render_visualisation(" in shear
    assert "diagram_placeholder = st.empty()" in deflection
