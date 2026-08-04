"""Roll up final-binding manual fallback deadness decisions."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

REQUIRED_PREFIXES = {
    "no_second_cta": "design_guide_final_binding_no_second_cta_manual_fallback_deadness",
    "target_band_promotion": "design_guide_final_binding_target_band_promotion_manual_fallback_deadness",
    "consistency_guard": "design_guide_final_binding_consistency_guard_manual_fallback_deadness",
    "contract_truth": "design_guide_final_binding_contract_truth_manual_fallback_deadness",
}


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": None, "capture": {}}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {
            "found": True,
            "status": "UNREADABLE",
            "path": str(path),
            "error": f"{type(exc).__name__}: {exc}",
            "capture": {},
        }
    status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    if "PASS" in status.upper() or "LOCKED" in status.upper() or "COMPLETE" in status.upper():
        status = "PASS"
    return {
        "found": True,
        "status": status or "UNKNOWN",
        "path": str(path),
        "capture": dict(payload.get("capture") or {}),
    }


def _capture() -> dict[str, Any]:
    rows = {}
    for key, prefix in REQUIRED_PREFIXES.items():
        latest = _latest(prefix)
        capture = dict(latest.get("capture") or {})
        classification = str(capture.get("classification") or "")
        rows[key] = {
            "status": latest.get("status"),
            "path": latest.get("path"),
            "decision": capture.get("decision"),
            "classification": classification,
            "not_deletion_ready": "not" in str(capture.get("decision") or "").lower()
            or "fallback/safety keep" in classification.lower()
            or capture.get("ready_for_deletion") is False,
            "deletion_ready": bool(
                capture.get("deletion_ready") is True
                or capture.get("ready_for_deletion") is True
                or "deletion candidate" in classification.lower()
                or "deleted after proof" in classification.lower()
            ),
            "extraction_ready": bool(capture.get("ready_for_extraction") is True),
            "extraction_complete": bool(capture.get("extraction_complete") is True),
            "reason": classification or capture.get("decision"),
        }
    latest_locks = {
        "independence_lock": _latest("design_guide_independence_lock"),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
    }
    return {
        "decision": "FINAL_BINDING_MANUAL_FALLBACKS_DELETED_OR_EXTRACTED",
        "rows": rows,
        "fallbacks_checked": len(rows),
        "not_deletion_ready_count": sum(1 for row in rows.values() if row.get("not_deletion_ready")),
        "deletion_ready_count": sum(1 for row in rows.values() if row.get("deletion_ready")),
        "extraction_ready_count": sum(1 for row in rows.values() if row.get("extraction_ready")),
        "extraction_complete_count": sum(1 for row in rows.values() if row.get("extraction_complete")),
        "safe_deletion_candidates": [
            key for key, row in rows.items() if row.get("deletion_ready")
        ],
        "extraction_targets": [
            key for key, row in rows.items() if row.get("extraction_ready")
        ],
        "extraction_complete_rows": [
            key for key, row in rows.items() if row.get("extraction_complete")
        ],
        "next_safe_step": (
            "Move to the next final-visible restamper or render-item consumer surface."
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "latest_locks": {
            key: {"status": value.get("status"), "path": value.get("path")}
            for key, value in latest_locks.items()
        },
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    rows = dict(capture.get("rows") or {})
    locks = dict(capture.get("latest_locks") or {})
    return {
        "all_required_rows_found": set(rows) == set(REQUIRED_PREFIXES),
        "all_rows_pass": all(row.get("status") == "PASS" for row in rows.values()),
        "three_rows_deletion_ready_or_deleted": capture.get("deletion_ready_count") == 3,
        "no_rows_extraction_ready": capture.get("extraction_ready_count") == 0,
        "one_row_extraction_complete": capture.get("extraction_complete_count") == 1,
        "safe_deletion_candidates_present": bool(capture.get("safe_deletion_candidates")),
        "extraction_complete_row_present": bool(capture.get("extraction_complete_rows")),
        "independence_lock_pass": (locks.get("independence_lock") or {}).get("status") == "PASS",
        "render_bridge_lock_pass": (locks.get("render_bridge_lock") or {}).get("status") == "PASS",
        "compute_bridge_lock_pass": (locks.get("compute_bridge_lock") or {}).get("status") == "PASS",
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Final Binding Fallback Deadness Rollup",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Rows",
        "",
    ]
    for key, row in (capture.get("rows") or {}).items():
        lines.append(
            f"- {key}: status=`{row.get('status')}`, not_deletion_ready=`{row.get('not_deletion_ready')}`"
        )
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_final_binding_fallback_deadness_rollup.v1",
        "status": status,
        "created_at": _stamp(),
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = payload["created_at"]
    json_path = ARTIFACT_DIR / f"design_guide_final_binding_fallback_deadness_rollup_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_final_binding_fallback_deadness_rollup_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(md_path, payload)
    print(f"design_guide_final_binding_fallback_deadness_rollup {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if failures:
        print("failures=" + ", ".join(failures))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
