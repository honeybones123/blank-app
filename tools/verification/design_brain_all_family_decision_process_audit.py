"""Audit every Design Brain family against the required decision process.

Proof-only. This audit does not change product behaviour. It composes the
latest family architecture artifacts and the current global publication/render
locks into the decision ladder the product must follow:

current truth -> family classification -> family ladder -> candidate
evaluation/ranking -> final outcome -> FinalDesignGuidePublication -> render.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

FAMILY_ARCH_PREFIX = "family_architecture_end_to_end_audit"

GLOBAL_LOCKS = {
    "classification_contract": "family_classification_contract_check",
    "family_chooser_regression": "family_chooser_classification_regression",
    "family_classification_lock": "family_classification_lock_verifier",
    "locked_family_live_wiring": "locked_family_live_wiring_snapshot",
    "cta_button_contract": "cta_button_contract_check",
    "design_guide_independence_lock": "design_guide_independence_lock",
    "render_bridge_lock": "design_guide_render_bridge_lock",
    "compute_publication_bridge_lock": "design_guide_compute_resolver_publication_bridge_lock",
    "zero_authority_inventory_lock": "design_brain_inputs_page_zero_authority_inventory_lock",
}

PROCESS_STEPS = (
    "compute_current_truth",
    "classify_governing_family",
    "run_selected_family_ladder",
    "evaluate_filter_rank_candidates",
    "choose_final_outcome",
    "publish_final_design_guide_publication",
    "render_publication_only",
)

LIVE_LOCK_SLUGS = {
    "BENDING_FAIL_GOVERNS": "bending_fail_governs",
    "SHEAR_FAIL_GOVERNS": "shear_fail_governs",
    "BENDING_OVERDESIGN_GOVERNS": "bending_overdesign_governs",
    "SHEAR_OVERDESIGN_GOVERNS": "shear_overdesign_governs",
    "COMBINED_BENDING_SHEAR_FAIL_GOVERNS": "combined_bending_shear_fail",
    "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS": "bending_fail_shear_overdesign_governs",
    "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS": "shear_fail_bending_overdesign_governs",
    "COMBINED_OVERDESIGN_GOVERNS": "combined_overdesign",
    "SERVICEABILITY_GOVERNS": "serviceability_governs",
}


def _status(payload: dict[str, Any]) -> str:
    for key in ("status", "result", "lock_status"):
        value = payload.get(key)
        if not isinstance(value, str):
            continue
        upper = value.upper()
        if "PASS" in upper or "COMPLETE" in upper or "LOCKED" in upper:
            return "PASS"
        if "PARTIAL" in upper:
            return "PARTIAL"
        if "FAIL" in upper or "BLOCKED" in upper or "INCOMPLETE" in upper:
            return "FAIL"
        return value
    if payload.get("passed") is True:
        return "PASS"
    if payload.get("passed") is False:
        return "FAIL"
    return "UNKNOWN"


def _latest(prefix: str) -> dict[str, Any]:
    candidates = sorted(
        ARTIFACT_DIR.glob(f"{prefix}_*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        return {"found": False, "status": "MISSING", "path": None, "payload": {}}
    path = candidates[0]
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
    return {
        "found": True,
        "status": _status(payload),
        "path": str(path),
        "payload": payload,
    }


def _strict_live_lock_for_family(family_id: str) -> dict[str, Any]:
    slug = LIVE_LOCK_SLUGS.get(str(family_id or ""), str(family_id or "").lower())
    row = _latest(f"{slug}_live_fuzz_regression_lock_gate")
    payload = dict(row.get("payload") or {})
    locked = str(payload.get("lock_status") or "").upper() == "LOCKED"
    return {
        "found": row.get("found"),
        "status": "PASS" if locked else row.get("status"),
        "path": row.get("path"),
        "locked": locked,
    }


def _refresh_family_architecture() -> dict[str, Any]:
    script = ROOT / "tools" / "verification" / "family_architecture_end_to_end_audit.py"
    proc = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=180,
    )
    latest = _latest(FAMILY_ARCH_PREFIX)
    latest["refresh_returncode"] = proc.returncode
    latest["refresh_stdout_tail"] = proc.stdout[-4000:]
    latest["refresh_stderr_tail"] = proc.stderr[-4000:]
    return latest


def _family_process_row(family: dict[str, Any], global_gates: dict[str, dict[str, Any]]) -> dict[str, Any]:
    checks = dict(family.get("checks") or {})
    family_id = str(family.get("family_id") or "")
    strict_live_lock = _strict_live_lock_for_family(family_id)
    strict_live_locked = bool(strict_live_lock.get("locked"))
    family_status = "PASS" if strict_live_locked else str(family.get("status") or "").upper()
    step_checks = {
        "compute_current_truth": (
            global_gates["classification_contract"]["status"] == "PASS"
            and global_gates["family_classification_lock"]["status"] == "PASS"
        ),
        "classify_governing_family": (
            global_gates["classification_contract"]["status"] == "PASS"
            and global_gates["family_chooser_regression"]["status"] == "PASS"
            and global_gates["family_classification_lock"]["status"] == "PASS"
        ),
        "run_selected_family_ladder": (
            checks.get("runtime_or_ladder_passed") is True
            and checks.get("lock_passed") is True
        ),
        "evaluate_filter_rank_candidates": (
            checks.get("runtime_or_ladder_passed") is True
            and checks.get("product_path_evidence_passed") is True
        ),
        "choose_final_outcome": (
            strict_live_locked
            or (
                family_status == "PASS"
                and checks.get("product_path_evidence_passed") is True
                and checks.get("apply_effect_evidence_passed") is True
            )
        ),
        "publish_final_design_guide_publication": (
            global_gates["design_guide_independence_lock"]["status"] == "PASS"
            and global_gates["cta_button_contract"]["status"] == "PASS"
        ),
        "render_publication_only": (
            global_gates["render_bridge_lock"]["status"] == "PASS"
            and global_gates["compute_publication_bridge_lock"]["status"] == "PASS"
            and global_gates["zero_authority_inventory_lock"]["status"] == "PASS"
        ),
    }
    gaps = [step for step in PROCESS_STEPS if not step_checks.get(step)]
    return {
        "family_id": family_id,
        "family_status": family_status,
        "raw_family_status": family.get("status"),
        "strict_live_lock": strict_live_lock,
        "checks": checks,
        "process_steps": step_checks,
        "decision_process_followed": not gaps,
        "gaps": gaps,
        "next_action": (
            "PROCESS_LOCKED"
            if not gaps
            else "repair global publication/render lock or family proof for: " + ", ".join(gaps)
        ),
    }


def _capture() -> dict[str, Any]:
    family_arch = _refresh_family_architecture()
    family_payload = dict(family_arch.get("payload") or {})
    global_gates = {name: _latest(prefix) for name, prefix in GLOBAL_LOCKS.items()}
    families = list(family_payload.get("families") or [])
    family_rows = [_family_process_row(row, global_gates) for row in families]
    failing_global_gates = [
        name for name, row in global_gates.items() if row.get("status") != "PASS"
    ]
    failing_family_rows = [
        row["family_id"] for row in family_rows if not row["decision_process_followed"]
    ]
    return {
        "family_architecture": {
            "status": family_arch.get("status"),
            "path": family_arch.get("path"),
            "refresh_returncode": family_arch.get("refresh_returncode"),
            "refresh_stdout_tail": family_arch.get("refresh_stdout_tail"),
            "refresh_stderr_tail": family_arch.get("refresh_stderr_tail"),
            "family_counts": {
                "pass": family_payload.get("pass"),
                "partial": family_payload.get("partial"),
                "fail": family_payload.get("fail"),
            },
        },
        "global_gates": {
            name: {
                "status": row.get("status"),
                "path": row.get("path"),
                "found": row.get("found"),
            }
            for name, row in global_gates.items()
        },
        "families": family_rows,
        "summary": {
            "family_count": len(family_rows),
            "family_level_all_pass": bool(family_rows)
            and all(str(row.get("family_status") or "").upper() == "PASS" for row in family_rows),
            "all_decision_processes_followed": bool(family_rows)
            and not failing_global_gates
            and not failing_family_rows,
            "failing_global_gates": failing_global_gates,
            "families_with_process_gaps": failing_family_rows,
            "product_behavior_changed": False,
        },
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    summary = dict(capture.get("summary") or {})
    lines = [
        "# Design Brain All-Family Decision Process Audit",
        "",
        f"Status: `{payload.get('status')}`",
        f"Created: `{payload.get('created_at')}`",
        "",
        "## Required Process",
        "",
    ]
    for index, step in enumerate(PROCESS_STEPS, start=1):
        lines.append(f"{index}. `{step}`")
    lines.extend(
        [
            "",
            "## Executive Summary",
            "",
            f"- Families audited: `{summary.get('family_count')}`",
            f"- Family-level architecture all pass: `{summary.get('family_level_all_pass')}`",
            f"- All decision processes fully followed: `{summary.get('all_decision_processes_followed')}`",
            f"- Product behaviour changed: `{summary.get('product_behavior_changed')}`",
            f"- Failing global gates: `{', '.join(summary.get('failing_global_gates') or []) or '-'}`",
            "",
            "## Global Gates",
            "",
            "| Gate | Status | Artifact |",
            "| --- | --- | --- |",
        ]
    )
    for name, row in dict(capture.get("global_gates") or {}).items():
        lines.append(f"| `{name}` | `{row.get('status')}` | `{row.get('path') or '-'}` |")
    lines.extend(
        [
            "",
            "## Family Decision Matrix",
            "",
            "| Family | Family Status | Process Followed | Gaps |",
            "| --- | --- | ---: | --- |",
        ]
    )
    for row in capture.get("families") or []:
        lines.append(
            "| `{family}` | `{status}` | `{followed}` | {gaps} |".format(
                family=row.get("family_id"),
                status=row.get("family_status"),
                followed=row.get("decision_process_followed"),
                gaps=", ".join(row.get("gaps") or []) or "-",
            )
        )
    lines.extend(
        [
            "",
            "## Step Detail",
            "",
        ]
    )
    for row in capture.get("families") or []:
        lines.append(f"### {row.get('family_id')}")
        for step, passed in dict(row.get("process_steps") or {}).items():
            lines.append(f"- `{step}`: `{passed}`")
        lines.append(f"- next action: `{row.get('next_action')}`")
        lines.append("")
    lines.extend(
        [
            "## Conclusion",
            "",
            (
                "PASS: every tracked family follows the required process."
                if payload.get("status") == "PASS"
                else "FAIL: family-level evidence is present, but the full Design Guide process is not locked until the listed global gates are green."
            ),
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    status = "PASS" if (capture.get("summary") or {}).get("all_decision_processes_followed") else "FAIL"
    payload = {
        "status": status,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "capture": capture,
    }
    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"design_brain_all_family_decision_process_audit_{stamp}.json"
    report_path = AUDIT_DIR / f"design_brain_all_family_decision_process_audit_{stamp}.md"
    payload["artifact"] = str(json_path)
    payload["report"] = str(report_path)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_brain_all_family_decision_process_audit {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
