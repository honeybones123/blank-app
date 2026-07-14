from batch_design.assignment import assign_beam_case
from batch_design.models import BatchBeamCase, BatchBeamTemplate


def test_assignment_selects_nearest_stronger_passing_candidate():
    case = BatchBeamCase(member_id="M1", mz_star=95.0, vz_star=35.0)
    weak = BatchBeamTemplate(template_id="T1", label="Weak", capacities={"mz_star": 90.0, "vz_star": 50.0})
    strong = BatchBeamTemplate(template_id="T2", label="Strong", capacities={"mz_star": 100.0, "vz_star": 45.0})
    too_strong = BatchBeamTemplate(template_id="T3", label="Too Strong", capacities={"mz_star": 200.0, "vz_star": 100.0})

    result = assign_beam_case(case, [weak, too_strong, strong])

    assert result.passed
    assert result.assigned_template_id == "T2"
    assert any(item["template_id"] == "T1" for item in result.rejected_candidates)
    assert "nearest stronger passing candidate" in result.reason


def test_assignment_rejects_nonpassing_candidates():
    case = BatchBeamCase(member_id="M1", mz_star=10.0)
    failed = BatchBeamTemplate(template_id="T1", label="Failed", capacities={"mz_star": 100.0}, passing=False)

    result = assign_beam_case(case, [failed])

    assert not result.passed
    assert result.assigned_template_id is None


def test_assignment_prefers_exact_match_when_available():
    case = BatchBeamCase(member_id="M1", mz_star=100.0)
    exact = BatchBeamTemplate(template_id="exact", label="Exact", capacities={"mz_star": 100.0})
    stronger = BatchBeamTemplate(template_id="stronger", label="Stronger", capacities={"mz_star": 130.0})

    result = assign_beam_case(case, [stronger, exact])

    assert result.passed
    assert result.assigned_template_id == "exact"
    assert result.utilisation == 1.0


def test_assignment_does_not_select_over_strong_when_closer_passing_exists():
    case = BatchBeamCase(member_id="M1", mz_star=90.0)
    close = BatchBeamTemplate(template_id="close", label="Close", capacities={"mz_star": 100.0})
    over_strong = BatchBeamTemplate(template_id="over", label="Over", capacities={"mz_star": 500.0})

    result = assign_beam_case(case, [over_strong, close])

    assert result.assigned_template_id == "close"


def test_assignment_empty_candidate_library_returns_controlled_no_assignment():
    result = assign_beam_case(BatchBeamCase(member_id="M1", mz_star=90.0), [])

    assert not result.passed
    assert result.assigned_template_id is None
    assert result.reason == "No passing candidate met all demanded actions."
    assert result.rejected_candidates == []
