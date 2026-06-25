import json
import os
from dataclasses import asdict
from datetime import datetime
from typing import Any


def record_design_guide_card_data_attributes(
    fields: Any,
    data_attributes: dict,
) -> None:
    path = os.environ.get("DESIGN_GUIDE_CARD_DATA_ATTRIBUTES_SNAPSHOT_PATH", "").strip()
    if not path:
        return
    try:
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        row = {
            "timestamp": datetime.now().isoformat(timespec="milliseconds"),
            "source": "build_design_guide_card_data_attributes",
            "fields": asdict(fields),
            "data_attributes": dict(data_attributes or {}),
        }
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, default=str, sort_keys=True) + "\n")
    except (OSError, TypeError, ValueError):
        return


def record_design_guide_card_decision_display_fields(fields: Any) -> None:
    path = os.environ.get("DESIGN_GUIDE_CARD_DECISION_DISPLAY_SNAPSHOT_PATH", "").strip()
    if not path:
        return
    try:
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        row = {
            "timestamp": datetime.now().isoformat(timespec="milliseconds"),
            "source": "build_design_guide_card_decision_display_fields",
            "fields": asdict(fields),
        }
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, default=str, sort_keys=True) + "\n")
    except (OSError, TypeError, ValueError):
        return


def record_design_guide_card_render_model(
    model: Any,
    *,
    source: str,
) -> None:
    path = os.environ.get("DESIGN_GUIDE_CARD_RENDER_MODEL_SNAPSHOT_PATH", "").strip()
    if not path:
        return
    try:
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        row = {
            "timestamp": datetime.now().isoformat(timespec="milliseconds"),
            "source": str(source or "").strip(),
            "model": model.to_dict(),
        }
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, default=str, sort_keys=True) + "\n")
    except (OSError, TypeError, ValueError):
        return
