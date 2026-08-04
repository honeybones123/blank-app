"""Cutover plan verifier for SHEAR_FAIL active-repair preview proof.

This is plan-only. It proves the next implementation slice is narrow and
contract/family-owned without moving behaviour in this pass.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"
SHEAR_PACKAGE = ROOT / "design_brain" / "families" / "shear_fail_governs"

RESTAMP_SOURCE = "final_visible_active_shear_repair_family_restamp"
REPLACEMENT_TARGET = "_evaluate_auto_design_candidate("
PLANNED_AUTHORITY = "SHEAR_FAIL_GOVERNS.active_repair_preview_evidence"
ALLOWED_NEW_HELPER = "design_brain.families.shear_fail_governs.active_repair_preview"
NO_TOUCH_SURFACES = (
    "CTA rendering",
    "publication rendering",
    "apply routing",
    "one-click orchestration",
    "visible wording",
    "UI/session/debug ownership",
    "engineering formulas",
    "solver maths",
    "target bands",
    "family chooser",
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
        return {"found": False, "status": "MISSING", "path": None}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"found": True, "status": "UNREADABLE", "path": str(path), "error": f"{type(exc).__name__}: {exc}"}
    status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    if "PASS" in status.upper() or "COMPLETE" in status.upper():
        status = "PASS"
    return {
        "found": True,
        "status": status or "UNKNOWN",
        "path": str(path),
        "readiness": payload.get("readiness"),
        "payload_hash": _stable_hash(payload),
    }


def _target_context() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    index = source.find(f'source="{RESTAMP_SOURCE}"')
    context = source[max(0, index - 1800) : min(len(source), index + 5600)] if index >= 0 else ""
    return {
        "target_source_present": f'source="{RESTAMP_SOURCE}"' in source,
        "replacement_eval_call_present": REPLACEMENT_TARGET in context,
        "target_is_active_shear_only": (
            '"shear" in active_failures_for_active_shear' in context
            and '"bending" not in active_failures_for_active_shear' in context
        ),
        "target_updates_product_truth": all(
            marker in context
            for marker in (
                "contract.update(",
                'out["display_truth"]',
                'out["candidate_search_evidence"]',
                "final_binding_active_shear_repair_restamped",
            )
        ),
        "context_hash": _stable_hash(context),
    }


def _package_context() -> dict[str, Any]:
    return {
        "shear_package_exists": SHEAR_PACKAGE.exists(),
        "runtime_exists": (SHEAR_PACKAGE / "runtime.py").exists(),
        "contract_exists": (SHEAR_PACKAGE / "contract.json").exists(),
        "init_exists": (SHEAR_PACKAGE / "__init__.py").exists(),
    }


def _plan() -> dict[str, Any]:
    return {
        "replacement_target": {
            "file": str(INPUTS_PAGE),
            "source": RESTAMP_SOURCE,
            "current_call": REPLACEMENT_TARGET,
        },
        "new_authority": PLANNED_AUTHORITY,
        "allowed_helper": ALLOWED_NEW_HELPER,
        "preserve_page_owned_surfaces": NO_TOUCH_SURFACES,
        "implementation_rules": (
            "Keep evaluator execution/page plumbing unchanged.",
            "Move only preview proof normalization/decision into SHEAR_FAIL_GOVERNS evidence helper.",
            "Return a plain proof/effect payload that the existing page bridge can consume.",
            "Do not change button label, visible wording, apply route, publication semantics, or repair outcome.",
            "Keep the old source as compatibility/debug reference until cutover verifier passes.",
        ),
        "post_cutover_required_verifier": "shear_fail_governs_active_repair_preview_cutover_implementation",
    }


def _capture() -> dict[str, Any]:
    return {
        "preconditions": {
            "boundary": _latest("shear_fail_governs_active_repair_preview_boundary"),
            "parity": _latest("shear_fail_governs_active_repair_preview_parity"),
            "ownership": _latest("design_guide_active_shear_restamp_ownership_audit"),
            "shear_lock": _latest("shear_fail_governs_lock_verifier"),
            "independence_lock": _latest("design_guide_independence_lock"),
            "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
            "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
        },
        "target_context": _target_context(),
        "package_context": _package_context(),
        "plan": _plan(),
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    preconditions = dict(capture.get("preconditions") or {})
    return {
        "boundary_pass": (preconditions.get("boundary") or {}).get("status") == "PASS",
        "boundary_ready": (preconditions.get("boundary") or {}).get("readiness") == "READY_FOR_PARITY_PROOF",
        "parity_pass": (preconditions.get("parity") or {}).get("status") == "PASS",
        "parity_ready_for_plan": (preconditions.get("parity") or {}).get("readiness") == "READY_FOR_CUTOVER_PLAN",
        "ownership_pass": (preconditions.get("ownership") or {}).get("status") == "PASS",
        "shear_lock_pass": (preconditions.get("shear_lock") or {}).get("status") == "PASS",
        "design_guide_locks_pass": all(
            (preconditions.get(key) or {}).get("status") == "PASS"
            for key in ("independence_lock", "render_bridge_lock", "compute_bridge_lock")
        ),
        "target_callsite_present": all((capture.get("target_context") or {}).get(key) for key in (
            "target_source_present",
            "replacement_eval_call_present",
            "target_is_active_shear_only",
            "target_updates_product_truth",
        )),
        "shear_package_ready": all((capture.get("package_context") or {}).values()),
        "plan_keeps_no_touch_surfaces": set((capture.get("plan") or {}).get("preserve_page_owned_surfaces") or ()) == set(NO_TOUCH_SURFACES),
    }


def _report(payload: dict[str, Any]) -> str:
    lines = [
        "# SHEAR_FAIL_GOVERNS Active Repair Preview Cutover Plan",
        "",
        f"Status: `{payload.get('status')}`",
        f"Readiness: `{payload.get('readiness')}`",
        "",
        "## Scope",
        "",
        "- Plan verifier only.",
        "- No runtime, contract, CTA/publication/apply/render/session/UI behaviour changed.",
        "- No visible wording changed.",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Plan",
            "",
            "```json",
            json.dumps(payload.get("plan") or {}, indent=2, sort_keys=True),
            "```",
            "",
            "## Next Safe Slice",
            "",
            "Implement the narrow helper/effect bridge, then add the cutover implementation verifier. "
            "The old page restamp source should remain as compatibility/debug reference until that verifier passes.",
            "",
        ]
    )
    return "\n".join(lines)


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = str(payload["created_at"])
    json_path = ARTIFACT_DIR / f"shear_fail_governs_active_repair_preview_cutover_plan_{stamp}.json"
    report_path = AUDIT_DIR / f"shear_fail_governs_active_repair_preview_cutover_plan_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    report_path.write_text(_report(payload), encoding="utf-8")
    return json_path, report_path


def main() -> int:
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "schema": "shear_fail_governs_active_repair_preview_cutover_plan.v1",
        "created_at": _stamp(),
        "status": status,
        "readiness": "READY_FOR_NARROW_IMPLEMENTATION" if status == "PASS" else "NOT_READY",
        "product_behaviour_changed": False,
        "family_runtime_changed": False,
        "contract_changed": False,
        "cta_publication_apply_changed": False,
        "checks": checks,
        "failures": [key for key, ok in checks.items() if not ok],
        "snapshot_hash": _stable_hash({"capture": capture, "checks": checks}),
        **capture,
    }
    json_path, report_path = _write(payload)
    print(f"shear_fail_governs_active_repair_preview_cutover_plan {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    print(json.dumps({"status": status, "readiness": payload["readiness"], "failures": payload["failures"]}, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
