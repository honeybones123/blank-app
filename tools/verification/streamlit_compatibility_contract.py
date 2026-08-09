"""Lock supported Streamlit API usage and iframe compatibility semantics."""

from __future__ import annotations

from pathlib import Path

from ui.streamlit_iframe import render_trusted_iframe


ROOT = Path(__file__).resolve().parents[2]


class _FakeStreamlit:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def iframe(self, body: str, **kwargs):
        self.calls.append((body, kwargs))
        return "iframe"


def verify_iframe_contract() -> None:
    fake = _FakeStreamlit()
    assert render_trusted_iframe(
        fake,
        "<script>window.parent;</script>",
        height=0,
        width=0,
        scrolling=False,
    ) == "iframe"
    body, kwargs = fake.calls[-1]
    assert "overflow:hidden" in body
    assert kwargs == {"width": 1, "height": 1}

    render_trusted_iframe(fake, "<p>diagram</p>", height=500, scrolling=True)
    body, kwargs = fake.calls[-1]
    assert "overflow:hidden" not in body
    assert kwargs == {"width": "stretch", "height": 500}


def verify_no_deprecated_calls() -> None:
    python_files = tuple(
        path
        for path in ROOT.rglob("*.py")
        if ".venv" not in path.parts
        and "build" not in path.parts
        and "__pycache__" not in path.parts
    )
    offenders: list[str] = []
    for path in python_files:
        source = path.read_text(encoding="utf-8")
        if (
            "use_container" + "_width" in source
            or "components." + "html(" in source
            or "experimental" + "_" in source
        ):
            offenders.append(str(path.relative_to(ROOT)))
    assert not offenders, f"deprecated Streamlit calls remain: {offenders}"


def main() -> None:
    verify_iframe_contract()
    verify_no_deprecated_calls()
    print("streamlit compatibility contract: PASS")


if __name__ == "__main__":
    main()
