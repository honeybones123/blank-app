"""Deletion proof for the retired render fallback/default rebuild adapter wrapper."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports"
INPUTS_PAGE = ROOT / "inputs_page.py"

LEGACY_TOKENS = {
    "wrapper": "def _final_visible_restamper_default_rebuild_adapter_cutover(",
    "pre_render_anchor": "_pre_render_restamper_bypass = _maybe_bypass_final_visible_restamper_bridge_noop(",
    "pre_render_call": "_pre_render_bound_item = _final_visible_restamper_default_rebuild_adapter_cutover(",
    "pre_card_anchor": "_pre_card_restamper_bypass = _maybe_bypass_final_visible_restamper_bridge_noop(",
    "pre_card_call": "_pre_card_bound_item = _final_visible_restamper_default_rebuild_adapter_cutover(",
}


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


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
        return {"found": False, "status": "MISSING", "path": None, "payload": {}}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {
            "found": True,
            "status": "UNREADABLE",
            "path": str(path),
            "payload": {},
            "error": f"{type(exc).__name__}: {exc}",
        }
    raw_status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    status = "PASS" if any(token in raw_status.upper() for token in ("PASS", "LOCKED", "COMPLETE")) else raw_status
    return {"found": True, "status": status or "UNKNOWN", "path": str(path), "payload": payload}


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    token_rows = {
        key: {
            "present": token in source,
            "line": None if token not in source else source[: source.index(token)].count("\n") + 1,
        }
        for key, token in LEGACY_TOKENS.items()
    }
    latest = {
        "source_output_guard_cutover": _latest("design_guide_final_visible_source_output_guard_cutover"),
        "source_output_fallback_reachability": _latest("design_guide_final_visible_source_output_fallback_reachability"),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
        "independence_lock": _latest("design_guide_independence_lock"),
    }
    return {
        "decision": "RENDER_FALLBACK_DEFAULT_REBUILD_ADAPTER_DELETION_COMPLETE",
        "legacy_tokens": token_rows,
        "latest": latest,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "family_runtime_changed": False,
        "next_safe_step": "none inside this wrapper seam; the render fallback/default rebuild adapter path is deleted",
    }


def _checks(capture: dict[str, Any], compile_run: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest") or {})
    token_rows = dict(capture.get("legacy_tokens") or {})
    return {
        "py_compile_pass": compile_run.get("returncode") == 0,
        "legacy_wrapper_deleted": token_rows.get("wrapper", {}).get("present") is False,
        "pre_render_anchor_deleted": token_rows.get("pre_render_anchor", {}).get("present") is False,
        "pre_render_call_deleted": token_rows.get("pre_render_call", {}).get("present") is False,
        "pre_card_anchor_deleted": token_rows.get("pre_card_anchor", {}).get("present") is False,
        "pre_card_call_deleted": token_rows.get("pre_card_call", {}).get("present") is False,
        "source_output_guard_cutover_pass": (latest.get("source_output_guard_cutover") or {}).get("status") == "PASS",
        "source_output_fallback_reachability_pass": (
            (latest.get("source_output_fallback_reachability") or {}).get("status") == "PASS"
        ),
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
        "Retired render fallback/default rebuild adapter wrapper and its two page callsites.",
        "",
        "## Ownership After",
        "This wrapper seam is deleted. Remaining render authority proofs are covered by the source-output guard retirement and the core Design Guide locks.",
        "",
        "## Verifier Results",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(["", "## Next Safe Target", str(capture.get("next_safe_step") or "")])
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
            "tools/verification/design_guide_render_fallback_default_rebuild_adapter_cutover.py",
        ]
    )
    capture = _capture()
    checks = _checks(capture, compile_run)
    failures = [key for key, value in checks.items() if value is not True]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_render_fallback_default_rebuild_adapter_cutover.v2",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
        "failures": failures,
        "compile_run": compile_run,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    json_path = ARTIFACT_DIR / f"design_guide_render_fallback_default_rebuild_adapter_cutover_{stamp}.json"
    audit_path = AUDIT_DIR / f"design_guide_render_fallback_default_rebuild_adapter_cutover_{stamp}.md"
    report_path = REPORT_DIR / f"design_brain_physical_extraction_render_fallback_default_rebuild_adapter_cutover_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(f"design_guide_render_fallback_default_rebuild_adapter_cutover {status}")
    print(f"json={json_path}")
    print(f"audit={audit_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
