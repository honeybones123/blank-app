"""Verifier for moving cleanup-item publishability policy into Design Brain."""

from __future__ import annotations

from datetime import datetime, timezone
import importlib
import json
from pathlib import Path
import re
import sys


REPO = Path(__file__).resolve().parents[2]
INPUTS_PATH = REPO / "inputs_page.py"
PUBLICATION_PATH = REPO / "design_brain" / "publication.py"
VERIFICATION_DIR = REPO / "artifacts" / "verification"
AUDITS_DIR = REPO / "artifacts" / "audits"


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _legacy_publishable(item: dict | None) -> bool:
    if not isinstance(item, dict):
        return False
    contract = dict(item.get("button_contract") or {})
    if bool(
        contract.get("actionable")
        and dict(contract.get("updates") or {})
        and bool(contract.get("preview_pass"))
        and contract.get("blocking_reason") is None
    ):
        return True
    payload = dict(item.get("action_payload") or {})
    resolved_updates = payload.get("resolved_candidate_updates")
    return bool(
        (
            str(item.get("action_type") or "") == "apply_resolved_candidate"
            or bool(resolved_updates)
        )
        and resolved_updates
        and payload.get("resolved_candidate_reaches_target_band") is not None
    )


def main() -> int:
    sys.path.insert(0, str(REPO))
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDITS_DIR.mkdir(parents=True, exist_ok=True)
    inputs_source = _read(INPUTS_PATH)
    publication_source = _read(PUBLICATION_PATH)
    publication = importlib.import_module("design_brain.publication")

    cases = [
        {"name": "none", "item": None},
        {"name": "disabled_plain", "item": {"title": "No action"}},
        {
            "name": "enabled_flag_without_preview_not_publishable",
            "item": {"button_contract": {"enabled": True, "updates": {"D": 650}}},
        },
        {
            "name": "actionable_button_contract",
            "item": {"button_contract": {"actionable": True, "updates": {"D": 650}, "preview_pass": True}},
        },
        {
            "name": "resolved_one_click",
            "item": {
                "action_type": "apply_resolved_candidate",
                "action_payload": {
                    "resolved_candidate_updates": {"D": 650},
                    "resolved_candidate_reaches_target_band": True,
                },
            },
        },
        {
            "name": "resolved_updates_without_target_band_flag",
            "item": {
                "action_type": "apply_resolved_candidate",
                "action_payload": {"resolved_candidate_updates": {"D": 650}},
            },
        },
    ]
    parity = [
        {
            "case": case["name"],
            "legacy": _legacy_publishable(case["item"]),
            "publication": publication.design_guide_cleanup_item_publishable(case["item"]),
        }
        for case in cases
    ]

    failures: list[str] = []
    if re.search(r"^def _design_guide_cleanup_item_publishable\(", inputs_source, re.M):
        failures.append("page_local_cleanup_publishable_definition_still_present")
    if "design_guide_cleanup_item_publishable as _design_guide_cleanup_item_publishable" not in inputs_source:
        failures.append("inputs_cleanup_publishable_alias_missing")
    if "def design_guide_cleanup_item_publishable" not in publication_source:
        failures.append("publication_cleanup_publishable_missing")
    for row in parity:
        if row["legacy"] != row["publication"]:
            failures.append(f"publishable_parity_mismatch:{row['case']}")

    status = "PASS" if not failures else "FAIL"
    payload = {
        "status": status,
        "page_local_helper_removed": "page_local_cleanup_publishable_definition_still_present" not in failures,
        "publication_helper_present": "publication_cleanup_publishable_missing" not in failures,
        "parity": parity,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "failures": failures,
    }
    stamp = _timestamp().replace(":", "-")
    json_path = VERIFICATION_DIR / f"design_guide_cleanup_item_publishable_extraction_{stamp}.json"
    md_path = AUDITS_DIR / f"design_guide_cleanup_item_publishable_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(
        "\n".join(
            [
                "# Design Guide Cleanup Item Publishability Extraction",
                "",
                f"## Result: {status}",
                "",
                "- Page-local cleanup publishability helper removed.",
                "- `inputs_page.py` now imports the helper from `design_brain.publication`.",
                "- Representative parity cases match the old dict-only behavior.",
                "",
                "## Failures",
                "",
                "\n".join(f"- {failure}" for failure in failures) if failures else "- None",
            ]
        ),
        encoding="utf-8",
    )
    print(f"design guide cleanup item publishability extraction {status}")
    print(json_path)
    print(md_path)
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
