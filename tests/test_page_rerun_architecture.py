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


def test_result_pages_use_one_neutral_refresh_contract() -> None:
    source = (ROOT / "app.py").read_text(encoding="utf-8-sig")
    for slug in ("bending", "shear", "creep", "shrinkage", "crack", "deflection"):
        assert f'_prepare_result_page_workspace("{slug}")' in source
    # One function definition plus its single call from the neutral contract.
    assert source.count("_refresh_result_page_fragment_calculations()") == 2
    assert "inputs_page.hydrate_committed_design_action_widgets(force=True)" in source


def test_global_header_actions_are_fragment_scoped() -> None:
    source = (ROOT / "app.py").read_text(encoding="utf-8-sig")
    assert "@st.fragment\ndef _render_header_actions(" in source
    assert "_render_header_actions(\n                user_id=user_id," in source


def test_result_pages_have_no_direct_app_rerun_authority() -> None:
    pages = (
        "bending_page_runtime.py",
        "shear_page_runtime.py",
        "creep.py",
        "shrinkage.py",
        "crack_page_runtime.py",
        "deflection_page_runtime.py",
    )
    offenders = {
        name: _direct_rerun_calls(ROOT / name)
        for name in pages
        if _direct_rerun_calls(ROOT / name)
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


def test_inputs_widget_coordinator_has_no_second_rerun_authority() -> None:
    source = (ROOT / "inputs_page_modules/widgets/render_coordinators.py").read_text(
        encoding="utf-8-sig"
    )

    assert "rerun_inputs_current_scope" not in source
    assert "_inputs_diagram_settle_revision" not in source


def test_inputs_hydrates_committed_actions_before_summary_workspace_render() -> None:
    source = (ROOT / "inputs_page.py").read_text(encoding="utf-8-sig")
    start = source.index("def _render_v2_workspace_fragment(")
    end = source.index("\ndef render_inputs_page()", start)
    fragment_source = source[start:end]

    hydrate_index = fragment_source.index(
        "hydrate_committed_design_action_widgets(force=True)"
    )
    assert hydrate_index < fragment_source.index("render_engineering_workspace(")


def test_inputs_apply_is_consumed_before_any_projection_or_rendering() -> None:
    source = (ROOT / "inputs_page.py").read_text(encoding="utf-8-sig")
    start = source.index("def _render_v2_workspace_fragment(")
    end = source.index("\ndef render_inputs_page()", start)
    fragment_source = source[start:end]

    apply_index = fragment_source.index(
        "_INPUTS_PAGE_RUNTIME.handle_pending_apply()"
    )
    assert apply_index < fragment_source.index("render_action_source_toggle(")
    assert apply_index < fragment_source.index(
        "_INPUTS_PAGE_RUNTIME.reconcile_design_actions()"
    )
    assert apply_index < fragment_source.index("render_engineering_workspace(")


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


def test_design_brain_renderer_projects_result_and_binds_one_typed_apply_handler() -> None:
    source = (ROOT / "inputs_application" / "engineering_workspace.py").read_text(
        encoding="utf-8-sig"
    )
    start = source.index("def render_inputs_design_guide_fragment_section(")
    end = source.index("\ndef render_inputs_widget_fragment_section(", start)
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
            f'_prepare_result_page_workspace("{page}")'
        ) == 1
        assert "_refresh_result_page_fragment_calculations()" not in fragment_source
