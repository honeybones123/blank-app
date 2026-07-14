"""Browser probe rebuild readiness snapshot.

Audit-only. The rerun trigger profile reports browser_probe_payload_rebuild
because the hidden browser-state probe is emitted on traced runs. This verifier
classifies which parts of that probe may be optimized without breaking browser
verifiers that read the payload.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
APP = ROOT / "app.py"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": None, "payload": {}}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "found": True,
            "status": "UNREADABLE",
            "path": str(path),
            "payload": {},
            "error": f"{type(exc).__name__}: {exc}",
        }
    status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    if "PASS" in status.upper() or "COMPLETE" in status.upper():
        status = "PASS"
    return {"found": True, "status": status or "UNKNOWN", "path": str(path), "payload": payload}


def _lines(source: str, token: str) -> list[int]:
    return [index for index, line in enumerate(source.splitlines(), start=1) if token in line]


def _capture() -> dict[str, Any]:
    source = APP.read_text(encoding="utf-8", errors="replace")
    latest_rerun = _latest("design_guide_rerun_trigger_source_profile")
    latest_dom_gap = _latest("design_guide_browser_dom_gap_source")
    latest_impact = _latest("design_guide_stable_publication_summary_render_reuse_live_impact")
    latest_independence = _latest("design_guide_independence_lock")
    latest_render = _latest("design_guide_render_bridge_lock")
    latest_compute = _latest("design_guide_compute_resolver_publication_bridge_lock")
    classifications = [
        {
            "surface": "pre-page lightweight probe",
            "classification": "A. keep live",
            "source_lines": _lines(source, "pre_page_render_lightweight")[:8],
            "reason": "browser verifiers use this before the page body mounts",
            "safe_next_step": "none",
        },
        {
            "surface": "post-page summary state / overview probes",
            "classification": "B. possible keyed reuse later",
            "source_lines": _lines(source, "browser_probe.summary_state_probe_build")[:8]
            + _lines(source, "browser_probe.summary_overview_probe_build")[:8],
            "reason": "these rebuild plain probe state and overview for hidden diagnostics",
            "safe_next_step": "prove state/overview probe hashes are stable across no-input reruns",
        },
        {
            "surface": "post-page guidance probe",
            "classification": "C. already has rendered-bundle reuse path",
            "source_lines": _lines(source, "_probe_rendered_design_guide_reuse_payload")[:8],
            "reason": "fallback to compute is guarded by rendered bundle / pending / fingerprint checks",
            "safe_next_step": "measure rendered_bundle_reuse hit rate before changing fallback",
        },
        {
            "surface": "payload JSON + hidden text area emission",
            "classification": "D. best next bypass candidate",
            "source_lines": _lines(source, "_browser_state_probe_text_area_")[:8]
            + _lines(source, "app.browser_test_state_emit.payload_json")[:8],
            "reason": "payload emission repeats even when final probe payload hash is unchanged",
            "safe_next_step": "proof-only stable payload-hash readiness for hidden text-area reuse",
        },
    ]
    rerun_payload = dict(latest_rerun.get("payload") or {})
    source_flags = dict(rerun_payload.get("source_flags") or {})
    if not source_flags:
        source_flags = dict((rerun_payload.get("classification") or {}).get("source_flags") or {})
    return {
        "latest": {
            "rerun_trigger_profile": latest_rerun,
            "dom_gap_source": latest_dom_gap,
            "summary_reuse_live_impact": latest_impact,
            "independence_lock": latest_independence,
            "render_bridge_lock": latest_render,
            "compute_bridge_lock": latest_compute,
        },
        "source_flags": source_flags,
        "classifications": classifications,
        "source_markers": {
            "should_emit_probe_gate": "def _should_emit_browser_state_probe" in source,
            "pre_page_lightweight_path": "pre_page_render_lightweight" in source,
            "rendered_bundle_reuse_path": "_probe_rendered_design_guide_reuse_payload" in source,
            "payload_json_timing": "app.browser_test_state_emit.payload_json" in source,
            "hidden_text_area_probe": "_browser_state_probe_text_area_" in source,
        },
        "recommended_next_slice": (
            "Create proof-only stable browser probe payload hash readiness for hidden text-area reuse. "
            "Do not bypass summary/overview/guidance probe computation until their own hashes and "
            "rendered-bundle reuse hit rate are proven."
        ),
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest") or {})
    labels = {row.get("classification") for row in capture.get("classifications") or []}
    return {
        "rerun_trigger_profile_pass": (latest.get("rerun_trigger_profile") or {}).get("status") == "PASS",
        "dom_gap_source_pass": (latest.get("dom_gap_source") or {}).get("status") == "PASS",
        "summary_reuse_live_impact_pass": (latest.get("summary_reuse_live_impact") or {}).get("status") == "PASS",
        "independence_lock_pass": (latest.get("independence_lock") or {}).get("status") == "PASS",
        "render_bridge_lock_pass": (latest.get("render_bridge_lock") or {}).get("status") == "PASS",
        "compute_bridge_lock_pass": (latest.get("compute_bridge_lock") or {}).get("status") == "PASS",
        "source_markers_present": all((capture.get("source_markers") or {}).values()),
        "probe_surfaces_classified": {
            "A. keep live",
            "B. possible keyed reuse later",
            "C. already has rendered-bundle reuse path",
            "D. best next bypass candidate",
        } <= labels,
    }


def _report(payload: dict[str, Any]) -> str:
    lines = [
        "# Design Guide Browser Probe Rebuild Readiness",
        "",
        f"Status: `{payload.get('status')}`",
        f"Readiness: `{payload.get('readiness')}`",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(["", "## Classified Probe Surfaces", "", "| Surface | Classification | Safe next step |", "|---|---|---|"])
    for row in payload.get("classifications") or []:
        lines.append(
            f"| {row.get('surface')} | {row.get('classification')} | {row.get('safe_next_step')} |"
        )
    lines.extend(["", "## Recommendation", "", str(payload.get("recommended_next_slice") or ""), ""])
    return "\n".join(lines)


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = str(payload["created_at"])
    json_path = ARTIFACT_DIR / f"design_guide_browser_probe_rebuild_readiness_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_browser_probe_rebuild_readiness_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(_report(payload), encoding="utf-8")
    return json_path, md_path


def main() -> int:
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "created_at": _stamp(),
        "status": status,
        "readiness": "READY_FOR_BROWSER_PROBE_PAYLOAD_HASH_READINESS" if status == "PASS" else "NOT_READY",
        "checks": checks,
        "product_behavior_changed": False,
        **capture,
    }
    payload["snapshot_hash"] = _stable_hash(
        {
            "status": status,
            "checks": checks,
            "classifications": payload.get("classifications"),
            "recommended_next_slice": payload.get("recommended_next_slice"),
        }
    )
    json_path, md_path = _write(payload)
    print(json.dumps({"status": status, "json": str(json_path), "report": str(md_path)}, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
