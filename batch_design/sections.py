"""Concrete section parsing helpers for Batch Design."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ConcreteSectionDimensions:
    width: float
    depth: float

    def label(self) -> str:
        return f"RECT {_format_number(self.width)} x {_format_number(self.depth)}"


def _format_number(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{float(value):g}"


def _clean_section_text(value: object) -> str:
    text = str(value or "").strip()
    text = text.replace("\u00d7", "x")
    text = re.sub(r"\s+", " ", text)
    return text


def parse_concrete_section_dimensions(value: object) -> ConcreteSectionDimensions | None:
    """Return width/depth only for explicit rectangular concrete section labels.

    SPACEGASS member-size strings such as ``310UB40`` are deliberately ignored:
    this app designs concrete beams, so non-concrete member labels must not be
    reinterpreted as geometry.
    """

    text = _clean_section_text(value)
    if not text:
        return None

    keyed_width = re.search(r"\b(?:b|bw|width|w)\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(?:mm)?\b", text, re.I)
    keyed_depth = re.search(r"\b(?:d|depth|height|h)\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(?:mm)?\b", text, re.I)
    if keyed_width and keyed_depth:
        width = float(keyed_width.group(1))
        depth = float(keyed_depth.group(1))
        if width > 0.0 and depth > 0.0:
            return ConcreteSectionDimensions(width=width, depth=depth)

    pair = re.search(
        r"(?:\b(?:rc|r\.c\.|conc|concrete|rect|rectangular)\b\s*)?"
        r"(\d+(?:\.\d+)?)\s*(?:mm)?\s*(?:x|by)\s*(\d+(?:\.\d+)?)\s*(?:mm)?\b",
        text,
        re.I,
    )
    if not pair:
        return None
    width = float(pair.group(1))
    depth = float(pair.group(2))
    if width <= 0.0 or depth <= 0.0:
        return None
    return ConcreteSectionDimensions(width=width, depth=depth)


def normalise_concrete_section_label(value: object) -> str | None:
    dimensions = parse_concrete_section_dimensions(value)
    return None if dimensions is None else dimensions.label()
