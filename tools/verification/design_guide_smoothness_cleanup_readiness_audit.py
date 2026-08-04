"""Design Guide smoothness cleanup readiness audit.

Audit-only. This script classifies cleanup and performance opportunities after
the render bridge, independence, and compute resolver/publication bridge locks.
It does not delete code, bypass live paths, or change product behaviour.
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

CLASS_A = "A. safe deletion candidate"
CLASS_B = "B. safe bypass candidate"
CLASS_C = "C. compatibility-only keep for now"
CLASS_D = "D. fallback/safety keep"
CLASS_E = "E. performance profiling target"
CLASS_F = "F. unsafe/needs proof"
CLASS_G = "G. deleted after proof"

REQUIRED_LOCKS = {
    "design_guide_independence_lock": "design_guide_independence_lock",
    "design_guide_render_bridge_lock": "design_guide_render_bridge_lock",
    "design_guide_compute_resolver_publication_bridge_lock": (
        "design_guide_compute_resolver_publication_bridge_lock"
    ),
    "design_guide_collapsed_replacement_authority_cutover": (
        "design_guide_collapsed_replacement_authority_cutover"
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


def _line_numbers(source: str, token: str, *, limit: int = 8) -> list[int]:
    lines: list[int] = []
    for index, line in enumerate(source.splitlines(), start=1):
        if token in line:
            lines.append(index)
            if len(lines) >= limit:
                break
    return lines


def _count_token(source: str, token: str) -> int:
    return source.count(token)


def _count_call(source: str, name: str) -> int:
    return len(re.findall(rf"(?<!def )\b{re.escape(name)}\s*\(", source))


def _build_inventory(input_source: str, final_source: str) -> dict[str, Any]:
    return {
        "compatibility_only_tokens": _count_token(input_source, "compatibility_only"),
        "proof_only_tokens": _count_token(input_source, "proof_only"),
        "non_authoritative_tokens": _count_token(input_source, "non_authoritative"),
        "fallback_only_tokens": _count_token(input_source, "fallback_only"),
        "final_publication_verifier_payload_tokens": _count_token(input_source, "final_publication_verifier_payload"),
        "final_publication_authority_hash_tokens": _count_token(input_source, "final_publication_authority_hash"),
        "compute_debug_restamp_rows_tokens": _count_token(
            input_source,
            "final_publication_compute_debug_restamp_metadata_rows",
        ),
        "a_class_compute_evidence_rows_tokens": _count_token(
            input_source,
            "final_publication_compute_a_class_evidence_rows",
        ),
        "resolve_final_visible_design_guide_item_calls": _count_call(
            input_source,
            "resolve_final_visible_design_guide_item",
        ),
        "publish_final_visible_contract_binding_calls": _count_call(
            input_source,
            "_publish_final_visible_design_guide_contract_binding",
        ),
        "compute_design_guidance_items_tokens": _count_token(input_source, "_compute_design_guidance_items"),
        "evaluate_candidate_full_calls": _count_call(input_source, "evaluate_candidate_full"),
        "evaluate_candidate_fast_calls": _count_call(input_source, "evaluate_candidate_fast"),
        "_evaluate_candidate_fast_calls": _count_call(input_source, "_evaluate_candidate_fast"),
        "candidate_search_evidence_tokens": _count_token(input_source, "candidate_search_evidence"),
        "local_cleanup_tokens": _count_token(input_source, "local_cleanup"),
        "target_band_tokens": _count_token(input_source, "target_band"),
        "st_rerun_calls": _count_token(input_source, "st.rerun()"),
        "button_tokens": _count_token(input_source, "st.button("),
        "set_rerun_pure_cache_tokens": _count_token(input_source, "set_rerun_pure_cache"),
        "get_rerun_pure_cache_tokens": _count_token(input_source, "get_rerun_pure_cache"),
        "final_publication_has_no_page_or_ui_imports": all(
            token not in final_source
            for token in (
                "inputs_page",
                "streamlit",
                "st.session_state",
                "design_guide_page.render_final_panel",
                "_design_guide_dashboard_card_html_from_render_model",
                "_record_rendered_design_guide_primary_apply_payload",
            )
        ),
    }


def _entry(
    *,
    area: str,
    classification: str,
    current_owner: str,
    evidence: list[str],
    rationale: str,
    first_action: str,
    risk: str,
    priority: int,
) -> dict[str, Any]:
    return {
        "area": area,
        "classification": classification,
        "current_owner": current_owner,
        "evidence": evidence,
        "rationale": rationale,
        "first_action": first_action,
        "risk": risk,
        "priority": priority,
    }


def _build_entries(input_source: str, locks: dict[str, Any]) -> list[dict[str, Any]]:
    compute_lock = dict(locks["design_guide_compute_resolver_publication_bridge_lock"].get("snapshot") or {})
    render_lock = dict(locks["design_guide_render_bridge_lock"].get("snapshot") or {})
    independence_lock = dict(locks["design_guide_independence_lock"].get("snapshot") or {})

    return [
        _entry(
            area="duplicate compute proof/debug payload stamping",
            classification=CLASS_G,
            current_owner="deleted from inputs_page.py after consumer proof",
            evidence=[
                "compute bridge lock PASS",
                "A-class compute truth helper deleted",
                "compute debug/restamp metadata helper deleted",
                "FinalDesignGuidePublication remains authority",
            ],
            rationale=(
                "The helper-row values were compatibility/proof-only, had zero product consumers, "
                "and are now physically deleted. The remaining duplicate-stamp bypass mechanism stays "
                "available for other debug/session compatibility surfaces."
            ),
            first_action=(
                "No further action for this deleted surface; keep deletion snapshots in the lock chain."
            ),
            risk="Closed for this helper-row surface; future work should target remaining bypass candidates.",
            priority=1,
        ),
        _entry(
            area="render-stage compatibility restamps",
            classification=CLASS_C,
            current_owner="inputs_page.py compatibility/proof-only render bridge rows",
            evidence=[
                "render bridge lock PASS",
                "remaining live resolver rows = 0",
                "render-stage selected item mutation truth narrowed",
            ],
            rationale=(
                "These are proven non-authoritative, but deletion needs consumer reachability proof because "
                "browser/debug checks may still read compatibility rows."
            ),
            first_action="Create consumer reachability proof for one render-stage compatibility stamp before deletion.",
            risk="Low runtime authority risk; unknown consumer risk until delete proof exists.",
            priority=4,
        ),
        _entry(
            area="fallback-only shells",
            classification=CLASS_D,
            current_owner="inputs_page.py render/browser resilience path",
            evidence=[
                "independence lock PASS",
                "fallback shells non-authoritative",
                "render bridge lock PASS",
            ],
            rationale=(
                "Fallback shells are not authority, but they protect browser/render resilience. Keep until a "
                "fallback-shell removal smoke proof exists."
            ),
            first_action="Do not delete yet; profile whether fallback shell construction appears on the hot path.",
            risk="Potential live rendering safety risk if removed without browser coverage.",
            priority=7,
        ),
        _entry(
            area="duplicate debug/session publication stamps",
            classification=CLASS_B,
            current_owner="inputs_page.py session/debug storage",
            evidence=[
                "session boundary canonicalization PASS",
                "unsafe duplicate publication authority keys = 0",
                "FinalDesignGuidePublication hash-stamped payloads present",
            ],
            rationale=(
                "Legacy publication-shaped session/debug keys are non-authoritative. They are candidates "
                "for bypassing repeated restamps when the publication hash has not changed."
            ),
            first_action=(
                "Add a hash-stability bypass proof for repeated session/debug publication stamps within one rerun."
            ),
            risk="Low visible risk; moderate diagnostic compatibility risk.",
            priority=2,
        ),
        _entry(
            area="repeated verifier/debug payload stamping",
            classification=CLASS_B,
            current_owner="inputs_page.py verifier/debug payload assembly",
            evidence=[
                "verifier/debug same-object proof PASS",
                "FinalDesignGuidePublication verifier payload hash exists",
                "publication bridge locks PASS",
            ],
            rationale=(
                "Verifier payloads are same-object proof data. The likely smoothness win is bypassing rebuilds "
                "when the publication hash is unchanged."
            ),
            first_action="Add memoized verifier payload rebuild bypass keyed by publication_hash in proof-only mode first.",
            risk="Low visible risk; requires verifier parity proof.",
            priority=3,
        ),
        _entry(
            area="old resolver callsites",
            classification=CLASS_D,
            current_owner="inputs_page.py compute pre-publication handoff / safety logic",
            evidence=[
                f"resolve call count: {_count_call(input_source, 'resolve_final_visible_design_guide_item')}",
                "compute bridge lock says B/D surfaces remain expected live logic",
            ],
            rationale=(
                "The render-stage resolver is no longer final truth, but compute-stage resolver/safety paths "
                "still own legitimate pre-publication or fallback decisions."
            ),
            first_action="Keep compute resolver callsites; only profile their frequency and cache hit behaviour.",
            risk="High if deleted or bypassed before compute/safety ownership changes.",
            priority=8,
        ),
        _entry(
            area="repeated Design Guide recomputation",
            classification=CLASS_E,
            current_owner="inputs_page.py compute/render orchestration",
            evidence=[
                f"_compute_design_guidance_items tokens: {_count_token(input_source, '_compute_design_guidance_items')}",
                f"set_rerun_pure_cache tokens: {_count_token(input_source, 'set_rerun_pure_cache')}",
                f"get_rerun_pure_cache tokens: {_count_token(input_source, 'get_rerun_pure_cache')}",
            ],
            rationale=(
                "There is already cache machinery, but smoothness work should prove whether Design Guide compute "
                "runs more than once per stable publication/input hash."
            ),
            first_action=(
                "Add a lightweight performance trace counting Design Guide compute calls, cache hits, and "
                "publication_hash churn per rerun."
            ),
            risk="No behaviour risk for profiling; later bypass requires cache-key proof.",
            priority=5,
        ),
        _entry(
            area="candidate evaluation/search churn",
            classification=CLASS_E,
            current_owner="inputs_page.py candidate search/evaluation loops",
            evidence=[
                f"evaluate_candidate_full calls: {_count_call(input_source, 'evaluate_candidate_full')}",
                f"evaluate_candidate_fast calls: {_count_call(input_source, 'evaluate_candidate_fast')}",
                f"candidate_search_evidence tokens: {_count_token(input_source, 'candidate_search_evidence')}",
                f"local_cleanup tokens: {_count_token(input_source, 'local_cleanup')}",
            ],
            rationale=(
                "Evaluation/search churn is the likely real compute cost. Do not bypass until counters identify "
                "which paths repeat under unchanged state."
            ),
            first_action="Add counters around candidate evaluation/search families and correlate to publication_hash.",
            risk="No behaviour risk for profiling; bypass is unsafe without deterministic cache proof.",
            priority=6,
        ),
        _entry(
            area="Streamlit rerun triggers around Design Guide/apply/batch controls",
            classification=CLASS_E,
            current_owner="inputs_page.py UI and apply controls",
            evidence=[
                f"st.rerun calls: {_count_token(input_source, 'st.rerun()')}",
                f"st.button calls: {_count_token(input_source, 'st.button(')}",
                "apply routing remains page-owned by independence/compute locks",
            ],
            rationale=(
                "Rerun churn is likely visible smoothness cost. It is not Design Brain authority and should be "
                "profiled before any control-flow change."
            ),
            first_action="Add rerun cause tracing for Design Guide/apply/batch controls, then rank top rerun loops.",
            risk="No behaviour risk for tracing; rerun suppression is unsafe without apply/session proof.",
            priority=9,
        ),
        _entry(
            area="unproven deletion candidates",
            classification=CLASS_F,
            current_owner="mixed legacy compatibility consumers",
            evidence=[
                "No current audit proves direct deletion is safe",
                "compatibility consumers still possible",
            ],
            rationale=(
                "The locks prove authority, not consumer absence. Deletion should start only after a focused "
                "reachability/deletion proof for one compatibility path."
            ),
            first_action="Do not delete in the first smoothness slice; choose bypass/profiling first.",
            risk="Unknown until consumer reachability is proven.",
            priority=10,
        ),
    ]


def _classification_counts(entries: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entry in entries:
        key = str(entry["classification"])
        counts[key] = counts.get(key, 0) + 1
    return counts


def _write_report(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# Design Guide Smoothness Cleanup Readiness Audit",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Summary",
        "",
        f"- Product behaviour changed: `{payload['product_behavior_changed']}`",
        f"- Lock prerequisites passed: `{payload['lock_prerequisites_passed']}`",
        f"- First safe slice: {payload['first_safe_slice']}",
        "",
        "## Classification Counts",
        "",
    ]
    for key, value in sorted(payload["classification_counts"].items()):
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Prioritized Plan", "", "| Priority | Area | Class | First action | Risk |", "| --- | --- | --- | --- | --- |"])
    for entry in sorted(payload["entries"], key=lambda row: int(row["priority"])):
        lines.append(
            "| {priority} | {area} | `{classification}` | {action} | {risk} |".format(
                priority=entry["priority"],
                area=_escape_md(entry["area"]),
                classification=_escape_md(entry["classification"]),
                action=_escape_md(entry["first_action"]),
                risk=_escape_md(entry["risk"]),
            )
        )
    lines.extend(["", "## Inventory", ""])
    for key, value in sorted(payload["inventory"].items()):
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Lock Artifacts", ""])
    for key, row in payload["locks"].items():
        lines.append(f"- `{key}`: passed=`{row['passed']}`, path=`{row['path']}`")
    lines.extend(["", "## Failures", ""])
    if payload["failures"]:
        lines.extend(f"- `{failure}`" for failure in payload["failures"])
    else:
        lines.append("- None")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    input_source = INPUTS_PAGE.read_text(encoding="utf-8")
    final_source = FINAL_PUBLICATION.read_text(encoding="utf-8")
    locks = {name: _latest(prefix) for name, prefix in REQUIRED_LOCKS.items()}
    inventory = _build_inventory(input_source, final_source)
    entries = _build_entries(input_source, locks)
    counts = _classification_counts(entries)

    failures: list[str] = []
    for name, lock in locks.items():
        if lock.get("passed") is not True:
            failures.append(f"{name}_not_passed_or_missing")
    if not inventory["final_publication_has_no_page_or_ui_imports"]:
        failures.append("final_publication_imports_page_or_ui")
    if counts.get(CLASS_A, 0) != 0:
        failures.append("unexpected_direct_deletion_candidate_without_deletion_proof")
    if counts.get(CLASS_F, 0) == 0:
        failures.append("unsafe_bucket_missing_for_unproven_deletion")

    first_safe_slice = (
        "Next: consumer reachability proof for render-stage compatibility restamps, or profiling "
        "for repeated Design Guide recomputation. The compute helper-row bypass surface is already deleted."
    )
    payload = {
        "schema": "design_guide_smoothness_cleanup_readiness_audit.v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "product_behavior_changed": False,
        "lock_prerequisites_passed": all(lock.get("passed") is True for lock in locks.values()),
        "locks": {
            name: {
                "path": lock.get("path"),
                "passed": lock.get("passed"),
                "found": lock.get("found"),
            }
            for name, lock in locks.items()
        },
        "inventory": inventory,
        "entries": sorted(entries, key=lambda row: int(row["priority"])),
        "classification_counts": counts,
        "safe_deletion_candidates": [
            entry for entry in entries if entry["classification"] == CLASS_A
        ],
        "safe_bypass_candidates": [
            entry for entry in entries if entry["classification"] == CLASS_B
        ],
        "performance_profiling_targets": [
            entry for entry in entries if entry["classification"] == CLASS_E
        ],
        "first_safe_slice": first_safe_slice,
        "audit_hash": _stable_hash(
            {
                "locks": {name: lock.get("path") for name, lock in locks.items()},
                "inventory": inventory,
                "entries": entries,
                "first_safe_slice": first_safe_slice,
            }
        ),
    }

    stamp = datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_smoothness_cleanup_readiness_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_smoothness_cleanup_readiness_{stamp}.md"
    payload["artifact"] = str(json_path)
    payload["report"] = str(md_path)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(payload, md_path)

    print(f"design_guide_smoothness_cleanup_readiness_audit {payload['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    print(f"first_safe_slice={first_safe_slice}")
    if failures:
        print("failures:", json.dumps(failures, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
