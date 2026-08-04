"""Typed permanent application runtime for Inputs page composition."""

from __future__ import annotations

from dataclasses import dataclass, field
import importlib
import os
import sys
from typing import Any, Callable

import streamlit as st

from inputs_page_modules.design_guide import (
    current_coordinators as design_guide_current_coordinators,
)
from inputs_application.page_runtime.batch import (
    render_inputs_batch_design_manager_coordinator,
)
from inputs_application.page_runtime.calculations import (
    render_inputs_calculation_fragment_current_coordinator,
)
from inputs_application.page_runtime.common import (
    _handle_inputs_apply_buttons_current_coordinator,
    make_beam_3d_figure,
    make_summary_cross_section_figure,
    reconcile_inputs_design_actions_before_authority,
)
from inputs_application.page_runtime.design_guide import (
    render_inputs_design_guide_current_coordinator,
)
from inputs_application.page_runtime.divider import (
    render_inputs_page_divider_coordinator,
)
from inputs_application.page_runtime.mode import (
    render_inputs_design_mode_selector_coordinator,
)
from inputs_application.page_runtime.setup import (
    refresh_inputs_design_brain_result_background,
    refresh_inputs_engineering_result,
    refresh_inputs_authoritative_design_result,
    render_inputs_page_setup_current_coordinator,
)
from inputs_application.page_runtime.summaries import (
    render_inputs_summary_pipeline_current_coordinator,
)
from inputs_application.page_runtime.tail import (
    render_inputs_tail_current_coordinator,
)
from inputs_application.page_runtime.widgets import (
    render_inputs_widget_sections_current_coordinator,
)


PageCallable = Callable[..., Any]

_DESIGN_GUIDE_DEPENDENCY_MODULE_NAMES = (
    "inputs_application.policy_constants",
    "inputs_application.guidance_runtime_config",
    "inputs_page_modules.guidance_compute",
    "inputs_page_modules.design_overview_adapter",
    "inputs_page_modules.recommendation_compute",
    "inputs_page_modules.design_guide",
    "inputs_page_modules.design_guide.presentation_state",
    "inputs_page_modules.design_guide.pending_recommendation",
    "inputs_page_modules.design_guide.guidance_item_consolidation",
    "inputs_page_modules.design_guide.guidance_item_dedupe",
    "inputs_page_modules.design_guide.terminal_state",
    "inputs_page_modules.design_guide.display_truth",
    "inputs_page_modules.design_guide.banner_render_state",
    "inputs_page_modules.design_guide.button_contract",
    "inputs_page_modules.design_guide.title_alignment_verification",
    "design_brain.family_ladder_runtime",
    "inputs_page_modules.design_guide.guidance_items",
    "inputs_page_modules.design_guide.local_cleanup_promotion",
    "inputs_page_modules.design_guide.primary_button_queue",
    "inputs_page_modules.design_guide.main_panel_status",
    "inputs_page_modules.design_guide.shear_local_cleanup",
    "inputs_application.efficiency_classification",
    "inputs_application.guidance_entrypoint",
    "inputs_application.page_runtime.design_guide_runtime_support",
)


@dataclass(frozen=True)
class InputsRuntimeDependencyProvider:
    """Resolve extracted runtime dependencies without a page-level bridge."""

    modules: tuple[Any, ...]
    bindings: dict[str, Any] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        indexed: dict[str, Any] = {}
        for module in self.modules:
            for name, value in vars(module).items():
                indexed.setdefault(str(name), value)
        object.__setattr__(self, "bindings", indexed)

    def __getattr__(self, name: str) -> Any:
        try:
            return self.bindings[name]
        except KeyError as exc:
            raise AttributeError(
                f"Inputs runtime dependency is not owned: {name}"
            ) from exc

    def __contains__(self, name: object) -> bool:
        if not isinstance(name, str):
            return False
        try:
            getattr(self, name)
        except AttributeError:
            return False
        return True

    def __getitem__(self, name: str) -> Any:
        return getattr(self, name)


def _bind_declared_runtime_dependencies(
    provider: InputsRuntimeDependencyProvider,
) -> None:
    """Populate explicit extraction contracts from the typed runtime graph."""
    for module in provider.modules:
        for name in dir(module):
            if not (
                name.startswith("bind_")
                and name.endswith("_dependencies")
            ):
                continue
            binder = getattr(module, name)
            if callable(binder):
                binder(provider)


@dataclass(frozen=True)
class InputsPageRuntime:
    """Complete, explicit application boundary consumed by the page shell."""

    make_beam_3d_figure: PageCallable
    make_summary_cross_section_figure: PageCallable
    render_page_setup: PageCallable
    handle_pending_apply: PageCallable
    reconcile_design_actions: PageCallable
    refresh_authoritative_result: PageCallable
    refresh_engineering_result: PageCallable
    refresh_design_brain_result: PageCallable
    render_batch_design_manager: PageCallable
    render_calculation: PageCallable
    render_design_guide: PageCallable
    render_design_mode_selector: PageCallable
    render_page_divider: PageCallable
    render_summary_pipeline: PageCallable
    render_tail: PageCallable
    render_widget_sections: PageCallable


def build_inputs_page_runtime() -> InputsPageRuntime:
    dependency_modules = tuple(
        importlib.import_module(module_name)
        for module_name in _DESIGN_GUIDE_DEPENDENCY_MODULE_NAMES
    )
    provider = InputsRuntimeDependencyProvider(
        modules=(
            common,
            calculations,
            widgets,
            setup,
            summaries,
            tail,
            mode,
            batch,
            design_guide,
            divider,
            *dependency_modules,
        )
    )
    design_guide_current_coordinators.configure_design_guide_current_provider(
        provider,
        st_module=st,
        os_module=os,
        sys_module=sys,
    )
    _bind_declared_runtime_dependencies(provider)
    return InputsPageRuntime(
        make_beam_3d_figure=make_beam_3d_figure,
        make_summary_cross_section_figure=make_summary_cross_section_figure,
        render_page_setup=render_inputs_page_setup_current_coordinator,
        handle_pending_apply=_handle_inputs_apply_buttons_current_coordinator,
        reconcile_design_actions=reconcile_inputs_design_actions_before_authority,
        refresh_authoritative_result=refresh_inputs_authoritative_design_result,
        refresh_engineering_result=refresh_inputs_engineering_result,
        refresh_design_brain_result=refresh_inputs_design_brain_result_background,
        render_batch_design_manager=render_inputs_batch_design_manager_coordinator,
        render_calculation=render_inputs_calculation_fragment_current_coordinator,
        render_design_guide=render_inputs_design_guide_current_coordinator,
        render_design_mode_selector=render_inputs_design_mode_selector_coordinator,
        render_page_divider=render_inputs_page_divider_coordinator,
        render_summary_pipeline=render_inputs_summary_pipeline_current_coordinator,
        render_tail=render_inputs_tail_current_coordinator,
        render_widget_sections=render_inputs_widget_sections_current_coordinator,
    )


__all__ = [
    "InputsPageRuntime",
    "InputsRuntimeDependencyProvider",
    "build_inputs_page_runtime",
]
