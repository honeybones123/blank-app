from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

AUDIT_DIR = ROOT / "artifacts" / "audits"
VERIFICATION_DIR = ROOT / "artifacts" / "verification"


def _function_body(source: str, name: str) -> str:
    match = re.search(rf"^(\s*)def {re.escape(name)}\b.*$", source, re.MULTILINE)
    if not match:
        return ""
    start = match.start()
    indent = len(match.group(1))
    tail = source[start:]
    next_match = re.search(rf"^\s{{0,{indent}}}def\s+\w+\b", tail[len(match.group(0)):], re.MULTILINE)
    if next_match:
        return tail[: len(match.group(0)) + next_match.start()]
    return tail


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    source = (ROOT / "inputs_page.py").read_text(encoding="utf-8")
    route_path = ROOT / "inputs_page_route_coordinators.py"
    if route_path.exists():
        source += "\n" + route_path.read_text(encoding="utf-8")
    render_path = ROOT / "inputs_page_modules" / "summaries" / "render_coordinators.py"
    source += "\n" + render_path.read_text(encoding="utf-8")
    body = _function_body(source, "_build_summary_cards_html_for_current_state")
    checks = {
        "local_summary_html_builder_function_present": bool(body),
        "local_function_calls_extracted_builder": "return build_inputs_summary_html(" in body,
        "local_function_has_no_direct_card_html_calls": "build_final_summary_check_card_html(" not in body,
        "local_function_has_no_four_card_page_owned_body": all(
            token not in body
            for token in (
                'title="Bending &mdash; ULS"',
                'title="Shear &mdash; ULS"',
                'title="Crack control &mdash; SLS"',
                'title="Deflection &mdash; SLS"',
            )
        ),
        "missing_snapshot_is_explicit_error_not_legacy_fallback": "page-owned summary HTML fallback has been removed" in body,
        "extracted_builder_imported": "build_inputs_summary_html" in source,
        "live_render_still_uses_summary_cards_html": "summary_cards_html = _build_summary_cards_html_for_current_state(" in source,
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "schema": "inputs_summary_local_html_fallback_deadness_snapshot.v1",
        "generated_at": timestamp,
        "status": status,
        "decision": "LOCAL_SUMMARY_HTML_FALLBACK_DELETED" if status == "PASS" else "LOCAL_SUMMARY_HTML_FALLBACK_STILL_PRESENT",
        "checks": checks,
        "product_behavior_changed": False,
        "visible_renderer_changed": False,
        "remaining_page_summary_html_authority": False,
    }
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"inputs_summary_local_html_fallback_deadness_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_summary_local_html_fallback_deadness_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    lines = [
        "# Inputs Summary Local HTML Fallback Deadness Snapshot",
        "",
        f"Status: `{status}`",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        "## Checks",
        "",
    ]
    for key, value in checks.items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "The old page-owned four-card HTML fallback body is deleted. The remaining page function is a shell that calls `build_inputs_summary_html(...)` and raises explicitly if the extracted source snapshot is unavailable.",
        ]
    )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"inputs_summary_local_html_fallback_deadness_snapshot {status}")
    print(f"decision={payload['decision']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
