from __future__ import annotations


def normalise_shape_name(shape_name: str | None) -> str:
    """
    Convert any UI / legacy string into canonical tokens used INSIDE section_props only:
      - "RECT" | "T" | "I"
    Unknown shapes are returned as-is (so we fail loudly where appropriate).
    """
    if not shape_name:
        return "RECT"

    s = str(shape_name).strip()
    sl = s.lower()

    # Rectangle variants
    if sl in {"rect", "rectangle", "rectangular", "bxd"}:
        return "RECT"
    if "rectangle" in sl:
        return "RECT"

    # T variants
    if sl in {"t", "t-section", "tsection"}:
        return "T"
    if "t-section" in sl or "t section" in sl:
        return "T"

    # I variants
    if sl in {"i", "i-section", "isection"}:
        return "I"
    if "i-section" in sl or "i section" in sl:
        return "I"

    return s
