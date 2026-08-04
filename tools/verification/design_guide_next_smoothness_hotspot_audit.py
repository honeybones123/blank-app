"""Next Design Guide smoothness hotspot audit.

Audit-only. This verifier classifies the next repeated-work opportunities after
the duplicate publication stamp bypass. It does not implement bypasses, delete
code, or change product behaviour.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"

CLASS_A = "A. safe bypass candidate"
CLASS_B = "B. safe memo/cache candidate"
CLASS_C = "C. keep live because input-sensitive"
CLASS_D = "D. fallback/safety keep"
CLASS_E = "E. needs browser/live proof"
CLASS_F = "F. unsafe/unclear"

REQUIRED_LOCKS = {
    "duplicate_publication_stamp_bypass_live_impact": (
        "design_guide_duplicate_publication_stamp_bypass_live_impact"
    ),
    "duplicate_publication_stamp_bypass_implementation": (
        "design_guide_duplicate_publication_stamp_bypass_implementation"
    ),
    "card_render_model_bypass_live_impact": (
        "design_guide_card_render_model_bypass_live_impact"
    ),
    "card_render_model_bypass_implementation": (
        "design_guide_card_render_model_bypass_implementation"
    ),
    "cta_apply_binding_bypass_live_impact": (
        "design_guide_cta_apply_binding_bypass_live_impact"
    ),
    "cta_apply_binding_bypass_implementation": (
        "design_guide_cta_apply_binding_bypass_implementation"
    ),
    "final_publication_memo_implementation": (
        "design_guide_final_publication_memo_implementation"
    ),
    "controller_request_key_live_stability": (
        "design_guide_controller_request_key_live_stability"
    ),
    "browser_live_smoothness_profile": "design_guide_browser_live_smoothness_profile",
    "no_input_candidate_search_reuse_readiness": (
        "design_guide_no_input_candidate_search_reuse_readiness"
    ),
    "candidate_search_reuse_adapter": "design_guide_candidate_search_reuse_adapter",
    "no_input_candidate_search_reuse_implementation": (
        "design_guide_no_input_candidate_search_reuse_implementation"
    ),
    "no_input_candidate_search_reuse_live_impact": (
        "design_guide_no_input_candidate_search_reuse_live_impact"
    ),
    "no_input_reload_publication_hash_drift_audit": (
        "design_guide_no_input_reload_publication_hash_drift_audit"
    ),
    "design_guide_independence_lock": "design_guide_independence_lock",
    "design_guide_render_bridge_lock": "design_guide_render_bridge_lock",
    "design_guide_compute_resolver_publication_bridge_lock": (
        "design_guide_compute_resolver_publication_bridge_lock"
    ),
}


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _escape_md(value: Any) -> str:
    return str(value).replace("|", "\\|")


def _latest(prefix: str) -> dict[str, Any]:
    artifacts = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not artifacts:
        return {"found": False, "path": None, "snapshot": {}, "passed": False}
    path = artifacts[-1]
    try:
        snapshot = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"found": True, "path": str(path), "snapshot": {}, "passed": False, "error": str(exc)}
    return {
        "found": True,
        "path": str(path),
        "snapshot": snapshot,
        "passed": snapshot.get("status") == "PASS",
    }


def _count_call(source: str, name: str) -> int:
    return len(re.findall(rf"(?<!def )\b{re.escape(name)}\s*\(", source))


def _count_token(source: str, token: str) -> int:
    return source.count(token)


def _line_numbers(source: str, token: str, *, limit: int = 8) -> list[int]:
    out: list[int] = []
    for index, line in enumerate(source.splitlines(), start=1):
        if token in line:
            out.append(index)
            if len(out) >= limit:
                break
    return out


def _entry(
    *,
    area: str,
    classification: str,
    current_owner: str,
    proposed_key: str | None,
    evidence: list[str],
    rationale: str,
    required_proof: str,
    first_action: str,
    priority: int,
) -> dict[str, Any]:
    return {
        "area": area,
        "classification": classification,
        "current_owner": current_owner,
        "proposed_key": proposed_key,
        "evidence": evidence,
        "rationale": rationale,
        "required_proof": required_proof,
        "first_action": first_action,
        "priority": priority,
    }


def _inventory(input_source: str, final_source: str) -> dict[str, Any]:
    return {
        "build_final_publication_calls": _count_call(input_source, "_build_final_design_guide_publication"),
        "build_card_render_model_calls": _count_call(input_source, "_build_design_guide_card_render_model"),
        "dashboard_card_html_with_render_model_calls": _count_call(
            input_source,
            "_design_guide_dashboard_card_html_with_render_model",
        ),
        "record_card_render_model_calls": _count_call(input_source, "_record_design_guide_card_render_model"),
        "stamp_display_authority_calls": _count_call(input_source, "_stamp_final_publication_display_authority"),
        "stamp_cta_authority_calls": _count_call(input_source, "_stamp_final_publication_cta_authority"),
        "record_primary_apply_payload_calls": _count_call(
            input_source,
            "_record_rendered_design_guide_primary_apply_payload",
        ),
        "same_object_verifier_payload_calls": _count_call(
            input_source,
            "_stamp_final_publication_same_object_verifier_payload",
        ),
        "evaluate_candidate_full_calls": _count_call(input_source, "evaluate_candidate_full"),
        "evaluate_candidate_fast_calls": _count_call(input_source, "evaluate_candidate_fast"),
        "_evaluate_candidate_fast_calls": _count_call(input_source, "_evaluate_candidate_fast"),
        "get_rerun_pure_cache_tokens": _count_token(input_source, "get_rerun_pure_cache"),
        "set_rerun_pure_cache_tokens": _count_token(input_source, "set_rerun_pure_cache"),
        "speed_diag_candidate_tokens": _count_token(input_source, "_dg_speed_diag_note_candidate_eval"),
        "st_rerun_calls": _count_token(input_source, "st.rerun()"),
        "final_publication_display_hash_tokens": _count_token(input_source, "final_publication_display_hash"),
        "final_publication_cta_hash_tokens": _count_token(input_source, "final_publication_cta_hash"),
        "publication_hash_tokens": _count_token(input_source, "publication_hash"),
        "final_publication_no_page_imports": "inputs_page" not in final_source and "streamlit" not in final_source,
        "card_render_model_lines": _line_numbers(input_source, "_design_guide_dashboard_card_html_with_render_model"),
        "apply_payload_lines": _line_numbers(input_source, "_record_rendered_design_guide_primary_apply_payload"),
        "candidate_eval_lines": _line_numbers(input_source, "evaluate_candidate_full"),
        "rerun_lines": _line_numbers(input_source, "st.rerun()"),
    }


def _entries(input_source: str, locks: dict[str, Any]) -> list[dict[str, Any]]:
    impact = dict(locks["duplicate_publication_stamp_bypass_live_impact"].get("snapshot") or {})
    stable_hits = int(impact.get("stable_non_debug_bypass_hits") or 0)
    rerun_hits = int(impact.get("rerun_without_input_changes_bypass_hits") or 0)
    card_impact = dict(locks["card_render_model_bypass_live_impact"].get("snapshot") or {})
    card_stable_hits = int(card_impact.get("stable_non_debug_bypass_hits") or 0)
    card_rerun_hits = int(card_impact.get("rerun_without_input_changes_bypass_hits") or 0)
    cta_impact = dict(locks["cta_apply_binding_bypass_live_impact"].get("snapshot") or {})
    cta_observed = dict(cta_impact.get("observed_impact") or {})
    cta_stable_hits = int(cta_observed.get("stable_non_debug_bypass_hits") or 0)
    cta_rerun_hits = int(cta_observed.get("rerun_without_input_changes_bypass_hits") or 0)
    cta_guarded_rebuilds = int(cta_observed.get("forced_rebuilds_in_guarded_cases") or 0)
    memo_implementation = dict(locks["final_publication_memo_implementation"].get("snapshot") or {})
    memo_live = dict(locks["controller_request_key_live_stability"].get("snapshot") or {})
    memo_live_browser = dict(memo_live.get("browser_live") or {})
    memo_live_rerun = dict(memo_live_browser.get("stable_rerun") or {})
    memo_live_hits = int(memo_live_rerun.get("memo_cache_hits") or 0)
    browser_profile = dict(locks["browser_live_smoothness_profile"].get("snapshot") or {})
    candidate_readiness = dict(locks["no_input_candidate_search_reuse_readiness"].get("snapshot") or {})
    candidate_readiness_detail = dict(candidate_readiness.get("scenario_readiness") or {})
    candidate_adapter = dict(locks["candidate_search_reuse_adapter"].get("snapshot") or {})
    candidate_implementation = dict(
        locks["no_input_candidate_search_reuse_implementation"].get("snapshot") or {}
    )
    candidate_live_impact = dict(locks["no_input_candidate_search_reuse_live_impact"].get("snapshot") or {})
    candidate_live_observed = dict(candidate_live_impact.get("impact") or {})
    candidate_live_hits = int(candidate_live_observed.get("stable_no_input_reuse_hits") or 0)
    candidate_live_misses = int(candidate_live_observed.get("stable_no_input_reuse_misses") or 0)
    candidate_live_force_rebuilds = int(candidate_live_observed.get("stable_no_input_force_rebuilds") or 0)
    drift_audit = dict(locks["no_input_reload_publication_hash_drift_audit"].get("snapshot") or {})
    render_lock = dict(locks["design_guide_render_bridge_lock"].get("snapshot") or {})
    independence_lock = dict(locks["design_guide_independence_lock"].get("snapshot") or {})

    return [
        _entry(
            area="repeated card render-model rebuilds with same publication/display hash",
            classification=CLASS_C,
            current_owner="inputs_page.py render-model builder and display authority stamp",
            proposed_key="FinalDesignGuidePublication.display hash / final_publication_display_hash",
            evidence=[
                f"_design_guide_dashboard_card_html_with_render_model calls: {_count_call(input_source, '_design_guide_dashboard_card_html_with_render_model')}",
                f"_build_design_guide_card_render_model calls: {_count_call(input_source, '_build_design_guide_card_render_model')}",
                f"final_publication_display_hash tokens: {_count_token(input_source, 'final_publication_display_hash')}",
                f"stable non-debug card bypass hits: {card_stable_hits}",
                f"rerun without input changes card bypass hits: {card_rerun_hits}",
                "card render-model bypass implementation PASS",
                "card render-model bypass live impact PASS",
                f"render bridge lock PASS: {render_lock.get('status') == 'PASS'}",
            ],
            rationale=(
                "This hotspot already has the measured non-debug same-display-hash bypass. Keep it live as "
                "implemented and do not target it again until browser profiling shows it remains hot."
            ),
            required_proof="No additional proof needed for this slice; already bypassed and measured.",
            first_action="Do not target again immediately.",
            priority=5,
        ),
        _entry(
            area="repeated CTA/apply payload binding with same CTA hash",
            classification=CLASS_C,
            current_owner="inputs_page.py CTA authority and apply payload binding",
            proposed_key="FinalDesignGuidePublication.cta hash / final_publication_cta_hash",
            evidence=[
                f"_stamp_final_publication_cta_authority calls: {_count_call(input_source, '_stamp_final_publication_cta_authority')}",
                f"_record_rendered_design_guide_primary_apply_payload calls: {_count_call(input_source, '_record_rendered_design_guide_primary_apply_payload')}",
                f"final_publication_cta_hash tokens: {_count_token(input_source, 'final_publication_cta_hash')}",
                f"stable non-debug CTA/apply bypass hits: {cta_stable_hits}",
                f"rerun without input changes CTA/apply bypass hits: {cta_rerun_hits}",
                f"guarded CTA/apply forced rebuilds: {cta_guarded_rebuilds}",
                "CTA/apply binding bypass implementation PASS",
                "CTA/apply binding bypass live impact PASS",
            ],
            rationale=(
                "This hotspot now has the measured non-debug same-CTA/payload/state bypass. Keep it live as "
                "implemented and do not target it again until browser profiling shows it remains hot."
            ),
            required_proof="No additional proof needed for this slice; already bypassed and measured.",
            first_action="Do not target again immediately.",
            priority=5,
        ),
        _entry(
            area="repeated FinalDesignGuidePublication rebuilds with same input hash",
            classification=CLASS_C,
            current_owner="DesignGuideController guarded memo cache",
            proposed_key="canonical DesignGuideController request hash",
            evidence=[
                f"_build_final_design_guide_publication calls: {_count_call(input_source, '_build_final_design_guide_publication')}",
                "FinalDesignGuidePublication is immutable and hash-stamped",
                f"final publication memo implementation PASS: {memo_implementation.get('status') == 'PASS'}",
                f"controller request-key live stability PASS: {memo_live.get('status') == 'PASS'}",
                f"stable rerun controller memo hits: {memo_live_hits}",
                f"independence lock PASS: {independence_lock.get('status') == 'PASS'}",
            ],
            rationale=(
                "This hotspot now has a guarded controller memo keyed by canonical product-relevant request data. "
                "Raw debug/guidance_debug proof churn is excluded from the key, while changed inputs and guarded "
                "debug/post-click/missing-publication states still rebuild."
            ),
            required_proof="No additional proof needed for this slice; already memoized and browser-live verified.",
            first_action="Do not target again immediately.",
            priority=5,
        ),
        _entry(
            area="repeated session/debug payload stamping with same publication hash",
            classification=CLASS_C,
            current_owner="inputs_page.py debug/session compatibility stamp helpers",
            proposed_key="FinalDesignGuidePublication.publication_hash",
            evidence=[
                f"stable non-debug bypass hits: {stable_hits}",
                f"rerun without input changes bypass hits: {rerun_hits}",
                "duplicate publication stamp bypass implementation PASS",
            ],
            rationale=(
                "This area already has the first measured bypass. Keep it live as implemented and do not stack "
                "another bypass here until browser profiling shows it remains hot."
            ),
            required_proof="No additional proof needed for this slice; already bypassed and measured.",
            first_action="Do not target again immediately.",
            priority=5,
        ),
        _entry(
            area="repeated candidate evaluation/search calls during no-input-change reruns",
            classification=CLASS_C,
            current_owner="inputs_page.py shared evaluation/search plumbing",
            proposed_key="guidance runtime fingerprint + candidate evaluation fingerprint set",
            evidence=[
                f"evaluate_candidate_full calls: {_count_call(input_source, 'evaluate_candidate_full')}",
                f"evaluate_candidate_fast calls: {_count_call(input_source, 'evaluate_candidate_fast')}",
                f"_evaluate_candidate_fast calls: {_count_call(input_source, '_evaluate_candidate_fast')}",
                f"get_rerun_pure_cache tokens: {_count_token(input_source, 'get_rerun_pure_cache')}",
                f"set_rerun_pure_cache tokens: {_count_token(input_source, 'set_rerun_pure_cache')}",
                f"speed diag candidate tokens: {_count_token(input_source, '_dg_speed_diag_note_candidate_eval')}",
                f"browser/live smoothness profile PASS: {browser_profile.get('status') == 'PASS'}",
                f"stable no-input candidate eval counts: {candidate_readiness_detail.get('stable_candidate_eval_counts')}",
                f"stable no-input candidate cache misses: {candidate_readiness_detail.get('stable_candidate_cache_misses')}",
                f"candidate-search reuse readiness PASS: {candidate_readiness.get('status') == 'PASS'}",
                f"candidate-search reuse adapter PASS: {candidate_adapter.get('status') == 'PASS'}",
                f"candidate-search reuse implementation PASS: {candidate_implementation.get('status') == 'PASS'}",
                f"stable no-input candidate-search reuse hits: {candidate_live_hits}",
                f"stable no-input candidate-search reuse misses: {candidate_live_misses}",
                f"stable no-input candidate-search forced rebuilds: {candidate_live_force_rebuilds}",
                f"no-input reload publication hash drift classification: {drift_audit.get('classification')}",
            ],
            rationale=(
                "This hotspot has crossed from proof into a measured live same-input reuse implementation. "
                "Keep it live as implemented; if candidate evaluation/search remains hot in browser profiles, "
                "the next work should be deeper profiling of remaining miss paths, not another broad bypass."
            ),
            required_proof="No additional proof needed for this slice; already implemented and measured.",
            first_action="Do not target again immediately; profile remaining miss paths if it stays hot.",
            priority=5,
        ),
        _entry(
            area="Streamlit rerun triggers from Apply, batch controls, constraints info, and Design Guide panel render",
            classification=CLASS_E,
            current_owner="inputs_page.py UI/event routing",
            proposed_key="rerun cause marker",
            evidence=[
                f"st.rerun calls: {_count_token(input_source, 'st.rerun()')}",
                f"rerun lines: {_line_numbers(input_source, 'st.rerun()', limit=12)}",
            ],
            rationale=(
                "Rerun triggers can dominate perceived smoothness, but they are UI/event semantics. They need "
                "cause tracing before any throttling or bypass."
            ),
            required_proof="Rerun-cause trace around Apply, batch controls, constraints info, and Design Guide render.",
            first_action="Add rerun-cause profiling only after render-model/CTA surfaces are assessed.",
            priority=6,
        ),
        _entry(
            area="fallback shells and safety render paths",
            classification=CLASS_D,
            current_owner="inputs_page.py fallback-only render paths",
            proposed_key=None,
            evidence=[
                "render bridge lock keeps fallback shells non-authoritative",
                "independence lock keeps fallback/session/debug non-authoritative",
            ],
            rationale=(
                "Fallback shells are intentionally retained and should not be optimized until deletion/readiness "
                "proof says they are unreachable or safely bypassable."
            ),
            required_proof="Fallback reachability/deletion proof, not a smoothness bypass.",
            first_action="Keep out of this smoothness slice.",
            priority=7,
        ),
    ]


def _write_report(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# Design Guide Next Smoothness Hotspot Audit",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Summary",
        "",
        f"- First recommended next slice: `{payload['first_recommended_next_slice']['area']}`",
        f"- Classification: `{payload['first_recommended_next_slice']['classification']}`",
        f"- Product behaviour changed: `{payload['product_behavior_changed']}`",
        "",
        "## Hotspots",
        "",
        "| Priority | Area | Classification | Proposed key | First action |",
        "| ---: | --- | --- | --- | --- |",
    ]
    for row in payload["hotspots"]:
        lines.append(
            "| {priority} | {area} | `{classification}` | `{key}` | {action} |".format(
                priority=row["priority"],
                area=_escape_md(row["area"]),
                classification=_escape_md(row["classification"]),
                key=_escape_md(row.get("proposed_key") or ""),
                action=_escape_md(row["first_action"]),
            )
        )
    lines.extend(["", "## Inventory", "", "```json", json.dumps(payload["inventory"], indent=2, sort_keys=True), "```"])
    lines.extend(["", "## Locks", ""])
    for name, lock in payload["locks"].items():
        lines.append(f"- `{name}`: passed=`{lock['passed']}`, path=`{lock['path']}`")
    lines.extend(["", "## Failures", ""])
    if payload["failures"]:
        lines.extend(f"- `{failure}`" for failure in payload["failures"])
    else:
        lines.append("- None")
    lines.extend(["", "## Recommendation", "", payload["recommendation"]])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    input_source = INPUTS_PAGE.read_text(encoding="utf-8")
    final_source = FINAL_PUBLICATION.read_text(encoding="utf-8")
    locks = {name: _latest(prefix) for name, prefix in REQUIRED_LOCKS.items()}
    inventory = _inventory(input_source, final_source)
    hotspots = sorted(_entries(input_source, locks), key=lambda row: int(row["priority"]))
    actionable_hotspots = [
        row for row in hotspots if row["classification"] in {CLASS_A, CLASS_B, CLASS_E}
    ]

    failures: list[str] = []
    for name, lock in locks.items():
        if lock.get("passed") is not True:
            failures.append(f"{name}_not_passed")
    if not inventory["final_publication_no_page_imports"]:
        failures.append("final_publication_imports_page_or_ui")
    if not hotspots:
        failures.append("no_hotspots_classified")
    if not actionable_hotspots:
        failures.append("first_recommendation_not_actionable")
    if any(row["classification"] == CLASS_F for row in hotspots):
        failures.append("unsafe_unclear_hotspot_present")

    passed = not failures
    first = actionable_hotspots[0] if actionable_hotspots else (hotspots[0] if hotspots else {})
    payload = {
        "schema": "design_guide_next_smoothness_hotspot_audit.v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": "PASS" if passed else "FAIL",
        "failures": failures,
        "product_behavior_changed": False,
        "inventory": inventory,
        "hotspots": hotspots,
        "first_recommended_next_slice": first,
        "locks": {
            name: {
                "path": lock.get("path"),
                "passed": lock.get("passed"),
                "found": lock.get("found"),
            }
            for name, lock in locks.items()
        },
        "snapshot_hash": _stable_hash(
            {
                "inventory": inventory,
                "hotspots": hotspots,
                "locks": {name: lock.get("path") for name, lock in locks.items()},
            }
        ),
        "recommendation": str(first.get("first_action") or "No next action classified."),
    }

    stamp = datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_next_smoothness_hotspot_audit_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_next_smoothness_hotspot_audit_{stamp}.md"
    payload["artifact"] = str(json_path)
    payload["report"] = str(md_path)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(payload, md_path)

    print(f"design_guide_next_smoothness_hotspot_audit {payload['status']}")
    print(f"first_recommended_next_slice={first.get('area')}")
    print(f"classification={first.get('classification')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if failures:
        print("failures:", json.dumps(failures, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
