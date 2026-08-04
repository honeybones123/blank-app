from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def main() -> int:
    import inputs_page

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"inputs_page_displayed_primary_truth_normalisation_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_displayed_primary_truth_normalisation_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals: dict[str, Any] = {
        "_design_guide_item_display_family": inputs_page._design_guide_item_display_family,
        "_design_guide_family_summary_util": inputs_page._design_guide_family_summary_util,
        "_design_guide_family_item_current_util": inputs_page._design_guide_family_item_current_util,
        "_design_guide_button_contract_enabled": inputs_page._design_guide_button_contract_enabled,
    }
    failures: list[str] = []
    cases: list[dict[str, Any]] = []

    def _restore() -> None:
        for name, value in originals.items():
            setattr(inputs_page, name, value)

    def _run_case(
        name: str,
        *,
        item: dict | None,
        payload: dict,
        resolved: dict,
        contract_enabled: bool,
        summary_util,
        fallback_util,
    ) -> dict[str, Any]:
        events: list[dict[str, Any]] = []

        def _display_family(item_arg):
            events.append({"event": "display_family", "id": dict(item_arg or {}).get("id")})
            return dict(item_arg or {}).get("family", "bending")

        def _summary_util(overview, family):
            events.append({"event": "summary_util", "family": family})
            return summary_util

        def _current_util(item_arg, family):
            events.append({"event": "current_util", "family": family})
            return fallback_util

        def _contract_enabled(contract):
            events.append({"event": "contract_enabled", "contract": dict(contract or {})})
            return bool(contract_enabled)

        try:
            inputs_page._design_guide_item_display_family = _display_family
            inputs_page._design_guide_family_summary_util = _summary_util
            inputs_page._design_guide_family_item_current_util = _current_util
            inputs_page._design_guide_button_contract_enabled = _contract_enabled
            result = inputs_page.render_design_guide_displayed_primary_truth_normalisation(
                displayed_primary_item=None if item is None else dict(item),
                displayed_primary_payload=dict(payload),
                displayed_primary_resolved=dict(resolved),
                displayed_primary_button_contract={"enabled": contract_enabled},
                overview={"overview": True},
            )
        finally:
            _restore()

        (
            displayed_primary_item,
            displayed_primary_truth,
            displayed_primary_family,
            displayed_primary_family_util,
            displayed_primary_truth_source,
            displayed_primary_source,
            displayed_primary_action_type,
        ) = result
        case = {
            "name": name,
            "events": events,
            "displayed_primary_item": displayed_primary_item,
            "displayed_primary_truth": displayed_primary_truth,
            "displayed_primary_family": displayed_primary_family,
            "displayed_primary_family_util": displayed_primary_family_util,
            "displayed_primary_truth_source": displayed_primary_truth_source,
            "displayed_primary_source": displayed_primary_source,
            "displayed_primary_action_type": displayed_primary_action_type,
        }
        cases.append(case)
        return case

    post_commit = _run_case(
        "post_commit_summary_update",
        item={
            "id": "primary",
            "family": "bending",
            "action_type": "apply",
            "display_truth": {"display_truth_source": "post_commit_truth"},
        },
        payload={},
        resolved={"source": "resolved_source"},
        contract_enabled=True,
        summary_util=0.87,
        fallback_util=None,
    )
    if post_commit["displayed_primary_truth"].get("displayed_util") != 0.87:
        failures.append(f"post_commit_displayed_util_mismatch:{post_commit}")
    if post_commit["displayed_primary_truth"].get("source_post_commit_util") != 0.87:
        failures.append(f"post_commit_source_post_commit_mismatch:{post_commit}")
    if post_commit["displayed_primary_item"].get("displayed_util") != 0.87:
        failures.append(f"post_commit_item_util_mismatch:{post_commit}")
    if post_commit["displayed_primary_source"] != "resolved_source":
        failures.append(f"post_commit_source_mismatch:{post_commit}")
    if post_commit["displayed_primary_action_type"] != "apply":
        failures.append(f"post_commit_action_type_mismatch:{post_commit}")

    candidate_preview = _run_case(
        "candidate_preview_enabled_preserved",
        item={
            "id": "primary",
            "family": "bending",
            "display_truth": {"display_truth_source": "candidate_preview", "displayed_util": 0.91},
        },
        payload={"resolved_candidate_source": "payload_resolved_source"},
        resolved={},
        contract_enabled=True,
        summary_util=0.80,
        fallback_util=None,
    )
    if candidate_preview["displayed_primary_truth"].get("displayed_util") != 0.91:
        failures.append(f"candidate_preview_overwritten:{candidate_preview}")
    if candidate_preview["displayed_primary_source"] != "payload_resolved_source":
        failures.append(f"candidate_preview_source_mismatch:{candidate_preview}")

    disabled_preview = _run_case(
        "candidate_preview_disabled_updates",
        item={
            "id": "primary",
            "family": "shear",
            "display_truth": {"display_truth_source": "candidate_preview", "displayed_util": 0.91},
        },
        payload={"source": "payload_source"},
        resolved={},
        contract_enabled=False,
        summary_util=0.82,
        fallback_util=None,
    )
    if disabled_preview["displayed_primary_truth"].get("displayed_util") != 0.82:
        failures.append(f"disabled_preview_not_updated:{disabled_preview}")
    if disabled_preview["displayed_primary_source"] != "payload_source":
        failures.append(f"disabled_preview_source_mismatch:{disabled_preview}")

    fallback = _run_case(
        "fallback_current_util",
        item={"id": "primary", "family": "bending", "source": "item_source", "display_truth": {}},
        payload={},
        resolved={},
        contract_enabled=True,
        summary_util=None,
        fallback_util=0.77,
    )
    if fallback["displayed_primary_family_util"] != 0.77:
        failures.append(f"fallback_util_mismatch:{fallback}")
    if fallback["displayed_primary_source"] != "item_source":
        failures.append(f"fallback_source_mismatch:{fallback}")
    if not any(event.get("event") == "current_util" for event in fallback["events"]):
        failures.append(f"fallback_current_util_not_called:{fallback['events']}")

    none_item = _run_case(
        "none_item",
        item=None,
        payload={},
        resolved={},
        contract_enabled=True,
        summary_util=None,
        fallback_util=None,
    )
    if none_item["displayed_primary_source"] is not None:
        failures.append(f"none_source_mismatch:{none_item}")
    if none_item["displayed_primary_action_type"] is not None:
        failures.append(f"none_action_type_mismatch:{none_item}")

    payload = {
        "verifier": "inputs_page_displayed_primary_truth_normalisation_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Displayed Primary Truth Normalisation Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                "## Evidence",
                "",
                *(
                    f"- `{case['name']}` source: `{case['displayed_primary_source']}`, util: `{case['displayed_primary_family_util']}`"
                    for case in cases
                ),
                "",
                "## Failures",
                "",
                *(f"- `{failure}`" for failure in failures),
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(payload["status"])
    print(f"json={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ";".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
