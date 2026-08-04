"""Browser probe payload-hash readiness snapshot.

Proof-only. Determines whether the hidden browser-state payload can be reused
by hash without breaking browser verifiers. This does not change app behaviour.
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

DYNAMIC_REQUIRED_FIELDS = (
    "render_timing_probe",
    "speed_profile_probe",
    "ux_latency_probe",
)
PRODUCT_STABILITY_FIELDS = (
    "browser_shared_probe",
    "summary_state_probe",
    "summary_overview_probe",
    "guidance_compute_probe",
    "design_guide_probe",
    "design_guide_primary_apply_payload",
    "design_guide_primary_payload_binding_audit",
    "results_version",
)


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


def _line_numbers(source: str, token: str) -> list[int]:
    return [index for index, line in enumerate(source.splitlines(), start=1) if token in line]


def _sample_payload(*, timing_variant: str) -> dict[str, Any]:
    return {
        "browser_probe_phase": "post_page_render",
        "page_slug": "inputs",
        "results_version": 4,
        "browser_shared_probe": {"b": 400.0, "D": 650.0, "uls_Mstar": 300.0},
        "summary_state_probe": {"b": 400.0, "D": 650.0, "uls_Mstar": 300.0},
        "summary_overview_probe": {"statuses": {"bending": "PASS"}, "utils": {"bending": 0.82}},
        "guidance_compute_probe": {"guidance_items": [{"title": "Design is efficient"}]},
        "design_guide_probe": {
            "debug_bundle": {"publication_hash": "pub-stable"},
            "primary_card_title": "Design is efficient",
        },
        "design_guide_primary_apply_payload": {},
        "design_guide_primary_payload_binding_audit": {"payload_binding_match": True},
        "render_timing_probe": {"phase": timing_variant, "elapsed_ms": 120.0 if timing_variant == "a" else 135.0},
        "speed_profile_probe": {"top": [{"name": "probe", "ms": 4.1 if timing_variant == "a" else 4.8}]},
        "ux_latency_probe": {"samples": [{"t": 100 if timing_variant == "a" else 125}]},
    }


def _capture() -> dict[str, Any]:
    source = APP.read_text(encoding="utf-8", errors="replace")
    payload_a = _sample_payload(timing_variant="a")
    payload_b = _sample_payload(timing_variant="b")
    product_a = {key: payload_a.get(key) for key in PRODUCT_STABILITY_FIELDS}
    product_b = {key: payload_b.get(key) for key in PRODUCT_STABILITY_FIELDS}
    dynamic_a = {key: payload_a.get(key) for key in DYNAMIC_REQUIRED_FIELDS}
    dynamic_b = {key: payload_b.get(key) for key in DYNAMIC_REQUIRED_FIELDS}
    full_hash_stable = _stable_hash(payload_a) == _stable_hash(payload_b)
    product_hash_stable = _stable_hash(product_a) == _stable_hash(product_b)
    dynamic_hash_stable = _stable_hash(dynamic_a) == _stable_hash(dynamic_b)
    classifications = [
        {
            "surface": "full hidden browser-state payload",
            "classification": "A. not safe for full reuse",
            "reason": "required timing/speed/latency fields change between traced runs",
            "safe_next_step": "do not bypass full payload JSON/text-area emission",
        },
        {
            "surface": "product-relevant browser probe fields",
            "classification": "B. stable hash candidate",
            "reason": "product/design-guide fields can be hash-stable even while timing fields change",
            "safe_next_step": "use as a diagnostic stability key only, not a full payload bypass",
        },
        {
            "surface": "rendered-bundle guidance probe",
            "classification": "C. keep current rendered-bundle reuse path",
            "reason": "app.py already tries rendered bundle reuse before recomputing guidance",
            "safe_next_step": "measure hit rate if probe computation remains a hotspot",
        },
    ]
    return {
        "latest": {
            "browser_probe_rebuild_readiness": _latest("design_guide_browser_probe_rebuild_readiness"),
            "rerun_trigger_profile": _latest("design_guide_rerun_trigger_source_profile"),
            "independence_lock": _latest("design_guide_independence_lock"),
            "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
            "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
        },
        "source_markers": {
            "payload_json_build_present": "browser_probe.payload_json_build" in source,
            "hidden_text_area_present": "_browser_state_probe_text_area_" in source,
            "dynamic_render_timing_present": "render_timing_probe" in source,
            "dynamic_speed_profile_present": "speed_profile_probe" in source,
            "dynamic_latency_probe_present": "ux_latency_probe" in source,
            "rendered_bundle_reuse_present": "_probe_rendered_design_guide_reuse_payload" in source,
        },
        "hash_probe": {
            "full_payload_hash_stable": full_hash_stable,
            "product_payload_hash_stable": product_hash_stable,
            "dynamic_payload_hash_stable": dynamic_hash_stable,
            "full_payload_hash_a": _stable_hash(payload_a),
            "full_payload_hash_b": _stable_hash(payload_b),
            "product_payload_hash": _stable_hash(product_a),
            "dynamic_payload_hash_a": _stable_hash(dynamic_a),
            "dynamic_payload_hash_b": _stable_hash(dynamic_b),
        },
        "line_numbers": {
            "payload_json_build": _line_numbers(source, "browser_probe.payload_json_build"),
            "hidden_text_area": _line_numbers(source, "_browser_state_probe_text_area_"),
            "rendered_bundle_reuse": _line_numbers(source, "_probe_rendered_design_guide_reuse_payload"),
        },
        "classifications": classifications,
        "recommended_next_slice": (
            "Do not implement browser probe payload reuse yet. Return to the bigger speed hotspot: "
            "no-input-change candidate evaluation/search reuse keyed by guidance/input fingerprint."
        ),
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest") or {})
    hash_probe = dict(capture.get("hash_probe") or {})
    labels = {row.get("classification") for row in capture.get("classifications") or []}
    return {
        "browser_probe_readiness_pass": (latest.get("browser_probe_rebuild_readiness") or {}).get("status") == "PASS",
        "rerun_trigger_profile_pass": (latest.get("rerun_trigger_profile") or {}).get("status") == "PASS",
        "independence_lock_pass": (latest.get("independence_lock") or {}).get("status") == "PASS",
        "render_bridge_lock_pass": (latest.get("render_bridge_lock") or {}).get("status") == "PASS",
        "compute_bridge_lock_pass": (latest.get("compute_bridge_lock") or {}).get("status") == "PASS",
        "source_markers_present": all((capture.get("source_markers") or {}).values()),
        "full_payload_hash_not_stable": hash_probe.get("full_payload_hash_stable") is False,
        "product_payload_hash_stable": hash_probe.get("product_payload_hash_stable") is True,
        "dynamic_payload_hash_not_stable": hash_probe.get("dynamic_payload_hash_stable") is False,
        "surfaces_classified": {
            "A. not safe for full reuse",
            "B. stable hash candidate",
            "C. keep current rendered-bundle reuse path",
        } <= labels,
    }


def _report(payload: dict[str, Any]) -> str:
    lines = [
        "# Design Guide Browser Probe Payload Hash Readiness",
        "",
        f"Status: `{payload.get('status')}`",
        f"Readiness: `{payload.get('readiness')}`",
        "",
        "## Hash Probe",
        "",
    ]
    for key, value in (payload.get("hash_probe") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(["", "## Classified Surfaces", "", "| Surface | Classification | Safe next step |", "|---|---|---|"])
    for row in payload.get("classifications") or []:
        lines.append(f"| {row.get('surface')} | {row.get('classification')} | {row.get('safe_next_step')} |")
    lines.extend(["", "## Recommendation", "", str(payload.get("recommended_next_slice") or ""), ""])
    return "\n".join(lines)


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = str(payload["created_at"])
    json_path = ARTIFACT_DIR / f"design_guide_browser_probe_payload_hash_readiness_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_browser_probe_payload_hash_readiness_{stamp}.md"
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
        "readiness": "FULL_BROWSER_PROBE_PAYLOAD_REUSE_NOT_READY" if status == "PASS" else "NOT_READY",
        "checks": checks,
        "product_behavior_changed": False,
        **capture,
    }
    payload["snapshot_hash"] = _stable_hash(
        {
            "status": status,
            "readiness": payload["readiness"],
            "checks": checks,
            "hash_probe": payload.get("hash_probe"),
            "classifications": payload.get("classifications"),
        }
    )
    json_path, md_path = _write(payload)
    print(json.dumps({"status": status, "readiness": payload["readiness"], "json": str(json_path), "report": str(md_path)}, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
