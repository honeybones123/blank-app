from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, is_dataclass
from typing import Any

from .contracts import (
    CALCULATION_EXPLAINER_CARD_ORDER,
    CALCULATION_EXPLAINER_CARD_TITLES,
    CALCULATION_EXPLAINER_ROUTE_PAGES,
    CALCULATION_EXPLAINER_ROW_FIELDS,
    DISPLAY_HASH_FIELDS,
)
from .models import (
    CalculationExplainerCardViewModel,
    CalculationExplainerRowViewModel,
    InputsCalculationExplainerSectionViewModel,
    InputsCalculationExplainerSourceSnapshot,
)


def _json_default(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, tuple):
        return list(value)
    return str(value)


def stable_calculation_explainer_json(payload: Any) -> str:
    return json.dumps(payload, default=_json_default, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def stable_calculation_explainer_hash(payload: Any) -> str:
    return hashlib.sha256(stable_calculation_explainer_json(payload).encode("utf-8")).hexdigest()


def _row_tuple(rows: Any) -> tuple[dict[str, Any], ...]:
    if not rows:
        return ()
    return tuple(dict(row) for row in rows if isinstance(row, dict))


def build_inputs_calculation_explainer_source_snapshot(
    *,
    bending_rows: Any = (),
    shear_rows: Any = (),
    crack_rows: Any = (),
    deflection_rows: Any = (),
    run_state: dict[str, Any] | None = None,
) -> InputsCalculationExplainerSourceSnapshot:
    return InputsCalculationExplainerSourceSnapshot(
        bending_rows=_row_tuple(bending_rows),
        shear_rows=_row_tuple(shear_rows),
        crack_rows=_row_tuple(crack_rows),
        deflection_rows=_row_tuple(deflection_rows),
        run_state=dict(run_state or {}),
    )


def build_inputs_calculation_explainer_source_hash(
    source: InputsCalculationExplainerSourceSnapshot,
) -> str:
    return stable_calculation_explainer_hash(
        {
            "bending_rows": source.bending_rows,
            "shear_rows": source.shear_rows,
            "crack_rows": source.crack_rows,
            "deflection_rows": source.deflection_rows,
            "run_state": source.run_state,
        }
    )


def _text(value: Any) -> str:
    return "" if value is None else str(value)


def _row_payload(row: dict[str, Any], route_page: str) -> dict[str, Any]:
    payload = {field: row.get(field) for field in CALCULATION_EXPLAINER_ROW_FIELDS if field in row}
    payload["route_page"] = _text(payload.get("route_page") or route_page)
    return payload


def _row_view_model(row: dict[str, Any], route_page: str) -> CalculationExplainerRowViewModel:
    raw = _row_payload(row, route_page)
    calculated = (
        row.get("calculated")
        or row.get("capacity")
        or row.get("value")
        or ""
    )
    requirement = (
        row.get("requirement")
        or row.get("limit")
        or row.get("action")
        or ""
    )
    model_payload = {
        "uid": _text(row.get("uid") or row.get("id") or ""),
        "title": _text(row.get("title") or row.get("label") or ""),
        "calculated": _text(calculated),
        "requirement": _text(requirement),
        "utilisation": _text(row.get("util") or row.get("utilisation") or ""),
        "status": _text(row.get("status") or ""),
        "route_page": _text(row.get("route_page") or route_page),
        "tab": _text(row.get("tab") or ""),
        "is_informational": bool(row.get("is_informational")),
        "raw": raw,
    }
    display_payload = {key: value for key, value in model_payload.items() if key != "raw"}
    return CalculationExplainerRowViewModel(
        **model_payload,
        display_hash=stable_calculation_explainer_hash(display_payload),
    )


def _card_status(rows: tuple[CalculationExplainerRowViewModel, ...]) -> str:
    statuses = [row.status.strip().upper() for row in rows if row.status.strip()]
    if any(status in {"FAIL", "NG"} for status in statuses):
        return "FAIL"
    if any(status in {"NEAR LIMIT", "WARN", "CHECK"} for status in statuses):
        return "NEAR LIMIT"
    if any(status == "PASS" for status in statuses):
        return "PASS"
    if any(status in {"NOT RUN", "CAPACITY", "INFO"} for status in statuses):
        return statuses[0]
    return ""


def _card_view_model(check_id: str, rows: tuple[dict[str, Any], ...]) -> CalculationExplainerCardViewModel:
    route_page = CALCULATION_EXPLAINER_ROUTE_PAGES[check_id]
    row_models = tuple(_row_view_model(dict(row), route_page) for row in rows if isinstance(row, dict))
    card_payload = {
        "check_id": check_id,
        "title": CALCULATION_EXPLAINER_CARD_TITLES[check_id],
        "status": _card_status(row_models),
        "route_page": route_page,
        "rows": tuple(row.display_hash for row in row_models),
    }
    return CalculationExplainerCardViewModel(
        check_id=check_id,
        title=CALCULATION_EXPLAINER_CARD_TITLES[check_id],
        rows=row_models,
        status=card_payload["status"],
        route_page=route_page,
        display_hash=stable_calculation_explainer_hash(
            {field: card_payload.get(field) for field in DISPLAY_HASH_FIELDS}
        ),
    )


def build_inputs_calculation_explainer_view_model(
    source: InputsCalculationExplainerSourceSnapshot,
) -> InputsCalculationExplainerSectionViewModel:
    source_by_id = {
        "bending": source.bending_rows,
        "shear": source.shear_rows,
        "crack": source.crack_rows,
        "deflection": source.deflection_rows,
    }
    cards = tuple(
        _card_view_model(check_id, tuple(source_by_id.get(check_id) or ()))
        for check_id in CALCULATION_EXPLAINER_CARD_ORDER
    )
    section_payload = {
        "cards": tuple(card.display_hash for card in cards),
        "order": CALCULATION_EXPLAINER_CARD_ORDER,
        "run_state": dict(source.run_state or {}),
    }
    return InputsCalculationExplainerSectionViewModel(
        cards=cards,
        display_hash=stable_calculation_explainer_hash(section_payload),
    )
