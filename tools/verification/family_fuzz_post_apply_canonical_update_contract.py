"""Lock canonical post-Apply matching without trusting compatibility aliases."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification.run_family_10_fuzz_audit import (  # noqa: E402
    _canonical_post_apply_update_expectations,
    _post_apply_update_match_probe,
)


def main() -> int:
    expanded_updates = {
        "bot1_count": 4,
        "bot_row_1_bars": 4,
        "bot1_spacing": 0,
        "bot_row_1_spacing": 0,
        "db_bot_1": 20,
        "bot_row_1_dia": 20,
        "bot2_count": 0,
        "bot_row_2_bars": 0,
        "db_bot_2": 12,
        "bot_row_2_dia": 12,
        "bot2_spacing": 0,
        "bot_row_2_spacing": 0,
        "bot_row_count": 1,
        "lig_d": 0,
        "lig_legs": 0,
        "s_lig": 0,
    }
    canonical = _canonical_post_apply_update_expectations(expanded_updates)
    normalized_browser_state = {
        "browser_shared_probe": {
            "bot1_count": 4,
            "bot1_spacing": 200,
            "db_bot_2": 0,
            "bot_row_1_bars": 4,
            "bot_row_1_spacing": 0,
            "bot_row_1_dia": 20,
            "bot_row_2_bars": 0,
            "bot_row_2_dia": 0,
            "bot_row_2_spacing": 0,
            "bot_row_count": 1,
            "lig_d": 0,
            "lig_legs": 0,
            "s_lig": 200,
        },
        "summary_state_probe": {
            "bot1_count": 4,
            "bot1_spacing": 200,
            "db_bot_2": 0,
            "bot_row_1_bars": 4,
            "bot_row_1_spacing": 0,
            "bot_row_1_dia": 20,
            "bot_row_2_bars": 0,
            "bot_row_2_dia": 0,
            "bot_row_2_spacing": 0,
            "bot_row_count": 1,
            "lig_d": 0,
            "lig_legs": 0,
            "s_lig": 200,
        },
    }
    normalized_probe = _post_apply_update_match_probe(
        normalized_browser_state,
        canonical,
    )
    bad_state = json.loads(json.dumps(normalized_browser_state))
    bad_state["browser_shared_probe"]["bot_row_1_bars"] = 5
    bad_probe = _post_apply_update_match_probe(bad_state, canonical)

    checks = {
        "legacy_count_alias_removed": "bot1_count" not in canonical,
        "legacy_spacing_alias_removed": "bot1_spacing" not in canonical,
        "inactive_row_diameter_not_material": "bot_row_2_dia" not in canonical,
        "inactive_row_spacing_not_material": "bot_row_2_spacing" not in canonical,
        "inactive_link_spacing_not_material": "s_lig" not in canonical,
        "inactive_link_identity_remains_material": (
            canonical.get("lig_d") == 0
            and canonical.get("lig_legs") == 0
        ),
        "inactive_row_count_remains_material": canonical.get("bot_row_2_bars") == 0,
        "canonical_active_row_fields_remain_material": all(
            key in canonical
            for key in (
                "bot_row_1_bars",
                "bot_row_1_dia",
                "bot_row_1_spacing",
                "bot_row_count",
            )
        ),
        "normalized_compatibility_aliases_do_not_fail": (
            normalized_probe.get("all_updates_published") is True
            and normalized_probe.get("all_published_sources_match") is True
        ),
        "canonical_mismatch_still_fails": (
            bad_probe.get("all_published_sources_match") is False
        ),
    }
    artifact = {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "canonical_updates": canonical,
        "normalized_probe": normalized_probe,
        "canonical_mismatch_probe": bad_probe,
    }
    artifact_path = (
        ROOT
        / "artifacts"
        / "verification"
        / "family_fuzz_post_apply_canonical_update_contract.json"
    )
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(
        json.dumps(artifact, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(
        f"{artifact['status']}: canonical post-Apply update proof "
        f"artifact={artifact_path}"
    )
    return 0 if artifact["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
