"""Audit deadness of the old final-visible binding helper body.

The product callsites have moved to controller/final-publication adapters. This
snapshot distinguishes product deadness from verifier-only consumers before the
old helper body is deleted.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
TOOLS_DIR = ROOT / "tools" / "verification"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports"

HELPER_DEF = "def _publish_final_visible_design_guide_contract_binding("
HELPER_CALL = "_publish_final_visible_design_guide_contract_binding("
DIRECT_VERIFIER_CALL = "module._publish_final_visible_design_guide_contract_binding("


def _line_for_offset(source: str, offset: int) -> int:
    return source.count("\n", 0, max(0, offset)) + 1


def _input_product_calls(source: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for match in re.finditer(re.escape(HELPER_CALL), source):
        line = _line_for_offset(source, match.start())
        line_text = source.splitlines()[line - 1].strip()
        if line_text.startswith("def "):
            continue
        rows.append({"file": "inputs_page.py", "line": line, "source_line": line_text})
    return rows


def _verifier_consumers() -> tuple[list[dict[str, object]], int]:
    direct: list[dict[str, object]] = []
    string_reference_count = 0
    for path in sorted(TOOLS_DIR.glob("*.py")):
        text = path.read_text(encoding="utf-8", errors="replace")
        if HELPER_CALL not in text:
            continue
        for match in re.finditer(re.escape(HELPER_CALL), text):
            line = _line_for_offset(text, match.start())
            line_text = text.splitlines()[line - 1].strip()
            if DIRECT_VERIFIER_CALL in line_text and not line_text.startswith(("DIRECT_VERIFIER_CALL", "#", '"', "'")):
                direct.append(
                    {
                        "file": str(path.relative_to(ROOT)),
                        "line": line,
                        "source_line": line_text,
                        "consumer_type": "direct_helper_call",
                    }
                )
            else:
                string_reference_count += 1
    return direct, string_reference_count


def _build_payload() -> dict[str, object]:
    source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    helper_body_present = HELPER_DEF in source
    product_calls = _input_product_calls(source)
    direct_verifier_consumers, string_reference_count = _verifier_consumers()
    failures: list[str] = []
    if product_calls:
        failures.append("product_calls_still_present")
    helper_deleted = not helper_body_present
    safe_to_delete_now = bool(helper_body_present and not product_calls and not direct_verifier_consumers)
    deletion_locked = bool(helper_deleted and not product_calls and not direct_verifier_consumers)
    return {
        "schema": "design_guide_final_visible_binding_helper_deadness.v1",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S"),
        "status": "PASS" if not failures else "FAIL",
        "helper_body_present": helper_body_present,
        "helper_body_deleted": helper_deleted,
        "product_call_count": len(product_calls),
        "product_calls": product_calls,
        "direct_verifier_consumer_count": len(direct_verifier_consumers),
        "direct_verifier_consumers": direct_verifier_consumers,
        "string_reference_count": string_reference_count,
        "safe_to_delete_helper_now": safe_to_delete_now,
        "deletion_locked": deletion_locked,
        "next_safe_step": (
            "delete helper body"
            if safe_to_delete_now
            else (
                "helper body deleted; keep zero-count lock"
                if deletion_locked
                else "migrate direct verifier consumers, then delete helper body"
            )
        ),
        "product_behavior_changed": False,
        "failures": failures,
    }


def _write(payload: dict[str, object]) -> tuple[Path, Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = str(payload["generated_at"])
    json_path = ARTIFACT_DIR / f"design_guide_final_visible_binding_helper_deadness_{stamp}.json"
    audit_path = AUDIT_DIR / f"design_guide_final_visible_binding_helper_deadness_{stamp}.md"
    report_path = REPORT_DIR / f"design_brain_physical_extraction_final_visible_binding_helper_deadness_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# Final Visible Binding Helper Deadness",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Executive Summary",
        f"- Helper body present: `{payload['helper_body_present']}`",
        f"- Helper body deleted: `{payload['helper_body_deleted']}`",
        f"- Product call count: `{payload['product_call_count']}`",
        f"- Direct verifier consumer count: `{payload['direct_verifier_consumer_count']}`",
        f"- String/reference-only verifier mentions: `{payload['string_reference_count']}`",
        f"- Safe to delete helper now: `{payload['safe_to_delete_helper_now']}`",
        f"- Deletion locked: `{payload['deletion_locked']}`",
        f"- Next safe step: `{payload['next_safe_step']}`",
        "",
        "## Direct Verifier Consumers",
    ]
    consumers = list(payload.get("direct_verifier_consumers") or [])
    if consumers:
        for row in consumers:
            lines.append(f"- `{row['file']}:{row['line']}` {row['consumer_type']}")
    else:
        lines.append("- None")
    lines.extend(["", "## Product Calls", ""])
    calls = list(payload.get("product_calls") or [])
    if calls:
        for row in calls:
            lines.append(f"- `{row['file']}:{row['line']}` {row['source_line']}")
    else:
        lines.append("- None")
    lines.extend(["", "## Failures", ""])
    failures = list(payload.get("failures") or [])
    if failures:
        lines.extend(f"- `{failure}`" for failure in failures)
    else:
        lines.append("- None")
    text = "\n".join(lines) + "\n"
    audit_path.write_text(text, encoding="utf-8")
    report_path.write_text(text, encoding="utf-8")
    return json_path, audit_path, report_path


def main() -> int:
    payload = _build_payload()
    json_path, audit_path, report_path = _write(payload)
    print(f"design_guide_final_visible_binding_helper_deadness {payload['status']}")
    print(f"json={json_path}")
    print(f"audit={audit_path}")
    print(f"report={report_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
