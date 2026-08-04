from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"
APP_PAGE = ROOT / "app.py"
APP_CONTRACT_BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
APPLY_PAYLOAD = ROOT / "inputs_page_modules" / "apply_payload.py"
RUN_FAMILY_FUZZ = ROOT / "tools" / "verification" / "run_family_10_fuzz_audit.py"
CURRENT_FAMILY_RUNTIME_CERT = "design_brain_current_universal_family_evidence"
CURRENT_FAMILY_VISUAL = "design_guide_family_browser_live_visual_consistency"
CURRENT_APPLY_STABILITY = "app_stability_inputs_apply_10x_workflow_lock"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _status_from_payload(payload: dict[str, Any]) -> str:
    for key in ("status", "result", "lock_status"):
        value = payload.get(key)
        if isinstance(value, str):
            upper = value.upper()
            if "PASS" in upper or "LOCKED" in upper or "COMPLETE" in upper:
                return "PASS"
            if "PARTIAL" in upper:
                return "PARTIAL"
            if "FAIL" in upper or "BLOCKED" in upper:
                return "FAIL"
            return upper
    if payload.get("passed") is True:
        return "PASS"
    if payload.get("passed") is False:
        return "FAIL"
    return "UNKNOWN"


def _latest_payload(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "path": None, "payload": {}, "status": "MISSING"}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "found": True,
            "path": str(path),
            "payload": {},
            "status": "UNREADABLE",
            "error": f"{type(exc).__name__}: {exc}",
        }
    return {
        "found": True,
        "path": str(path),
        "payload": payload,
        "status": _status_from_payload(payload),
    }


def _latest_payload_anywhere(prefix: str) -> dict[str, Any]:
    paths = sorted(
        list(ARTIFACT_DIR.glob(f"{prefix}_*.json"))
        + list(AUDIT_DIR.glob(f"{prefix}_*.json")),
        key=lambda path: path.stat().st_mtime,
    )
    if not paths:
        return {"found": False, "path": None, "payload": {}, "status": "MISSING"}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "found": True,
            "path": str(path),
            "payload": {},
            "status": "UNREADABLE",
            "error": f"{type(exc).__name__}: {exc}",
        }
    return {"found": True, "path": str(path), "payload": payload, "status": _status_from_payload(payload)}


def _family_architecture_expected_count(payload: dict[str, Any]) -> int:
    families = payload.get("families")
    if isinstance(families, list):
        return len(families)
    summary = dict(payload.get("summary") or {})
    return int(summary.get("pass") or 0) + int(summary.get("partial") or 0) + int(summary.get("fail") or 0)


def _iter_dict_values(value: Any) -> list[Any]:
    output: list[Any] = []
    if isinstance(value, dict):
        output.append(value)
        for child in value.values():
            output.extend(_iter_dict_values(child))
    elif isinstance(value, list):
        for child in value:
            output.extend(_iter_dict_values(child))
    return output


def _post_apply_contract_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in _iter_dict_values(payload):
        contract = item.get("post_apply_green_pass_visual_contract")
        if isinstance(contract, dict):
            rows.append(dict(contract))
    return rows


def _family_names_from_fuzz(payload: dict[str, Any]) -> list[str]:
    families = payload.get("families")
    names: list[str] = []
    if isinstance(families, list):
        for row in families:
            if isinstance(row, dict):
                name = row.get("family") or row.get("family_id")
                if name:
                    names.append(str(name))
    elif isinstance(families, dict):
        names.extend(str(key) for key in families.keys())
    return sorted(dict.fromkeys(names))


def _find_latest_broad_post_apply_fuzz(expected_family_count: int) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    for path in sorted(ARTIFACT_DIR.glob("family_10_fuzz_audit_*.json"), key=lambda item: item.stat().st_mtime):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            payload = json.loads(text)
        except Exception as exc:
            candidates.append(
                {
                    "path": str(path),
                    "status": "UNREADABLE",
                    "error": f"{type(exc).__name__}: {exc}",
                    "broad_enough": False,
                }
            )
            continue
        summary = dict(payload.get("summary") or {})
        families_audited = int(summary.get("families_audited") or len(_family_names_from_fuzz(payload)))
        contracts = _post_apply_contract_rows(payload)
        has_visual_contract = "post_apply_green_pass_visual_contract" in text
        bad_contracts = [
            row
            for row in contracts
            if not bool(row.get("pass_visible"))
            or bool(row.get("blocked_visible"))
            or bool(row.get("cleanup_visible"))
            or bool(row.get("pending_shell_visible"))
            or bool(row.get("raw_status_visible"))
        ]
        candidates.append(
            {
                "path": str(path),
                "status": _status_from_payload(payload),
                "families_audited": families_audited,
                "families": _family_names_from_fuzz(payload),
                "has_post_apply_visual_contract": has_visual_contract,
                "post_apply_visual_contract_count": len(contracts),
                "bad_post_apply_visual_contract_count": len(bad_contracts),
                "broad_enough": (
                    has_visual_contract
                    and families_audited >= expected_family_count
                    and _status_from_payload(payload) == "PASS"
                    and len(contracts) > 0
                    and not bad_contracts
                ),
            }
        )
    broad = [row for row in candidates if row.get("broad_enough")]
    latest = candidates[-1] if candidates else {}
    return {
        "latest": latest,
        "latest_broad_pass": broad[-1] if broad else {},
        "candidate_count": len(candidates),
    }


def _write_report(snapshot: dict[str, Any], report_path: Path) -> None:
    latest_fuzz = dict(snapshot.get("latest_family_10_fuzz") or {}).get("latest") or {}
    broad_fuzz = dict(snapshot.get("latest_family_10_fuzz") or {}).get("latest_broad_pass") or {}
    lines = [
        "# Design Brain Shared Post-Apply Readiness Lock",
        "",
        f"Status: `{snapshot['status']}`",
        "",
        "## Scope",
        "",
        "This shared lock checks whether Apply can be treated as settled only when post-Apply output reaches the final Design Guide card, rather than leaving a pending shell, stale raw status block, or non-final card.",
        "",
        "## Ownership",
        "",
        "- Apply payload safety: shared Apply payload contracts plus page-owned Apply routing.",
        "- Post-Apply readiness: controller/publication readiness gates plus browser/live settled-card proof.",
        "- UI/render layer: render-only, cannot reinterpret engineering truth after Apply.",
        "",
        "## Static Checks",
        "",
    ]
    for key, value in snapshot.get("static_checks", {}).items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Latest Evidence", ""])
    for key, value in (snapshot.get("latest_evidence") or {}).items():
        lines.append(f"- `{key}`: `{value.get('status')}` at `{value.get('path')}`")
    lines.extend(
        [
            "",
            "## Family 10-Fuzz Post-Apply Visual Proof",
            "",
            f"- Expected current family count: `{snapshot.get('expected_family_count')}`",
            f"- Latest fuzz path: `{latest_fuzz.get('path')}`",
            f"- Latest fuzz status: `{latest_fuzz.get('status')}`",
            f"- Latest fuzz families audited: `{latest_fuzz.get('families_audited')}`",
            f"- Latest fuzz post-Apply visual contracts: `{latest_fuzz.get('post_apply_visual_contract_count')}`",
            f"- Latest broad passing proof: `{broad_fuzz.get('path')}`",
            "",
            "## Blockers",
            "",
        ]
    )
    if snapshot.get("blockers"):
        lines.extend(f"- {blocker}" for blocker in snapshot["blockers"])
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Next Safe Slice",
            "",
            "Create or refresh a broad browser/live post-Apply settled-final-card proof for all currently locked/affected families. The proof must include `post_apply_green_pass_visual_contract`, final-card DOM readiness, no pending shell, no raw Status block, and unchanged Apply semantics.",
            "",
            f"JSON: `{snapshot['artifact']}`",
        ]
    )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    inputs_source = _read(INPUTS_PAGE)
    app_source = _read(APP_PAGE) if APP_PAGE.exists() else ""
    bridge_source = _read(APP_CONTRACT_BRIDGE) if APP_CONTRACT_BRIDGE.exists() else ""
    apply_payload_source = _read(APPLY_PAYLOAD) if APPLY_PAYLOAD.exists() else ""
    current_apply_sources = "\n".join([inputs_source, app_source, bridge_source, apply_payload_source])
    fuzz_source = _read(RUN_FAMILY_FUZZ) if RUN_FAMILY_FUZZ.exists() else ""
    latest_arch = _latest_payload("family_architecture_end_to_end_audit")
    latest_apply_lock = _latest_payload("design_brain_shared_apply_payload_lock")
    latest_apply_safety = _latest_payload("design_guide_apply_current_state_safety")
    latest_shear_readiness = _latest_payload("design_guide_shear_fail_bending_overdesign_post_click_card_readiness")
    latest_shear_gate = _latest_payload("design_guide_shear_fail_bending_overdesign_pending_completion_gate_audit")
    latest_shear_dom = _latest_payload("design_guide_shear_fail_bending_overdesign_slot_dom_replacement")
    latest_family_visual = _latest_payload(CURRENT_FAMILY_VISUAL)
    latest_family_runtime = _latest_payload_anywhere(CURRENT_FAMILY_RUNTIME_CERT)
    latest_apply_stability = _latest_payload(CURRENT_APPLY_STABILITY)

    expected_family_count = _family_architecture_expected_count(dict(latest_arch.get("payload") or {}))
    family_fuzz = _find_latest_broad_post_apply_fuzz(expected_family_count)

    static_checks = {
        "apply_in_flight_key_exists": "DESIGN_GUIDE_COMPONENT_APPLY_IN_FLIGHT_KEY" in current_apply_sources,
        "apply_in_flight_clearer_exists": "def _clear_design_guide_component_apply_in_flight(" in current_apply_sources,
        "apply_completion_clears_in_flight": '_clear_design_guide_component_apply_in_flight("apply_resolved_candidate_completed")' in current_apply_sources,
        "post_apply_overview_recorded": '"post_apply_overview": dict(post_overview)' in current_apply_sources,
        "post_apply_all_key_pass_recorded": '"post_apply_all_key_pass": bool(post_apply_all_key_pass)' in current_apply_sources,
        "post_apply_any_fail_recorded": '"post_apply_any_fail": bool(post_apply_any_fail)' in current_apply_sources,
        "terminal_post_apply_required_checks_pass_exists": "post_apply_required_checks_pass" in current_apply_sources,
        "fuzz_visual_contract_function_exists": "def _post_apply_green_pass_visual_contract(" in fuzz_source,
        "fuzz_pending_shell_check_exists": "pending_shell_visible" in fuzz_source,
        "fuzz_raw_status_check_exists": "raw_status_visible" in fuzz_source,
        "current_family_runtime_certification_source_exists": bool(latest_family_runtime.get("found")),
        "current_family_visual_source_exists": bool(latest_family_visual.get("found")),
        "current_apply_stability_source_exists": bool(latest_apply_stability.get("found")),
    }

    latest_evidence = {
        "family_architecture_end_to_end_audit": {
            "status": latest_arch.get("status"),
            "path": latest_arch.get("path"),
        },
        "design_brain_shared_apply_payload_lock": {
            "status": latest_apply_lock.get("status"),
            "path": latest_apply_lock.get("path"),
        },
        "design_guide_apply_current_state_safety": {
            "status": latest_apply_safety.get("status"),
            "path": latest_apply_safety.get("path"),
        },
        "narrow_shear_post_click_card_readiness": {
            "status": latest_shear_readiness.get("status"),
            "path": latest_shear_readiness.get("path"),
        },
        "narrow_shear_pending_completion_gate": {
            "status": latest_shear_gate.get("status"),
            "path": latest_shear_gate.get("path"),
        },
        "narrow_shear_slot_dom_replacement": {
            "status": latest_shear_dom.get("status"),
            "path": latest_shear_dom.get("path"),
        },
        "current_family_runtime_certification": {
            "status": latest_family_runtime.get("status"),
            "path": latest_family_runtime.get("path"),
        },
        "current_family_browser_visual_consistency": {
            "status": latest_family_visual.get("status"),
            "path": latest_family_visual.get("path"),
        },
        "current_apply_stability": {
            "status": latest_apply_stability.get("status"),
            "path": latest_apply_stability.get("path"),
        },
    }

    blockers: list[str] = []
    for key, passed in static_checks.items():
        if not passed:
            blockers.append(f"static check failed: {key}")
    if latest_arch.get("status") != "PASS":
        blockers.append("family architecture end-to-end audit is not PASS")
    if latest_apply_lock.get("status") != "PASS":
        blockers.append("shared Apply payload lock is not PASS")
    if latest_apply_safety.get("status") != "PASS":
        blockers.append("Apply current-state safety proof is not PASS")

    runtime_payload = dict(latest_family_runtime.get("payload") or {})
    expected_runtime_count = int(
        runtime_payload.get("expected_family_count")
        or runtime_payload.get("family_count")
        or expected_family_count
    )
    runtime_count = int(
        runtime_payload.get("family_count")
        or runtime_payload.get("certified_count")
        or len(runtime_payload.get("families") or [])
    )
    if latest_family_runtime.get("status") != "PASS":
        blockers.append("current universal family runtime certification is not PASS")
    if runtime_count < expected_runtime_count:
        blockers.append(
            f"current runtime certification covers {runtime_count} of {expected_runtime_count} required families"
        )
    if latest_family_visual.get("status") != "PASS":
        blockers.append("current family browser/live visual consistency proof is not PASS")
    if latest_apply_stability.get("status") != "PASS":
        blockers.append("current 10x Apply stability proof is not PASS")

    status = "LOCKED" if not blockers else "DEFERRED_WITH_BLOCKER"
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    artifact_path = ARTIFACT_DIR / f"design_brain_shared_post_apply_readiness_lock_{stamp}.json"
    report_path = AUDIT_DIR / f"design_brain_shared_post_apply_readiness_lock_{stamp}.md"
    snapshot = {
        "schema": "design_brain_shared_post_apply_readiness_lock.v1",
        "status": status,
        "lock_status": status,
        "component": "post-Apply readiness",
        "expected_family_count": expected_family_count,
        "static_checks": static_checks,
        "latest_evidence": latest_evidence,
        "latest_family_10_fuzz": family_fuzz,
        "current_post_apply_evidence": {
            "family_runtime_certification": latest_family_runtime,
            "family_browser_visual_consistency": latest_family_visual,
            "apply_stability": latest_apply_stability,
            "certified_family_count": runtime_count,
        },
        "blockers": list(dict.fromkeys(blockers)),
        "artifact": str(artifact_path),
        "report": str(report_path),
    }
    artifact_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(snapshot, report_path)
    print(f"design_brain_shared_post_apply_readiness_lock {status}")
    print(f"json={artifact_path}")
    print(f"report={report_path}")
    if blockers:
        print("blockers=" + "; ".join(snapshot["blockers"]))
    return 0 if status == "LOCKED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
