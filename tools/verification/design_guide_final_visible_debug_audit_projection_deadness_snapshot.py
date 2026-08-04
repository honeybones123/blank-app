"""Classify deadness of adapter-backed final-visible debug/audit helpers."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS = ROOT / "inputs_page.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


HELPERS = {
    "_set_final_visible_disabled_primary_payload_binding_audit_projection": {
        "required_write": "_set_design_guide_primary_payload_binding_audit(",
        "classification": "bounded page-shell session/debug write",
        "reason": "updates session payload-binding audit consumed by apply traces and live/browser verifiers",
    },
    "_update_final_visible_enabled_action_debug_projection": {
        "required_write": "debug_sink.update(",
        "classification": "bounded page-shell session/debug write",
        "reason": "updates current render debug sink for enabled CTA/apply diagnostics",
    },
    "_update_final_visible_disabled_debug_projection": {
        "required_write": "debug_sink.update(",
        "classification": "bounded page-shell session/debug write",
        "reason": "updates current render debug sink for disabled CTA/apply diagnostics",
    },
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _function_body(source: str, name: str) -> str:
    needle = f"def {name}("
    start = source.find(needle)
    if start < 0:
        return ""
    next_def = source.find("\ndef ", start + len(needle))
    return source[start:] if next_def < 0 else source[start:next_def]


def _line_numbers(source: str, token: str) -> list[int]:
    return [idx for idx, line in enumerate(source.splitlines(), start=1) if token in line]


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda p: p.stat().st_mtime)
    if not paths:
        return {"found": False, "path": None, "status": None}
    path = paths[-1]
    try:
        payload = json.loads(_read(path))
    except Exception as exc:
        return {"found": True, "path": str(path), "status": None, "load_error": str(exc)}
    return {"found": True, "path": str(path), "status": payload.get("status"), "payload": payload}


def build_snapshot() -> dict[str, Any]:
    source = _read(INPUTS)
    rows: list[dict[str, Any]] = []
    failures: list[str] = []
    for helper, spec in HELPERS.items():
        body = _function_body(source, helper)
        call_lines = [line for line in _line_numbers(source, f"{helper}(") if f"def {helper}(" not in source.splitlines()[line - 1]]
        adapter_backed = (
            "_build_final_visible_primary_payload_binding_audit_projection(" in body
            or "_build_final_visible_debug_projection(" in body
        )
        required_write_present = spec["required_write"] in body
        dead = bool(adapter_backed and not required_write_present and not call_lines)
        if not body:
            failures.append(f"missing_helper:{helper}")
        if not adapter_backed:
            failures.append(f"helper_not_adapter_backed:{helper}")
        rows.append(
            {
                "helper": helper,
                "call_lines": call_lines,
                "adapter_backed": adapter_backed,
                "required_write": spec["required_write"],
                "required_write_present": required_write_present,
                "classification": spec["classification"],
                "reason": spec["reason"],
                "dead": dead,
                "safe_to_delete_now": False,
                "lock_state": "retain_bounded_non_authoritative_page_shell_write",
            }
        )
    cutover = _latest("design_guide_final_visible_debug_audit_projection_adapter_cutover")
    if cutover.get("status") != "PASS":
        failures.append("adapter_cutover_not_pass")
    status = "PASS" if not failures else "FAIL"
    return {
        "schema": "design_guide_final_visible_debug_audit_projection_deadness_snapshot.v1",
        "created_at": datetime.now().strftime("%Y-%m-%dT%H-%M-%S"),
        "status": status,
        "decision": (
            "DEBUG_AUDIT_PROJECTION_HELPERS_BOUNDED_NOT_DEAD"
            if status == "PASS"
            else "DEBUG_AUDIT_PROJECTION_DEADNESS_FAILED"
        ),
        "rows": rows,
        "totals": {
            "bounded_non_authoritative_page_shell_write_count": sum(
                1 for row in rows if row["lock_state"] == "retain_bounded_non_authoritative_page_shell_write"
            ),
            "safe_deletion_candidate_count": sum(1 for row in rows if row["safe_to_delete_now"]),
            "dead_count": sum(1 for row in rows if row["dead"]),
        },
        "adapter_cutover": {
            "path": cutover.get("path"),
            "status": cutover.get("status"),
        },
        "safe_to_delete_any_now": False,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
        "next_safe_step": (
            "treat these three helpers as bounded non-authoritative page-shell writes; "
            "move to R1 apply/session/CTA shell boundary only with a dedicated apply/session parity proof"
        ),
        "failures": failures,
    }


def _write_report(snapshot: dict[str, Any], path: Path) -> None:
    lines = [
        "# Final Visible Debug/Audit Projection Deadness Snapshot",
        "",
        f"Status: `{snapshot['status']}`",
        f"Decision: `{snapshot['decision']}`",
        f"Safe to delete any now: `{snapshot['safe_to_delete_any_now']}`",
        "",
        "## Rows",
        "| Helper | Calls | Required write present | Classification | Safe to delete |",
        "| --- | ---: | --- | --- | --- |",
    ]
    for row in snapshot["rows"]:
        lines.append(
            "| `{helper}` | {calls} | `{write}` | {classification} | `{safe}` |".format(
                helper=row["helper"],
                calls=len(row["call_lines"]),
                write=row["required_write_present"],
                classification=row["classification"],
                safe=row["safe_to_delete_now"],
            )
        )
    lines.extend(
        [
            "",
            "## Totals",
            *[f"- `{key}`: `{value}`" for key, value in snapshot["totals"].items()],
            "",
            "## Next Safe Step",
            snapshot["next_safe_step"],
            "",
        ]
    )
    if snapshot["failures"]:
        lines.extend(["## Failures", *[f"- `{failure}`" for failure in snapshot["failures"]], ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    snapshot = build_snapshot()
    stamp = snapshot["created_at"]
    json_path = ARTIFACT_DIR / f"design_guide_final_visible_debug_audit_projection_deadness_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_final_visible_debug_audit_projection_deadness_{stamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(snapshot, report_path)
    print(f"design_guide_final_visible_debug_audit_projection_deadness {snapshot['status']}")
    print(f"decision={snapshot['decision']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
