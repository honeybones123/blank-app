"""Adapter from the application port to the current Design Brain runtime."""

from __future__ import annotations

from typing import Callable, Mapping

from application.design_brain_port import DesignBrainExecution, DesignBrainRequest
from inputs_application.design_brain_pipeline_runtime import (
    run_live_design_brain_pipeline,
)


LegacyGuidanceProvider = Callable[[DesignBrainRequest], Mapping[str, object]]


class LegacyDesignBrainAdapter:
    """Keep current behavior behind the replacement boundary during cutover."""

    def __init__(self, guidance_provider: LegacyGuidanceProvider) -> None:
        if not callable(guidance_provider):
            raise TypeError("guidance_provider must be callable")
        self._guidance_provider = guidance_provider

    def run(self, request: DesignBrainRequest) -> DesignBrainExecution:
        guidance_payload = dict(self._guidance_provider(request) or {})
        execution = run_live_design_brain_pipeline(
            engineering_snapshot=request.engineering_snapshot,
            guidance_payload=guidance_payload,
            family_override=request.family_hint,
            resolved_inputs=request.resolved_inputs,
            engineering_calculations=request.engineering_calculations,
        )
        return DesignBrainExecution(
            result=execution.result,
            stage_trace=tuple(execution.stage_trace),
            pipeline_applied=bool(execution.pipeline_applied),
            bypass_reason=execution.bypass_reason,
        )


__all__ = ["LegacyDesignBrainAdapter", "LegacyGuidanceProvider"]
