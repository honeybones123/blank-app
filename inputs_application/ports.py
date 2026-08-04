"""Capability ports consumed by the replacement Inputs transaction runtime."""

from __future__ import annotations

from typing import Mapping, Protocol

from inputs_application.contracts import (
    InputsApplyCommand,
    InputsEngineeringResult,
    InputsPageRequest,
    InputsPublicationResult,
    InputsSessionMutation,
)


class EngineeringPort(Protocol):
    def evaluate(
        self,
        engineering_state: Mapping[str, object],
        *,
        force_recompute: bool = False,
    ) -> InputsEngineeringResult: ...


class DesignGuidePort(Protocol):
    def publish(
        self,
        request: InputsPageRequest,
        engineering: InputsEngineeringResult,
    ) -> InputsPublicationResult: ...


class ApplyPort(Protocol):
    def execute(
        self,
        command: InputsApplyCommand,
        *,
        publication: InputsPublicationResult,
    ) -> InputsSessionMutation: ...


class SessionPort(Protocol):
    def commit(self, mutation: InputsSessionMutation) -> None: ...

