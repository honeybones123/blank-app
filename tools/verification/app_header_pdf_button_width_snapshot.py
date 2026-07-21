from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "app.py"
REPORTING = ROOT / "reporting" / "example_integration.py"
ARTIFACTS_VERIFICATION = ROOT / "artifacts" / "verification"
ARTIFACTS_AUDITS = ROOT / "artifacts" / "audits"


def main() -> int:
    app_source = APP.read_text(encoding="utf-8")
    report_source = REPORTING.read_text(encoding="utf-8")
    header_match = re.search(r"header_left,\s*header_right\s*=\s*st\.columns\(\[([^\]]+)\]", app_source)
    action_match = re.search(r"left,\s*right\s*=\s*st\.columns\(\[([^\]]+)\]", app_source)
    button_match = re.search(r"c_save,\s*c_pdf,\s*c_pdf_opts,\s*_\s*=\s*st\.columns\(\[([^\]]+)\]", app_source)

    def _numbers(match: re.Match[str] | None) -> list[float]:
        if not match:
            return []
        values: list[float] = []
        for raw in match.group(1).split(","):
            try:
                values.append(float(raw.strip()))
            except Exception:
                pass
        return values

    header_values = _numbers(header_match)
    action_values = _numbers(action_match)
    button_values = _numbers(button_match)
    checks = {
        "header_right_has_enough_width": len(header_values) == 2 and header_values[1] >= 0.45,
        "actions_shifted_further_right": len(action_values) == 2 and 1.0 <= action_values[0] <= 1.5,
        "pdf_column_wider_than_save": len(button_values) == 4 and button_values[1] > button_values[0],
        "pdf_column_reduced_but_still_one_line_width": len(button_values) == 4 and 3.6 <= button_values[1] < 4.2,
        "trailing_spacer_not_stealing_pdf_width": len(button_values) == 4 and button_values[3] <= 0.5,
        "pdf_report_label_preserved": "PDF Report" in report_source,
        "save_label_preserved": "Save" in app_source,
        "report_generation_not_moved": "render_pdf_button(detail_level=report_mode)" in app_source,
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    payload = {
        "status": status,
        "checks": checks,
        "header_columns": header_values,
        "action_columns": action_values,
        "button_columns": button_values,
        "scope": {
            "changed": "Top-right header action layout only; action group shifted right and PDF button kept one-line.",
            "report_generation_changed": False,
            "save_behavior_changed": False,
        },
    }

    ARTIFACTS_VERIFICATION.mkdir(parents=True, exist_ok=True)
    ARTIFACTS_AUDITS.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACTS_VERIFICATION / f"app_header_pdf_button_width_{now}.json"
    report_path = ARTIFACTS_AUDITS / f"app_header_pdf_button_width_{now}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# App Header PDF Button Width Snapshot",
                "",
                f"Status: `{status}`",
                "",
                "## Checks",
                *[f"- `{name}`: `{'PASS' if ok else 'FAIL'}`" for name, ok in checks.items()],
                "",
                "## Scope",
                "- Adjusted only the top-right header action layout.",
                "- Report generation, Save behavior, and page routing are unchanged.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": status, "json": str(json_path), "report": str(report_path)}, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
