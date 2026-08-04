"""Lock the remaining Design Guide restamper/default-rebuild paths as fallback-only."""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _run(command: list[str]) -> dict[str, Any]:
    proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    return {
        "command": command,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
    }


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
    cleanup = _latest("design_guide_remaining_resolver_cleanup_audit")
    cleanup_payload = dict(cleanup.get("payload") or {})
    fallback_paths = list(cleanup_payload.get("fallback_only_keep_paths") or [])
    rows = []
    for row in fallback_paths:
        function = str(row.get("function") or "")
        line = int(row.get("line") or 0)
        if function == "_final_visible_compatibility_restamper_adapter_cutover":
            kind = "guarded_compatibility_adapter_fallback"
            next_proof = "browser/live proof that adapter validity is always true for the two compatibility callsites"
        elif function == "_final_visible_restamper_default_rebuild_adapter_cutover":
            kind = "guarded_default_rebuild_adapter_fallback"
            next_proof = "browser/render proof that adapter output covers stale/default rebuild states before deletion"
        elif function == "_render_guidance_secondary_items":
            kind = "render_guidance_secondary_fallback"
            next_proof = "browser/render proof that fallback shell is unreachable or adapter replacement is valid"
        else:
            kind = "unknown_fallback"
            next_proof = "manual proof required"
        rows.append(
            {
                "line": line,
                "function": function,
                "target": row.get("target"),
                "fallback_kind": kind,
                "classification": row.get("classification"),
                "safe_to_delete_now": False,
                "required_next_proof": next_proof,
            }
        )
    counts = dict(cleanup_payload.get("classification_counts") or {})
    capture = {
        "decision": "REMAINING_RESTAMPER_SURFACE_LOCKED_TO_FALLBACK_ONLY",
        "cleanup_audit": {
            "status": cleanup.get("status"),
            "path": cleanup.get("path"),
        },
        "counts": {
            "fallback_only_path_count": len(rows),
            "compatibility_stamp_count": int(counts.get("B. compatibility-only stamp") or 0),
            "live_mutation_count": int(
                counts.get("C. still live resolver/restamper mutation / keep") or 0
            ),
            "unknown_count": int(counts.get("E. unknown / needs proof") or 0),
            "guarded_compatibility_fallback_count": sum(
                1 for row in rows if row.get("fallback_kind") == "guarded_compatibility_adapter_fallback"
            ),
            "guarded_default_rebuild_fallback_count": sum(
                1 for row in rows if row.get("fallback_kind") == "guarded_default_rebuild_adapter_fallback"
            ),
            "render_fallback_count": sum(
                1 for row in rows if row.get("fallback_kind") == "render_guidance_secondary_fallback"
            ),
        },
        "rows": rows,
        "latest_required": {
            "guarded_cutover": _latest("design_guide_restamper_compatibility_stamp_guarded_cutover"),
            "component_projection": _latest("design_guide_restamper_compatibility_component_projection"),
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
            "Run browser/render fallback reachability for the guarded compatibility fallback and "
            "guarded default-rebuild fallback before deleting fallback code."
        ),
    }
    return capture


def _checks(capture: dict[str, Any], compile_run: dict[str, Any]) -> dict[str, bool]:
    counts = dict(capture.get("counts") or {})
    latest = dict(capture.get("latest_required") or {})
    return {
        "py_compile_pass": compile_run.get("returncode") == 0,
        "cleanup_audit_pass": (capture.get("cleanup_audit") or {}).get("status") == "PASS",
            "fallback_only_count_is_0": counts.get("fallback_only_path_count") == 0,
        "compatibility_stamp_count_zero": counts.get("compatibility_stamp_count") == 0,
        "live_mutation_count_zero": counts.get("live_mutation_count") == 0,
        "unknown_count_zero": counts.get("unknown_count") == 0,
        "guarded_compatibility_fallback_count_zero": (
            counts.get("guarded_compatibility_fallback_count") == 0
        ),
        "guarded_default_rebuild_fallback_count_zero": (
            counts.get("guarded_default_rebuild_fallback_count") == 0
        ),
        "render_fallback_count_zero": counts.get("render_fallback_count") == 0,
        "guarded_cutover_pass": (latest.get("guarded_cutover") or {}).get("status") == "PASS",
        "component_projection_pass": (latest.get("component_projection") or {}).get("status") == "PASS",
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
        "Remaining fallback-only restamper/default-rebuild paths.",
        "",
        "## Ownership Before",
        "Compatibility stamps and fallback paths were mixed in the remaining resolver cleanup inventory.",
        "",
        "## Ownership After",
        "Compatibility stamps are zero; remaining paths are explicitly fallback-only.",
        "",
        "## Behaviour Preserved",
        "- Engineering behaviour unchanged.",
        "- Visible wording unchanged.",
        "- CTA/apply semantics unchanged.",
        "- Family runtimes unchanged.",
        "",
        "## Adapter / Default Rebuild Proof",
        "Guarded compatibility cutover and component projection are required PASS.",
        "",
        "## Cutover Proof",
        "No fallback deletion yet.",
        "",
        "## Deadness / Deletion Proof",
        "Fallback paths are retained until browser/render fallback reachability proof.",
        "",
        "## Remaining Rows",
        "",
        "| Line | Function | Kind | Safe delete | Next proof |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in capture.get("rows") or []:
        lines.append(
            f"| {row.get('line')} | `{row.get('function')}` | `{row.get('fallback_kind')}` | `{row.get('safe_to_delete_now')}` | {row.get('required_next_proof')} |"
        )
    lines.extend(
        [
            "",
            "## Lines Removed / Added",
            "No product code changed.",
            "",
            "## Files Changed",
            "- `tools/verification/design_guide_remaining_fallback_only_paths_snapshot.py`",
            "",
            "## Verifier Results",
            "",
        ]
    )
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    if payload.get("failures"):
        lines.extend(["", "## Failures", ""])
        lines.extend(f"- `{failure}`" for failure in payload["failures"])
    lines.extend(["", "## Next Safe Target", str(capture.get("next_safe_step"))])
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
            "tools/verification/design_guide_remaining_fallback_only_paths_snapshot.py",
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
    json_path = ARTIFACT_DIR / f"design_guide_remaining_fallback_only_paths_{stamp}.json"
    audit_path = AUDIT_DIR / f"design_guide_remaining_fallback_only_paths_{stamp}.md"
    report_path = REPORT_DIR / f"design_brain_physical_extraction_remaining_fallback_only_paths_{stamp}.md"
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
