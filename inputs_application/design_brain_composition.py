"""Composition root for the single supported Design Brain implementation."""

from __future__ import annotations

from typing import Mapping

from application.design_brain_port import DesignBrainRequest
from application.design_brain_service import DesignBrainService
from inputs_application.replacement_design_brain_adapter import (
    ReplacementDesignBrainAdapter,
    ReplacementResultMapper,
)


def selected_design_brain_adapter_name(adapter_name: str | None = None) -> str:
    """Return the only supported composition binding: the isolated V2 brain."""

    if adapter_name not in (None, "", "v2", "new"):
        raise ValueError(
            "the legacy Design Brain has been removed; use the V2 composition"
        )
    return "v2"


def build_design_brain_service(
    guidance_provider=None,
    *,
    adapter_name: str | None = None,
    source_root=None,
) -> DesignBrainService:
    """Build the application service backed exclusively by V2."""

    del guidance_provider
    selected_design_brain_adapter_name(adapter_name)
    return build_new_design_brain_service(source_root=source_root)


def build_replacement_design_brain_service(
    implementation,
    *,
    result_mapper: ReplacementResultMapper | None = None,
) -> DesignBrainService:
    """Bind a neutral replacement implementation for contract tests."""

    return DesignBrainService(
        ReplacementDesignBrainAdapter(
            implementation,
            result_mapper=result_mapper,
        )
    )


def build_new_design_brain_service(*, source_root=None) -> DesignBrainService:
    """Compose the isolated V2 implementation at the sole concrete boundary."""

    from inputs_application.new_design_brain_adapter import NewDesignBrainAdapter

    return DesignBrainService(NewDesignBrainAdapter(source_root=source_root))


def build_browser_publication_probe(
    *,
    item: Mapping[str, object],
    debug: Mapping[str, object],
    publication_reason: str,
    current_publication: Mapping[str, object] | None = None,
):
    """Return the authoritative V2 publication for browser diagnostics."""

    publication = dict(current_publication or {})
    if publication:
        return publication
    return {
        "selected_family": str(item.get("selected_family_id") or item.get("family") or ""),
        "publication_reason": str(publication_reason or ""),
        "guidance_items": [dict(item)],
        "display": {},
        "cta": {},
        "evidence": dict(debug),
    }


__all__ = [
    "build_browser_publication_probe",
    "build_design_brain_service",
    "build_new_design_brain_service",
    "build_replacement_design_brain_service",
    "selected_design_brain_adapter_name",
]
