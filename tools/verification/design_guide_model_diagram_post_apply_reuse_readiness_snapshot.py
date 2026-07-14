"""Post-Apply readiness for model/diagram render reuse.

Proof-only. Combines the focused post-Apply settle profile with the existing
model/diagram trace-only reuse guard. It decides whether a live post-Apply
Plotly/model render bypass is safe to implement, or whether more fingerprint
parity is required first.
"""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _run(command: list[str]) -> dict[str, Any]:
    proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    return {
        "command": command,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
        "passed": proc.returncode == 0,
    }


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "path": None, "payload": {}, "status": None}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"found": True, "path": str(path), "payload": {}, "status": "UNREADABLE", "error": str(exc)}
    return {"found": True, "path": str(path), "payload": payload, "status": payload.get("status")}


def _function_block(source: str, name: str) -> str:
    match = re.search(rf"^def {re.escape(name)}\(", source, re.MULTILINE)
    if not match:
        return ""
    next_match = re.search(r"^def\s+\w+\(", source[match.end() :], re.MULTILINE)
    end = match.end() + next_match.start() if next_match else len(source)
    return source[match.start() : end]


def _source_checks() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    helper = _function_block(source, "_record_inputs_model_diagram_render_reuse_trace")
    section_2d = _function_block(source, "_render_section_2d_diagram_block")
    section_3d = _function_block(source, "_render_3d_diagram_block")
    return {
        "trace_helper_exists": bool(helper),
        "trace_helper_trace_only": '"trace_only": True' in helper,
        "trace_helper_never_skips_render": '"render_skipped": False' in helper,
        "fingerprint_helper_exists": "def _inputs_geometry_fingerprint" in source,
        "two_d_uses_trace_before_plotly": (
            "_record_inputs_model_diagram_render_reuse_trace(" in section_2d
            and section_2d.find("_record_inputs_model_diagram_render_reuse_trace(")
            < section_2d.find("render_plotly_diagram(")
        ),
        "three_d_uses_trace_before_plotly": (
            "_record_inputs_model_diagram_render_reuse_trace(" in section_3d
            and section_3d.find("_record_inputs_model_diagram_render_reuse_trace(")
            < section_3d.find("render_plotly_diagram(")
        ),
        "live_render_bypass_absent": "render_skipped\": True" not in source and "model_diagram_render_bypassed" not in source,
    }


def _build() -> dict[str, Any]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    compile_run = _run([sys.executable, "-m", "py_compile", "inputs_page.py"])
    readiness = _latest("design_guide_model_diagram_render_reuse_readiness")
    trace = _latest("design_guide_model_diagram_render_reuse_trace")
    post_apply = _latest("design_guide_post_apply_settle_source_profile")
    post_summary = dict((post_apply.get("payload") or {}).get("summary") or {})
    post_payload = dict(post_apply.get("payload") or {})
    initial_trace = dict(
        (((post_payload.get("initial") or {}).get("counters") or {}).get("model_diagram_render_reuse_trace") or {})
    )
    post_trace = dict(
        (((post_payload.get("post_apply") or {}).get("counters") or {}).get("model_diagram_render_reuse_trace") or {})
    )
    source = _source_checks()
    focused_owner = str(post_summary.get("focused_post_click_top_owner") or "")
    focused_totals = dict(post_summary.get("focused_post_click_owner_totals") or {})
    plotly_records = int(focused_totals.get("plotly_or_chart") or 0)
    trace_payload = dict(trace.get("payload") or {})
    trace_class = dict(trace_payload.get("classification") or {})
    readiness_payload = dict(readiness.get("payload") or {})
    readiness_class = dict(readiness_payload.get("classification") or {})

    ready_for_bypass = False
    blockers: list[str] = []
    if not compile_run["passed"]:
        blockers.append("inputs_page_py_compile_failed")
    if readiness.get("status") != "PASS":
        blockers.append("model_reuse_readiness_not_pass")
    if trace.get("status") != "PASS":
        blockers.append("model_reuse_trace_not_pass")
    if post_apply.get("status") != "PASS":
        blockers.append("post_apply_profile_not_pass")
    if focused_owner not in {"plotly_or_chart", "model_panel"} or plotly_records < 500:
        blockers.append("post_apply_model_or_plotly_hotspot_not_strong")
    if not trace_class.get("ready_for_live_trace_profile"):
        blockers.append("trace_profile_not_ready")
    if not readiness_class.get("ready_for_trace_only_guard"):
        blockers.append("trace_only_guard_not_ready")
    changed_after_apply = False
    trace_pairs: dict[str, Any] = {}
    for key, post_row in post_trace.items():
        if not isinstance(post_row, dict):
            continue
        initial_row = dict(initial_trace.get(key) or {})
        before_hash = initial_row.get("render_fingerprint_hash")
        after_previous = post_row.get("previous_render_fingerprint_hash")
        after_hash = post_row.get("render_fingerprint_hash")
        row_changed = bool(after_hash and before_hash and after_hash != before_hash)
        changed_after_apply = changed_after_apply or row_changed
        trace_pairs[key] = {
            "before_hash": before_hash,
            "post_previous_hash": after_previous,
            "post_hash": after_hash,
            "changed_after_apply": row_changed,
            "post_decision": post_row.get("decision"),
            "post_reuse_eligible": post_row.get("reuse_eligible"),
        }
    if changed_after_apply:
        blockers.append("initial_post_apply_model_fingerprint_changed_render_required")
    for key, value in source.items():
        if not value:
            blockers.append(f"source_check_failed:{key}")

    # The existing trace guard does not yet prove stale/missing/changed
    # fingerprint rebuild behaviour for actually skipping Plotly render, so a
    # live bypass is intentionally not ready in this slice.
    if not blockers:
        blockers.append("missing_live_bypass_stale_changed_debug_apply_inflight_guard_proof")

    if changed_after_apply:
        decision = "INITIAL_POST_APPLY_RENDER_REQUIRED_BY_CHANGED_MODEL_FINGERPRINT"
    else:
        decision = "READY_FOR_BYPASS_GUARD_PROOF_NOT_IMPLEMENTATION" if len(blockers) == 1 and blockers[0].startswith("missing_live_bypass") else "NOT_READY_FOR_LIVE_BYPASS"
    return {
        "schema": "design_guide_model_diagram_post_apply_reuse_readiness.v1",
        "created_at": _stamp(),
        "status": "PASS",
        "decision": decision,
        "ready_for_live_bypass": ready_for_bypass,
        "ready_for_next_guard_proof": decision == "READY_FOR_BYPASS_GUARD_PROOF_NOT_IMPLEMENTATION",
        "blockers": blockers,
        "product_behaviour_changed": False,
        "source_checks": source,
        "compile_run": compile_run,
        "latest_readiness": {
            "path": readiness.get("path"),
            "status": readiness.get("status"),
            "classification": readiness_class,
        },
        "latest_trace": {
            "path": trace.get("path"),
            "status": trace.get("status"),
            "classification": trace_class,
        },
        "latest_post_apply": {
            "path": post_apply.get("path"),
            "status": post_apply.get("status"),
            "decision": post_summary.get("decision"),
            "focused_top_owner": focused_owner,
            "focused_owner_totals": focused_totals,
            "post_apply_milestones_ms": post_summary.get("post_apply_milestones_ms"),
            "model_trace_pairs": trace_pairs,
            "changed_after_apply": changed_after_apply,
        },
        "recommended_next_slice": (
            "Do not skip the first post-Apply model render; it is required because the model fingerprint changed. Next target is stable rerun after Apply, where the same fingerprint can become eligible for reuse."
            if changed_after_apply
            else "Create a bypass guard proof for model/diagram render skip keyed by geometry/model fingerprint, proving changed/missing/stale/debug/post-apply-inflight rebuild cases."
            if decision == "READY_FOR_BYPASS_GUARD_PROOF_NOT_IMPLEMENTATION"
            else "Do not implement model/diagram bypass; fix blockers or gather stronger post-Apply trace proof first."
        ),
    }


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    stamp = str(payload["created_at"])
    json_path = ARTIFACT_DIR / f"design_guide_model_diagram_post_apply_reuse_readiness_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_model_diagram_post_apply_reuse_readiness_{stamp}.md"
    latest = dict(payload.get("latest_post_apply") or {})
    lines = [
        "# Design Guide Model/Diagram Post-Apply Reuse Readiness",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Decision: `{payload.get('decision')}`",
        f"- Ready for live bypass: `{payload.get('ready_for_live_bypass')}`",
        f"- Ready for next guard proof: `{payload.get('ready_for_next_guard_proof')}`",
        f"- Product behaviour changed: `{payload.get('product_behaviour_changed')}`",
        "",
        "## Post-Apply Evidence",
        "",
        f"- Focused top owner: `{latest.get('focused_top_owner')}`",
        f"- Owner totals: `{latest.get('focused_owner_totals')}`",
        f"- Milestones: `{latest.get('post_apply_milestones_ms')}`",
        "",
        "## Blockers",
        "",
    ]
    lines.extend(f"- `{item}`" for item in payload.get("blockers") or [])
    lines.extend(["", "## Recommendation", "", str(payload.get("recommended_next_slice") or ""), ""])
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def main() -> int:
    payload = _build()
    json_path, md_path = _write(payload)
    print(f"wrote {json_path}")
    print(f"wrote {md_path}")
    print(json.dumps({"status": payload["status"], "decision": payload["decision"]}, indent=2))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
