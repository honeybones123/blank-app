"""Design Brain family classification contract facade.

This module intentionally does not implement live classification yet. It exposes
the machine-readable classification contract from inside Design Brain without
importing page runtime modules, Streamlit, page state, CTA rendering,
publication, or family strategy ladders.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any


_CONTRACT_MODULE_PATH = Path(__file__).resolve().parent / "contracts" / "family_classification_contract.py"


def _load_contract_module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "design_brain_family_classification_contract_file",
        _CONTRACT_MODULE_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load family classification contract: {_CONTRACT_MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_family_classification_contract() -> dict[str, Any]:
    """Load the family-classification contract through the Design Brain facade."""

    return _load_contract_module().load_family_classification_contract()


def allowed_family_ids() -> tuple[str, ...]:
    """Return family IDs allowed by the classification contract."""

    return _load_contract_module().allowed_family_ids()


def classification_priority_order() -> tuple[str, ...]:
    """Return explicit family classification priority order."""

    return _load_contract_module().classification_priority_order()


def classification_rules() -> dict[str, dict[str, Any]]:
    """Return the contract-defined family classification rules."""

    return _load_contract_module().classification_rules()


__all__ = [
    "allowed_family_ids",
    "classification_priority_order",
    "classification_rules",
    "load_family_classification_contract",
]
