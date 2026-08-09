"""Authoritative application and calculation metadata for presentation surfaces."""

from __future__ import annotations

from dataclasses import dataclass
import os

from application.contracts.design_brain import AUTHORITATIVE_DESIGN_RESULT_SCHEMA_VERSION
from application.reference_registry import REFERENCE_SET_VERSION
from application.v2_source_manifest import EXPECTED_INPUTS_V2_VERSION


@dataclass(frozen=True)
class ApplicationMetadata:
    application_version: str
    calculation_engine_version: str
    reference_set_version: str
    last_updated_date: str


def application_metadata() -> ApplicationMetadata:
    return ApplicationMetadata(
        application_version=os.getenv("STRUCTURALBASE_APP_VERSION", "development"),
        calculation_engine_version=os.getenv(
            "STRUCTURALBASE_ENGINE_VERSION",
            f"{AUTHORITATIVE_DESIGN_RESULT_SCHEMA_VERSION}+inputs-v2.{EXPECTED_INPUTS_V2_VERSION}",
        ),
        reference_set_version=REFERENCE_SET_VERSION,
        last_updated_date=os.getenv("STRUCTURALBASE_LAST_UPDATED", "2026-08-09"),
    )


__all__ = ["ApplicationMetadata", "application_metadata"]
