from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


CONTRACT_PATH = Path(__file__).with_name("min_bending_reo_contract.json")


def load_min_bending_reo_contract() -> dict[str, Any]:
    with CONTRACT_PATH.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("Minimum bending reo compatibility contract must be a JSON object")
    return data


def contract_hash() -> str:
    payload = json.dumps(load_min_bending_reo_contract(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


__all__ = ["CONTRACT_PATH", "contract_hash", "load_min_bending_reo_contract"]
