"""Smoke checks for the extracted curved-beam bending diagram."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import curved_beam_diagram  # noqa: E402
from ui.diagrams.curved_beam_diagram import render_curved_beam_fig  # noqa: E402


def _signature(fig) -> tuple[int, int, int, int, tuple[str, ...], bool]:
    axes = list(fig.axes)
    if not axes:
        return (0, 0, 0, 0, (), True)
    ax = axes[0]
    return (
        len(axes),
        len(ax.lines),
        len(ax.patches),
        len(ax.texts),
        tuple(str(text.get_text() or "") for text in ax.texts),
        bool(ax.axison),
    )


def main() -> int:
    failures: list[str] = []
    module_fig = render_curved_beam_fig(L=6.0, D=0.8, b=0.4, dn_uls=0.21, curvature=0.22)
    legacy_fig = curved_beam_diagram.render_curved_beam_fig(
        L=6.0,
        D=0.8,
        b=0.4,
        dn_uls=0.21,
        curvature=0.22,
    )
    module_sig = _signature(module_fig)
    legacy_sig = _signature(legacy_fig)

    if curved_beam_diagram.render_curved_beam_fig is not render_curved_beam_fig:
        failures.append("curved_beam_legacy_wrapper_not_delegated")
    if module_sig != legacy_sig:
        failures.append("curved_beam_legacy_signature_changed")
    if module_sig[:4] != (1, 21, 2, 10):
        failures.append("curved_beam_signature_changed")
    text_values = module_sig[4]
    for expected in ("Compression", "Tension"):
        if expected not in text_values:
            failures.append(f"curved_beam_text_missing_{expected}")
    if module_sig[5] is not False:
        failures.append("curved_beam_axis_not_hidden")
    root_source = (ROOT / "curved_beam_diagram.py").read_text(encoding="utf-8")
    if "plt.subplots" in root_source or "Polygon(" in root_source:
        failures.append("curved_beam_builder_body_still_in_root_wrapper")

    if failures:
        print("DIAGRAM_CURVED_BEAM_SMOKE FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("DIAGRAM_CURVED_BEAM_SMOKE PASS")
    print("- curved-beam module builder and legacy wrapper verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
