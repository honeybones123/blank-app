"""Application service enforcing Design Brain request/result coherence."""

from __future__ import annotations

from application.contracts.design_brain import (
    AuthoritativeDesignResult,
    EngineeringInputSnapshot,
)
from application.design_brain_port import (
    DesignBrainExecution,
    DesignBrainPort,
    DesignBrainRequest,
)


class DesignBrainService:
    """Run the selected implementation and reject incoherent publications."""

    def __init__(self, implementation: DesignBrainPort) -> None:
        if not callable(getattr(implementation, "run", None)):
            raise TypeError("implementation must provide run(request)")
        self._implementation = implementation

    def run(self, request: DesignBrainRequest) -> DesignBrainExecution:
        if not isinstance(request, DesignBrainRequest):
            raise TypeError("request must be a DesignBrainRequest")
        if not isinstance(request.engineering_snapshot, EngineeringInputSnapshot):
            raise TypeError("request must contain an EngineeringInputSnapshot")
        execution = self._implementation.run(request)
        if not isinstance(execution, DesignBrainExecution):
            raise TypeError("Design Brain must return a DesignBrainExecution")
        if not isinstance(execution.result, AuthoritativeDesignResult):
            raise TypeError(
                "DesignBrainExecution must contain an AuthoritativeDesignResult"
            )
        expected_hash = request.engineering_snapshot.engineering_hash
        if execution.result.engineering_hash != expected_hash:
            raise ValueError(
                "Design Brain result engineering_hash does not match the request"
            )
        if (
            request.input_revision is not None
            and execution.input_revision != request.input_revision
        ):
            raise ValueError(
                "Design Brain result input_revision does not match the request"
            )
        return execution


__all__ = ["DesignBrainService"]
