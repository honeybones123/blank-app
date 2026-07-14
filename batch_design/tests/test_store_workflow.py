from batch_design.models import BatchAssignmentResult, BatchBeamCase, BatchDesignResult
from batch_design.store import BatchDesignWorkflowState


def test_workflow_blocks_until_valid_rows_are_reviewed():
    workflow = BatchDesignWorkflowState()
    workflow.replace_imported_cases([BatchBeamCase(member_id="M1", mz_star=120.0)])

    assert not workflow.can_run_design()
    assert workflow.blocked_run_reasons() == ["Valid rows must be reviewed before design."]

    workflow.mark_all_valid_reviewed()

    assert workflow.can_run_design()
    assert [case.member_id for case in workflow.runnable_cases()] == ["M1"]


def test_workflow_allows_invalid_rows_when_explicitly_excluded():
    workflow = BatchDesignWorkflowState()
    workflow.replace_imported_cases(
        [
            BatchBeamCase(member_id="valid", mz_star=120.0),
            BatchBeamCase(member_id="invalid"),
        ]
    )

    assert "Included rows contain validation errors." in workflow.blocked_run_reasons()

    workflow.set_excluded("invalid", True)
    workflow.mark_all_valid_reviewed()

    assert workflow.can_run_design()
    assert [case.member_id for case in workflow.runnable_cases()] == ["valid"]
    assert workflow.preview_summary()["excluded"] == 1


def test_workflow_replaces_results_and_clears_stale_assignments():
    workflow = BatchDesignWorkflowState()
    case = BatchBeamCase(member_id="M1", mz_star=120.0)
    workflow.replace_imported_cases([case])
    workflow.replace_assignment_results(
        [BatchAssignmentResult(member_id="M1", assigned_template_id="T1", assigned_label="T1", passed=True, reason="ok")]
    )

    workflow.replace_design_results(
        [BatchDesignResult(member_id="M1", input_case=case, passed=True, selected_section="RECT", utilisation=0.8)]
    )

    assert len(workflow.design_results) == 1
    assert workflow.assignment_results == []


def test_workflow_adds_unique_manual_batch_case():
    workflow = BatchDesignWorkflowState()
    workflow.replace_imported_cases([BatchBeamCase(member_id="M1", mz_star=120.0)])

    case = workflow.add_manual_case()

    assert case.member_id == "M2"
    assert case.source.value == "manual"
    assert [row.member_id for row in workflow.imported_cases] == ["M1", "M2"]
