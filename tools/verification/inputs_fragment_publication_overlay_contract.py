"""Lock fragment-owned publication fallback for browser verification."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs_application.design_guide_fragment_store import (  # noqa: E402
    DesignGuideFragmentState,
)
from inputs_application.engineering_workspace import (  # noqa: E402
    _fragment_browser_publication_projection,
)
from design_brain.authority import AuthoritativeDesignResult  # noqa: E402


def main() -> int:
    final_publication = {
        "selected_family": "TARGET_BAND_REACHED",
        "outcome_state": "PASS",
        "publication_hash": "terminal-publication-hash",
        "cta": {
            "enabled": False,
            "actionable": False,
            "family": "TARGET_BAND_REACHED",
        },
    }
    verifier = {
        "selected_family_id": "TARGET_BAND_REACHED",
        "outcome_state": "PASS",
        "final_publication_cta_hash": "terminal-cta-hash",
    }
    fragment_state = DesignGuideFragmentState(
        status="ready",
        active_engineering_hash="terminal-engineering-hash",
        active_publication_authority_hash="terminal-publication-hash",
        active_publication={
            "final_design_guide_publication": final_publication,
            "final_publication_verifier_payload": verifier,
        },
    )
    projection = _fragment_browser_publication_projection(
        authoritative_result=None,
        fragment_state=fragment_state,
    )
    authoritative_projection = _fragment_browser_publication_projection(
        authoritative_result=AuthoritativeDesignResult(
            engineering_hash="authoritative-engineering-hash",
            governing_family="TARGET_BAND_REACHED",
            family_outcome="PASS",
            final_publication={
                "final_design_guide_publication": final_publication,
                "final_publication_verifier_payload": {
                    "selected_family_id": "TARGET_BAND_REACHED",
                    "final_publication_cta_hash": "terminal-cta-hash",
                },
            },
            cta_model=final_publication["cta"],
            publication_authority_hash="terminal-publication-hash",
        ),
        fragment_state=fragment_state,
    )
    checks = {
        "fragment_publication_restored": (
            projection.get("final_publication") == final_publication
        ),
        "fragment_verifier_restored": (
            projection.get("final_verifier") == verifier
        ),
        "terminal_family_restored": (
            projection.get("selected_family_id") == "TARGET_BAND_REACHED"
        ),
        "terminal_outcome_restored": (
            dict(projection.get("final_verifier") or {}).get("outcome_state")
            == "PASS"
        ),
        "disabled_cta_restored": (
            dict(projection.get("cta_model") or {}).get("enabled") is False
        ),
        "engineering_hash_restored": (
            projection.get("engineering_hash") == "terminal-engineering-hash"
        ),
        "authority_hash_restored": (
            projection.get("publication_authority_hash")
            == "terminal-publication-hash"
        ),
        "authoritative_outcome_backfilled": (
            dict(authoritative_projection.get("final_verifier") or {}).get(
                "outcome_state"
            )
            == "PASS"
        ),
    }
    artifact = {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "projection": projection,
        "authoritative_projection": authoritative_projection,
    }
    path = (
        ROOT
        / "artifacts"
        / "verification"
        / "inputs_fragment_publication_overlay_contract.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(artifact, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(f"{artifact['status']}: fragment publication overlay artifact={path}")
    return 0 if artifact["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
