from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class InputsWidgetSpecViewModel:
    widget_id: str
    group_id: str
    kind: str
    label: str
    widget_key: str
    shared_key: str = ""
    callback_key: str = ""
    help_text: str = ""
    default: Any = None
    options: tuple[Any, ...] = ()
    disabled: bool = False
    display_hash: str = ""


@dataclass(frozen=True)
class InputsWidgetGroupViewModel:
    group_id: str
    widgets: tuple[InputsWidgetSpecViewModel, ...] = field(default_factory=tuple)
    display_hash: str = ""
