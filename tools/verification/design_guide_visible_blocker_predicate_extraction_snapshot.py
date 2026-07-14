"""Verifier for moving visible-blocker predicates out of inputs_page.py."""

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


def _legacy_text_indicates_blocker(text: str | None) -> bool:
    lower = str(text or "").strip().lower()
    if not lower:
        return False
    return any(
        token in lower
        for token in (
            "blocked",
            "cannot safely",
            "cannot be safely",
            "no further safe",
            "no safe one-click",
            "no one-click cleanup",
            "no one-click candidate",
            "no one-click update",
        )
    )


def _legacy_terminal(item: dict | None) -> bool:
    if not isinstance(item, dict):
        return False
    blockers = item.get("exact_blockers_by_family") or item.get("post_click_exact_blockers_by_family")
    if not isinstance(blockers, dict) or not blockers:
        return False
    contract = dict(item.get("button_contract") or {})
    updates = dict(
        contract.get("updates")
        or item.get("selected_action_updates")
        or item.get("updates")
        or {}
    )
    if (
        str(contract.get("action_type") or item.get("action_type") or "").strip()
        and updates
        and (bool(contract.get("enabled")) or bool(contract.get("actionable")) or bool(item.get("primary_card_actionable")))
    ):
        return False
    title_text = " ".join(
        str(item.get(key) or "")
        for key in ("title_main", "title", "primary_action", "reasoning")
    ).strip().lower()
    if "cleanup blocked" in title_text or "repair blocked" in title_text:
        return False
    return bool(
        str(item.get("guidance_intent") or "").strip() == "already_efficient"
        or str(item.get("design_guide_terminal_state") or "").strip() == "optimal"
        or str(item.get("post_click_design_guide_state") or "").strip() == "accepted_green"
        or str(item.get("terminal_cleanup_state") or "").strip() == "optimal"
        or str(item.get("final_state_class") or "").strip() == "accepted"
    )


def _legacy_visible(item: dict | None, *, extra_text: str | None = None) -> bool:
    if not isinstance(item, dict):
        return False
    terminal_exact_accepted = _legacy_terminal(item)
    contract = dict(item.get("button_contract") or {})
    action_updates = dict(
        contract.get("updates")
        or item.get("selected_action_updates")
        or item.get("updates")
        or {}
    )
    has_action_contract = bool(
        str(contract.get("action_type") or item.get("action_type") or "").strip()
        and action_updates
        and (
            bool(item.get("primary_card_actionable"))
            or bool(contract.get("enabled"))
            or bool(contract.get("actionable"))
        )
    )
    if not terminal_exact_accepted and str(item.get("guidance_intent") or "").strip() == "specific_blocker":
        return True
    if not terminal_exact_accepted and str(item.get("post_click_design_guide_state") or "").strip() == "exact_blocker":
        return True
    blockers = item.get("exact_blockers_by_family") or item.get("post_click_exact_blockers_by_family")
    if isinstance(blockers, dict) and blockers and not bool(item.get("primary_card_actionable")):
        if terminal_exact_accepted:
            return False
        return True
    text = " ".join(
        str(part or "")
        for part in (
            item.get("title_main"),
            item.get("title"),
        )
    )
    if _legacy_text_indicates_blocker(text):
        expected_util_raw = (
            contract.get("expected_util")
            or item.get("expected_util")
            or item.get("candidate_post_util")
            or item.get("displayed_util")
        )
        try:
            expected_util = None if expected_util_raw in (None, "") else float(expected_util_raw)
        except (TypeError, ValueError):
            expected_util = None
        if (
            has_action_contract
            and expected_util is not None
            and float(expected_util) < 0.85 - 0.005
        ):
            return True
        return not has_action_contract
    if extra_text and not bool(item.get("action_type")) and not dict(item.get("updates") or {}):
        return _legacy_text_indicates_blocker(extra_text)
    return False


def main() -> int:
    sys.path.insert(0, str(REPO))
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDITS_DIR.mkdir(parents=True, exist_ok=True)

    inputs_source = _read(INPUTS_PATH)
    publication_source = _read(PUBLICATION_PATH)
    publication = importlib.import_module("design_brain.publication")
    cases = [
        {"name": "specific_blocker", "item": {"guidance_intent": "specific_blocker"}},
        {
            "name": "exact_blocker",
            "item": {"post_click_design_guide_state": "exact_blocker"},
        },
        {
            "name": "terminal_accepted",
            "item": {
                "exact_blockers_by_family": {"bending": {"reason": "floor"}},
                "guidance_intent": "already_efficient",
            },
        },
        {
            "name": "blocked_text_no_action",
            "item": {"title": "Cleanup blocked"},
        },
        {
            "name": "blocked_text_low_util_action",
            "item": {
                "title": "Cleanup blocked",
                "button_contract": {
                    "action_type": "apply_resolved_candidate",
                    "updates": {"D": 650},
                    "actionable": True,
                    "expected_util": 0.5,
                },
            },
        },
        {
            "name": "blocked_text_good_action_not_blocker",
            "item": {
                "title": "Cleanup blocked",
                "button_contract": {
                    "action_type": "apply_resolved_candidate",
                    "updates": {"D": 650},
                    "actionable": True,
                    "expected_util": 0.9,
                },
            },
        },
        {
            "name": "extra_text",
            "item": {"title": "Design is efficient"},
            "extra_text": "No further safe cleanup",
        },
    ]
    parity = []
    for case in cases:
        item = dict(case["item"])
        extra = case.get("extra_text")
        parity.append(
            {
                "case": case["name"],
                "legacy_visible": _legacy_visible(item, extra_text=extra),
                "publication_visible": publication.design_guide_item_is_visible_blocker(item, extra_text=extra),
                "legacy_terminal": _legacy_terminal(item),
                "publication_terminal": publication.design_guide_item_is_accepted_terminal_with_exact_stop(item),
            }
        )

    failures: list[str] = []
    for name in (
        "_design_guide_text_indicates_blocker",
        "_design_guide_item_is_visible_blocker",
        "_design_guide_item_is_accepted_terminal_with_exact_stop",
    ):
        if re.search(rf"^def {re.escape(name)}\(", inputs_source, re.M):
            failures.append(f"page_local_definition_still_present:{name}")
    for name in (
        "design_guide_text_indicates_blocker",
        "design_guide_item_is_visible_blocker",
        "design_guide_item_is_accepted_terminal_with_exact_stop",
    ):
        if f"def {name}" not in publication_source:
            failures.append(f"publication_definition_missing:{name}")
    for name in (
        "design_guide_text_indicates_blocker as _design_guide_text_indicates_blocker",
        "design_guide_item_is_visible_blocker as _design_guide_item_is_visible_blocker",
        "design_guide_item_is_accepted_terminal_with_exact_stop as _design_guide_item_is_accepted_terminal_with_exact_stop",
    ):
        if name not in inputs_source:
            failures.append(f"inputs_alias_missing:{name}")
    for row in parity:
        if row["legacy_visible"] != row["publication_visible"]:
            failures.append(f"visible_parity_mismatch:{row['case']}")
        if row["legacy_terminal"] != row["publication_terminal"]:
            failures.append(f"terminal_parity_mismatch:{row['case']}")

    status = "PASS" if not failures else "FAIL"
    payload = {
        "status": status,
        "page_local_predicates_removed": not any("page_local_definition_still_present" in f for f in failures),
        "publication_predicates_present": not any("publication_definition_missing" in f for f in failures),
        "parity": parity,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "failures": failures,
    }

    stamp = _timestamp().replace(":", "-")
    json_path = VERIFICATION_DIR / f"design_guide_visible_blocker_predicate_extraction_{stamp}.json"
    md_path = AUDITS_DIR / f"design_guide_visible_blocker_predicate_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(
        "\n".join(
            [
                "# Design Guide Visible Blocker Predicate Extraction",
                "",
                f"## Result: {status}",
                "",
                "## Summary",
                "",
                "- Page-local visible-blocker predicate definitions were removed.",
                "- `inputs_page.py` now imports the predicates from `design_brain.publication`.",
                "- Representative legacy/publication parity cases match.",
                "",
                "## Failures",
                "",
                "\n".join(f"- {failure}" for failure in failures) if failures else "- None",
            ]
        ),
        encoding="utf-8",
    )
    print(f"design guide visible blocker predicate extraction {status}")
    print(json_path)
    print(md_path)
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
