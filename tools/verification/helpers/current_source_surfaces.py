"""Current production source surfaces used by structural verifiers.

Keep this list deliberately small and explicit.  Verifiers should inspect the
current shell/coordinator split, not assume that retired monolith filenames
still exist.
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]

CURRENT_INPUTS_COMPOSITION_SURFACES = (
    "inputs_page.py",
    "inputs_page_app_contracts.py",
    "inputs_page_modules/design_guide/current_coordinators.py",
    "inputs_page_modules/design_guide/render_coordinators.py",
    "inputs_page_modules/widgets/render_coordinators.py",
    "inputs_application/page_runtime/widgets.py",
    "inputs_application/page_runtime/design_guide.py",
)


def read_current_inputs_composition_surface() -> str:
    """Return the current Inputs shell/coordinator source for static checks."""
    missing = [path for path in CURRENT_INPUTS_COMPOSITION_SURFACES if not (ROOT / path).is_file()]
    if missing:
        raise FileNotFoundError(f"Current Inputs composition surface is incomplete: {missing}")
    return "\n".join(
        f"# SOURCE: {path}\n{(ROOT / path).read_text(encoding='utf-8', errors='replace')}"
        for path in CURRENT_INPUTS_COMPOSITION_SURFACES
    )
