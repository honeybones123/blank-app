"""Typed service bundle over the session-scoped storage adapter.

Streamlit owns the mapping lifetime. Application and Design Brain coordinators
consume these explicit stores instead of treating that mapping as their API.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, MutableMapping

from application.design_result_store import EngineeringResultStore
from inputs_application.apply_transaction_store import ApplyTransactionStore
from inputs_application.design_guide_fragment_store import PublicationStore
from inputs_application.engineering_input_store import InputSnapshotStore
from inputs_application.recommendation_store import RecommendationStore


@dataclass(frozen=True)
class InputsSessionServices:
    input_snapshots: InputSnapshotStore
    engineering_results: EngineeringResultStore
    publications: PublicationStore
    recommendations: RecommendationStore
    apply_transactions: ApplyTransactionStore

    @classmethod
    def from_mapping(
        cls,
        session_storage: MutableMapping[str, Any],
    ) -> "InputsSessionServices":
        """Bind all services to one shared session storage adapter."""

        return cls(
            input_snapshots=InputSnapshotStore(session_storage),
            engineering_results=EngineeringResultStore(session_storage),
            publications=PublicationStore(session_storage),
            recommendations=RecommendationStore(session_storage),
            apply_transactions=ApplyTransactionStore(session_storage),
        )


__all__ = ["InputsSessionServices"]
