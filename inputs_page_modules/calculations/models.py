from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CalculationExplainerRowViewModel:
    uid: str
    title: str
    calculated: str = ""
    requirement: str = ""
    utilisation: str = ""
    status: str = ""
    route_page: str = ""
    tab: str = ""
    is_informational: bool = False
    raw: dict[str, Any] = field(default_factory=dict)
    display_hash: str = ""


@dataclass(frozen=True)
class CalculationExplainerCardViewModel:
    check_id: str
    title: str
    rows: tuple[CalculationExplainerRowViewModel, ...]
    status: str = ""
    route_page: str = ""
    display_hash: str = ""


@dataclass(frozen=True)
class InputsCalculationExplainerSourceSnapshot:
    bending_rows: tuple[dict[str, Any], ...] = ()
    shear_rows: tuple[dict[str, Any], ...] = ()
    crack_rows: tuple[dict[str, Any], ...] = ()
    deflection_rows: tuple[dict[str, Any], ...] = ()
    run_state: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class InputsCalculationExplainerSectionViewModel:
    cards: tuple[CalculationExplainerCardViewModel, ...]
    display_hash: str
