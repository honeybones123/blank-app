import pandas as pd

from batch_design.models import BatchBeamCase
from batch_design.store import BatchDesignWorkflowState
from batch_design.ui.review_table import apply_review_rows, review_rows


def test_review_rows_show_batch_owned_editable_details():
    workflow = BatchDesignWorkflowState()
    workflow.replace_imported_cases(
        [
            BatchBeamCase(
                member_id="M1",
                existing_section="RECT 300 x 600",
                length=6.2,
                n_star=10.0,
                vy_star=2.0,
                vz_star=55.0,
                mx_star=1.0,
                my_star=8.0,
                mz_star=130.0,
                confidence=0.92,
            )
        ]
    )
    workflow.mark_all_valid_reviewed()

    rows = review_rows(workflow)

    record = rows.to_dict("records")[0]
    assert record["include"] is True
    assert record["reviewed"] is True
    assert record["member_id"] == "M1"
    assert record["existing_section"] == "RECT 300 x 600"
    assert record["mz_star"] == 130.0


def test_apply_review_rows_updates_actions_review_and_exclusion_state():
    workflow = BatchDesignWorkflowState()
    workflow.replace_imported_cases(
        [
            BatchBeamCase(member_id="M1", length=6.2, mz_star=130.0),
            BatchBeamCase(member_id="M2", length=7.1, mz_star=155.0),
        ]
    )

    edited = pd.DataFrame(
        [
            {
                "include": True,
                "reviewed": True,
                "member_id": "M1A",
                "source": "spacegass_excel",
                "existing_section": "RECT 300 x 600",
                "length": 6.5,
                "n_star": 12.0,
                "vy_star": 4.0,
                "vz_star": 60.0,
                "mx_star": 1.0,
                "my_star": 8.5,
                "mz_star": 140.0,
                "confidence": 0.9,
                "warnings": "",
            },
            {
                "include": False,
                "reviewed": True,
                "member_id": "M2",
                "source": "spacegass_excel",
                "existing_section": "",
                "length": 7.1,
                "n_star": None,
                "vy_star": None,
                "vz_star": None,
                "mx_star": None,
                "my_star": None,
                "mz_star": 155.0,
                "confidence": 0.89,
                "warnings": "",
            },
        ]
    )

    apply_review_rows(workflow, edited)

    assert [case.member_id for case in workflow.imported_cases] == ["M1A", "M2"]
    assert workflow.imported_cases[0].existing_section == "RECT 300 x 600"
    assert workflow.imported_cases[0].length == 6.5
    assert workflow.imported_cases[0].mz_star == 140.0
    assert workflow.excluded_member_ids == {"M2"}
    assert workflow.reviewed_member_ids == {"M1A"}
    assert [case.member_id for case in workflow.runnable_cases()] == ["M1A"]


def test_apply_review_rows_clears_stale_design_results():
    workflow = BatchDesignWorkflowState()
    case = BatchBeamCase(member_id="M1", mz_star=130.0)
    workflow.replace_imported_cases([case])
    workflow.replace_design_results([])
    workflow.metadata["placeholder"] = True

    edited = review_rows(workflow)
    edited.loc[0, "mz_star"] = 140.0

    apply_review_rows(workflow, edited)

    assert workflow.design_results == []
    assert workflow.assignment_results == []
    assert workflow.imported_cases[0].mz_star == 140.0


def test_apply_review_rows_accepts_new_manual_rows_from_dynamic_editor():
    workflow = BatchDesignWorkflowState()
    workflow.replace_imported_cases([BatchBeamCase(member_id="M1", mz_star=130.0)])

    existing_record = review_rows(workflow).to_dict("records")[0]
    edited = pd.DataFrame(
        [
            existing_record,
            {
                "include": True,
                "reviewed": True,
                "member_id": "M2",
                "source": "",
                "existing_section": "RECT 300 x 600",
                "length": 7.0,
                "n_star": 0.0,
                "vy_star": 12.0,
                "vz_star": 40.0,
                "mx_star": 0.0,
                "my_star": 5.0,
                "mz_star": 120.0,
                "confidence": 0.95,
                "warnings": "",
            },
        ]
    )

    apply_review_rows(workflow, edited)

    manual = workflow.imported_cases[1]
    assert manual.member_id == "M2"
    assert manual.source.value == "manual"
    assert manual.existing_section == "RECT 300 x 600"
    assert manual.vz_star == 40.0
    assert manual.mz_star == 120.0
    assert workflow.reviewed_member_ids == {"M2"}
