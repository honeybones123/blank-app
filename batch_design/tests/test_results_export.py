from batch_design.models import BatchAssignmentResult, BatchBeamCase, BatchDesignResult
from batch_design.ui.results_table import (
    assignment_results_csv,
    assignment_results_export_frame,
    design_results_csv,
    design_results_export_frame,
)


def test_design_results_export_contains_input_demands_and_result_fields():
    case = BatchBeamCase(member_id="M1", existing_section="310UB40", length=6.2, mz_star=120.0, vz_star=55.0)
    result = BatchDesignResult(
        member_id="M1",
        input_case=case,
        passed=True,
        selected_section="RECT 300 x 600",
        utilisation=0.82,
    )

    frame = design_results_export_frame([result])

    row = frame.to_dict("records")[0]
    assert row["member_id"] == "M1"
    assert row["selected_section"] == "RECT 300 x 600"
    assert row["mz_star"] == 120.0
    assert "M1" in design_results_csv([result])


def test_assignment_results_export_contains_reason_and_template():
    result = BatchAssignmentResult(
        member_id="M1",
        assigned_template_id="T1",
        assigned_label="Template 1",
        passed=True,
        reason="Selected nearest stronger passing candidate.",
        utilisation=0.9,
    )

    frame = assignment_results_export_frame([result])

    row = frame.to_dict("records")[0]
    assert row["assigned_template_id"] == "T1"
    assert row["reason"] == "Selected nearest stronger passing candidate."
    assert "Template 1" in assignment_results_csv([result])
