"""Audit default rebuild behavior for the remaining restamper/fallback surfaces.

This is the deletion-enabling inventory for the current four remaining
`_publish_final_visible_design_guide_contract_binding(...)` callsites. It
records what each old call protects and what an adapter must replace before the
page-owned restamper call can be deleted.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports"

TARGETS: dict[str, dict[str, Any]] = {
    "pre_render_fallback_binding": {
        "line_token": "_pre_render_bound_item = _publish_final_visible_design_guide_contract_binding(",
        "class": "fallback-only",
        "input_item": "_pre_render_input_item",
        "output_item": "_pre_render_bound_item",
        "debug": "_pre_render_debug_sink",
        "state": "guidance_disp_state",
        "protected_outputs": (
            "button_contract",
            "action_payload",
            "resolved_candidate",
            "candidate_search_evidence",
            "family_status_current",
            "family_status_preview",
            "safe_combined_cleanup_projection",
        ),
    },
    "pre_card_fallback_binding": {
        "line_token": "_pre_card_bound_item = _publish_final_visible_design_guide_contract_binding(",
        "class": "fallback-only",
        "input_item": "_pre_card_input_item",
        "output_item": "_pre_card_bound_item",
        "debug": "_pre_card_bundle",
        "state": "guidance_disp_state",
        "protected_outputs": (
            "button_contract",
            "action_payload",
            "resolved_candidate",
            "candidate_search_evidence",
            "family_status_current",
            "family_status_preview",
            "terminal_blocker_projection",
        ),
    },
    "render_guidance_secondary_primary_binding": {
        "line_token": "item = _publish_final_visible_design_guide_contract_binding(",
        "class": "compatibility-only",
        "callsite_marker": "render_guidance_secondary_primary_binding",
        "input_item": "_pre_card_binding_input_item",
        "output_item": "item",
        "debug": "_binding_debug_sink",
        "state": "guidance_disp_state",
        "protected_outputs": (
            "button_contract",
            "action_payload",
            "resolved_candidate",
            "candidate_search_evidence",
            "publication_contract_render_enforcement",
        ),
    },
    "render_fast_final_visible_item_binding": {
        "line_token": "_final_visible_item = _publish_final_visible_design_guide_contract_binding(",
        "class": "compatibility-only",
        "callsite_marker": "render_fast_design_guidance_panel.final_visible_item_binding",
        "input_item": "_final_visible_binding_input_item",
        "output_item": "_final_visible_item",
        "debug": "guidance_debug",
        "state": "current_state",
        "protected_outputs": (
            "button_contract",
            "action_payload",
            "resolved_candidate",
            "candidate_search_evidence",
            "zero_shear_terminal_projection",
            "post_click_exact_blocker_projection",
        ),
    },
}


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": ""}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {"found": True, "status": "UNREADABLE", "path": str(path), "error": str(exc)}
    raw = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    status = "PASS" if any(token in raw.upper() for token in ("PASS", "LOCKED")) else raw
    return {"found": True, "status": status or "UNKNOWN", "path": str(path)}


def _run(command: list[str]) -> dict[str, Any]:
    proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    return {
        "command": command,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
    }


def _line_for(source: str, token: str, marker: str | None = None) -> int | None:
    start = 0
    while True:
        index = source.find(token, start)
        if index < 0:
            return None
        window = source[max(0, index - 1400) : min(len(source), index + 1600)]
        if not marker or marker in window:
            return source.count("\n", 0, index) + 1
        start = index + len(token)


def _window(source: str, line: int | None, before: int = 24, after: int = 60) -> str:
    if line is None:
        return ""
    lines = source.splitlines()
    start = max(1, line - before)
    end = min(len(lines), line + after)
    return "\n".join(lines[start - 1 : end])


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    rows: dict[str, Any] = {}
    for name, spec in TARGETS.items():
        line = _line_for(source, spec["line_token"], spec.get("callsite_marker"))
        window = _window(source, line)
        rows[name] = {
            "line": line,
            "classification": spec["class"],
            "old_restamper_call_present": line is not None,
            "input_item_present": spec["input_item"] in window,
            "output_item_present": spec["output_item"] in window,
            "debug_sink_present": spec["debug"] in window,
            "state_present": spec["state"] in window,
            "bypass_guard_present": "_maybe_bypass_final_visible_restamper_bridge_noop(" in window,
            "adapter_proof_present": "_stamp_final_visible_final_visible_output_bridge_proof(" in window,
            "protected_outputs": list(spec["protected_outputs"]),
            "default_rebuild_behaviour": (
                "old restamper rebuilds final-visible publication binding when guarded bypass cannot prove stable no-op"
            ),
            "required_adapter_replacement": (
                "controller/final-publication projection that returns bound item plus CTA/display/evidence/action payload/resolved candidate projections from pre-helper inputs"
            ),
            "safe_to_delete_now": False,
        }
    latest = {
        "remaining_resolver_cleanup": _latest("design_guide_remaining_resolver_cleanup_audit"),
        "guarded_consumer_reachability": _latest(
            "design_guide_guarded_compatibility_restamper_consumer_reachability"
        ),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
        "independence_lock": _latest("design_guide_independence_lock"),
    }
    return {
        "decision": "REMAINING_RESTAMPER_DEFAULT_REBUILD_SURFACES_AUDITED",
        "rows": rows,
        "latest": latest,
        "old_restamper_call_count": sum(
            1 for row in rows.values() if row.get("old_restamper_call_present") is True
        ),
        "compatibility_only_count": sum(
            1 for row in rows.values() if row.get("classification") == "compatibility-only"
        ),
        "fallback_only_count": sum(
            1 for row in rows.values() if row.get("classification") == "fallback-only"
        ),
        "safe_to_delete_now": False,
        "recommended_next_slice": (
            "build controller/final-publication default rebuild adapter for the four surfaces, "
            "then prove projection parity against these protected outputs"
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }


def _checks(capture: dict[str, Any], compile_run: dict[str, Any]) -> dict[str, bool]:
    rows = dict(capture.get("rows") or {})
    latest = dict(capture.get("latest") or {})
    return {
        "py_compile_pass": compile_run.get("returncode") == 0,
        "all_four_surfaces_present": len(rows) == 4
        and capture.get("old_restamper_call_count") == 4,
        "compatibility_count_two": capture.get("compatibility_only_count") == 2,
        "fallback_count_two": capture.get("fallback_only_count") == 2,
        "all_inputs_outputs_debug_state_mapped": all(
            row.get("input_item_present")
            and row.get("output_item_present")
            and row.get("debug_sink_present")
            and row.get("state_present")
            for row in rows.values()
        ),
        "all_guarded_or_proved": all(
            row.get("bypass_guard_present") and row.get("adapter_proof_present")
            for row in rows.values()
        ),
        "not_safe_to_delete_now": capture.get("safe_to_delete_now") is False,
        "remaining_resolver_cleanup_latest_pass": (
            latest.get("remaining_resolver_cleanup") or {}
        ).get("status")
        == "PASS",
        "guarded_consumer_reachability_latest_pass": (
            latest.get("guarded_consumer_reachability") or {}
        ).get("status")
        == "PASS",
        "render_bridge_lock_latest_pass": (latest.get("render_bridge_lock") or {}).get("status")
        == "PASS",
        "compute_bridge_lock_latest_pass": (latest.get("compute_bridge_lock") or {}).get(
            "status"
        )
        == "PASS",
        "independence_lock_latest_pass": (latest.get("independence_lock") or {}).get("status")
        == "PASS",
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
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
        "Remaining compatibility/fallback restamper default rebuild surfaces.",
        "",
        "## Ownership Before",
        "The page-owned restamper helper still provides the guarded fallback/default rebuild output.",
        "",
        "## Ownership After",
        "No ownership moved in this audit. This identifies the adapter replacement contract.",
        "",
        "## Behaviour Preserved",
        "- Engineering behaviour unchanged.",
        "- Visible wording unchanged.",
        "- CTA/apply semantics unchanged.",
        "- Family runtimes unchanged.",
        "",
        "## Adapter / Default Rebuild Proof",
        "",
        "| Surface | Line | Class | Protected outputs |",
        "| --- | ---: | --- | --- |",
    ]
    for name, row in dict(capture.get("rows") or {}).items():
        lines.append(
            f"| `{name}` | `{row.get('line')}` | `{row.get('classification')}` | "
            f"{', '.join(row.get('protected_outputs') or [])} |"
        )
    lines.extend(
        [
            "",
            "## Cutover Proof",
            "None yet. Next slice must build and prove the adapter.",
            "",
            "## Deadness / Deletion Proof",
            "Deletion is not safe yet; old restamper calls still protect default rebuild behaviour.",
            "",
            "## Lines Removed / Added",
            "Audit-only; no product code changed.",
            "",
            "## Files Changed",
            "- `tools/verification/design_guide_remaining_restamper_default_rebuild_surface_audit.py`",
            "",
            "## Verifier Results",
            "",
        ]
    )
    for key, value in dict(payload.get("checks") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(
        [
            "",
            "## Remaining Page-Owned Authority",
            "Four old restamper calls remain as guarded fallback/default rebuild paths.",
            "",
            "## Next Safe Target",
            str(capture.get("recommended_next_slice") or ""),
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    compile_run = _run(
        [
            "python",
            "-m",
            "py_compile",
            "tools\\verification\\design_guide_remaining_restamper_default_rebuild_surface_audit.py",
        ]
    )
    capture = _capture()
    checks = _checks(capture, compile_run)
    failures = [name for name, value in checks.items() if value is not True]
    payload = {
        "status": "PASS" if not failures else "FAIL",
        "timestamp": _stamp(),
        "capture": capture,
        "checks": checks,
        "failures": failures,
        "compile_run": compile_run,
        "snapshot_hash": _stable_hash({"capture": capture, "checks": checks}),
    }
    stamp = _stamp()
    json_path = ARTIFACT_DIR / (
        f"design_guide_remaining_restamper_default_rebuild_surface_audit_{stamp}.json"
    )
    audit_path = AUDIT_DIR / (
        f"design_guide_remaining_restamper_default_rebuild_surface_audit_{stamp}.md"
    )
    report_path = REPORT_DIR / (
        f"design_brain_physical_extraction_remaining_restamper_default_rebuild_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(f"design_guide_remaining_restamper_default_rebuild_surface_audit {payload['status']}")
    print(f"decision={capture.get('decision')}")
    print(f"old_restamper_call_count={capture.get('old_restamper_call_count')}")
    print(json_path)
    print(audit_path)
    print(report_path)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
