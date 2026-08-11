from __future__ import annotations

from inputs_application import time_dependent_presentation as presentation


def test_authoritative_values_replace_only_requested_fallback_fields(monkeypatch) -> None:
    monkeypatch.setattr(
        presentation,
        "current_authoritative_family",
        lambda _state, family: {
            "phi_cc_t": 1.75,
            "eps_cc_micro": 321.0,
            "unrequested_internal_value": 999.0,
        }
        if family == "creep"
        else None,
    )

    resolved = presentation.resolve_time_dependent_family_values(
        {},
        family="creep",
        fallback={"phi_cc_t": 1.1, "eps_cc_micro": 0.0},
    )

    assert resolved == {"phi_cc_t": 1.75, "eps_cc_micro": 321.0}


def test_missing_authoritative_family_preserves_local_fallback(monkeypatch) -> None:
    monkeypatch.setattr(
        presentation,
        "current_authoritative_family",
        lambda _state, _family: None,
    )

    fallback = {"eps_cse": 0.0001, "eps_cs_total_micro": 630.0}
    resolved = presentation.resolve_time_dependent_family_values(
        {},
        family="shrinkage",
        fallback=fallback,
    )

    assert resolved == fallback
    assert resolved is not fallback


def test_none_authoritative_value_does_not_erase_valid_fallback(monkeypatch) -> None:
    monkeypatch.setattr(
        presentation,
        "current_authoritative_family",
        lambda _state, _family: {"eps_cse": None},
    )

    resolved = presentation.resolve_time_dependent_family_values(
        {},
        family="shrinkage",
        fallback={"eps_cse": 0.00012},
    )

    assert resolved["eps_cse"] == 0.00012
