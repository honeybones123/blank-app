from __future__ import annotations

import sys
from pathlib import Path

import matplotlib


matplotlib.use("Agg")

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ui.diagrams.stress_strain_diagram import make_sls_strain_distribution_figure


def _assert_figure_for_key(key: str) -> None:
    fig = make_sls_strain_distribution_figure(
        [
            {"Layer": "Top fibre", "Depth y (mm)": 0.0, key: -0.00012},
            {"Layer": "Bottom fibre", "Depth y (mm)": 750.0, key: 0.00034},
        ],
        dn_sls=280.0,
    )
    assert fig.axes
    assert fig.axes[0].get_title() == "SLS strain distribution"
    fig.clear()


def test_sls_strain_diagram_accepts_canonical_and_legacy_keys() -> None:
    _assert_figure_for_key("\u03b5")
    _assert_figure_for_key("\u00ce\u00b5")
    _assert_figure_for_key("\u00c3\u017d\u00c2\u00b5")
    _assert_figure_for_key("eps")
    _assert_figure_for_key("epsilon")


def main() -> int:
    test_sls_strain_diagram_accepts_canonical_and_legacy_keys()
    print("bending_sls_strain_diagram_key_contract: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
