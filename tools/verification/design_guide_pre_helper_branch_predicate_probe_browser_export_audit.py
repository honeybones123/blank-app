"""Audit browser export/reachability for pre-helper branch predicate probes."""

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

PROBE_PREFIX = "design_guide_controller_rebind_effects_pre_helper_branch_predicate_probe"
LIVE_PREFIX = "design_guide_controller_rebind_effects_pre_helper_browser_live_parity"
PROBE_KEY = "controller_final_visible_rebind_effects_pre_helper_branch_predicate_probes"
TARGETS = ("combined_evidence_rebind_bridge", "engine_evidence_rebind_bridge")


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
    helper_index = source.find("def _record_controller_pre_helper_rebind_branch_predicate_probe(")
    helper_context = source[helper_index : helper_index + 5000] if helper_index >= 0 else ""
    final_bundle_index = source.find(
        '"controller_final_visible_rebind_effects_pre_helper_branch_predicate_probes": dict('
    )
    final_bundle_context = (
        source[final_bundle_index : final_bundle_index + 5000]
        if final_bundle_index >= 0
        else ""
    )
    return {
        "probe_helper_defined": "def _record_controller_pre_helper_rebind_branch_predicate_probe(" in source,
        "probe_key_stamped": PROBE_KEY in source,
        "combined_probe_callsite": 'callsite_id="combined_evidence_rebind_bridge"' in source,
        "engine_probe_callsite": 'callsite_id="engine_evidence_rebind_bridge"' in source,
        "debug_bundle_written": "st.session_state[DESIGN_GUIDE_DEBUG_BUNDLE_KEY]" in source,
        "browser_state_probe_has_design_guide_probe": '"design_guide_probe"' in source,
        "helper_mirrors_late_probe_to_debug_bundle": (
            "debug_bundle = st.session_state.get(DESIGN_GUIDE_DEBUG_BUNDLE_KEY)" in helper_context
            and PROBE_KEY in helper_context
            and "controller_final_visible_rebind_effects_pre_helper_branch_predicate_probe_product_driving"
            in helper_context
        ),
        "final_debug_bundle_exports_probe_key": (
            PROBE_KEY in final_bundle_context
            and "controller_final_visible_rebind_effects_pre_helper_branch_predicate_probe_hash"
            in final_bundle_context
            and "controller_final_visible_rebind_effects_pre_helper_branch_predicate_probe_render_driving"
            in final_bundle_context
        ),
    }


def _live_probe_rows(live_payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for capture in live_payload.get("recipe_captures") or []:
        probes = dict(capture.get("predicate_probes") or {})
        rows.append(
            {
                "recipe": capture.get("recipe"),
                "visible_card": bool(dict(capture.get("dom") or {}).get("design_guide_card_visible")),
                "loading_shell_visible": bool(dict(capture.get("dom") or {}).get("loading_shell_visible")),
                "probe_callsites": sorted(str(key) for key in probes.keys()),
                "missing_probe_callsites": [
                    callsite for callsite in TARGETS if callsite not in probes
                ],
            }
        )
    return rows


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Design Guide Pre-Helper Branch Predicate Probe Browser Export Audit",
        "",
        f"Status: `{payload['status']}`",
        f"Decision: `{payload['decision']}`",
        "",
        "## Live Browser Probe Rows",
        "",
        "| Recipe | Visible Card | Loading Shell | Probe Callsites | Missing |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload.get("live_probe_rows") or []:
        lines.append(
            f"| `{row.get('recipe')}` | `{row.get('visible_card')}` | `{row.get('loading_shell_visible')}` | `{row.get('probe_callsites')}` | `{row.get('missing_probe_callsites')}` |"
        )
    lines.extend(
        [
            "",
            "## Conclusion",
            "",
            (
                "The predicate probes are source-wired but were not browser-visible in "
                "the latest live parity capture. The next safe proof must distinguish "
                "between render-block reachability and browser debug export omission."
            ),
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
            "tools/verification/design_guide_pre_helper_branch_predicate_probe_browser_export_audit.py",
        ]
    )
    latest_probe = _latest(PROBE_PREFIX)
    latest_live = _latest(LIVE_PREFIX)
    live_payload = dict(latest_live.get("payload") or {})
    live_probe_rows = _live_probe_rows(live_payload)
    source_checks = _source_checks()
    no_live_probes = bool(live_probe_rows) and all(not row["probe_callsites"] for row in live_probe_rows)
    checks = {
        "py_compile_pass": compile_run["returncode"] == 0,
        "probe_source_snapshot_pass": latest_probe.get("status") == "PASS",
        "live_browser_snapshot_found": latest_live.get("found") is True,
        "source_probe_wired": all(source_checks.values()),
        "live_probe_rows_present": bool(live_probe_rows),
        "latest_live_has_no_browser_visible_probe_callsites": no_live_probes,
    }
    failures = [key for key, value in checks.items() if value is not True]
    status = "PASS" if not failures else "FAIL"
    decision = (
        "PROBES_WIRED_BUT_NOT_BROWSER_VISIBLE_REACHABILITY_OR_EXPORT_GAP"
        if status == "PASS"
        else "UNSAFE_TO_DECIDE"
    )
    payload = {
        "schema": "design_guide_pre_helper_branch_predicate_probe_browser_export_audit.v1",
        "status": status,
        "created_at": stamp,
        "decision": decision,
        "checks": checks,
        "compile_run": compile_run,
        "latest_probe": {key: value for key, value in latest_probe.items() if key != "payload"},
        "latest_live": {key: value for key, value in latest_live.items() if key != "payload"},
        "source_checks": source_checks,
        "live_probe_rows": live_probe_rows,
        "failures": failures,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_pre_helper_branch_predicate_probe_browser_export_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_pre_helper_branch_predicate_probe_browser_export_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(audit_path, payload)
    print(f"design_guide_pre_helper_branch_predicate_probe_browser_export {status}")
    print(f"json={json_path}")
    print(f"audit={audit_path}")
    if failures:
        print("failures=" + json.dumps(failures))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
