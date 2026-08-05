"""Single composition point for the currently selected Design Brain."""

from __future__ import annotations

from importlib import import_module
import os
from typing import Callable, Mapping

from application.design_brain_port import DesignBrainRequest
from application.design_brain_service import DesignBrainService
from inputs_application.replacement_design_brain_adapter import (
    ReplacementDesignBrainAdapter,
    ReplacementResultMapper,
)


LegacyGuidanceProvider = Callable[[DesignBrainRequest], Mapping[str, object]]

DESIGN_BRAIN_ADAPTER_ENV = "INPUTS_DESIGN_BRAIN_ADAPTER"
_LEGACY_ADAPTER_NAMES = frozenset({"legacy", "v1"})
_NEW_ADAPTER_NAMES = frozenset({"new", "v2"})


def _legacy_adapter_module():
    """Load the selected compatibility adapter without a static import edge."""

    return import_module("inputs_application.legacy_design_brain_adapter")


def build_design_brain_service(
    guidance_provider: LegacyGuidanceProvider | None = None,
    *,
    adapter_name: str | None = None,
    source_root=None,
) -> DesignBrainService:
    """Bind the selected implementation without exposing it to consumers.

    The V2 adapter is the default.  ``INPUTS_DESIGN_BRAIN_ADAPTER`` (or the
    explicit ``adapter_name`` argument used by probes) is the only
    composition-level switch.  This keeps the cutover reversible: setting the
    variable to ``legacy`` immediately restores the verified V1 path while
    the V2 implementation remains the normal application binding.
    """

    selected = selected_design_brain_adapter_name(adapter_name)
    if selected == "v2":
        return build_new_design_brain_service(source_root=source_root)

    if guidance_provider is None:
        raise TypeError("legacy Design Brain selection requires guidance_provider")

    legacy_adapter = _legacy_adapter_module()
    return DesignBrainService(legacy_adapter.LegacyDesignBrainAdapter(guidance_provider))


def selected_design_brain_adapter_name(adapter_name: str | None = None) -> str:
    """Return the canonical composition binding name.

    An explicit value takes precedence over the process environment so tests
    and controlled callers can exercise rollback without mutating global
    state.  Unknown values fail closed instead of silently selecting a brain.
    """

    raw = adapter_name
    if raw is None:
        raw = os.environ.get(DESIGN_BRAIN_ADAPTER_ENV)
    normalized = str(raw or "v2").strip().lower()
    if normalized in _LEGACY_ADAPTER_NAMES:
        return "legacy"
    if normalized in _NEW_ADAPTER_NAMES:
        return "v2"
    raise ValueError(
        f"unsupported Design Brain adapter {normalized!r}; "
        "expected legacy, v1, v2, or new"
    )


def build_replacement_design_brain_service(
    implementation,
    *,
    result_mapper: ReplacementResultMapper | None = None,
) -> DesignBrainService:
    """Bind a supplied replacement only through the neutral application port."""

    return DesignBrainService(
        ReplacementDesignBrainAdapter(
            implementation,
            result_mapper=result_mapper,
        )
    )


def build_new_design_brain_service(*, source_root=None) -> DesignBrainService:
    """Compose the isolated V2 implementation used by the default binding."""

    from inputs_application.new_design_brain_adapter import NewDesignBrainAdapter

    return DesignBrainService(NewDesignBrainAdapter(source_root=source_root))


def build_guidance_blocker_builder():
    """Expose the selected implementation's blocker through composition."""

    legacy_adapter = _legacy_adapter_module()
    return legacy_adapter.build_design_guide_controller_active_fail_executor_no_repair_blocker_from_evidence


def build_guidance_blocker():
    """Return the compatibility preflight blocker through this boundary."""

    return build_guidance_blocker_builder()


def build_publication_cta_builder():
    """Expose the selected implementation's CTA proof builder by composition."""

    legacy_adapter = _legacy_adapter_module()
    return legacy_adapter.build_final_publication_cta_from_current_state


def build_publication_cta():
    """Return the compatibility CTA builder through this boundary."""

    return build_publication_cta_builder()


def build_bottom_arrangement_pool_builder():
    """Expose the selected bending family arrangement generator by composition."""

    legacy_adapter = _legacy_adapter_module()
    return legacy_adapter.build_bottom_reo_arrangement_pool_from_state


def build_bottom_arrangement_pool():
    """Return the compatibility arrangement pool through this boundary."""

    return build_bottom_arrangement_pool_builder()


def build_publication_builder():
    """Expose the selected implementation's publication builder by composition."""

    legacy_adapter = _legacy_adapter_module()
    return legacy_adapter.build_final_design_guide_publication


def build_browser_publication_probe(
    *,
    item: Mapping[str, object],
    debug: Mapping[str, object],
    publication_reason: str,
    current_publication: Mapping[str, object] | None = None,
):
    """Return the browser-probe publication through the neutral boundary.

    V2 already publishes the complete display/CTA/evidence envelope.  Reusing
    that envelope keeps the V2 path independent from the legacy publication
    formatter.  The explicit legacy rollback still uses its historical
    formatter so rollback verification remains meaningful.
    """

    if selected_design_brain_adapter_name() == "v2":
        publication = dict(current_publication or {})
        if publication:
            return publication
        # A missing authoritative publication is a probe failure, not a reason
        # to silently invoke V1.  Preserve enough neutral shape for diagnostics.
        return {
            "selected_family": str(item.get("selected_family_id") or item.get("family") or ""),
            "publication_reason": str(publication_reason or ""),
            "guidance_items": [dict(item)],
            "display": {},
            "cta": {},
            "evidence": dict(debug),
        }
    return build_publication_builder()(
        item=dict(item),
        debug=dict(debug),
        publication_reason=publication_reason,
    )


def build_primary_apply_payload_projection_builder():
    """Expose the selected implementation's Apply projection by composition."""

    legacy_adapter = _legacy_adapter_module()
    return legacy_adapter.build_final_design_guide_primary_apply_payload_projection


def build_primary_apply_payload_projection():
    """Return the compatibility Apply projection through this boundary."""

    return build_primary_apply_payload_projection_builder()


def selected_legacy_design_brain_namespace():
    """Return the selected compatibility namespace for historical facades."""

    return _legacy_adapter_module()


def selected_compatibility_namespace():
    """Return the rollback namespace without exposing its concrete owner."""

    return selected_legacy_design_brain_namespace()


__all__ = [
    "build_design_brain_service",
    "selected_design_brain_adapter_name",
    "build_replacement_design_brain_service",
    "build_new_design_brain_service",
    "build_guidance_blocker_builder",
    "build_guidance_blocker",
    "build_publication_cta_builder",
    "build_publication_cta",
    "build_bottom_arrangement_pool_builder",
    "build_bottom_arrangement_pool",
    "build_publication_builder",
    "build_browser_publication_probe",
    "build_primary_apply_payload_projection_builder",
    "build_primary_apply_payload_projection",
    "selected_legacy_design_brain_namespace",
    "selected_compatibility_namespace",
]
