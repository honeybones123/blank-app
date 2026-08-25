"""Batch result table helpers."""

from __future__ import annotations

import pandas as pd

from batch_design.models import BatchAssignmentResult, BatchDesignResult


def design_results_frame(results: list[BatchDesignResult]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Member ID": result.member_id,
                "Passed": result.passed,
                "Selected Section": result.selected_section,
                "Utilisation": result.utilisation,
                "Error": result.error,
            }
            for result in results
        ]
    )


def assignment_results_frame(results: list[BatchAssignmentResult]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Member ID": result.member_id,
                "Assigned": result.assigned_label,
                "Passed": result.passed,
                "Utilisation": result.utilisation,
                "Reason": result.reason,
            }
            for result in results
        ]
    )


def design_results_export_frame(results: list[BatchDesignResult]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "member_id": result.member_id,
                "passed": result.passed,
                "selected_section": result.selected_section,
                "utilisation": result.utilisation,
                "error": result.error,
                "source": str(result.input_case.source.value if hasattr(result.input_case.source, "value") else result.input_case.source),
                "existing_section": result.input_case.existing_section,
                "length": result.input_case.length,
                "n_star": result.input_case.n_star,
                "vy_star": result.input_case.vy_star,
                "vz_star": result.input_case.vz_star,
                "mx_star": result.input_case.mx_star,
                "my_star": result.input_case.my_star,
                "mz_star": result.input_case.mz_star,
            }
            for result in results
        ]
    )


def assignment_results_export_frame(results: list[BatchAssignmentResult]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "member_id": result.member_id,
                "assigned_template_id": result.assigned_template_id,
                "assigned_label": result.assigned_label,
                "passed": result.passed,
                "utilisation": result.utilisation,
                "reason": result.reason,
            }
            for result in results
        ]
    )


def design_results_csv(results: list[BatchDesignResult]) -> str:
    return design_results_export_frame(results).to_csv(index=False)


def assignment_results_csv(results: list[BatchAssignmentResult]) -> str:
    return assignment_results_export_frame(results).to_csv(index=False)


def render_results_table(st, results: list[BatchDesignResult]) -> None:
    st.dataframe(design_results_frame(results), hide_index=True, use_container_width=True)
