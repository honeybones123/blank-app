import pandas as pd

from batch_design.models import BatchBeamCase
from batch_design.store import BatchDesignWorkflowState
from batch_design.ui.project_beam_load_table import (
    ACTION_COLUMNS,
    apply_project_beam_load_editor_rows,
    project_beam_load_editor_frame,
    project_beam_templates_from_frame,
)


def _schedule_frame():
    return pd.DataFrame(
        [
            {
                "active": "ACTIVE",
                "beam_id": "beam_1",
                "beam_label": "Beam 1",
                "sec_shape": "RECT",
                "b": 300,
                "D": 600,
                "L": 7000,
                "phi_Mu_cap": 180,
                "phi_Vu_cap": 90,
                "overall_status": "PASS",
            },
            {
                "active": "",
                "beam_id": "beam_2",
                "beam_label": "Beam 2",
                "sec_shape": "RECT",
                "b": 250,
                "D": 500,
                "L": 6000,
                "overall_status": "NOT_RUN",
            },
        ]
    )


def test_project_beam_load_editor_frame_adds_load_columns_from_workflow():
    workflow = BatchDesignWorkflowState()
    workflow.replace_imported_cases([BatchBeamCase(member_id="beam_1", mz_star=120.0, vz_star=55.0)])

    frame = project_beam_load_editor_frame(_schedule_frame(), workflow)

    assert all(column in frame.columns for column in ACTION_COLUMNS)
    row = frame.to_dict("records")[0]
    assert row["beam_id"] == "beam_1"
    assert row["mz_star"] == 120.0
    assert row["vz_star"] == 55.0


def test_project_beam_load_editor_frame_adds_capacity_status_column():
    workflow = BatchDesignWorkflowState()
    schedule = pd.concat(
        [
            _schedule_frame(),
            pd.DataFrame(
                [
                    {
                        "active": "",
                        "beam_id": "beam_3",
                        "beam_label": "Beam 3",
                        "sec_shape": "RECT",
                        "b": 250,
                        "D": 450,
                        "L": 6000,
                        "overall_status": "FAIL",
                    }
                ]
            ),
        ],
        ignore_index=True,
    )

    frame = project_beam_load_editor_frame(schedule, workflow)

    assert "capacity_status" in frame.columns
    statuses = dict(zip(frame["beam_id"], frame["capacity_status"], strict=True))
    assert statuses["beam_1"] == "PASS"
    assert statuses["beam_2"] == "NOT RUN"
    assert statuses["beam_3"] == "FAIL"


def test_apply_project_beam_load_rows_creates_reviewed_cases_from_loaded_beams_only():
    workflow = BatchDesignWorkflowState()
    edited = _schedule_frame()
    edited["n_star"] = [None, None]
    edited["vy_star"] = [None, None]
    edited["vz_star"] = [55.0, None]
    edited["mx_star"] = [None, None]
    edited["my_star"] = [None, None]
    edited["mz_star"] = [120.0, None]

    apply_project_beam_load_editor_rows(workflow, edited)

    assert [case.member_id for case in workflow.imported_cases] == ["beam_1"]
    assert workflow.imported_cases[0].existing_section == "RECT 300 x 600"
    assert workflow.imported_cases[0].length == 7000.0
    assert workflow.imported_cases[0].mz_star == 120.0
    assert workflow.reviewed_member_ids == {"beam_1"}
    assert workflow.can_run_design()


def test_blank_project_beam_load_rows_do_not_create_invalid_cases():
    workflow = BatchDesignWorkflowState()
    edited = _schedule_frame()
    for column in ACTION_COLUMNS:
        edited[column] = None

    apply_project_beam_load_editor_rows(workflow, edited)

    assert workflow.imported_cases == []
    assert workflow.reviewed_member_ids == set()


def test_project_beam_templates_from_frame_uses_cached_capacities():
    templates = project_beam_templates_from_frame(_schedule_frame())

    assert templates[0].template_id == "beam_1"
    assert templates[0].passing is True
    assert templates[0].capacities["mz_star"] == 180.0
    assert templates[0].capacities["vz_star"] == 90.0
