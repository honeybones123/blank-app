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
    json_path = ARTIFACT_DIR / f"inputs_page_heading_section_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_heading_section_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    events: list[str] = []
    originals: dict[str, Any] = {
        "_render_design_guide_heading_if_needed": inputs_page._render_design_guide_heading_if_needed,
        "_render_auto_design_main_panel_status": inputs_page._render_auto_design_main_panel_status,
    }
    try:
        inputs_page._render_design_guide_heading_if_needed = lambda: events.append("heading")
        inputs_page._render_auto_design_main_panel_status = lambda: events.append("status")
        inputs_page.render_design_guide_heading_section(
            stage=lambda label: events.append(f"stage:{label}")
        )
    finally:
        for name, value in originals.items():
            setattr(inputs_page, name, value)

    expected = ["stage:before_heading", "heading", "status", "stage:after_heading"]
    failures = [] if events == expected else [f"order_mismatch:expected={expected}:actual={events}"]
    payload = {
        "verifier": "inputs_page_heading_section_verifier",
        "status": "PASS" if not failures else "FAIL",
        "events": events,
        "expected": expected,
        "failures": failures,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Heading Section Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                "## Evidence",
                "",
                f"- events: `{events}`",
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
        print("failures=" + ",".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
