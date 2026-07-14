from batch_design.models import BatchBeamCase, BatchDesignResult
from batch_design.runner import (
    DesignBrainCallableAdapter,
    run_batch_design,
    run_reviewed_batch_design,
    run_single_design_brain_path,
)
from batch_design.store import BatchDesignWorkflowState


def _single_beam_design_brain_path(case, assumptions):
    return BatchDesignResult(
        member_id=case.member_id,
        input_case=case,
        passed=True,
        selected_section="RECT 300 x 600",
        utilisation=0.82,
        design_brain_result={"outcome_id": "passing_exact_stop", "assumptions": dict(assumptions or {})},
        raw_result={"adapter": "existing_design_brain_path"},
    )


def test_single_batch_beam_matches_single_beam_design_brain_path():
    case = BatchBeamCase(member_id="M1", mz_star=120.0)
    calls = []

    def adapter_callable(case, assumptions):
        calls.append({"case": case.to_dict(), "assumptions": dict(assumptions or {})})
        return _single_beam_design_brain_path(case, assumptions)

    adapter = DesignBrainCallableAdapter(adapter_callable)

    single = run_single_design_brain_path(case, adapter, assumptions={"fc": 40})
    batch = run_batch_design([case], adapter, assumptions={"fc": 40})

    assert len(batch) == 1
    assert batch[0].to_dict() == single.to_dict()
    assert calls[0] == calls[1]
    assert batch[0].passed is True
    assert batch[0].selected_section == "RECT 300 x 600"
    assert batch[0].utilisation == 0.82
    assert batch[0].design_brain_result["outcome_id"] == "passing_exact_stop"


def test_invalid_rows_are_not_sent_to_design_brain_when_skip_invalid_is_true():
    calls = []

    def adapter_callable(case, assumptions):
        calls.append(case.member_id)
        return _single_beam_design_brain_path(case, assumptions)

    results = run_batch_design(
        [
            BatchBeamCase(member_id="valid", mz_star=120.0),
            BatchBeamCase(member_id="invalid"),
        ],
        DesignBrainCallableAdapter(adapter_callable),
    )

    assert calls == ["valid"]
    invalid_result = next(result for result in results if result.member_id == "invalid")
    assert invalid_result.passed is False
    assert invalid_result.error == "Invalid row was not sent to Design Brain."


def test_runner_captures_adapter_errors_as_failed_results():
    def adapter_callable(case, assumptions):
        if case.member_id == "bad":
            raise RuntimeError("single beam path failed")
        return _single_beam_design_brain_path(case, assumptions)

    results = run_batch_design(
        [
            BatchBeamCase(member_id="good", mz_star=120.0),
            BatchBeamCase(member_id="bad", mz_star=130.0),
        ],
        DesignBrainCallableAdapter(adapter_callable),
    )

    good = next(result for result in results if result.member_id == "good")
    bad = next(result for result in results if result.member_id == "bad")
    assert good.passed is True
    assert bad.passed is False
    assert "single beam path failed" in bad.error
    assert any("Design Brain adapter failed" in warning.message for warning in bad.warnings)


def test_reviewed_workflow_runner_does_not_call_adapter_when_blocked():
    calls = []
    workflow = BatchDesignWorkflowState()
    workflow.replace_imported_cases([BatchBeamCase(member_id="M1", mz_star=120.0)])

    def adapter_callable(case, assumptions):
        calls.append(case.member_id)
        return _single_beam_design_brain_path(case, assumptions)

    results = run_reviewed_batch_design(workflow, DesignBrainCallableAdapter(adapter_callable))

    assert results == []
    assert calls == []
    assert workflow.design_results == []
    assert workflow.metadata["last_run_blocked_reasons"] == ["Valid rows must be reviewed before design."]


def test_reviewed_workflow_runner_updates_results_for_reviewed_cases_only():
    calls = []
    workflow = BatchDesignWorkflowState()
    workflow.replace_imported_cases(
        [
            BatchBeamCase(member_id="valid", mz_star=120.0),
            BatchBeamCase(member_id="excluded-invalid"),
        ]
    )
    workflow.set_excluded("excluded-invalid", True)
    workflow.mark_all_valid_reviewed()

    def adapter_callable(case, assumptions):
        calls.append({"member_id": case.member_id, "assumptions": dict(assumptions or {})})
        return _single_beam_design_brain_path(case, assumptions)

    results = run_reviewed_batch_design(
        workflow,
        DesignBrainCallableAdapter(adapter_callable),
        assumptions={"fc": 40},
    )

    assert [result.member_id for result in results] == ["valid"]
    assert workflow.design_results == results
    assert calls == [{"member_id": "valid", "assumptions": {"fc": 40}}]
    assert workflow.metadata["last_run_blocked_reasons"] == []
    assert workflow.metadata["last_run_result_count"] == 1
