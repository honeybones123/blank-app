"""Lock recursive fragment browser-state overlay semantics."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification.helpers.browser_state_overlay import (  # noqa: E402
    merge_fragment_browser_state_overlay,
)


def main() -> int:
    base = {
        "final_publication_verifier_payload": {
            "selected_family_id": "TARGET_BAND_REACHED",
            "outcome_state": "PASS",
            "publication_hash": "old-hash",
            "cta": {"enabled": True, "actionable": True},
        },
        "final_publication_hashes": {
            "selected_family_id": "TARGET_BAND_REACHED",
            "outcome_state": "PASS",
            "publication_hash": "old-hash",
        },
        "summary_overview_probe": {
            "all_key_pass": False,
            "any_fail": True,
        },
    }
    overlay = {
        "fragment_fresh": True,
        "final_publication_verifier_payload": {
            "publication_hash": "new-hash",
            "cta": {"enabled": False, "actionable": False},
        },
        "final_publication_hashes": {
            "publication_hash": "new-hash",
        },
        "summary_overview_probe": {
            "all_key_pass": True,
            "any_fail": False,
        },
    }
    merged = merge_fragment_browser_state_overlay(base, overlay)
    verifier = dict(merged.get("final_publication_verifier_payload") or {})
    hashes = dict(merged.get("final_publication_hashes") or {})
    overview = dict(merged.get("summary_overview_probe") or {})
    checks = {
        "family_survives_nested_overlay": (
            verifier.get("selected_family_id") == "TARGET_BAND_REACHED"
            and hashes.get("selected_family_id") == "TARGET_BAND_REACHED"
        ),
        "outcome_survives_nested_overlay": (
            verifier.get("outcome_state") == "PASS"
            and hashes.get("outcome_state") == "PASS"
        ),
        "fresh_hash_overrides": (
            verifier.get("publication_hash") == "new-hash"
            and hashes.get("publication_hash") == "new-hash"
        ),
        "explicit_false_overrides": (
            dict(verifier.get("cta") or {}).get("enabled") is False
            and dict(verifier.get("cta") or {}).get("actionable") is False
            and overview.get("any_fail") is False
        ),
        "explicit_true_overrides": overview.get("all_key_pass") is True,
        "fragment_fresh_preserved": merged.get("fragment_fresh") is True,
    }
    artifact = {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "merged": merged,
    }
    path = (
        ROOT
        / "artifacts"
        / "verification"
        / "browser_state_fragment_overlay_merge_contract.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(artifact, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(f"{artifact['status']}: fragment overlay merge artifact={path}")
    return 0 if artifact["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
