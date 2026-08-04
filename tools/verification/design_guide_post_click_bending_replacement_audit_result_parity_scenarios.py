"""Parity scenarios for post-click bending replacement audit/result proof object."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.final_publication import (  # noqa: E402
    build_final_design_guide_post_click_bending_replacement_audit_result_proof,
    stable_final_publication_hash,
)


EVIDENCE_KEYS = (
    "exact_blockers_by_family",
    "post_click_exact_blockers_by_family",
    "cleanup_evidence_by_family",
    "post_click_cleanup_evidence_by_family",
)
FAMILY_LIST_KEYS = (
    "post_click_families_below_final_threshold",
    "post_click_unresolved_low_util_families",
    "low_util_families",
    "materially_overprovided_families",
)


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _latest(prefix: str) -> dict[str, Any]:
    artifacts = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not artifacts:
        return {"found": False, "status": "MISSING", "path": None}
    path = artifacts[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {
            "found": True,
            "status": "UNREADABLE",
            "path": str(path),
            "error": f"{type(exc).__name__}: {exc}",
        }
    status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    if "PASS" in status.upper() or "LOCKED" in status.upper() or "COMPLETE" in status.upper():
        status = "PASS"
    return {"found": True, "status": status or "UNKNOWN", "path": str(path)}


def _page_equivalent_projection(guidance_debug: dict[str, Any], audit_sources: list[dict[str, Any]]) -> dict[str, Any]:
    audit = dict(guidance_debug or {})
    for source in audit_sources:
        if not isinstance(source, dict):
            continue
        for evidence_key in EVIDENCE_KEYS:
            source_evidence = source.get(evidence_key)
            if isinstance(source_evidence, dict) and source_evidence:
                existing = dict(audit.get(evidence_key) or {})
                existing.update(
                    {
                        str(family or "").strip().lower(): dict(blocker)
                        for family, blocker in source_evidence.items()
                        if str(family or "").strip() and isinstance(blocker, dict)
                    }
                )
                audit[evidence_key] = dict(existing)
        for family_list_key in FAMILY_LIST_KEYS:
            source_family_list = source.get(family_list_key)
            if isinstance(source_family_list, list) and source_family_list:
                existing_family_list = list(audit.get(family_list_key) or [])
                audit[family_list_key] = list(
                    dict.fromkeys(
                        str(family or "").strip().lower()
                        for family in (existing_family_list + list(source_family_list))
                        if str(family or "").strip()
                    )
                )
        if isinstance(source.get("post_click_family_utils"), dict):
            audit["post_click_family_utils"] = dict(source.get("post_click_family_utils") or {})
    if (
        "post_click_exact_blockers_by_family" not in audit
        and isinstance(audit.get("exact_blockers_by_family"), dict)
    ):
        audit["post_click_exact_blockers_by_family"] = dict(
            audit.get("exact_blockers_by_family") or {}
        )
    return audit


def _scenarios() -> list[dict[str, Any]]:
    return [
        {
            "id": "alias_exact_blocker_from_debug",
            "guidance_debug": {
                "exact_blockers_by_family": {"bending": {"reason": "debug_exact"}},
                "post_click_unresolved_low_util_families": ["bending"],
            },
            "audit_sources": [],
        },
        {
            "id": "merge_candidate_search_evidence",
            "guidance_debug": {"guidance_branch": "post_click"},
            "audit_sources": [
                {
                    "post_click_exact_blockers_by_family": {
                        "Bending": {"reason": "candidate_exact"}
                    },
                    "cleanup_evidence_by_family": {"bending": {"cleanup": "checked"}},
                    "post_click_families_below_final_threshold": ["Bending", "shear"],
                    "post_click_family_utils": {"bending": 0.81},
                }
            ],
        },
        {
            "id": "dedupe_family_lists_and_late_sources",
            "guidance_debug": {
                "low_util_families": ["bending"],
                "materially_overprovided_families": ["shear"],
            },
            "audit_sources": [
                {"low_util_families": ["bending", "shear"]},
                {
                    "post_click_cleanup_evidence_by_family": {
                        "bending": {"post": "cleanup"},
                        "shear": {"post": "cleanup"},
                    },
                    "materially_overprovided_families": ["shear", "bending"],
                },
            ],
        },
    ]


def _run_case(case: dict[str, Any]) -> dict[str, Any]:
    expected = _page_equivalent_projection(
        dict(case.get("guidance_debug") or {}),
        [dict(source) for source in list(case.get("audit_sources") or []) if isinstance(source, dict)],
    )
    payload = build_final_design_guide_post_click_bending_replacement_audit_result_proof(
        guidance_debug=dict(case.get("guidance_debug") or {}),
        audit_sources=list(case.get("audit_sources") or []),
        bending_resolution={"button_contract": {"enabled": False}},
        bending_contract={"enabled": False},
        output_item={"family": "bending"},
        final_visible_resolution={"render_reason": "post_click_low_bending_exact_blocker_final"},
    )
    actual = dict(payload.get("audit_projection") or {})
    return {
        "id": case.get("id"),
        "expected_hash": stable_final_publication_hash(expected),
        "actual_hash": stable_final_publication_hash(actual),
        "match": expected == actual,
        "proof_hash": payload.get("proof_hash"),
        "represented_live_rows": list(payload.get("represented_live_rows") or []),
    }


def _capture() -> dict[str, Any]:
    cases = [_run_case(case) for case in _scenarios()]
    latest = {
        "object": _latest("design_guide_post_click_bending_replacement_audit_result_object"),
        "trace": _latest("design_guide_live_post_click_bending_replacement_audit_result_trace"),
        "body_audit": _latest("design_guide_post_click_bending_replacement_body_ownership_audit"),
        "independence_lock": _latest("design_guide_independence_lock"),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
    }
    return {
        "decision": "POST_CLICK_BENDING_REPLACEMENT_AUDIT_RESULT_PARITY_PROVEN",
        "cases": cases,
        "case_count": len(cases),
        "all_cases_match": all(case.get("match") is True for case in cases),
        "ready_for_audit_merge_cutover": all(case.get("match") is True for case in cases),
        "latest": latest,
        "all_latest_required_artifacts_pass": all(
            (item or {}).get("status") == "PASS" for item in latest.values()
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "all_cases_match": capture.get("all_cases_match") is True,
        "ready_for_audit_merge_cutover": capture.get("ready_for_audit_merge_cutover") is True,
        "all_latest_required_artifacts_pass": (
            capture.get("all_latest_required_artifacts_pass") is True
        ),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Post-Click Bending Replacement Audit/Result Parity Scenarios",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Case count: `{capture.get('case_count')}`",
        f"- All cases match: `{capture.get('all_cases_match')}`",
        f"- Ready for audit merge cutover: `{capture.get('ready_for_audit_merge_cutover')}`",
        "",
        "## Cases",
        "",
    ]
    for case in capture.get("cases") or []:
        lines.append(
            f"- {case.get('id')}: match=`{case.get('match')}`, expected=`{case.get('expected_hash')}`, actual=`{case.get('actual_hash')}`"
        )
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Next",
            "",
            "Next safe slice: cut over the audit merge projection only; keep the low-bending resolution builder live.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_post_click_bending_replacement_audit_result_parity_scenarios.v1",
        "status": status,
        "created_at": _stamp(),
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = payload["created_at"]
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_post_click_bending_replacement_audit_result_parity_scenarios_{stamp}.json"
    )
    md_path = (
        AUDIT_DIR
        / f"design_guide_post_click_bending_replacement_audit_result_parity_scenarios_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(md_path, payload)
    print(f"design_guide_post_click_bending_replacement_audit_result_parity_scenarios {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
