from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_shared_stable_tabs_are_scoped_native_view_only_tabs() -> None:
    source = (ROOT / "engineering_page_sections" / "stable_tabs.py").read_text(
        encoding="utf-8"
    )

    assert "return tuple(st_module.tabs(tab_labels))" in source
    assert "st_module.radio(" not in source
    assert 'const listenerKey = "__sbStableInteractionRuntime"' in source
    assert "stableTabFor(event.target)" in source
    assert "tabset?.dataset?.sbTabScope" in source
    assert "tagStableTabsets()" in source
    assert 'data-sb-tab-scope=' in source
    assert "session_state" not in source


def test_bending_state_switch_has_one_server_owned_plot_host() -> None:
    helper = (ROOT / "engineering_page_sections" / "stable_tabs.py").read_text(
        encoding="utf-8"
    )
    diagrams = (
        ROOT / "engineering_page_sections" / "bending_diagram_bundle.py"
    ).read_text(encoding="utf-8")
    shell = (
        ROOT / "engineering_page_sections" / "bending_diagrams.py"
    ).read_text(encoding="utf-8")

    assert 'key="bending_state_main"' in diagrams
    assert diagrams.count("st.plotly_chart(") == 1
    assert shell.count(".js-plotly-plot .scatterlayer .trace") == 1
    assert shell.count(".js-plotly-plot g.shapelayer .shape-group") == 1
    assert shell.count(".js-plotly-plot .annotation") == 1
    assert "bending_state_plot_" not in diagrams
    assert "state_figures" not in diagrams
    assert "data-bending-selected-state" in diagrams
    assert "switchPreloadedPlotlyVisibility" not in helper
    assert "switchPreloadedPlotlyState" not in helper
    assert "node.style.opacity" not in helper
    assert "dataset.sbPlotlyState" not in helper
    assert "data-sb-preloaded-plotly-state" not in helper
    assert "Plotly.react" not in helper
    assert "Plotly.update" not in helper


def test_tab_scroll_preservation_is_one_shot_and_yields_to_user_intent() -> None:
    source = (ROOT / "engineering_page_sections" / "stable_tabs.py").read_text(
        encoding="utf-8"
    )

    assert "pendingTabRestore" in source
    assert "pendingWidgetRestore" not in source
    assert "sawReadyRemoval" not in source
    assert "preserve_scroll_for_preceding_widget" not in source
    assert "cancelPendingScrollPreservation" in source
    for event_name in ("wheel", "touchmove", "PageDown", "PageUp", "Home", "End"):
        assert event_name in source
    assert "holdPosition" not in source
    assert "MutationObserver(lockScroll)" not in source
    assert "3500" not in source
    assert "750" not in source
    assert "event.preventDefault()" not in source


def test_synchronized_tabs_remain_browser_only_presentation_state() -> None:
    source = (ROOT / "engineering_page_sections" / "stable_tabs.py").read_text(
        encoding="utf-8"
    )

    assert "def synchronize_stable_tab_scopes(" in source
    assert "sessionStorage.setItem" in source
    assert "targetButtons[safe].click()" in source
    assert "st_module.radio(" not in source
    assert "st_module.session_state" not in source


def test_calculation_pages_use_one_shared_stable_tab_boundary() -> None:
    for filename, scope in (
        ("bending_page_runtime.py", "bending-calculation-checks"),
        ("shear_page_runtime.py", "shear-calculation-checks"),
        ("creep.py", "creep-calculation-checks"),
    ):
        source = (ROOT / filename).read_text(encoding="utf-8-sig")
        assert "from engineering_page_sections.stable_tabs import" in source
        assert "render_stable_tabs" in source
        assert f'scope_id="{scope}"' in source
        assert "render_lazy_check_tab_selector" not in source

    assert not (ROOT / "engineering_page_sections" / "lazy_check_tabs.py").exists()


def test_diagram_tabs_use_the_shared_stable_boundary() -> None:
    bending = (
        ROOT / "engineering_page_sections" / "bending_diagram_bundle.py"
    ).read_text(encoding="utf-8")
    shear = (ROOT / "shear_page_runtime.py").read_text(encoding="utf-8-sig")
    creep = (ROOT / "creep.py").read_text(encoding="utf-8-sig")
    crack = (ROOT / "crack_page_runtime.py").read_text(encoding="utf-8")

    assert 'scope_id="bending-section-diagrams"' in bending
    assert 'scope_id="shear-visualisation-diagrams"' in shear
    assert 'scope_id="creep-side-view-diagrams"' in creep
    assert 'scope_id="crack-method-diagrams"' in crack
    assert 'scope_id="crack-as5100-method-diagrams"' in crack


def test_bending_owns_one_stable_interaction_runtime() -> None:
    runtime = (ROOT / "bending_page_runtime.py").read_text(encoding="utf-8")
    diagrams = (
        ROOT / "engineering_page_sections" / "bending_diagram_bundle.py"
    ).read_text(encoding="utf-8")

    assert 'scope_id="bending-calculation-checks"' in runtime
    assert 'scope_id="bending-section-diagrams"' in diagrams
    assert "install_runtime=False" in diagrams


def test_cross_page_calculation_jumps_target_native_tabs() -> None:
    source = (ROOT / "jump_nav.py").read_text(encoding="utf-8")

    assert "'[role=\"tab\"], button[data-baseweb=\"tab\"]'" in source
