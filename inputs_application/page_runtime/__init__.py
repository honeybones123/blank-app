"""Typed permanent application runtime for Inputs page composition."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import streamlit as st

from inputs_application.design_brain_composition import selected_design_brain_adapter_name
from inputs_application.page_runtime import calculations, common, mode, setup, summaries, tail, widgets
from inputs_application.page_runtime.calculations import (
    render_inputs_calculation_fragment_current_coordinator,
)
from inputs_application.page_runtime.common import (
    _handle_inputs_apply_buttons_current_coordinator,
    make_beam_3d_figure,
    make_summary_cross_section_figure,
    reconcile_inputs_design_actions_before_authority,
)
from inputs_application.page_runtime.mode import (
    render_inputs_design_mode_selector_coordinator,
)
from inputs_application.page_runtime.setup import (
    project_committed_action_source_for_result_page,
    refresh_inputs_design_brain_result,
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


def _render_design_guide_placeholder(**_: Any) -> None:
    """V2 owns Design Guide rendering through the workspace card adapter."""

    return None


def _render_page_divider_placeholder() -> None:
    """Compatibility slot retained while the unused divider is retired."""

    return None


def _render_inputs_batch_design_manager_lazy(**kwargs: Any) -> Any:
    """Load the optional Batch Design surface only when it is rendered."""

    from inputs_application.page_runtime.batch import (
        render_inputs_batch_design_manager_coordinator,
    )

    return render_inputs_batch_design_manager_coordinator(**kwargs)

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
    hydrate_design_action_widgets: PageCallable
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
    # V2 is the only supported Design Brain composition.  The old branch used
    # to import a large V1 module graph here; keeping that branch latent made a
    # direct page-runtime import capable of reintroducing retired V1 code.
    # The V2 card is rendered by the engineering workspace from the neutral
    # publication, so no legacy renderer or dependency modules are needed.
    selected_adapter = selected_design_brain_adapter_name()
    if selected_adapter != "v2":
        raise RuntimeError("Inputs page runtime requires the V2 Design Brain")
    render_design_guide_current_coordinator: PageCallable = _render_design_guide_placeholder
    runtime_modules = (
        common,
        calculations,
        widgets,
        setup,
        summaries,
        tail,
        mode,
    )
    provider = InputsRuntimeDependencyProvider(
        modules=runtime_modules
    )
    _bind_declared_runtime_dependencies(provider)
    return InputsPageRuntime(
        make_beam_3d_figure=make_beam_3d_figure,
        make_summary_cross_section_figure=make_summary_cross_section_figure,
        render_page_setup=render_inputs_page_setup_current_coordinator,
        handle_pending_apply=_handle_inputs_apply_buttons_current_coordinator,
        hydrate_design_action_widgets=widgets.hydrate_inputs_design_action_widgets_before_summary,
        reconcile_design_actions=reconcile_inputs_design_actions_before_authority,
        refresh_authoritative_result=refresh_inputs_authoritative_design_result,
        refresh_engineering_result=refresh_inputs_engineering_result,
        # Match V2: preview synchronously in the Design Brain fragment and
        # cache/reuse by the committed revision/hash.  A subprocess poll here
        # added a second state machine and made the card flicker while widgets
        # and calculations were already independent.
        refresh_design_brain_result=refresh_inputs_design_brain_result,
        render_batch_design_manager=_render_inputs_batch_design_manager_lazy,
        render_calculation=render_inputs_calculation_fragment_current_coordinator,
        render_design_guide=render_design_guide_current_coordinator,
        render_design_mode_selector=render_inputs_design_mode_selector_coordinator,
        render_page_divider=_render_page_divider_placeholder,
        render_summary_pipeline=render_inputs_summary_pipeline_current_coordinator,
        render_tail=render_inputs_tail_current_coordinator,
        render_widget_sections=render_inputs_widget_sections_current_coordinator,
    )


__all__ = [
    "InputsPageRuntime",
    "InputsRuntimeDependencyProvider",
    "build_inputs_page_runtime",
]
