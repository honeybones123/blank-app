"""Pure orchestration for one replacement Inputs application transaction."""

from __future__ import annotations

from dataclasses import dataclass

from inputs_application.contracts import (
    InputsPageRequest,
    InputsPageResult,
    InputsSessionMutation,
)
from inputs_application.ports import ApplyPort, DesignGuidePort, EngineeringPort, SessionPort


@dataclass(frozen=True)
class InputsApplicationPorts:
    engineering: EngineeringPort
    design_guide: DesignGuidePort
    apply: ApplyPort
    session: SessionPort


def run_inputs_transaction(
    request: InputsPageRequest,
    *,
    ports: InputsApplicationPorts,
) -> InputsPageResult:
    """Evaluate, optionally Apply, then republish from the resulting state.

    Apply mutations are committed exactly once. A successful mutation is
    followed by a forced evaluation and publication so a pre-Apply CTA cannot
    survive as the current transaction result.
    """

    trace: list[str] = ["engineering.evaluate"]
    engineering = ports.engineering.evaluate(
        request.engineering_state,
        force_recompute=request.force_recompute,
    )
    trace.append("design_guide.publish")
    publication = ports.design_guide.publish(request, engineering)
    mutation = None
    apply_status = None

    if request.apply_command is not None:
        trace.append("apply.execute")
        mutation = ports.apply.execute(
            request.apply_command,
            publication=publication,
        )
        ports.session.commit(mutation)
        trace.append("session.commit")
        apply_status = (
            "failed"
            if mutation.status == "failed"
            else "rerun_required"
            if mutation.rerun_required or mutation.status == "rerun_required"
            else "dispatch_ok"
        )

        if apply_status != "failed" and (mutation.updates or mutation.removals):
            next_state = dict(request.engineering_state)
            next_state.update(dict(mutation.updates))
            for key in mutation.removals:
                next_state.pop(key, None)
            next_request = InputsPageRequest(
                engineering_state=next_state,
                session_context=request.session_context,
                force_recompute=True,
            )
            engineering = ports.engineering.evaluate(next_state, force_recompute=True)
            trace.append("engineering.evaluate_post_apply")
            publication = ports.design_guide.publish(next_request, engineering)
            trace.append("design_guide.publish_post_apply")

    return InputsPageResult(
        engineering=engineering,
        publication=publication,
        session_mutation=mutation or InputsSessionMutation(),
        apply_status=apply_status,
        transaction_trace=tuple(trace),
    )
