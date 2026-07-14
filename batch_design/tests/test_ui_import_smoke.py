from batch_design.assignment import assign_beam_case
from batch_design.models import BatchBeamCase, BatchBeamTemplate, BatchDesignResult
from batch_design.ui.assignment_panel import render_assignment_panel
from batch_design.ui.assumptions_panel import render_assumptions_panel
from batch_design.ui.import_panel import render_import_panel
from batch_design.ui.preview_table import preview_rows
from batch_design.ui.project_beam_manager_adapters import build_schedule_export_df
from batch_design.ui.results_table import assignment_results_frame, design_results_frame


def test_batch_design_ui_components_import_and_build_non_streamlit_frames():
    assert callable(render_import_panel)
    assert callable(render_assumptions_panel)
    assert callable(render_assignment_panel)
    assert callable(build_schedule_export_df)

    case = BatchBeamCase(member_id="M1", mz_star=90.0)
    design = BatchDesignResult(member_id="M1", input_case=case, passed=True, selected_section="RECT", utilisation=0.9)
    assignment = assign_beam_case(case, [BatchBeamTemplate(template_id="T1", label="Template", capacities={"mz_star": 100.0})])

    assert list(preview_rows([case])["member_id"]) == ["M1"]
    assert list(design_results_frame([design])["Member ID"]) == ["M1"]
    assert list(assignment_results_frame([assignment])["Member ID"]) == ["M1"]
