"""Contract check for the browser-live red-screen sentinel."""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification.browser_red_screen_sentinel import browser_red_screen_findings  # noqa: E402


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def main() -> int:
    cases = {
        "normal_pass_card": {
            "payload": {"text": "Design Guide PASS Design accepted - target band achieved"},
            "expected_reasons": [],
        },
        "name_error_traceback": {
            "payload": {"text": "NameError: name '_cleanup_candidate_rank' is not defined\nTraceback:"},
            "expected_reasons": ["python_traceback", "name_error"],
        },
        "duplicate_streamlit_key": {
            "payload": {"text": "streamlit.errors.StreamlitDuplicateElementKey: multiple elements with the same key"},
            "expected_reasons": ["streamlit_duplicate_key", "streamlit_runtime_error"],
        },
        "family_contract_violation": {
            "payload": {"text": "Design Guide family contract violation Publication blocked by family contract."},
            "expected_reasons": ["family_contract_violation_card"],
        },
        "stale_primary_payload": {
            "payload": {"text": "One-click found a candidate, but it was blocked: stale_primary_design_guide_payload."},
            "expected_reasons": ["stale_primary_payload_blocker"],
        },
    }
    rows = []
    for case_id, case in cases.items():
        findings = browser_red_screen_findings(case["payload"])
        reasons = sorted({finding["reason"] for finding in findings})
        expected = sorted(case["expected_reasons"])
        rows.append(
            {
                "case_id": case_id,
                "expected_reasons": expected,
                "actual_reasons": reasons,
                "passed": reasons == expected,
                "findings": findings,
            }
        )
    payload = {
        "schema": "browser_red_screen_sentinel_contract.v1",
        "status": "PASS" if all(row["passed"] for row in rows) else "FAIL",
        "timestamp": _stamp(),
        "cases": rows,
        "product_behaviour_changed": False,
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_DIR / f"browser_red_screen_sentinel_contract_{payload['timestamp']}.json"
    report_path = AUDIT_DIR / f"browser_red_screen_sentinel_contract_{payload['timestamp']}.md"
    payload["artifact"] = str(json_path)
    payload["report"] = str(report_path)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Browser Red-Screen Sentinel Contract",
                "",
                f"Status: `{payload['status']}`",
                "",
                *[
                    f"- `{row['case_id']}`: `{row['passed']}` reasons=`{row['actual_reasons']}`"
                    for row in rows
                ],
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"browser_red_screen_sentinel_contract {payload['status']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
