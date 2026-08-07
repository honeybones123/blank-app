"""Neutral contracts between the beam application and a Design Brain.

These immutable models belong to the application, not to any concrete Design
Brain implementation.  A replacement implementation may depend on this
module; the application must not depend on the replacement's internal types.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields, replace
import hashlib
import json
from typing import Any


ENGINEERING_INPUT_SNAPSHOT_SCHEMA_VERSION = "engineering_input_snapshot.v1"
AUTHORITATIVE_DESIGN_RESULT_SCHEMA_VERSION = "authoritative_design_result.v1"

UI_ONLY_EXCLUDED_FIELDS = frozenset(
    {
        "active_tabs",
        "expanded_panels",
        "scroll_state",
        "camera_settings",
        "help_toggles",
        "fullscreen_state",
        "loading_flags",
        "timestamps",
    }
)

PUBLICATION_AUTHORITY_EXCLUDED_FIELDS = frozenset(
    {
        "evaluation_timings",
        "trace_ordering",
        "candidate_iteration_order",
        "timestamps",
        "cache_hit_metadata",
        "debug",
        "debug_only",
        "profiling",
    }
)


def _canonical(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _canonical(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    if isinstance(value, set):
        return [_canonical(item) for item in sorted(value, key=lambda item: repr(item))]
    return value


def stable_authority_hash(value: Any) -> str:
    payload = json.dumps(_canonical(value), sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class EngineeringInputSnapshot:
    """Complete committed engineering input state, excluding UI-only state."""

    geometry: dict[str, Any] = field(default_factory=dict)
    materials: dict[str, Any] = field(default_factory=dict)
    reinforcement: dict[str, Any] = field(default_factory=dict)
    design_actions: dict[str, Any] = field(default_factory=dict)
    design_settings: dict[str, Any] = field(default_factory=dict)
    locked_variables: dict[str, Any] = field(default_factory=dict)
    unlocked_variables: dict[str, Any] = field(default_factory=dict)
    contract_versions: dict[str, Any] = field(default_factory=dict)
    calculation_versions: dict[str, Any] = field(default_factory=dict)
    schema_version: str = ENGINEERING_INPUT_SNAPSHOT_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def engineering_hash(self) -> str:
        return stable_authority_hash(self.to_dict())


@dataclass(frozen=True)
class AuthoritativeDesignResult:
    """Single immutable result consumed by application and presentation code."""

    engineering_hash: str
    current_calculations: dict[str, Any] = field(default_factory=dict)
    governing_family: str | None = None
    family_contract_version: str | None = None
    family_outcome: str | None = None
    selected_candidate: dict[str, Any] | None = None
    selected_candidate_absence: dict[str, Any] | None = None
    selected_updates: dict[str, Any] = field(default_factory=dict)
    candidate_evaluation: dict[str, Any] = field(default_factory=dict)
    candidate_acceptance_proof: dict[str, Any] = field(default_factory=dict)
    blocker_or_exhaustion_proof: dict[str, Any] = field(default_factory=dict)
    final_publication: dict[str, Any] = field(default_factory=dict)
    display_model: dict[str, Any] = field(default_factory=dict)
    cta_model: dict[str, Any] = field(default_factory=dict)
    apply_payload: dict[str, Any] = field(default_factory=dict)
    publication_authority_hash: str | None = None
    schema_version: str = AUTHORITATIVE_DESIGN_RESULT_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def publication_authority_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "engineering_hash": self.engineering_hash,
            "governing_family": self.governing_family,
            "family_outcome": self.family_outcome,
            "selected_candidate": self.selected_candidate,
            "selected_candidate_absence": self.selected_candidate_absence,
            "selected_updates": self.selected_updates,
            "candidate_acceptance_proof": self.candidate_acceptance_proof,
            "blocker_or_exhaustion_proof": self.blocker_or_exhaustion_proof,
            "final_publication": self.final_publication,
            "display_model": self.display_model,
            "cta_model": self.cta_model,
            "apply_payload": self.apply_payload,
        }

    def with_publication_authority_hash(self) -> "AuthoritativeDesignResult":
        return replace(
            self,
            publication_authority_hash=stable_authority_hash(
                self.publication_authority_payload()
            ),
        )


_AUTHORITATIVE_RESULT_FIELD_NAMES = frozenset(
    field_info.name for field_info in fields(AuthoritativeDesignResult)
)
_AUTHORITATIVE_RESULT_COMPATIBILITY_MODULES = frozenset(
    {
        AuthoritativeDesignResult.__module__,
        "design_brain.authority",
    }
)


def coerce_authoritative_design_result(
    value: Any,
) -> AuthoritativeDesignResult | None:
    """Normalize a result across Streamlit hot-reload module identities.

    Streamlit can retain an object created by a previous module instance while
    the current rerun imports a fresh ``AuthoritativeDesignResult`` class.
    Structural rebinding keeps the neutral contract authoritative without
    accepting arbitrary dictionaries or legacy result types.
    """

    if isinstance(value, AuthoritativeDesignResult):
        return value
    value_type = type(value)
    if (
        value_type.__module__ not in _AUTHORITATIVE_RESULT_COMPATIBILITY_MODULES
        or value_type.__name__ != AuthoritativeDesignResult.__name__
    ):
        return None
    to_dict = getattr(value, "to_dict", None)
    if not callable(to_dict):
        return None
    try:
        payload = to_dict()
        if not isinstance(payload, dict):
            return None
        return AuthoritativeDesignResult(
            **{
                key: payload[key]
                for key in _AUTHORITATIVE_RESULT_FIELD_NAMES
                if key in payload
            }
        )
    except (KeyError, TypeError, ValueError):
        return None


def build_authoritative_design_result(
    *,
    engineering_snapshot: EngineeringInputSnapshot,
    current_calculations: dict[str, Any] | None = None,
    governing_family: str | None = None,
    family_contract_version: str | None = None,
    family_outcome: str | None = None,
    selected_candidate: dict[str, Any] | None = None,
    selected_candidate_absence: dict[str, Any] | None = None,
    selected_updates: dict[str, Any] | None = None,
    candidate_evaluation: dict[str, Any] | None = None,
    candidate_acceptance_proof: dict[str, Any] | None = None,
    blocker_or_exhaustion_proof: dict[str, Any] | None = None,
    final_publication: dict[str, Any] | None = None,
    display_model: dict[str, Any] | None = None,
    cta_model: dict[str, Any] | None = None,
    apply_payload: dict[str, Any] | None = None,
) -> AuthoritativeDesignResult:
    result = AuthoritativeDesignResult(
        engineering_hash=engineering_snapshot.engineering_hash,
        current_calculations=dict(current_calculations or {}),
        governing_family=governing_family,
        family_contract_version=family_contract_version,
        family_outcome=family_outcome,
        selected_candidate=(
            dict(selected_candidate) if selected_candidate is not None else None
        ),
        selected_candidate_absence=(
            dict(selected_candidate_absence)
            if selected_candidate_absence is not None
            else None
        ),
        selected_updates=dict(selected_updates or {}),
        candidate_evaluation=dict(candidate_evaluation or {}),
        candidate_acceptance_proof=dict(candidate_acceptance_proof or {}),
        blocker_or_exhaustion_proof=dict(blocker_or_exhaustion_proof or {}),
        final_publication=dict(final_publication or {}),
        display_model=dict(display_model or {}),
        cta_model=dict(cta_model or {}),
        apply_payload=dict(apply_payload or {}),
        publication_authority_hash=None,
    )
    return result.with_publication_authority_hash()


__all__ = [
    "AUTHORITATIVE_DESIGN_RESULT_SCHEMA_VERSION",
    "AuthoritativeDesignResult",
    "ENGINEERING_INPUT_SNAPSHOT_SCHEMA_VERSION",
    "EngineeringInputSnapshot",
    "PUBLICATION_AUTHORITY_EXCLUDED_FIELDS",
    "UI_ONLY_EXCLUDED_FIELDS",
    "build_authoritative_design_result",
    "coerce_authoritative_design_result",
    "stable_authority_hash",
]
