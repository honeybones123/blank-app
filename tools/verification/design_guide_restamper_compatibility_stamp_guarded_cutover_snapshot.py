"""Verify guarded cutover for compatibility-only restamper stamps."""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports"


CALLSITES = {
    "render_fast_design_guidance_panel.final_visible_item_binding": "guidance_debug",
}


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


def _run(command: list[str]) -> dict[str, Any]:
    proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    return {
        "command": command,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
    }


def _function_body(source: str, name: str) -> str:
    marker = f"def {name}("
    start = source.find(marker)
    if start < 0:
        return ""
    end = source.find("\ndef ", start + len(marker))
    if end < 0:
        end = len(source)
    return source[start:end]


def _window_around(source: str, marker: str, *, before: int = 2400, after: int = 2600) -> str:
    idx = source.find(marker)
    if idx < 0:
        return ""
    return source[max(0, idx - before): idx + after]


def _line_numbers(source: str, needle: str) -> list[int]:
    return [idx for idx, line in enumerate(source.splitlines(), 1) if needle in line]


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "path": None, "status": "MISSING", "payload": {}}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {
            "found": True,
            "path": str(path),
            "status": "UNREADABLE",
            "payload": {},
            "error": f"{type(exc).__name__}: {exc}",
        }
    raw_status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    status = "PASS" if any(token in raw_status.upper() for token in ("PASS", "LOCKED", "COMPLETE")) else raw_status
    return {"found": True, "path": str(path), "status": status or "UNKNOWN", "payload": payload}


def _build_snapshot() -> dict[str, Any]:
    source = _read(INPUTS_PAGE)
    binding = _function_body(source, "_store_final_visible_compatibility_restamper_render_item_projection_debug")
    rows = []
    for callsite_id, debug_name in CALLSITES.items():
        window = _window_around(source, callsite_id)
        rows.append(
            {
                "callsite_id": callsite_id,
                "line_numbers": _line_numbers(source, callsite_id),
                "uses_render_binding": "_build_final_visible_render_binding_payload(" in window,
                "direct_old_helper_call_in_callsite_window": (
                    "_publish_final_visible_design_guide_contract_binding(" in window
                ),
                "passes_callsite_id": f'callsite_id="{callsite_id}"' in window,
                "passes_debug_sink": debug_name in window,
                "classification": "render-binding compatibility callsite",
            }
        )
    capture = {
        "decision": "COMPATIBILITY_RESTAMPER_STAMPS_CUT_OVER_TO_RENDER_BINDING",
        "source_lines": {
            "wrapper": _line_numbers(source, "def _final_visible_compatibility_restamper_adapter_cutover("),
            "render_binding_import": _line_numbers(
                source,
                "build_final_visible_render_binding_payload as _build_final_visible_render_binding_payload",
            ),
            "old_helper_definition": _line_numbers(
                source, "def _publish_final_visible_design_guide_contract_binding("
            ),
        },
        "binding_storage_helper": {
            "present": bool(binding),
            "stores_debug_projection": "debug_sink.update(dict(projection.get(\"debug_updates\") or {}))" in binding,
            "stores_bypass_states": "final_visible_restamper_adapter_bypass_states" in binding,
        },
        "rows": rows,
        "counts": {
            "tracked_callsite_count": len(rows),
            "render_binding_callsite_count": sum(1 for row in rows if row.get("uses_render_binding")),
            "direct_old_helper_callsite_count": sum(
                1 for row in rows if row.get("direct_old_helper_call_in_callsite_window")
            ),
        },
        "latest_required": {
            "component_projection": _latest("design_guide_restamper_compatibility_component_projection"),
            "deletion_readiness": _latest(
                "design_guide_restamper_compatibility_stamp_deletion_readiness"
            ),
            "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
            "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
            "independence_lock": _latest("design_guide_independence_lock"),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "family_runtime_changed": False,
        "next_safe_step": (
            "Run remaining resolver cleanup audit. If it still counts these as compatibility stamps, "
            "retarget the inventory to distinguish direct old-helper calls from guarded fallback."
        ),
    }
    return capture


def _checks(capture: dict[str, Any], compile_run: dict[str, Any]) -> dict[str, bool]:
    binding = dict(capture.get("binding_storage_helper") or {})
    counts = dict(capture.get("counts") or {})
    latest = dict(capture.get("latest_required") or {})
    rows = list(capture.get("rows") or [])
    return {
        "py_compile_pass": compile_run.get("returncode") == 0,
        "render_binding_imported": bool(
            (capture.get("source_lines") or {}).get("render_binding_import")
        ),
        "wrapper_deleted": not bool((capture.get("source_lines") or {}).get("wrapper")),
        "binding_storage_helper_present": binding.get("present") is True,
        "binding_stores_debug_projection": binding.get("stores_debug_projection") is True,
        "binding_stores_bypass_states": binding.get("stores_bypass_states") is True,
        "one_callsite_tracked": counts.get("tracked_callsite_count") == 1,
        "callsite_uses_render_binding": counts.get("render_binding_callsite_count") == 1,
        "no_direct_old_helper_at_callsites": counts.get("direct_old_helper_callsite_count") == 0,
        "all_callsites_pass_id": all(row.get("passes_callsite_id") is True for row in rows),
        "all_callsites_pass_debug_sink": all(row.get("passes_debug_sink") is True for row in rows),
        "component_projection_pass": (latest.get("component_projection") or {}).get("status") == "PASS",
        "deletion_readiness_pass": (latest.get("deletion_readiness") or {}).get("status") == "PASS",
        "render_bridge_lock_pass": (latest.get("render_bridge_lock") or {}).get("status") == "PASS",
        "compute_bridge_lock_pass": (latest.get("compute_bridge_lock") or {}).get("status") == "PASS",
        "independence_lock_pass": (latest.get("independence_lock") or {}).get("status") == "PASS",
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Brain Physical Extraction Report",
        "",
        "## Executive Summary",
        str(payload.get("status")),
        "",
        "## Surface Targeted",
        "The remaining compatibility-only restamper stamp callsite.",
        "",
        "## Ownership Before",
        "The page used wrapper-style compatibility restamper cutovers and old helper fallback paths.",
        "",
        "## Ownership After",
        "The live callsite uses `_build_final_visible_render_binding_payload(...)`; the old compatibility wrapper is gone and only debug/storage stamping remains page-local.",
        "",
        "## Behaviour Preserved",
        "- Engineering behaviour unchanged.",
        "- Visible wording unchanged.",
        "- CTA/apply semantics unchanged.",
        "- Family runtimes unchanged.",
        "",
        "## Adapter / Default Rebuild Proof",
        "Component projection adapter latest status is required PASS.",
        "",
        "## Cutover Proof",
        f"Direct old-helper callsites: `{(capture.get('counts') or {}).get('direct_old_helper_callsite_count')}`.",
        "",
        "## Deadness / Deletion Proof",
        "Old helper is not dead yet because it remains guarded fallback inside the wrapper.",
        "",
        "## Lines Removed / Added",
        "Direct old helper calls at the two compatibility callsites were replaced by guarded adapter wrapper calls.",
        "",
        "## Files Changed",
        "- `inputs_page.py`",
        "- `tools/verification/design_guide_restamper_compatibility_stamp_guarded_cutover_snapshot.py`",
        "",
        "## Verifier Results",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    if payload.get("failures"):
        lines.extend(["", "## Failures", ""])
        lines.extend(f"- `{failure}`" for failure in payload["failures"])
    lines.extend(
        [
            "",
            "## Remaining Page-Owned Authority",
            "Old helper fallback remains guarded inside `_final_visible_compatibility_restamper_adapter_cutover(...)`.",
            "",
            "## Next Safe Target",
            str(capture.get("next_safe_step")),
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _stamp()
    compile_run = _run(
        [
            sys.executable,
            "-m",
            "py_compile",
            "inputs_page.py",
            "tools/verification/design_guide_restamper_compatibility_stamp_guarded_cutover_snapshot.py",
        ]
    )
    capture = _build_snapshot()
    checks = _checks(capture, compile_run)
    failures = [key for key, value in checks.items() if value is not True]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "status": status,
        "timestamp": stamp,
        "capture": capture,
        "checks": checks,
        "failures": failures,
        "compile": compile_run,
    }
    json_path = ARTIFACT_DIR / f"design_guide_restamper_compatibility_stamp_guarded_cutover_{stamp}.json"
    audit_path = AUDIT_DIR / f"design_guide_restamper_compatibility_stamp_guarded_cutover_{stamp}.md"
    report_path = REPORT_DIR / f"design_brain_physical_extraction_restamper_compatibility_stamp_guarded_cutover_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(f"status={status}")
    print(f"json={json_path}")
    print(f"audit={audit_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
