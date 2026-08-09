"""Keep Load Analysis on the same native scroll model as other pages."""

from __future__ import annotations

from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    source = (root / "design_page_runtime.py").read_text(encoding="utf-8-sig")

    forbidden = {
        "_install_design_scroll_preserver": "custom scroll-preserver hook",
        "beam_design_scroll_restore_v1": "persisted stale scroll position",
        "__beamDesignPendingScroll": "page-wide pending scroll state",
    }
    offenders = [label for token, label in forbidden.items() if token in source]
    assert not offenders, (
        "Load Analysis must use native Streamlit/browser scroll behaviour: "
        f"{offenders}"
    )

    print("load analysis scroll contract: PASS")


if __name__ == "__main__":
    main()
