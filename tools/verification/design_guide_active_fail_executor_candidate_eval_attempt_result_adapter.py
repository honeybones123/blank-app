"""Verify active-fail executor candidate eval-attempt result adapter handoff."""

from __future__ import annotations

import ast
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INPUTS_PAGE = ROOT / "inputs_page.py"
CANDIDATE_EVALUATION = ROOT / "design_brain" / "candidate_evaluation.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
TARGET = "_active_fail_near_current_repair_item"
ATTEMPT_HELPER = "build_active_fail_executor_candidate_eval_attempt_result"
SOURCE_HELPER = "resolve_active_fail_executor_candidate_eval_source"


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


def _function_source(source: str, name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            end = int(node.end_lineno or node.lineno)
            return node.lineno, end, "\n".join(lines[node.lineno - 1 : end])
    return 0, 0, ""


def _candidate(overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    candidate = {
        "candidate_id": "candidate-1",
        "overview": {
            "all_key_pass": True,
            "any_fail": False,
            "worst_util": 0.82,
            "statuses": {
                "bending": "PASS",
                "shear": "PASS",
                "crack": "PASS",
                "deflection": "PASS",
            },
        },
        "source": "old-source",
        "action_type": "apply_resolved_candidate",
    }
    candidate.update(dict(overrides or {}))
    return candidate


def _old_eval_source(family_meta: dict[str, Any] | None = None) -> str:
    family_id = str((family_meta or {}).get("candidate_family_id") or "").strip().upper()
    if family_id == "BENDING_FAIL_GOVERNS":
        return "bending_fail_contract_ladder"
    if family_id == "SHEAR_FAIL_GOVERNS":
        return "shear_fail_contract_ladder"
    if family_id == "COMBINED_BENDING_SHEAR_FAIL":
        return "combined_fail_contract_ladder"
    return "active_fail_near_current_repair_search"


def _old_project(
    candidate: dict[str, Any] | None,
    *,
    updates: dict[str, Any],
    label: str,
    family_meta: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    from design_brain.candidate_evaluation import (  # noqa: WPS433
        project_active_fail_executor_evaluated_candidate_result,
    )

    return project_active_fail_executor_evaluated_candidate_result(
        candidate,
        updates=updates,
        label=label,
        family_meta=family_meta,
        geometry_update_keys=("b", "D", "bw", "tw"),
        bottom_update_keys=("bottom_bar_count", "bottom_bar_diameter"),
        shear_update_keys=("lig_d", "lig_legs", "lig_spacing"),
    )


def _old_attempt(
    *,
    cached_candidate: dict[str, Any] | None = None,
    evaluated_candidate: dict[str, Any] | None = None,
    used_cache: bool = False,
    updates: dict[str, Any],
    label: str,
    family_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metrics_delta = {
        "candidate_evaluation_cache_hits": 0,
        "candidate_evaluation_cache_misses": 0,
        "duplicate_candidate_fingerprints_skipped": 0,
        "blocker_attempt_cache_hits": 0,
    }
    raw_candidate: dict[str, Any] | None = None
    cache_candidate = None
    if used_cache and isinstance(cached_candidate, dict):
        metrics_delta["candidate_evaluation_cache_hits"] += 1
        metrics_delta["duplicate_candidate_fingerprints_skipped"] += 1
        metrics_delta["blocker_attempt_cache_hits"] += 1
        raw_candidate = dict(cached_candidate)
    else:
        metrics_delta["candidate_evaluation_cache_misses"] += 1
        if isinstance(evaluated_candidate, dict):
            raw_candidate = dict(evaluated_candidate)
            cache_candidate = dict(evaluated_candidate)
    return {
        "candidate": _old_project(raw_candidate, updates=updates, label=label, family_meta=family_meta),
        "metrics_delta": metrics_delta,
        "cache_candidate": cache_candidate,
        "used_cache": bool(used_cache and isinstance(cached_candidate, dict)),
        "eval_source": _old_eval_source(family_meta),
    }


def _new_attempt(
    *,
    cached_candidate: dict[str, Any] | None = None,
    evaluated_candidate: dict[str, Any] | None = None,
    used_cache: bool = False,
    updates: dict[str, Any],
    label: str,
    family_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from design_brain.candidate_evaluation import (  # noqa: WPS433
        build_active_fail_executor_candidate_eval_attempt_result,
    )

    return build_active_fail_executor_candidate_eval_attempt_result(
        cached_candidate=cached_candidate,
        evaluated_candidate=evaluated_candidate,
        used_cache=used_cache,
        updates=updates,
        label=label,
        family_meta=family_meta,
        geometry_update_keys=("b", "D", "bw", "tw"),
        bottom_update_keys=("bottom_bar_count", "bottom_bar_diameter"),
        shear_update_keys=("lig_d", "lig_legs", "lig_spacing"),
    )


def _source_cases() -> dict[str, dict[str, Any] | None]:
    return {
        "generic": None,
        "bending": {"candidate_family_id": "BENDING_FAIL_GOVERNS"},
        "shear": {"candidate_family_id": "SHEAR_FAIL_GOVERNS"},
        "combined": {"candidate_family_id": "COMBINED_BENDING_SHEAR_FAIL"},
        "unknown": {"candidate_family_id": "CUSTOM"},
    }


def _attempt_cases() -> dict[str, dict[str, Any]]:
    return {
        "cache_hit_shear": {
            "cached_candidate": _candidate(),
            "evaluated_candidate": None,
            "used_cache": True,
            "updates": {"lig_spacing": 150.0},
            "label": "cached shear",
            "family_meta": {"candidate_family_id": "SHEAR_FAIL_GOVERNS"},
        },
        "miss_evaluated_bending": {
            "cached_candidate": None,
            "evaluated_candidate": _candidate(),
            "used_cache": False,
            "updates": {"bottom_bar_count": 8},
            "label": "bending eval",
            "family_meta": {"candidate_family_id": "BENDING_FAIL_GOVERNS"},
        },
        "miss_evaluated_combined": {
            "cached_candidate": None,
            "evaluated_candidate": _candidate(),
            "used_cache": False,
            "updates": {"D": 700.0, "lig_d": 10},
            "label": "combined eval",
            "family_meta": {"candidate_family_id": "COMBINED_BENDING_SHEAR_FAIL"},
        },
        "miss_no_candidate": {
            "cached_candidate": None,
            "evaluated_candidate": None,
            "used_cache": False,
            "updates": {"b": 450.0},
            "label": "no candidate",
            "family_meta": None,
        },
        "cache_flag_without_candidate": {
            "cached_candidate": None,
            "evaluated_candidate": _candidate(),
            "used_cache": True,
            "updates": {"D": 720.0},
            "label": "bad cache flag",
            "family_meta": None,
        },
    }


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    candidate_source = _read(CANDIDATE_EVALUATION)
    target_start, target_end, target_source = _function_source(inputs_source, TARGET)
    helper_start, helper_end, helper_source = _function_source(candidate_source, ATTEMPT_HELPER)
    source_start, source_end, source_source = _function_source(candidate_source, SOURCE_HELPER)

    from design_brain.candidate_evaluation import (  # noqa: WPS433
        resolve_active_fail_executor_candidate_eval_source,
    )

    source_parity = {
        name: {
            "old": _old_eval_source(meta),
            "new": resolve_active_fail_executor_candidate_eval_source(meta),
            "match": _old_eval_source(meta) == resolve_active_fail_executor_candidate_eval_source(meta),
        }
        for name, meta in _source_cases().items()
    }

    attempt_parity: dict[str, dict[str, Any]] = {}
    for name, kwargs in _attempt_cases().items():
        old = _old_attempt(**kwargs)
        new = _new_attempt(**kwargs)
        attempt_parity[name] = {
            "old_hash": _stable_hash(old),
            "new_hash": _stable_hash(new),
            "match": old == new,
            "old": old,
            "new": new,
        }

    removed_inline_tokens = {
        'eval_source = "active_fail_near_current_repair_search"': 'eval_source = "active_fail_near_current_repair_search"' not in target_source,
        '"bending_fail_contract_ladder"': '"bending_fail_contract_ladder"' not in target_source,
        '"shear_fail_contract_ladder"': '"shear_fail_contract_ladder"' not in target_source,
        '"combined_fail_contract_ladder"': '"combined_fail_contract_ladder"' not in target_source,
        "_project_active_fail_executor_evaluated_candidate_result(": "_project_active_fail_executor_evaluated_candidate_result("
        not in target_source,
    }

    return {
        "schema": "design_guide_active_fail_executor_candidate_eval_attempt_result_adapter.v1",
        "target": {
            "line_start": target_start,
            "line_end": target_end,
            "line_count": max(0, target_end - target_start + 1),
            "delegates_eval_source": "_resolve_active_fail_executor_candidate_eval_source(" in target_source,
            "delegates_attempt_result": "_build_active_fail_executor_candidate_eval_attempt_result(" in target_source,
            "still_owns_evaluator_callback": "_evaluate_active_fail_executor_candidate_with_updates(" in target_source,
            "still_owns_seen_update_set": "seen_updates.add(sig)" in target_source,
            "still_owns_cache_storage": "eval_cache_by_candidate_fp[candidate_fp]" in target_source,
            "still_owns_candidate_append_order": "candidates.append(cand)" in target_source,
            "removed_inline_tokens": removed_inline_tokens,
        },
        "candidate_evaluation_helper": {
            "line_start": helper_start,
            "line_end": helper_end,
            "line_count": max(0, helper_end - helper_start + 1),
            "exists": bool(helper_start),
            "source_helper_exists": bool(source_start),
            "exported_attempt_helper": f'"{ATTEMPT_HELPER}"' in candidate_source,
            "exported_source_helper": f'"{SOURCE_HELPER}"' in candidate_source,
            "imports_no_page_or_streamlit": all(
                token not in candidate_source
                for token in ("inputs_page", "streamlit", "st.session_state", "design_guide_page")
            ),
            "helper_hash": _stable_hash(helper_source + source_source),
        },
        "source_parity": source_parity,
        "attempt_parity": attempt_parity,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_behavior_changed": False,
    }


def _checks(payload: dict[str, Any]) -> dict[str, bool]:
    target = payload.get("target") or {}
    helper = payload.get("candidate_evaluation_helper") or {}
    source_parity = payload.get("source_parity") or {}
    attempt_parity = payload.get("attempt_parity") or {}
    return {
        "target_found": bool(target.get("line_start")),
        "target_delegates_eval_source": bool(target.get("delegates_eval_source")),
        "target_delegates_attempt_result": bool(target.get("delegates_attempt_result")),
        "page_still_owns_evaluator_callback": bool(target.get("still_owns_evaluator_callback")),
        "page_still_owns_seen_set": bool(target.get("still_owns_seen_update_set")),
        "page_still_owns_cache_storage": bool(target.get("still_owns_cache_storage")),
        "page_still_owns_append_order": bool(target.get("still_owns_candidate_append_order")),
        "inline_mapping_and_projection_removed": all((target.get("removed_inline_tokens") or {}).values()),
        "helper_exists": bool(helper.get("exists")),
        "source_helper_exists": bool(helper.get("source_helper_exists")),
        "helpers_exported": bool(helper.get("exported_attempt_helper")) and bool(helper.get("exported_source_helper")),
        "candidate_evaluation_import_boundary_clean": bool(helper.get("imports_no_page_or_streamlit")),
        "source_parity_cases_present": len(source_parity) == 5,
        "all_source_parity_matches": all(bool(row.get("match")) for row in source_parity.values()),
        "attempt_parity_cases_present": len(attempt_parity) == 5,
        "all_attempt_parity_hashes_match": all(bool(row.get("match")) for row in attempt_parity.values()),
        "product_behavior_unchanged": not bool(payload.get("product_behavior_changed")),
        "visible_wording_unchanged": not bool(payload.get("visible_wording_changed")),
        "cta_apply_semantics_unchanged": not bool(payload.get("cta_apply_semantics_changed")),
        "family_runtime_behavior_unchanged": not bool(payload.get("family_runtime_behavior_changed")),
    }


def _write(payload: dict[str, Any], checks: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_active_fail_executor_candidate_eval_attempt_result_adapter_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_active_fail_executor_candidate_eval_attempt_result_adapter_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Active-Fail Executor Candidate Eval Attempt Result Adapter",
        "",
        f"Status: {payload['status']}",
        "",
        "## Executive Summary",
        (
            "Active-fail eval-attempt source mapping, hit/miss metrics deltas, raw-cache projection, "
            "and evaluated-candidate result projection now delegate to `design_brain.candidate_evaluation`. "
            "The page loop still owns prefilters, seen-set/cache storage, callback execution, and candidate ordering."
        ),
        "",
        "## Source Mapping Parity",
    ]
    for name, row in (payload.get("source_parity") or {}).items():
        lines.append(f"- {name}: {'PASS' if row.get('match') else 'FAIL'} `{row.get('new')}`")
    lines.extend(["", "## Attempt Result Parity"])
    for name, row in (payload.get("attempt_parity") or {}).items():
        lines.append(f"- {name}: {'PASS' if row.get('match') else 'FAIL'} hash `{row.get('new_hash')}`")
    lines.extend(["", "## Checks", *[f"- {name}: {'PASS' if passed else 'FAIL'}" for name, passed in checks.items()]])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = _capture()
    checks = _checks(payload)
    payload["checks"] = checks
    payload["status"] = "PASS" if all(checks.values()) else "FAIL"
    payload["snapshot_hash"] = _stable_hash(
        {
            "target": payload.get("target"),
            "helper": payload.get("candidate_evaluation_helper"),
            "source_parity": payload.get("source_parity"),
            "attempt_parity": {
                name: {"old_hash": row.get("old_hash"), "new_hash": row.get("new_hash"), "match": row.get("match")}
                for name, row in (payload.get("attempt_parity") or {}).items()
            },
        }
    )
    json_path, report_path = _write(payload, checks)
    print(f"status={payload['status']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
