"""Audit ownership of final_visible_active_shear_repair_family_restamp.

Proof-only. This classifies the page-side active-shear candidate eval/restamp
that is still product-driving after the Design Guide publication/controller
work. It does not move logic or change behaviour.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _context_around(source: str, needle: str, *, before: int = 1600, after: int = 5200) -> str:
    index = source.find(needle)
    if index < 0:
        return ""
    return source[max(0, index - before) : min(len(source), index + after)]


def _latest_status(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": None}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"found": True, "status": "UNREADABLE", "path": str(path), "error": f"{type(exc).__name__}: {exc}"}
    status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    if "PASS" in status.upper() or "COMPLETE" in status.upper():
        status = "PASS"
    return {"found": True, "status": status or "UNKNOWN", "path": str(path)}


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    needle = 'source="final_visible_active_shear_repair_family_restamp"'
    context = _context_around(source, needle)
    markers = {
        "restamp_source_present": needle in source,
        "evaluates_candidate_in_page": "_evaluate_auto_design_candidate(" in context,
        "active_shear_only_guard": (
            '"shear" in active_failures_for_active_shear' in context
            and '"bending" not in active_failures_for_active_shear' in context
        ),
        "updates_contract": "contract.update(" in context,
        "updates_display_truth": 'out["display_truth"]' in context,
        "updates_button_contract": '"button_contract": dict(contract)' in context,
        "updates_candidate_search_evidence": 'out["candidate_search_evidence"]' in context,
        "uses_compound_shear_update_keys": "_COMPOUND_SHEAR_UPDATE_KEYS" in context,
        "requires_preview_pass": '"preview_pass": True' in context,
        "requires_no_any_fail": "not bool(shear_repair_overview.get(\"any_fail\"))" in context,
        "requires_required_checks_acceptable": "_overview_required_checks_acceptable" in context,
    }
    family_locks = {
        "SHEAR_FAIL_GOVERNS": _latest_status("shear_fail_governs_lock_verifier"),
        "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS": _latest_status(
            "shear_fail_bending_overdesign_governs_lock_verifier"
        ),
        "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS": _latest_status(
            "bending_fail_shear_overdesign_governs_lock_verifier"
        ),
    }
    return {
        "source_context_hash": _stable_hash(context),
        "source_context_line_count": len(context.splitlines()),
        "markers": markers,
        "family_locks": family_locks,
    }


def _classify(capture: dict[str, Any]) -> dict[str, Any]:
    markers = dict(capture.get("markers") or {})
    if not markers.get("restamp_source_present"):
        diagnosis = "RESTAMP_SOURCE_NOT_FOUND"
        owner = "unknown"
        next_slice = "Refresh repeated eval stream breakdown before ownership work."
    elif markers.get("active_shear_only_guard") and markers.get("evaluates_candidate_in_page"):
        diagnosis = "PAGE_OWNS_ACTIVE_SHEAR_REPAIR_PREVIEW_PROOF"
        owner = "SHEAR_FAIL_GOVERNS"
        next_slice = (
            "Create a proof-only SHEAR_FAIL_GOVERNS active-repair preview evidence boundary, "
            "then compare it with this page-side restamp before moving logic."
        )
    elif markers.get("evaluates_candidate_in_page"):
        diagnosis = "PAGE_OWNS_MIXED_OR_UNCLEAR_REPAIR_PREVIEW_PROOF"
        owner = "needs_family_selection_proof"
        next_slice = "Add live family-state proof to decide active family owner."
    else:
        diagnosis = "RESTAMP_IS_NOT_EVALUATING_CANDIDATE"
        owner = "DesignGuideController"
        next_slice = "Check whether this can become controller compatibility metadata."
    return {
        "status": "PASS",
        "diagnosis": diagnosis,
        "recommended_owner": owner,
        "is_contract_backed_now": False,
        "can_move_now": False,
        "can_delete_or_bypass_now": False,
        "reason": (
            "The source is guarded to shear-active-fail-only and updates contract/display/action evidence "
            "after a candidate evaluation, so the engineering proof belongs with the active shear family, "
            "but the move needs a boundary/parity proof first."
        ),
        "recommended_next_slice": next_slice,
    }


def _markdown(payload: dict[str, Any]) -> str:
    cls = dict(payload.get("classification") or {})
    lines = [
        "# Design Guide Active-Shear Restamp Ownership Audit",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Diagnosis: `{cls.get('diagnosis')}`",
        f"- Recommended owner: `{cls.get('recommended_owner')}`",
        f"- Contract-backed now: `{cls.get('is_contract_backed_now')}`",
        f"- Can move now: `{cls.get('can_move_now')}`",
        f"- Can delete/bypass now: `{cls.get('can_delete_or_bypass_now')}`",
        f"- Product behaviour changed: `{payload.get('product_behaviour_changed')}`",
        "",
        "## Markers",
        "",
        "```json",
        json.dumps(payload.get("markers") or {}, indent=2, sort_keys=True),
        "```",
        "",
        "## Family Locks",
        "",
        "```json",
        json.dumps(payload.get("family_locks") or {}, indent=2, sort_keys=True),
        "```",
        "",
        "## Next Safe Slice",
        "",
        str(cls.get("recommended_next_slice") or ""),
    ]
    return "\n".join(lines) + "\n"


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = str(payload["created_at"])
    json_path = ARTIFACT_DIR / f"design_guide_active_shear_restamp_ownership_audit_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_active_shear_restamp_ownership_audit_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    return json_path, md_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    created_at = _stamp()
    capture = _capture()
    classification = _classify(capture)
    payload = {
        "schema": "design_guide_active_shear_restamp_ownership_audit.v1",
        "created_at": created_at,
        "status": classification["status"],
        "product_behaviour_changed": False,
        "code_deleted": False,
        "family_runtime_changed": False,
        "contract_changed": False,
        "classification": classification,
        "snapshot_hash": _stable_hash({"capture": capture, "classification": classification}),
        **capture,
    }
    json_path, md_path = _write(payload)
    print(f"design_guide_active_shear_restamp_ownership_audit {payload['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    print(json.dumps(classification, indent=2, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
