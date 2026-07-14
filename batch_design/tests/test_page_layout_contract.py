from pathlib import Path


def test_batch_design_page_uses_lazy_workspace_banner():
    source = Path("batch_design/ui/page.py").read_text(encoding="utf-8")

    assert "st.tabs(" not in source
    assert "WORKSPACE_EXPANDED_KEY" in source
    assert "WORKSPACE_QUERY_PARAM" in source
    assert "def _batch_design_workspace_banner_label" in source
    assert "def _render_batch_design_workspace_banner_visual" in source
    assert "def _workspace_expanded_from_state" in source
    assert "batch-design-workspace-expander-anchor" in source
    assert "batch-design-hero" in source
    assert "batch-design-hero-icon" in source
    assert "batch-design-hero-chip" in source
    assert '+ div div[data-testid="stButton"] button' in source
    assert "min-height: 58px" in source
    assert "opacity: 0" in source
    assert "with st.expander(" not in source
    assert 'key="batch_design_workspace_banner_toggle"' in source
    assert "if not workspace_expanded:" in source
    assert "return" in source
    assert "batch_design_workspace_summary_toggle" not in source
    assert "st.button(toggle_label" not in source
    assert "[>]" in source
    assert "B{project_beam_count}" in source
    assert "auto designed" in source
    assert "auto assigned" in source
    assert "imported actions" in source
    assert "Batch design workspace" in source
    assert "Constraints:" in source
    assert 'st.markdown("### Batch Design")' not in source
    assert 'st.markdown("### Batch design")' in source
    assert '"Import",' not in source
    assert '"Review & Map",' not in source
    assert '"Project Assumptions",' not in source
    assert '"Auto Assign",' not in source
    assert '"Results & Export",' not in source
    assert "Batch loads" not in source
    assert "Add Manual Batch Row" not in source
    assert "Project assumptions" not in source
    assert "Active Beam Status" not in source
    assert "Active Beam Section Preview" not in source


def test_batch_design_workflow_is_compact_expandable_card():
    source = Path("batch_design/ui/page.py").read_text(encoding="utf-8")

    assert "WORKFLOW_SUMMARY_EXPANDED_KEY" in source
    assert '"batch_design_workflow_summary_expanded"' in source
    assert '"batch_design_workflow_mode"' in source
    assert 'st.markdown("### Design workflow")' in source
    assert "def _render_design_workflow_card" in source
    assert "def _render_workflow_summary_banner" in source
    assert "def _render_workflow_mode_selector" in source
    assert "_render_run_design(workflow, ctx)" in source
    assert "render_assignment_panel(" in source
    assert 'st.markdown("#### Auto assign")' not in source
    assert 'st.markdown("#### Run design")' in source
