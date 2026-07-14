from batch_design.models import BatchBeamCase, BatchBeamSource, BatchProject


def test_batch_beam_case_demand_vector_defaults_missing_actions_to_zero():
    case = BatchBeamCase(member_id="M1", source=BatchBeamSource.SPACEGASS_EXCEL, mz_star=42.0)

    assert case.demand_vector()["mz_star"] == 42.0
    assert case.demand_vector()["vy_star"] == 0.0


def test_batch_project_contains_cases_without_side_effects():
    case = BatchBeamCase(member_id="M1", mz_star=12.0)
    project = BatchProject(project_id="P1", name="Demo", beam_cases=[case])

    assert project.to_dict()["beam_cases"][0]["member_id"] == "M1"
