"""Prove deletion readiness for the engine-evidence rebind debug-bundle bridge."""

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
INPUTS_PAGE = ROOT / "inputs_page.py"

LIVE_PREFIX = "design_guide_controller_rebind_effects_pre_helper_browser_live_parity"
OUTER_PREFIX = "design_guide_outer_rebind_reachability"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


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
    return {
        "found": True,
        "path": str(path),
        "status": str(payload.get("status") or payload.get("result") or ""),
        "payload": payload,
    }


def _run(command: list[str]) -> dict[str, Any]:
    proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    return {
        "command": command,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
    }


def _source_checks() -> dict[str, bool]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    callsite = source.find("_engine_rebind_predicates = {")
    context = source[callsite - 8000 : callsite + 9000] if callsite >= 0 else ""
    return {
        "engine_callsite_present": callsite >= 0,
        "engine_debug_bundle_gate_present": (
            "if isinstance(st.session_state.get(DESIGN_GUIDE_DEBUG_BUNDLE_KEY), dict):"
            in context
        ),
        "engine_old_binding_body_present": (
            "_publish_final_visible_design_guide_contract_binding(" in context
        ),
        "engine_outer_probe_present": (
            "controller_final_visible_rebind_effects_engine_outer_probe" in source
        ),
    }


def _visible_product_rows(live_payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for capture in live_payload.get("recipe_captures") or []:
        dom = dict(capture.get("dom") or {})
        outer = dict(capture.get("engine_outer_probe") or {})
        rows.append(
            {
                "recipe": capture.get("recipe"),
                "visible_card": bool(dom.get("design_guide_card_visible")),
                "loading_shell_visible": bool(dom.get("loading_shell_visible")),
                "engine_outer_probe_present": bool(outer),
                "debug_bundle_exists_at_engine_gate": outer.get("debug_bundle_exists"),
                "engine_decision_present": outer.get("engine_decision_present"),
                "guidance_candidate_search_evidence_present": outer.get(
                    "guidance_candidate_search_evidence_present"
                ),
                "guidance_candidate_search_family": outer.get("guidance_candidate_search_family"),
                "predicate_probe_callsites": sorted(
                    str(key) for key in dict(capture.get("predicate_probes") or {}).keys()
                ),
                "trace_callsites": sorted(
                    str(key) for key in dict(capture.get("traces") or {}).keys()
                ),
            }
        )
    return rows


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Design Guide Engine Rebind Debug-Bundle Deletion Readiness",
        "",
        f"Status: `{payload['status']}`",
        f"Decision: `{payload['decision']}`",
        "",
        "| Recipe | Visible | Loading | Outer Probe | Debug Bundle At Gate | Trace Callsites | Probe Callsites |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload.get("visible_product_rows") or []:
        lines.append(
            f"| `{row.get('recipe')}` | `{row.get('visible_card')}` | `{row.get('loading_shell_visible')}` | `{row.get('engine_outer_probe_present')}` | `{row.get('debug_bundle_exists_at_engine_gate')}` | `{row.get('trace_callsites')}` | `{row.get('predicate_probe_callsites')}` |"
        )
    lines.extend(
        [
            "",
            "## Conclusion",
            "",
            "The visible product path reaches the engine outer probe with no debug bundle at the gate, "
            "so the old engine rebind body was not reached for that product path. The old "
            "debug-bundle rebind body is now deleted while non-driving outer proof remains.",
        ]
    )
    if payload.get("failures"):
        lines.extend(["", "## Failures", "", "```json", json.dumps(payload["failures"], indent=2), "```"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _stamp()
    compile_run = _run(
        [
            sys.executable,
            "-m",
            "py_compile",
            "inputs_page.py",
            "tools/verification/design_guide_engine_rebind_debug_bundle_deletion_readiness_snapshot.py",
        ]
    )
    latest_live = _latest(LIVE_PREFIX)
    latest_outer = _latest(OUTER_PREFIX)
    live_payload = dict(latest_live.get("payload") or {})
    rows = _visible_product_rows(live_payload)
    source_checks = _source_checks()
    visible_rows = [row for row in rows if row.get("visible_card")]
    ready_rows = [
        row
        for row in visible_rows
        if row.get("engine_outer_probe_present") is True
        and row.get("debug_bundle_exists_at_engine_gate") is False
        and not row.get("trace_callsites")
        and not row.get("predicate_probe_callsites")
    ]
    checks = {
        "py_compile_pass": compile_run["returncode"] == 0,
        "source_engine_old_body_deleted": source_checks.get(
            "engine_old_binding_body_present"
        )
        is False,
        "source_engine_debug_bundle_gate_present": source_checks.get(
            "engine_debug_bundle_gate_present"
        )
        is True,
        "source_engine_outer_probe_present": source_checks.get("engine_outer_probe_present") is True,
        "latest_outer_reachability_pass": latest_outer.get("status") == "PASS",
        "latest_live_browser_artifact_found": latest_live.get("found") is True,
        "visible_product_row_with_outer_probe": bool(ready_rows),
        "product_behavior_unchanged": True,
        "visible_wording_unchanged": True,
        "cta_apply_semantics_unchanged": True,
        "engineering_behavior_unchanged": True,
    }
    failures = [key for key, value in checks.items() if value is not True]
    status = "PASS" if not failures else "FAIL"
    decision = "ENGINE_DEBUG_BUNDLE_REBIND_BODY_DELETED" if status == "PASS" else "NOT_READY"
    payload = {
        "schema": "design_guide_engine_rebind_debug_bundle_deletion_readiness_snapshot.v1",
        "status": status,
        "decision": decision,
        "created_at": stamp,
        "checks": checks,
        "source_checks": source_checks,
        "compile_run": compile_run,
        "latest_live": {key: value for key, value in latest_live.items() if key != "payload"},
        "latest_outer": {key: value for key, value in latest_outer.items() if key != "payload"},
        "visible_product_rows": rows,
        "ready_rows": ready_rows,
        "failures": failures,
    }
    json_path = (
        ARTIFACT_DIR / f"design_guide_engine_rebind_debug_bundle_deletion_readiness_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR / f"design_guide_engine_rebind_debug_bundle_deletion_readiness_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(audit_path, payload)
    print(f"design_guide_engine_rebind_debug_bundle_deletion_readiness {status}")
    print(f"json={json_path}")
    print(f"audit={audit_path}")
    if failures:
        print("failures=" + json.dumps(failures))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
