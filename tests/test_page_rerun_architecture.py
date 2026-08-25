from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _direct_rerun_calls(path: Path) -> list[int]:
    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    lines: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr not in {"rerun", "experimental_rerun"}:
            continue
        owner = node.func.value
        if isinstance(owner, ast.Name) and owner.id in {"st", "st_module"}:
            lines.append(int(node.lineno))
    return sorted(lines)


def test_general_result_pages_are_fragment_scoped() -> None:
    source = (ROOT / "app.py").read_text(encoding="utf-8-sig")
    expected = {
        "bending": "_render_bending_page_fragment",
        "shear": "_render_shear_page_fragment",
        "creep": "_render_creep_page_fragment",
        "shrinkage": "_render_shrinkage_page_fragment",
        "crack": "_render_crack_page_fragment",
        "deflection": "_render_deflection_page_fragment",
    }
    for slug, renderer in expected.items():
        assert f'"{slug}": (' in source
        assert f'"{slug}": (' in source and renderer in source
        assert f"def {renderer}():" in source
        assert f"@st.fragment\ndef {renderer}():" in source

    assert '"bending": ("Bending", _render_bending_page_fragment)' in source
    assert '"shear": ("Shear", _render_shear_page_fragment)' in source
    assert '"creep": ("Creep", _render_creep_page_fragment)' in source
    assert '"shrinkage": ("Shrinkage", _render_shrinkage_page_fragment)' in source
    assert '"crack": ("Crack Control", _render_crack_page_fragment)' in source
    assert '"deflection": ("Deflection", _render_deflection_page_fragment)' in source


def test_load_analysis_fragment_is_registered_by_the_eager_shell() -> None:
    app_source = (ROOT / "app.py").read_text(encoding="utf-8-sig")
    page_source = (ROOT / "design_page_runtime.py").read_text(encoding="utf-8-sig")

    assert "@st.fragment\ndef _render_design_page_fragment():" in app_source
    assert '"design": ("Load Analysis", _render_design_page_fragment)' in app_source
    assert "@st.fragment\ndef render_sfd_bmd_page():" not in page_source


def test_load_analysis_display_controls_commit_to_the_page_owned_draft() -> None:
    source = (ROOT / "design_page_runtime.py").read_text(encoding="utf-8-sig")

    source_callback = source.split("def _on_design_actions_source_change() -> None:", 1)[1].split(
        "source_options =", 1
    )[0]
    slider_callback = source.split("def _on_design_section_slider_change() -> None:", 1)[1].split(
        "def _on_design_section_input_change() -> None:", 1
    )[0]
    peak_widget = source.split('label="Show |M|max"', 1)[1].split(")", 1)[0]

    assert "load_analysis_store.capture_widgets()" in source_callback
    assert "load_analysis_store.capture_widgets()" in slider_callback
    assert "on_change=load_analysis_store.capture_widgets" in peak_widget


def test_shear_page_heading_has_one_shell_owner() -> None:
    app_source = (ROOT / "app.py").read_text(encoding="utf-8-sig")
    shear_source = (ROOT / "shear_page_runtime.py").read_text(encoding="utf-8-sig")

    assert '"shear": "Shear & Torsion"' in app_source
    assert 'render_result_page_title("Shear & Torsion"' not in shear_source


def test_result_pages_use_one_neutral_refresh_contract() -> None:
    source = (ROOT / "app.py").read_text(encoding="utf-8-sig")
    contract_start = source.index("def _render_result_page_fragment(")
    contract_end = source.index("\n\n@st.fragment", contract_start)
    contract_source = source[contract_start:contract_end]
    assert contract_source.count("_prepare_result_page_workspace(slug)") == 1
    assert contract_source.count("_ensure_general_page_engineering_publication(slug)") == 1
    for slug in ("bending", "shear", "creep", "shrinkage", "crack", "deflection"):
        assert source.count(f'_render_result_page_fragment("{slug}",') == 1
    assert "_refresh_result_page_fragment_calculations" not in source
    assert "CODEX_DIAGNOSTIC_SKIP_LEGACY_RESULT_PROJECTION" not in source
    assert "application.result_page_workspace" not in source
    assert "inputs_page.hydrate_committed_design_action_widgets(" in source
    assert "resolved_projection=True" in source


def test_global_header_actions_are_fragment_scoped() -> None:
    source = (ROOT / "app.py").read_text(encoding="utf-8-sig")
    assert "@st.fragment\ndef _render_header_actions(" in source
    assert "_render_header_actions(\n                user_id=user_id," in source


def test_result_pages_have_no_direct_app_rerun_authority() -> None:
    pages = (
        "bending_page_runtime.py",
        "shear_page_runtime.py",
        "creep_page_runtime.py",
        "shrinkage_page_runtime.py",
        "crack_page_runtime.py",
        "deflection_page_runtime.py",
    )
    offenders = {
        name: _direct_rerun_calls(ROOT / name)
        for name in pages
        if _direct_rerun_calls(ROOT / name)
    }
    assert offenders == {}


def test_result_pages_do_not_write_debug_session_inventories_during_render() -> None:
    """Page navigation must never perform diagnostic filesystem writes."""

    pages = (
        "bending_page_runtime.py",
        "shear_page_runtime.py",
        "creep_page_runtime.py",
        "shrinkage_page_runtime.py",
        "crack_page_runtime.py",
        "deflection_page_runtime.py",
    )
    offenders = {
        name: "dump_session_state_inventory"
        for name in pages
        if "dump_session_state_inventory"
        in (ROOT / name).read_text(encoding="utf-8-sig")
    }
    assert offenders == {}


def test_direct_app_reruns_are_confined_to_shell_transition_owners() -> None:
    approved = {
        "app.py",  # project creation modal and authentication/shell transitions
        "start_page.py",  # explicit navigation to another page
        "state_and_helpers.py",  # create/reset beam workspace
        "inputs_page_modules/fragments.py",  # centralized scoped compatibility boundary
        # These two owners request only the engineering workspace fragment;
        # their unscoped call is a compatibility fallback for older Streamlit
        # and test doubles, not ordinary Runtime authority.
        "inputs_application/engineering_workspace.py",
        # Mounted input cards own only a fragment-scoped header visibility
        # transition; their widget bodies stay mounted outside that fragment.
        "engineering_page_sections/mounted_card_shell.py",
    }
    offenders: dict[str, list[int]] = {}
    for path in ROOT.rglob("*.py"):
        relative = path.relative_to(ROOT).as_posix()
        if relative.startswith(
            (
                "tests/",
                "tools/",
                "packages/beamapp-inputs-v2/",
                ".venv/",
                "venv/",
                "env/",
            )
        ):
            continue
        lines = _direct_rerun_calls(path)
        if lines and relative not in approved:
            offenders[relative] = lines
    assert offenders == {}


def test_removed_legacy_apply_path_cannot_reintroduce_full_page_rerun() -> None:
    source = (ROOT / "state_and_helpers.py").read_text(encoding="utf-8-sig")
    assert "def apply_auto_design_results(" not in source


def test_load_analysis_has_no_competing_scroll_restoration_authority() -> None:
    source = (ROOT / "design_page_runtime.py").read_text(encoding="utf-8-sig")
    assert "_install_design_scroll_preserver" not in source
    assert "beam_design_scroll_restore" not in source
    assert "__beamDesignScrollObserver" not in source


def test_inputs_commits_do_not_enqueue_a_redundant_fragment_wake() -> None:
    source = (ROOT / "state_and_helpers.py").read_text(encoding="utf-8-sig")
    start = source.index("def _request_inputs_engineering_commit(")
    end = source.index("\ndef _engineering_widget_owner_slug(", start)
    commit_source = source[start:end]

    assert "request_inputs_fragment_wake" not in commit_source
    assert "auto_rerun" not in commit_source


def test_inputs_commit_identity_includes_selected_calculated_actions() -> None:
    """The early workspace cache cannot reuse a preceding zero-action solve."""

    source = (ROOT / "state_and_helpers.py").read_text(encoding="utf-8-sig")
    start = source.index("def _request_inputs_engineering_commit(")
    end = source.index("\ndef _engineering_widget_owner_slug(", start)
    commit_source = source[start:end]

    assert "uses_load_analysis_actions(st.session_state)" in commit_source
    assert "authoritative_action_source_projection(st.session_state)" in commit_source
    assert "live_snapshot.update(" in commit_source
    assert 'live_snapshot["uls_Mstar_pos_manual"]' not in commit_source
    assert 'live_snapshot["manual_uls_Vstar"]' not in commit_source


def test_inputs_widget_coordinator_has_no_second_rerun_authority() -> None:
    source = (ROOT / "inputs_page_modules/widgets/render_coordinators.py").read_text(
        encoding="utf-8-sig"
    )

    assert "rerun_inputs_current_scope" not in source
    assert "_inputs_diagram_settle_revision" not in source


def test_general_result_pages_project_committed_actions_before_refresh() -> None:
    source = (ROOT / "app.py").read_text(encoding="utf-8-sig")
    start = source.index("def _prepare_result_page_workspace(")
    end = source.index("\ndef _render_result_page_fragment(", start)
    boundary = source[start:end]

    projection = boundary.index(
        "project_committed_action_source_for_result_page()"
    )
    widget_hydration = boundary.index(
        "inputs_page.hydrate_committed_design_action_widgets("
    )
    assert projection < widget_hydration


def test_explicit_page_routes_do_not_mount_guest_preference_component() -> None:
    """A cold component response must not rerun an already selected route."""

    source = (ROOT / "app.py").read_text(encoding="utf-8-sig")
    call = source.index("guest_preference = render_guest_preference_bootstrap()")
    guard = source.rfind(
        'if st.session_state.get("_guest_opening_default_pending"):',
        0,
        call,
    )

    assert guard >= 0
    assert call - guard < 500


def test_navigation_adopts_query_page_once_then_keeps_widget_authority() -> None:
    """A replaceState URL cannot become a stale second page selector."""

    source = (ROOT / "app.py").read_text(encoding="utf-8-sig")
    assert 'QUERY_PAGE_ADOPTED_KEY = "_router_initial_query_page_adopted"' in source
    assert (
        "if not st.session_state.get(QUERY_PAGE_ADOPTED_KEY) or jump_pending:"
        in source
    )
    assert "if st.session_state.get(LAST_QP_KEY) != selected_slug:" in source
    assert 'if st.query_params.get("page") != selected_slug:' not in source


def test_calculation_coordinator_never_hydrates_live_inputs_widgets() -> None:
    """A calculation refresh may read a beam snapshot but cannot own widgets."""

    source = (
        ROOT / "inputs_application" / "page_runtime" / "setup.py"
    ).read_text(encoding="utf-8-sig")
    start = source.index(
        "def _ensure_authoritative_design_result_current_coordinator("
    )
    read_boundary = source.index("    if uses_load_analysis_actions(", start)
    snapshot_read_source = source[start:read_boundary]

    assert "st.session_state[widget_key] =" not in snapshot_read_source
    assert '"owner": "router_only"' in snapshot_read_source
    assert '"applied": False' in snapshot_read_source


def test_final_calculation_state_reapplies_selected_load_analysis_projection() -> None:
    """The final beam-snapshot rebuild cannot discard derived actions."""

    source = (
        ROOT / "inputs_application" / "page_runtime" / "setup.py"
    ).read_text(encoding="utf-8-sig")
    committed_projection = source.index("    committed_projection = (")
    final_rebuild = source.index(
        "    current_state = rebuild_engineering_derived_state(committed_projection)",
        committed_projection,
    )
    boundary = source[committed_projection:final_rebuild]

    assert (
        "committed_projection = "
        "_project_selected_action_source_current_coordinator(" in boundary
    )
    assert "if uses_load_analysis_actions(committed_projection):" in boundary
    assert "committed_projection.update(" in boundary
    assert (
        "authoritative_action_source_projection(committed_projection)" in boundary
    )


def test_calculated_action_projection_participates_in_workspace_identity() -> None:
    """A changed Load Analysis solve must invalidate the Inputs calculation."""

    source = (
        ROOT / "inputs_application" / "page_runtime" / "setup.py"
    ).read_text(encoding="utf-8-sig")
    start = source.index(
        "def _canonical_input_transaction_state_current_coordinator("
    )
    end = source.index("\ndef _reconcile_initial_reinforcement_widget_state(", start)
    transaction_source = source[start:end]

    assert (
        "action_source_state = "
        "_project_selected_action_source_current_coordinator(" in transaction_source
    )
    assert "if uses_load_analysis_actions(action_source_state):" in transaction_source
    assert "transaction.update(" in transaction_source
    assert (
        "authoritative_action_source_projection(action_source_state)"
        in transaction_source
    )
    # Derived action identity is included directly; it is never reassigned to
    # the independent Beam Inputs manual owner fields.
    assert 'transaction["uls_Mstar_pos_manual"]' not in transaction_source
    assert 'transaction["manual_uls_Vstar"]' not in transaction_source


def test_load_analysis_publishes_solved_actions_before_presentation_work() -> None:
    """Cold navigation cannot interrupt action publication after the solve."""

    source = (ROOT / "design_page_runtime.py").read_text(encoding="utf-8-sig")
    solve_boundary = source.index("    M_pos_max_uls = ")
    early_publication = source.index("    _publish_local_results(", solve_boundary)
    presentation_work = source.index("    M_max_abs = ", solve_boundary)
    publication = source[early_publication:presentation_work]

    assert early_publication < presentation_work
    for key in (
        "sfd_Mmax_abs_kNm",
        "sfd_Vmax_abs_kN",
        "sfd_Msls_max_kNm",
        "sfd_Vsls_max_kN",
        "M_pos_max_uls_kNm",
        "M_neg_min_uls_kNm",
        "M_pos_max_sls_kNm",
        "M_neg_min_sls_kNm",
    ):
        assert key in publication


def test_action_source_switch_never_commits_derived_controls_as_manual_actions() -> None:
    """Leaving Load Analysis must only move the source pointer."""

    source = (
        ROOT / "inputs_application" / "action_source_transaction.py"
    ).read_text(encoding="utf-8-sig")

    assert "def _commit_manual_actions_before_source_change" in source
    assert "if bool(state.get(INPUTS_ACTION_SOURCE_TOGGLE_KEY, False))" in source
    assert "before_commit=_commit_manual_actions_before_source_change" in source
    assert "before_commit=runtime.reconcile_design_actions" not in source
    load_analysis_exit = source.index("if uses_load_analysis_actions(state):")
    reconcile = source.index("runtime.reconcile_design_actions()", load_analysis_exit)
    assert load_analysis_exit < reconcile


def test_inputs_action_source_transaction_hydrates_before_manual_reconcile() -> None:
    source = (
        ROOT / "inputs_application" / "action_source_transaction.py"
    ).read_text(encoding="utf-8-sig")

    hydrate_index = source.index("hydrate_actions(force=True)")
    reconcile_index = source.index("runtime.reconcile_design_actions()", hydrate_index)
    assert hydrate_index < reconcile_index

    page_source = (ROOT / "inputs_page.py").read_text(encoding="utf-8-sig")
    fragment_start = page_source.index("def _render_v2_workspace_fragment(")
    fragment_end = page_source.index("\ndef render_inputs_page()", fragment_start)
    fragment_source = page_source[fragment_start:fragment_end]
    assert "render_inputs_action_source_transaction(" in fragment_source
    assert fragment_source.index("render_inputs_action_source_transaction(") < fragment_source.index(
        "render_engineering_workspace("
    )


def test_inputs_apply_is_consumed_before_action_source_transaction_or_rendering() -> None:
    source = (ROOT / "inputs_page.py").read_text(encoding="utf-8-sig")
    start = source.index("def _render_v2_workspace_fragment(")
    end = source.index("\ndef render_inputs_page()", start)
    fragment_source = source[start:end]

    apply_index = fragment_source.index("_INPUTS_PAGE_RUNTIME.handle_pending_apply()")
    action_source_index = fragment_source.index("render_inputs_action_source_transaction(")
    render_index = fragment_source.index("render_engineering_workspace(")
    assert apply_index < action_source_index < render_index


def test_apply_routing_never_requests_an_explicit_rerun_or_polling_wake() -> None:
    source = (ROOT / "inputs_page_modules" / "apply_routing.py").read_text(
        encoding="utf-8-sig"
    )
    assert ".rerun(" not in source
    assert "request_inputs_fragment_wake" not in source
    assert "current_inputs_fragment_id" not in source


def test_runtime_has_no_background_design_brain_publication_path() -> None:
    production_paths = (
        ROOT / "app.py",
        ROOT / "state_and_helpers.py",
        ROOT / "inputs_application" / "engineering_workspace.py",
        ROOT / "inputs_application" / "page_runtime" / "setup.py",
    )
    forbidden = (
        "design_brain_polling",
        "start_design_brain_polling",
        "refresh_inputs_design_brain_result_background",
        "DesignBrainJobService",
    )
    for path in production_paths:
        source = path.read_text(encoding="utf-8-sig")
        for symbol in forbidden:
            assert symbol not in source, f"{path.name} retains {symbol}"

    assert not (ROOT / "inputs_application" / "design_brain_polling.py").exists()
    assert not (ROOT / "inputs_application" / "design_brain_job_service.py").exists()
    assert not (ROOT / "inputs_application" / "design_brain_job_worker.py").exists()


def test_calcbox_has_no_duplicate_dom_observer_refresh_path() -> None:
    source = (ROOT / "widgets_helpers.py").read_text(encoding="utf-8-sig")
    assert "new MutationObserver" not in source
    assert "obs.observe(" not in source


def test_design_brain_renderer_projects_result_and_binds_one_typed_apply_handler() -> None:
    source = (ROOT / "inputs_application" / "engineering_workspace.py").read_text(
        encoding="utf-8-sig"
    )
    start = source.index("def render_inputs_design_guide_fragment_section(")
    end = source.index("\ndef render_inputs_async_design_brain_fragment(", start)
    renderer_source = source[start:end]

    assert renderer_source.count("apply_handler=runtime.handle_pending_apply") == 1
    assert "refresh_design_brain_result" not in renderer_source
    assert "refresh_authoritative_result" not in renderer_source
    assert "render_v2_design_guide_loading_shell" not in renderer_source
    assert "start_design_brain_polling" not in renderer_source
    assert "stop_design_brain_polling" not in renderer_source
    assert "request_inputs_fragment_wake" not in renderer_source
    assert ".rerun(" not in renderer_source
    assert "fragment_store.publish(" in renderer_source


def test_inputs_workspace_uses_ordered_engineering_controls_and_brain_fragments() -> None:
    page_source = (ROOT / "inputs_page.py").read_text(encoding="utf-8-sig")
    assert "include_design_brain=False" in page_source
    assert 'fragment_name="engineering_controls"' in page_source
    assert 'fragment_name="design_brain"' in page_source
    assert 'fragment_name="engineering_calculation"' in page_source
    assert "render_inputs_deferred_design_brain_fragment" in page_source
    assert "run_every=0.5" in page_source

    workspace_source = (ROOT / "inputs_application" / "engineering_workspace.py").read_text(
        encoding="utf-8-sig"
    )
    assert "render_inputs_deferred_design_brain_fragment" in workspace_source
    assert "inputs-v2-design-brain-runtime-loading" in workspace_source

    fragment_source = (ROOT / "inputs_page_modules" / "fragments.py").read_text(
        encoding="utf-8-sig"
    )
    assert "run_every: str | float | None = None" in fragment_source


def test_inputs_workspace_has_revision_bound_design_brain_publication() -> None:
    source = (ROOT / "inputs_application" / "engineering_workspace.py").read_text(
        encoding="utf-8-sig"
    )
    assert "def render_inputs_design_guide_fragment_section(" in source
    assert "authoritative_result.engineering_hash == identity.engineering_hash" in source
    assert "fragment_store.publish(" in source


def test_each_result_page_has_one_workspace_refresh_authority() -> None:
    source = (ROOT / "app.py").read_text(encoding="utf-8-sig")
    pages = ("bending", "shear", "creep", "shrinkage", "crack", "deflection")
    for index, page in enumerate(pages):
        start = source.index(f"def _render_{page}_page_fragment()")
        if index + 1 < len(pages):
            end = source.index(f"def _render_{pages[index + 1]}_page_fragment()", start)
        else:
            end = source.index("\ndef ", start + 5)
        fragment_source = source[start:end]
        assert fragment_source.count(
            f'_render_result_page_fragment("{page}",'
        ) == 1
        assert "_refresh_result_page_fragment_calculations()" not in fragment_source


def test_inputs_tail_has_no_implicit_scroll_on_widget_or_toggle_rerender() -> None:
    tail_runtime = (ROOT / "inputs_application/page_runtime/tail.py").read_text(
        encoding="utf-8-sig"
    )
    tail_coordinator = (ROOT / "inputs_page_modules/tail.py").read_text(
        encoding="utf-8-sig"
    )

    assert "_inputs_inject_scroll_to_design_actions" not in tail_runtime
    assert "inject_scroll_to_design_actions_fn" not in tail_coordinator
    assert "scrollIntoView" not in tail_runtime


def test_summary_tables_are_session_cached_authoritative_publication_projections() -> None:
    cache_source = (
        ROOT / "inputs_page_modules/summaries/state_cache.py"
    ).read_text(encoding="utf-8-sig")

    for family_key in ("_bend_pack", "_shear_pack", "_crack_pack", "_defl_pack"):
        assert f'ss["{family_key}"]' in cache_source
    assert "authoritative_packs" in cache_source
    assert "copy.deepcopy(authoritative_packs" in cache_source


def test_calculation_card_css_is_owned_by_shell_and_survives_fragment_clicks() -> None:
    app_source = (ROOT / "app.py").read_text(encoding="utf-8-sig")

    assert "apply_step_summary_expander_css," in app_source
    style_call = (
        'hc_try("css.apply_step_summary_expander_css", '
        "apply_step_summary_expander_css)"
    )
    assert style_call in app_source
    assert app_source.index("begin_render_cycle()") < app_source.index(
        style_call,
        app_source.index("begin_render_cycle()"),
    )


def test_authoritative_summaries_publish_before_heavy_page_content() -> None:
    """The first visible calculation result must not be a late-filled slot."""

    contracts = {
        "shear_page_runtime.py": (
            'render_timing_mark("shear_page.runtime.summary.start")',
            'render_timing_mark("shear_page.runtime.visualisation.start")',
        ),
        "creep_page_runtime.py": (
            "summary_values = compute_creep_results(publish=True)",
            "creep_inputs = render_creep_inputs(",
        ),
        "shrinkage_page_runtime.py": (
            "summary_values = compute_shrinkage_results(publish=True)",
            "inputs = render_shrinkage_inputs(",
        ),
        "crack_page_runtime.py": (
            "crack_pack = build_crack_check_rows_from_state(st.session_state)",
            'render_timing_mark("crack_page.runtime.inputs.start")',
        ),
        "deflection_page_runtime.py": (
            'render_timing_mark("deflection_page.runtime.summary_checks.start")',
            "def _seed_widget_from_shared(",
        ),
    }
    entrypoints = {
        "shear_page_runtime.py": "def render_shear():",
        "creep_page_runtime.py": "def render_creep():",
        "shrinkage_page_runtime.py": "def render_shrinkage():",
        "crack_page_runtime.py": "def render_crack():",
        "deflection_page_runtime.py": "def render_deflection():",
    }

    for filename, (summary_marker, heavy_marker) in contracts.items():
        source = (ROOT / filename).read_text(encoding="utf-8-sig")
        page_source = source[source.index(entrypoints[filename]) :]
        assert page_source.index(summary_marker) < page_source.index(heavy_marker)
        assert "top_summary_placeholder = st.empty()" not in page_source


def test_bending_summary_binding_is_deferred_without_changing_layout() -> None:
    """The browser component must not delay or shift the visible shell."""

    source = (ROOT / "bending_page_runtime.py").read_text(encoding="utf-8-sig")
    frame = source.index("shell_content = bending_page_shell.reserve_content(st)")
    calculation_shell = source.index(
        "render_bending_calculation_loading_shell(", frame
    )
    diagram_panel = source.index(
        "_render_bending_diagram_bundle_panel(", calculation_shell
    )
    binding = source.index("bind_summary_clicks()", diagram_panel)
    diagram_source = (
        ROOT / "engineering_page_sections/bending_diagram_bundle.py"
    ).read_text(
        encoding="utf-8-sig"
    )

    assert frame < calculation_shell < diagram_panel < binding
    assert "data-bending-diagrams-layout-slot" in diagram_source
    shell_source = (
        ROOT / "engineering_page_sections/bending_diagrams.py"
    ).read_text(encoding="utf-8-sig")
    assert ".st-key-bending_primary_plot_frame" in shell_source
    assert "> .st-key-bending_diagram_shell" in shell_source
    assert "margin-top: 16.640625px" not in diagram_source
