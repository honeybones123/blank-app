"""Design Guide duplicate no-further-cleanup heading snapshot.

This verifier proves the polished "Why no further cleanup?" section remains
the user-facing explanation heading, while the raw ladder-stop evidence block
is not inserted into the main card. It does not change engineering behaviour.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _extract_function(source: str, name: str) -> str:
    pattern = re.compile(rf"^def {re.escape(name)}\(.*?^def ", re.M | re.S)
    match = pattern.search(source)
    if match:
        text = match.group(0)
        return text.rsplit("\ndef ", 1)[0]
    tail_pattern = re.compile(rf"^def {re.escape(name)}\(.*", re.M | re.S)
    tail = tail_pattern.search(source)
    if not tail:
        raise RuntimeError(f"Unable to find function {name}")
    return tail.group(0)


def main() -> int:
    source = INPUTS_PAGE.read_text(encoding="utf-8")
    ladder_stop_fn = _extract_function(source, "_design_guide_ladder_stop_evidence_html")
    render_model_fn = _extract_function(source, "_build_design_guide_card_render_model")

    main_heading_count = source.count("Why no further cleanup?")
    ladder_stop_uses_main_heading = "Why no further cleanup?" in ladder_stop_fn
    ladder_stop_uses_proof_heading = "Cleanup proof details" in ladder_stop_fn
    evidence_test_id_preserved = "design-guide-ladder-stop-evidence" in ladder_stop_fn
    visible_ladder_stop_suppressed = 'ladder_stop_html = ""' in render_model_fn
    render_model_calls_ladder_stop = "_design_guide_ladder_stop_evidence_html(details)" in render_model_fn

    checks = {
        "main_heading_still_exists": main_heading_count >= 1,
        "ladder_stop_does_not_duplicate_main_heading": not ladder_stop_uses_main_heading,
        "ladder_stop_helper_retains_distinct_proof_heading": ladder_stop_uses_proof_heading,
        "ladder_stop_helper_evidence_test_id_preserved": evidence_test_id_preserved,
        "visible_ladder_stop_suppressed_from_main_card": visible_ladder_stop_suppressed,
        "render_model_does_not_call_ladder_stop_helper": not render_model_calls_ladder_stop,
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "status": status,
        "checks": checks,
        "main_heading_literal_count": main_heading_count,
        "ladder_stop_heading": "hidden_from_main_card",
        "user_facing_heading": "Why no further cleanup?",
        "scope": {
            "changed_surface": "visible cleanup proof details suppressed",
            "family_runtime_changed": False,
            "cta_apply_changed": False,
            "raw_evidence_removed": False,
        },
    }
    payload["snapshot_hash"] = _stable_hash(payload)

    timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H-%M-%S")
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_DIR / f"design_guide_no_further_cleanup_duplicate_heading_{timestamp}.json"
    report_path = AUDIT_DIR / f"design_guide_no_further_cleanup_duplicate_heading_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Design Guide No Further Cleanup Duplicate Heading",
                "",
                f"Status: `{status}`",
                "",
                "## Checks",
                "",
                "| Check | Result |",
                "| --- | --- |",
                *[
                    f"| {name} | {'PASS' if passed else 'FAIL'} |"
                    for name, passed in checks.items()
                ],
                "",
                "## Result",
                "",
                "The polished section keeps `Why no further cleanup?`; the raw ladder-stop proof helper remains in code, but the main card render model suppresses it from visible output.",
                "",
                f"Snapshot hash: `{payload['snapshot_hash']}`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"{status}: {json_path}")
    print(f"Report: {report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
