"""Lock SERVICEABILITY_GOVERNS live browser-family and CTA surface coverage."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def main() -> int:
    runner_path = ROOT / "tools" / "verification" / "run_family_10_fuzz_audit.py"
    regression_path = ROOT / "tools" / "verification" / "families" / "serviceability_governs_locked_regression.py"
    preview_contract_path = ROOT / "inputs_page_modules" / "design_guide" / "preview_contract.py"
    runner_source = runner_path.read_text(encoding="utf-8", errors="ignore")
    regression_source = regression_path.read_text(encoding="utf-8", errors="ignore")
    preview_contract_source = preview_contract_path.read_text(encoding="utf-8", errors="ignore")
    failures: list[str] = []

    required_runner_tokens = {
        "browser_family_identity_contract": "def _browser_family_identity_contract(",
        "family_mismatch_blocks_live_lock": "live_browser_family_mismatch:",
        "serviceability_accepts_optimisation_stop_alias": "SERVICEABILITY_GOVERNS_OPTIMISATION_STOP",
        "visible_card_text_family_fallback": "visible_inferred_family_id",
        "serviceability_not_action_required": '"SERVICEABILITY_GOVERNS",\n}',
        "serviceability_expected_no_family_cta": "serviceability blocked/exact-stop publication with no family-owned apply CTA",
    }
    for name, token in required_runner_tokens.items():
        if token not in runner_source:
            failures.append(f"{name}_missing")
    if '"SERVICEABILITY_GOVERNS",' in runner_source[
        runner_source.find("LIVE_ACTION_REQUIRED_FAMILIES") : runner_source.find("LIVE_ACTION_BUTTON_TEXTS")
    ]:
        failures.append("serviceability_must_not_be_in_live_action_required_families")
    if "serviceability_governs_live_surface_contract.py" not in regression_source:
        failures.append("serviceability_locked_regression_does_not_include_live_surface_contract")
    if 'if fail_statuses:\n        return False, expected_util, "candidate_preview_has_fail_status"' not in preview_contract_source:
        failures.append("one_click_preview_contract_must_block_remaining_fail_statuses")
    if "candidate_preview_not_compliant" not in preview_contract_source:
        failures.append("one_click_preview_contract_must_block_non_compliant_preview")

    payload = {
        "schema": "serviceability_governs.live_surface_contract.v1",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "locked_gap": (
            "SERVICEABILITY_GOVERNS live fuzz must prove the rendered browser family "
            "is serviceability and must not require a family-owned Apply CTA."
        ),
        "sources": [
            str(runner_path.relative_to(ROOT)),
            str(regression_path.relative_to(ROOT)),
            str(preview_contract_path.relative_to(ROOT)),
        ],
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"serviceability_governs_live_surface_contract_{stamp}.json"
    report_path = AUDIT_DIR / f"serviceability_governs_live_surface_contract_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# SERVICEABILITY_GOVERNS Live Surface Contract",
                "",
                f"Status: `{payload['status']}`",
                "",
                "## Locked Gap",
                "",
                "- The live browser card family must match `SERVICEABILITY_GOVERNS` before serviceability fuzz can pass.",
                "- Serviceability remains a blocked/exact-stop surface unless the family contract publishes a valid executor-backed CTA.",
                "- One-click preview contracts must not enable a CTA when any required check remains failed.",
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
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
