"""Batch runner that delegates auto design to the existing Design Brain path."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from typing import Any, Protocol

from batch_design.models import BatchBeamCase, BatchDesignResult, BatchImportWarning
from batch_design.store import BatchDesignWorkflowState
from batch_design.validation import validate_batch_cases


class DesignBrainAdapter(Protocol):
    def run_case(
        self,
        case: BatchBeamCase,
        *,
        assumptions: Mapping[str, Any] | None = None,
        base_state: Mapping[str, Any] | None = None,
        request_kind: str | None = None,
    ) -> BatchDesignResult | dict[str, Any]:
        """Run the existing single-beam Design Brain path for one normalized case."""


class DesignBrainCallableAdapter:
    """Adapter for an existing Design Brain callable.

    The callable is supplied by app integration code or tests. This runner does
    not calculate recommendations itself.
    """

    def __init__(self, design_brain_callable: Callable[[BatchBeamCase, Mapping[str, Any] | None], BatchDesignResult | dict[str, Any]]):
        self._design_brain_callable = design_brain_callable

    def run_case(
        self,
        case: BatchBeamCase,
        *,
        assumptions: Mapping[str, Any] | None = None,
        base_state: Mapping[str, Any] | None = None,
        request_kind: str | None = None,
    ) -> BatchDesignResult | dict[str, Any]:
        del base_state, request_kind
        return self._design_brain_callable(case, assumptions)


def _coerce_result(case: BatchBeamCase, result: BatchDesignResult | dict[str, Any]) -> BatchDesignResult:
    if isinstance(result, BatchDesignResult):
        return result
    result_dict = dict(result or {})
    design_brain_result = dict(result_dict.get("design_brain_result") or {})
    return BatchDesignResult(
        member_id=case.member_id,
        input_case=case,
        passed=result_dict.get("passed"),
        selected_section=result_dict.get("selected_section") or design_brain_result.get("selected_section"),
        utilisation=result_dict.get("utilisation") or design_brain_result.get("utilisation"),
        design_brain_result=design_brain_result,
        raw_result=result_dict,
        warnings=list(result_dict.get("warnings") or []),
        error=result_dict.get("error"),
    )


def run_single_design_brain_path(
    case: BatchBeamCase,
    adapter: DesignBrainAdapter,
    *,
    assumptions: Mapping[str, Any] | None = None,
) -> BatchDesignResult:
    """Run exactly one normalized row through the provided Design Brain adapter."""

    return _coerce_result(case, adapter.run_case(case, assumptions=assumptions))


def run_batch_design(
    cases: Iterable[BatchBeamCase],
    adapter: DesignBrainAdapter,
    *,
    assumptions: Mapping[str, Any] | None = None,
    skip_invalid: bool = True,
) -> list[BatchDesignResult]:
    validation = validate_batch_cases(list(cases))
    runnable = validation.valid_cases if skip_invalid else list(cases)
    results: list[BatchDesignResult] = []

    for case in runnable:
        try:
            results.append(run_single_design_brain_path(case, adapter, assumptions=assumptions))
        except Exception as exc:
            results.append(
                BatchDesignResult(
                    member_id=case.member_id,
                    input_case=case,
                    passed=False,
                    error=str(exc),
                    warnings=[
                        BatchImportWarning(
                            row_number=None,
                            member_id=case.member_id,
                            severity="error",
                            message=f"Design Brain adapter failed: {exc}",
                        )
                    ],
                )
            )

    if skip_invalid:
        for case in validation.invalid_cases:
            results.append(
                BatchDesignResult(
                    member_id=case.member_id,
                    input_case=case,
                    passed=False,
                    error="Invalid row was not sent to Design Brain.",
                )
            )

    return results


def run_reviewed_batch_design(
    workflow: BatchDesignWorkflowState,
    adapter: DesignBrainAdapter,
    *,
    assumptions: Mapping[str, Any] | None = None,
) -> list[BatchDesignResult]:
    """Run only reviewed, valid, included workflow rows through Design Brain.

    The workflow owns preview and review state. This helper is the boundary used
    by UI code so invalid or unreviewed imported rows cannot be sent to the
    adapter by accident.
    """

    blockers = workflow.blocked_run_reasons()
    if blockers:
        workflow.metadata["last_run_blocked_reasons"] = blockers
        return []

    results = run_batch_design(
        workflow.runnable_cases(),
        adapter,
        assumptions=assumptions,
        skip_invalid=True,
    )
    workflow.replace_design_results(results)
    workflow.metadata["last_run_blocked_reasons"] = []
    workflow.metadata["last_run_result_count"] = len(results)
    return results
