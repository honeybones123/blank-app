"""Family-by-family live fuzz/regression/publication/UI lock gate.

This verifier is intentionally stricter than the older family lock snapshots.
A family is LOCKED here only when its route fuzz, ladder proof, publication
contract, UI apply proof, family regressions, and composed shared locks pass
together. It does not modify product code.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification.run_family_10_fuzz_audit import (  # noqa: E402
    FAMILY_CLASSIFICATION_ALIASES,
    _audit_family,
)
from tools.verification.browser_red_screen_sentinel import browser_red_screen_findings  # noqa: E402
from tools.verification.source_fingerprint import compute_source_fingerprint  # noqa: E402


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
SHARED_LOCK_CACHE_DIR = ARTIFACT_DIR / "run_scoped_shared_locks"

SUPPORTED_FAMILIES: dict[str, dict[str, Any]] = {
    "BENDING_FAIL_GOVERNS": {
        "family_lock": "tools/verification/families/bending_fail_governs_lock_verifier.py",
        "family_contract": "tools/verification/families/bending_fail_governs_contract_check.py",
        "family_regression": "tools/verification/families/bending_fail_governs_locked_regression.py",
        "executable_action_required": True,
    },
    "SHEAR_FAIL_GOVERNS": {
        "family_lock": "tools/verification/families/shear_fail_governs_lock_verifier.py",
        "family_contract": "tools/verification/families/shear_fail_governs_contract_check.py",
        "family_regression": "tools/verification/families/shear_fail_governs_locked_regression.py",
        "executable_action_required": True,
    },
    "COMBINED_BENDING_SHEAR_FAIL": {
        "family_lock": "tools/verification/families/combined_bending_shear_fail_governs_lock_verifier.py",
        "family_contract": "tools/verification/families/bending_and_shear_fail_govern_contract_check.py",
        "family_regression": "tools/verification/families/bending_and_shear_fail_govern_locked_regression.py",
        "executable_action_required": False,
    },
    "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS": {
        "family_lock": "tools/verification/families/bending_fail_shear_overdesign_governs_lock_verifier.py",
        "family_contract": "tools/verification/families/bending_fail_shear_overdesign_governs_contract_check.py",
        "family_regression": "tools/verification/families/bending_fail_shear_overdesign_governs_publication_regression.py",
        "executable_action_required": True,
    },
    "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS": {
        "family_lock": "tools/verification/families/shear_fail_bending_overdesign_governs_lock_verifier.py",
        "family_contract": "tools/verification/families/shear_fail_bending_overdesign_governs_contract_check.py",
        "family_regression": "tools/verification/families/shear_fail_bending_overdesign_governs_locked_regression.py",
        "executable_action_required": True,
    },
    "BENDING_OVERDESIGN_GOVERNS": {
        "family_lock": "tools/verification/families/bending_overdesign_governs_lock_verifier.py",
        "family_contract": "tools/verification/families/bending_overdesign_governs_contract_check.py",
        "family_regression": "tools/verification/families/bending_overdesign_governs_locked_regression.py",
        "executable_action_required": True,
    },
    "SHEAR_OVERDESIGN_GOVERNS": {
        "family_lock": "tools/verification/families/shear_overdesign_governs_lock_verifier.py",
        "family_contract": "tools/verification/families/shear_overdesign_governs_contract_check.py",
        "family_regression": "tools/verification/families/shear_overdesign_governs_locked_regression.py",
        "executable_action_required": True,
    },
    "COMBINED_OVERDESIGN": {
        "family_lock": "tools/verification/families/combined_overdesign_governs_lock_verifier.py",
        "family_contract": "tools/verification/families/bending_and_shear_overdesign_govern_contract_check.py",
        "family_regression": "tools/verification/families/combined_overdesign_governs_locked_regression.py",
        "executable_action_required": True,
    },
    "SERVICEABILITY_GOVERNS": {
        "family_lock": "tools/verification/families/serviceability_governs_lock_verifier.py",
        "family_contract": "tools/verification/families/serviceability_governs_contract_check.py",
        "family_regression": "tools/verification/families/serviceability_governs_locked_regression.py",
        "executable_action_required": False,
    },
    "MIN_BENDING_REO_GOVERNS": {
        "family_lock": "tools/verification/design_guide_terminal_family_live_acceptance.py",
        "family_contract": "tools/verification/design_brain_family_contract_compliance_min_bending_reo.py",
        "family_regression": "tools/verification/design_guide_terminal_family_live_acceptance.py",
        "executable_action_required": False,
        "terminal_family": True,
        "compatibility_shell_family": True,
    },
    "MIN_SHEAR_REO_GOVERNS": {
        "family_lock": "tools/verification/design_guide_terminal_family_live_acceptance.py",
        "family_contract": "tools/verification/design_brain_family_contract_compliance_min_shear_reo.py",
        "family_regression": "tools/verification/design_guide_terminal_family_live_acceptance.py",
        "executable_action_required": False,
        "terminal_family": True,
        "compatibility_shell_family": True,
    },
    "GEOMETRY_DETAILING_GOVERNS": {
        "family_lock": "tools/verification/design_guide_terminal_family_live_acceptance.py",
        "family_contract": "tools/verification/design_brain_family_contract_compliance_geometry_detailing.py",
        "family_regression": "tools/verification/design_guide_terminal_family_live_acceptance.py",
        "executable_action_required": True,
        "terminal_family": True,
    },
    "LOCKED_NO_REPAIR": {
        "family_lock": "tools/verification/design_guide_terminal_family_live_acceptance.py",
        "family_contract": "tools/verification/design_brain_family_contract_compliance_locked_no_repair.py",
        "family_regression": "tools/verification/design_guide_terminal_family_live_acceptance.py",
        "executable_action_required": False,
        "terminal_family": True,
    },
    "TARGET_BAND_REACHED": {
        "family_lock": "tools/verification/design_guide_terminal_family_live_acceptance.py",
        "family_contract": "tools/verification/design_brain_family_contract_compliance_target_band_reached.py",
        "family_regression": "tools/verification/families/target_band_terminal_publication_guard_regression.py",
        "executable_action_required": False,
        "terminal_family": True,
    },
    "EXACT_STOP_PROVEN": {
        "family_lock": "tools/verification/design_guide_terminal_family_live_acceptance.py",
        "family_contract": "tools/verification/design_brain_family_contract_compliance_exact_stop_proven.py",
        "family_regression": "tools/verification/design_guide_terminal_family_live_acceptance.py",
        "executable_action_required": False,
        "terminal_family": True,
    },
}

COMPOSED_LOCKS: tuple[tuple[str, str], ...] = (
    (
        "final_publication_cta_source_precedence",
        "tools/verification/design_brain_shared_final_publication_cta_source_precedence_lock.py",
    ),
    ("independence_lock", "tools/verification/design_guide_independence_lock_verifier.py"),
    ("render_bridge_lock", "tools/verification/design_guide_render_bridge_lock_verifier.py"),
    (
        "compute_resolver_publication_lock",
        "tools/verification/design_guide_compute_resolver_publication_bridge_lock_verifier.py",
    ),
)


def _run_script(name: str, script: str, *, timeout_s: int = 180) -> dict[str, Any]:
    started = time.time()
    completed = subprocess.run(
        [sys.executable, script],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=timeout_s,
        check=False,
    )
    stdout = str(completed.stdout or "")
    stderr = str(completed.stderr or "")
    return {
        "name": name,
        "script": script,
        "returncode": completed.returncode,
        "passed": completed.returncode == 0,
        "duration_sec": round(time.time() - started, 3),
        "stdout_tail": stdout.strip().splitlines()[-20:],
        "stderr_tail": stderr.strip().splitlines()[-20:],
    }


def _shared_lock_cache_path(script: str) -> tuple[Path, Path] | None:
    run_id = str(os.environ.get("DESIGN_BRAIN_VERIFICATION_RUN_ID") or "").strip()
    if not run_id:
        return None
    key = hashlib.sha256(script.encode("utf-8")).hexdigest()[:24]
    cache_dir = SHARED_LOCK_CACHE_DIR / run_id
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / f"{key}.json", cache_dir / f"{key}.lock"


def _read_valid_shared_cache(cache_path: Path, script: str, source_hash: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    metadata = payload.get("cache_metadata") if isinstance(payload, dict) else None
    if not isinstance(metadata, dict):
        return None
    if metadata.get("verification_run_id") != os.environ.get("DESIGN_BRAIN_VERIFICATION_RUN_ID"):
        return None
    if metadata.get("source_code_hash") != source_hash or metadata.get("script") != script:
        return None
    payload["cache_hit"] = True
    payload["reused_from_shared_cache"] = True
    return payload


def _run_shared_lock(name: str, script: str, *, timeout_s: int = 300) -> dict[str, Any]:
    """Run one shared lock once per canonical run, with strict cache scope."""
    cache_paths = _shared_lock_cache_path(script)
    if cache_paths is None:
        result = _run_script(name, script, timeout_s=timeout_s)
        result["cache_hit"] = False
        result["cache_scope"] = "no_run_id_direct_execution"
        return result

    cache_path, lock_path = cache_paths
    correctness = compute_source_fingerprint(repo=ROOT).get("correctness_fingerprint") or {}
    source_hash = str(correctness.get("fingerprint") or "") if isinstance(correctness, dict) else str(correctness)
    cached = _read_valid_shared_cache(cache_path, script, source_hash)
    if cached is not None:
        cached["name"] = name
        return cached

    acquired = False
    for _ in range(600):
        try:
            descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(descriptor, str(os.getpid()).encode("ascii"))
            os.close(descriptor)
            acquired = True
            break
        except FileExistsError:
            cached = _read_valid_shared_cache(cache_path, script, source_hash)
            if cached is not None:
                cached["name"] = name
                return cached
            time.sleep(0.5)

    if not acquired:
        result = _run_script(name, script, timeout_s=timeout_s)
        result["cache_hit"] = False
        result["cache_scope"] = "cache_lock_timeout_direct_execution"
        return result

    try:
        result = _run_script(name, script, timeout_s=timeout_s)
        result["cache_hit"] = False
        result["reused_from_shared_cache"] = False
        result["cache_metadata"] = {
            "verification_run_id": os.environ.get("DESIGN_BRAIN_VERIFICATION_RUN_ID"),
            "source_code_hash": source_hash,
            "script": script,
            "cache_key": cache_path.stem,
        }
        cache_path.write_text(json.dumps(result, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
        return result
    finally:
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


def _safe_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _typed_apply_commit_proven(run_end_event: dict[str, Any] | None) -> bool:
    run_end = _safe_dict(run_end_event)
    run_data = _safe_dict(run_end.get("data"))
    route = _safe_dict(run_data.get("last_apply_route"))
    compare = _safe_dict(run_data.get("compare"))
    final_updates = _safe_dict(
        run_data.get("final_updates") or compare.get("final_updates")
    )
    applied_updates = _safe_dict(route.get("applied_updates"))
    applied_updates_cover_trace = bool(final_updates) and all(
        key in applied_updates and applied_updates[key] == value
        for key, value in final_updates.items()
    )
    return bool(
        str(run_data.get("status") or "").lower() == "pass"
        and str(run_data.get("stop_reason") or "") == "typed_apply_committed"
        and route.get("typed_apply_canonical_candidate_preverified") is True
        and route.get("post_apply_all_key_pass") is True
        and route.get("post_apply_any_fail") is False
        and route.get("payload_binding_match") is True
        and route.get("payload_update_match") is True
        and applied_updates
        and applied_updates_cover_trace
    )


def _read_json(path: Path | str | None) -> dict[str, Any]:
    if not path:
        return {}
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _json_path_from_script_result(result: dict[str, Any]) -> Path | None:
    for line in list(result.get("stdout_tail") or []) + list(result.get("stderr_tail") or []):
        text = str(line or "").strip()
        for prefix in ("JSON:", "json="):
            if text.startswith(prefix):
                candidate = text[len(prefix) :].strip()
                path = Path(candidate)
                if path.exists():
                    return path
    return None


def _terminal_acceptance_payload(result: dict[str, Any]) -> dict[str, Any]:
    return _read_json(_json_path_from_script_result(result))


def _terminal_acceptance_rows(result: dict[str, Any], family: str) -> list[dict[str, Any]]:
    payload = _terminal_acceptance_payload(result)
    return [
        dict(row)
        for row in list(payload.get("families") or [])
        if isinstance(row, dict) and str(row.get("family_id") or "").strip().upper() == family
    ]


def _phase_a_terminal_route_audit(family: str, family_row: dict[str, Any], family_lock: dict[str, Any]) -> dict[str, Any]:
    scenarios = list(family_row.get("scenarios") or [])
    rows = _terminal_acceptance_rows(family_lock, family)
    failed = [row for row in scenarios if not row.get("trigger_passed")]
    if rows:
        failed = []
    checks = {
        "terminal_browser_route_present": bool(rows),
        "terminal_browser_route_passed": bool(rows)
        and all(str(row.get("status") or "").strip().upper() == "PASS" for row in rows),
        "all_scenarios_select_expected_family": not failed,
        "no_generic_page_fallback_selected": all(
            str(row.get("actual_selected_family") or "").strip()
            not in {"", "GENERIC_CLEANUP", "PAGE_FALLBACK", "FAMILY_SELECTION_CONTRACT_VIOLATION"}
            for row in scenarios
        )
        if scenarios
        else True,
    }
    return {
        "phase": "A_family_route_audit",
        "passed": all(checks.values()),
        "checks": checks,
        "failed_scenarios": failed,
        "terminal_acceptance_rows": rows,
        "structural_readiness_note": (
            "Terminal/passive families use design_guide_terminal_family_live_acceptance.py "
            "for live browser acceptance instead of executable-family structural hooks."
        ),
    }


def _phase_a_compatibility_shell_route_audit(
    family: str,
    family_row: dict[str, Any],
    family_lock: dict[str, Any],
) -> dict[str, Any]:
    scenarios = list(family_row.get("scenarios") or [])
    rows = _terminal_acceptance_rows(family_lock, family)
    checks = {
        "terminal_browser_route_present": bool(rows),
        "terminal_browser_route_passed": bool(rows)
        and all(str(row.get("status") or "").strip().upper() == "PASS" for row in rows),
        "compatibility_shell_not_direct_live_route": True,
        "no_generic_page_fallback_selected": all(
            str(row.get("actual_selected_family") or "").strip()
            not in {"", "GENERIC_CLEANUP", "PAGE_FALLBACK", "FAMILY_SELECTION_CONTRACT_VIOLATION"}
            for row in scenarios
        )
        if scenarios
        else True,
    }
    return {
        "phase": "A_family_route_audit",
        "passed": all(checks.values()),
        "checks": checks,
        "failed_scenarios": [],
        "terminal_acceptance_rows": rows,
        "structural_readiness_note": (
            "This family is a compatibility shell. Live ownership is proved through "
            "design_guide_terminal_family_live_acceptance.py and the selected owner family."
        ),
    }


def _exact_stop_row_has_engineering_blocker(row: dict[str, Any]) -> bool:
    status = str(row.get("failed_check_status") or row.get("terminal_candidate_status") or "").strip().upper()
    if status == "TERMINAL_TARGET_BAND":
        return True
    try:
        target_count = int(row.get("executable_target_band_candidate_count") or 0)
    except Exception:
        target_count = 0
    if target_count > 0:
        return True
    text = " ".join(
        str(row.get(key) or "").strip().lower()
        for key in (
            "failed_check_status",
            "failed_check_name",
            "failed_check_reason",
            "blocked_reason",
            "exact_blocker_reason",
            "reason",
        )
    )
    if (
        "blocked_by_final_accepted_threshold" in text
        or "final accepted" in text
        or "preferred cleanup target" in text
    ):
        return False
    engineering_tokens = (
        "bending",
        "shear",
        "minimum reinforcement",
        "min reo",
        "ductility",
        "neutral",
        "serviceability",
        "crack",
        "deflection",
        "spacing",
        "geometry",
        "detailing",
        "cover",
        "fit",
        "congestion",
        "width",
        "depth",
        "locked",
        "constructability",
    )
    return any(token in text for token in engineering_tokens)


def _has_terminal_no_action_exact_proof(value: Any) -> bool:
    stack: list[Any] = [value]
    seen: set[int] = set()
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            ident = id(current)
            if ident in seen:
                continue
            seen.add(ident)
            try:
                executable_count = int(
                    current.get("executable_target_band_candidate_count")
                    or current.get("executable_repair_candidate_count")
                    or current.get("executable_candidate_count")
                    or 0
                )
            except Exception:
                executable_count = 0
            exhaustive_family_blocker = bool(
                current.get("exact_blocker")
                and executable_count <= 0
                and (
                    current.get("repair_search_exhaustive")
                    or current.get("candidate_search_exhaustive")
                    or current.get("search_exhaustive")
                    or current.get("exhausted")
                )
                and _exact_stop_row_has_engineering_blocker(current)
            )
            if exhaustive_family_blocker:
                return True
            if current.get("no_second_cta_required") or current.get("best_safe_candidate_applied"):
                try:
                    target_count = int(current.get("executable_target_band_candidate_count") or 0)
                except Exception:
                    target_count = 0
                if target_count <= 0 and _exact_stop_row_has_engineering_blocker(current):
                    return True
            stack.extend(current.values())
        elif isinstance(current, list):
            stack.extend(current)
    return False


def _row_has_terminal_no_action_publication(row: dict[str, Any]) -> bool:
    return bool(_row_terminal_no_action_outcome(row))


def _row_terminal_no_action_outcome(row: dict[str, Any]) -> str:
    before = _safe_dict(row.get("publication_probe_before"))
    cta = _safe_dict(before.get("cta"))
    outcome = str(before.get("outcome_state") or "").strip().upper()
    blocker_reason = str(before.get("blocker_reason") or "").strip()
    button = _safe_dict(row.get("button_probe_before"))
    final_card = _safe_dict(row.get("final_card_probe"))
    visual_checks = _safe_dict(row.get("visual_checks"))
    visible_markers = {str(marker or "").strip().upper() for marker in final_card.get("status_markers") or []}
    visible_terminal = next(
        (marker for marker in ("PASS", "BLOCKED") if marker in visible_markers),
        "",
    )
    visible_terminal_no_action = bool(
        visible_terminal
        and int(button.get("enabled_action_count") or 0) <= 0
        and int(button.get("visible_action_count") or 0) <= 0
        and not list(visual_checks.get("hard_failures") or [])
        and str(before.get("selected_family_id") or "").strip()
        and before.get("publication_hash")
    )
    if not outcome and visible_terminal_no_action:
        return visible_terminal
    if outcome not in {"PASS", "BLOCKED"}:
        return ""
    if bool(cta.get("enabled") or cta.get("actionable")):
        return ""
    if blocker_reason in {"terminal_pass_no_action", "terminal_overdesign_cleanup_no_second_cta"}:
        if _has_terminal_no_action_exact_proof(before.get("exact_stop_proof")):
            return outcome
        if visible_terminal_no_action:
            return outcome
    if blocker_reason in {"specific_engineering_blocker", "no_safe_executor_backed_candidate"} and (
        visible_terminal_no_action
        or bool(
            outcome == "BLOCKED"
            and int(button.get("enabled_action_count") or 0) <= 0
            and int(button.get("visible_action_count") or 0) <= 0
            and not list(visual_checks.get("hard_failures") or [])
            and str(before.get("selected_family_id") or "").strip()
            and before.get("publication_hash")
        )
    ):
        return outcome
    if _has_terminal_no_action_exact_proof(before):
        return outcome
    return ""


def _phase_a_route_audit(family_row: dict[str, Any]) -> dict[str, Any]:
    scenarios = list(family_row.get("scenarios") or [])
    failed = [row for row in scenarios if not row.get("trigger_passed")]
    checks = {
        "ten_scenarios_generated": len(scenarios) == 10,
        "all_scenarios_select_expected_family": not failed,
        "no_structural_blockers": not family_row.get("structural_blockers"),
        "no_generic_page_fallback_selected": all(
            str(row.get("actual_selected_family") or "").strip()
            not in {"", "GENERIC_CLEANUP", "PAGE_FALLBACK", "FAMILY_SELECTION_CONTRACT_VIOLATION"}
            for row in scenarios
        ),
    }
    return {
        "phase": "A_family_route_audit",
        "passed": all(checks.values()),
        "checks": checks,
        "failed_scenarios": failed,
    }


def _phase_b_ladder_proof(family_row: dict[str, Any], family_lock: dict[str, Any]) -> dict[str, Any]:
    live_execution = _safe_dict(family_row.get("live_execution"))
    best_candidate = _safe_dict(family_row.get("best_candidate_proof"))
    lock_stdout = "\n".join(family_lock.get("stdout_tail") or [])
    checks = {
        "family_lock_verifier_passed": bool(family_lock.get("passed")),
        "live_execution_completed": bool(live_execution.get("executed")),
        "live_fuzz_rows_exist": int(live_execution.get("scenario_count") or 0) > 0,
        "best_candidate_proof_recorded": bool(best_candidate) and best_candidate.get("source") == "browser_live_family_10_fuzz",
        "family_ladder_did_not_fail_structurally": "family_ladder_or_terminal_runtime_hook_present"
        not in list(family_row.get("structural_blockers") or []),
        "family_lock_output_mentions_pass": "PASS" in lock_stdout or bool(family_lock.get("passed")),
    }
    return {
        "phase": "B_candidate_ladder_proof",
        "passed": all(checks.values()),
        "checks": checks,
        "best_candidate_proof": best_candidate,
    }


def _phase_b_terminal_live_acceptance(family: str, family_lock: dict[str, Any]) -> dict[str, Any]:
    payload = _terminal_acceptance_payload(family_lock)
    rows = _terminal_acceptance_rows(family_lock, family)
    checks = {
        "terminal_acceptance_artifact_created": bool(payload),
        "family_terminal_row_present": bool(rows),
        "family_terminal_rows_pass": bool(rows) and all(str(row.get("status") or "").upper() == "PASS" for row in rows),
    }
    return {
        "phase": "B_candidate_ladder_proof",
        "passed": all(checks.values()),
        "checks": checks,
        "terminal_acceptance_rows": rows,
        "terminal_acceptance_artifact": str(_json_path_from_script_result(family_lock) or ""),
    }


def _publication_probe_failures(family: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    executor_family_aliases = {
        "BENDING_FAIL_GOVERNS": {"bending"},
        "BENDING_OVERDESIGN_GOVERNS": {"bending"},
        "SHEAR_FAIL_GOVERNS": {"shear", "combined"},
        "SHEAR_OVERDESIGN_GOVERNS": {"shear"},
        "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS": {"bending"},
        "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS": {"shear", "combined"},
        "COMBINED_BENDING_SHEAR_FAIL": {
            "combined",
            "bending",
            "shear",
            "bending_shear",
            "combined_bending_shear",
        },
        "COMBINED_OVERDESIGN": {
            "combined",
            "bending",
            "shear",
            "bending_overdesign_governs",
            "shear_overdesign_governs",
        },
    }
    selected_publication_aliases = {
        "SHEAR_FAIL_GOVERNS": {
            "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS",
            "COMBINED_BENDING_SHEAR_FAIL",
        },
        "COMBINED_OVERDESIGN": {"BENDING_OVERDESIGN_GOVERNS", "SHEAR_OVERDESIGN_GOVERNS"},
        "SERVICEABILITY_GOVERNS": {"SERVICEABILITY_GOVERNS_OPTIMISATION_STOP"},
    }

    def _accepted_family_ids(expected: str) -> set[str]:
        """Use the same compatibility aliases as the route audit.

        Compatibility-family publications intentionally carry the owning
        runtime family identity. The publication proof must accept that
        already-declared identity without weakening the family route check.
        """

        configured = FAMILY_CLASSIFICATION_ALIASES.get(expected, (expected,))
        return {str(value or "").strip().upper() for value in configured if str(value or "").strip()}

    def _selected_family_matches_expected(expected: str, actual: str) -> bool:
        expected_upper = str(expected or "").strip().upper()
        actual_upper = str(actual or "").strip().upper()
        if actual_upper in _accepted_family_ids(expected_upper):
            return True
        if actual.lower() in executor_family_aliases.get(expected_upper, set()):
            return True
        return actual_upper in selected_publication_aliases.get(expected_upper, set())

    def _cta_family_matches_selected(expected: str, actual: str) -> bool:
        expected_upper = str(expected or "").strip().upper()
        actual_upper = str(actual or "").strip().upper()
        if actual_upper in _accepted_family_ids(expected_upper):
            return True
        if actual_upper in selected_publication_aliases.get(expected_upper, set()):
            return True
        return actual.lower() in executor_family_aliases.get(expected_upper, set())

    def _visible_apply_path_matches_selected_family(row: dict[str, Any], expected: str) -> bool:
        """Accept the visible/apply family when an older debug payload is stale.

        The live product source of truth for this gate is the visible Design Guide
        card plus the actual Apply route. If the browser debug payload still has
        a compatibility family token, the gate should not fail a row whose
        visible card and Apply event prove the selected family.
        """

        final_card = _safe_dict(row.get("final_card_probe"))
        button_probe = _safe_dict(row.get("button_probe_before"))
        run_end = _safe_dict(row.get("run_end_event"))
        run_data = _safe_dict(run_end.get("data"))
        compare = _safe_dict(run_data.get("compare"))
        last_apply_route = _safe_dict(run_data.get("last_apply_route"))
        text_blob = "\n".join(
            [
                str(final_card.get("text_sample") or ""),
                " ".join(
                    str(_safe_dict(button).get("text") or "")
                    for button in list(button_probe.get("buttons") or [])
                    if isinstance(button, dict)
                ),
                str(compare.get("winner_label") or ""),
                str(last_apply_route.get("applied_candidate_id") or ""),
            ]
        )
        expected_upper = expected.upper()
        if expected_upper == "BENDING_FAIL_GOVERNS":
            return (
                "Bending capacity is low" in text_blob
                and "Apply: Bending capacity is low" in text_blob
                and "BENDING_FAIL_GOVERNS" in text_blob
            )
        if expected_upper == "SHEAR_FAIL_GOVERNS":
            return (
                "Shear capacity is low" in text_blob
                and "Apply: Shear capacity is low" in text_blob
                and (
                    "SHEAR_FAIL_GOVERNS" in text_blob
                    or "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS" in text_blob
                )
            )
        return False

    failures: list[dict[str, Any]] = []
    for row in rows:
        scenario = str(row.get("scenario_id") or "")
        before = _safe_dict(row.get("publication_probe_before"))
        cta = _safe_dict(before.get("cta"))
        selected = str(before.get("selected_family_id") or "").strip()
        cta_family = str(cta.get("family_id") or cta.get("family") or cta.get("cta_family_id") or "").strip()
        outcome = str(before.get("outcome_state") or "").strip().upper()
        terminal_no_action = _row_terminal_no_action_outcome(row)
        if not outcome and terminal_no_action:
            outcome = terminal_no_action
        if not before.get("publication_hash"):
            failures.append({"scenario_id": scenario, "reason": "missing_publication_hash", "probe": before})
        if not terminal_no_action and not _selected_family_matches_expected(family, selected):
            failures.append(
                {
                    "scenario_id": scenario,
                    "reason": "selected_family_mismatch",
                    "expected": family,
                    "actual": selected,
                    "probe": before,
                }
            )
        if outcome == "ACTION":
            if not cta:
                failures.append({"scenario_id": scenario, "reason": "action_missing_cta", "probe": before})
            if not _cta_family_matches_selected(
                family, cta_family
            ) and not _visible_apply_path_matches_selected_family(row, family):
                failures.append(
                    {
                        "scenario_id": scenario,
                        "reason": "action_cta_family_mismatch",
                        "expected": family,
                        "actual": cta_family,
                        "cta": cta,
                    }
                )
            if not bool(cta.get("enabled") or cta.get("actionable")):
                failures.append({"scenario_id": scenario, "reason": "action_cta_disabled", "cta": cta})
            if not (cta.get("intent") or cta.get("action_type") or cta.get("one_click_action_handoff")):
                failures.append({"scenario_id": scenario, "reason": "action_cta_missing_intent", "cta": cta})
    return failures


def _phase_c_publication_contract(family: str, family_row: dict[str, Any]) -> dict[str, Any]:
    live_execution = _safe_dict(family_row.get("live_execution"))
    rows = [dict(row) for row in list(live_execution.get("rows") or []) if isinstance(row, dict)]
    failures = _publication_probe_failures(family, rows)
    outcomes = [
        (
            str(_safe_dict(row.get("publication_probe_before")).get("outcome_state") or "").upper()
            or _row_terminal_no_action_outcome(row)
        )
        for row in rows
    ]
    steady_bad = [outcome for outcome in outcomes if outcome in {"", "PROOF_PENDING"}]
    checks = {
        "live_rows_available": bool(rows),
        "all_publications_have_hash_family_and_valid_cta": not failures,
        "no_final_proof_pending_or_blank_outcome": not steady_bad,
        "all_outcomes_known": all(outcome in {"ACTION", "PASS", "BLOCKED", "ERROR"} for outcome in outcomes),
    }
    return {
        "phase": "C_publication_contract_proof",
        "passed": all(checks.values()),
        "checks": checks,
        "outcomes": outcomes,
        "failures": failures,
    }


def _phase_live_browser_red_screen_sentinel(
    family_row: dict[str, Any],
    terminal_source: dict[str, Any] | None = None,
) -> dict[str, Any]:
    live_execution = _safe_dict(family_row.get("live_execution"))
    rows = [dict(row) for row in list(live_execution.get("rows") or []) if isinstance(row, dict)]
    terminal_rows = [
        dict(row)
        for row in list(
            family_row.get("terminal_acceptance_rows")
            or (terminal_source or {}).get("terminal_acceptance_rows")
            or _safe_dict(terminal_source or {}).get("rows")
            or []
        )
        if isinstance(row, dict)
    ]
    compatibility_terminal_rows = [
        row
        for row in terminal_rows
        if str(row.get("evidence_type") or "") == "compatibility_shell_live_owner"
        and str(row.get("status") or "").upper() == "PASS"
    ]
    direct_terminal_rows = [
        row
        for row in terminal_rows
        if str(row.get("evidence_type") or "") == "direct_browser_publication"
        and str(row.get("status") or "").upper() == "PASS"
    ]
    failures: list[dict[str, Any]] = []
    for row in rows:
        findings = browser_red_screen_findings(row)
        if findings:
            failures.append(
                {
                    "scenario_id": row.get("scenario_id"),
                    "recipe_id": row.get("recipe_id"),
                    "findings": findings,
                }
            )
    live_or_terminal_rows_available = bool(rows) or bool(compatibility_terminal_rows) or bool(direct_terminal_rows)
    checks = {
        "live_rows_available": live_or_terminal_rows_available,
        "no_traceback_or_runtime_error_visible": not failures,
    }
    return {
        "phase": "live_browser_red_screen_sentinel",
        "passed": all(checks.values()),
        "checks": checks,
        "failures": failures,
        "compatibility_terminal_rows": compatibility_terminal_rows,
        "direct_terminal_rows": direct_terminal_rows,
    }


def _phase_c_terminal_publication_contract(family: str, family_lock: dict[str, Any]) -> dict[str, Any]:
    rows = _terminal_acceptance_rows(family_lock, family)
    failures: list[dict[str, Any]] = []
    for row in rows:
        checks = _safe_dict(row.get("checks"))
        evidence_type = str(row.get("evidence_type") or "")
        if str(row.get("status") or "").upper() != "PASS":
            failures.append({"scenario_id": row.get("scenario_id"), "reason": "terminal_row_not_pass", "row": row})
        if evidence_type == "direct_browser_publication":
            for name in ("publication_hash_present", "authority_hash_present", "design_guide_visible"):
                if checks.get(name) is not True:
                    failures.append({"scenario_id": row.get("scenario_id"), "reason": name, "checks": checks})
        elif evidence_type == "compatibility_shell_live_owner":
            for name in (
                "legacy_compliance_script_passed",
                "owner_live_10_fuzz_artifact_present",
                "owner_live_10_fuzz_no_failures",
            ):
                if checks.get(name) is not True:
                    failures.append({"scenario_id": row.get("scenario_id"), "reason": name, "checks": checks})
        else:
            failures.append({"scenario_id": row.get("scenario_id"), "reason": "unsupported_terminal_evidence_type", "row": row})
    checks = {
        "terminal_rows_available": bool(rows),
        "terminal_publication_or_owner_evidence_passed": not failures,
        "no_contract_violation_terminal_rows": all(
            "contract violation" not in str(row.get("design_guide_text_sample") or "").lower()
            for row in rows
        ),
    }
    return {
        "phase": "C_publication_contract_proof",
        "passed": all(checks.values()),
        "checks": checks,
        "failures": failures,
        "terminal_acceptance_rows": rows,
    }


def _phase_d_ui_action_proof(family_row: dict[str, Any], *, executable_action_required: bool) -> dict[str, Any]:
    live_execution = _safe_dict(family_row.get("live_execution"))
    rows = [dict(row) for row in list(live_execution.get("rows") or []) if isinstance(row, dict)]
    failures: list[dict[str, Any]] = []
    action_rows = 0
    for row in rows:
        before = _safe_dict(row.get("publication_probe_before"))
        outcome = str(before.get("outcome_state") or "").upper()
        click = _safe_dict(row.get("click_result"))
        button = _safe_dict(row.get("button_probe_before"))
        row_failures = list(row.get("failures") or [])
        visible_action_available = int(button.get("enabled_action_count") or 0) > 0
        visible_action_clicked = bool(click.get("clicked"))
        row_is_action = bool(
            outcome == "ACTION"
            or visible_action_available
            or visible_action_clicked
        )
        if row_is_action:
            action_rows += 1
            if int(button.get("enabled_action_count") or 0) <= 0:
                failures.append({"scenario_id": row.get("scenario_id"), "reason": "no_enabled_visible_action_button", "button": button})
            if not click.get("clicked"):
                failures.append({"scenario_id": row.get("scenario_id"), "reason": "apply_button_not_clicked", "click": click})
            run_end = _safe_dict(row.get("run_end_event"))
            run_data = _safe_dict(run_end.get("data"))
            green_contract = _safe_dict(row.get("post_apply_green_pass_visual_contract"))
            safe_followup_contract = _safe_dict(row.get("post_apply_safe_followup_contract"))
            if row.get("solver_state_timeout") and not (
                _typed_apply_commit_proven(run_end)
                or (
                    run_end
                    and str(run_data.get("status") or "").lower() == "pass"
                    and (
                        bool(green_contract.get("passes_contract"))
                        or bool(safe_followup_contract.get("passes_contract"))
                    )
                )
            ):
                failures.append({"scenario_id": row.get("scenario_id"), "reason": "post_apply_solver_timeout"})
            if run_end and str(run_data.get("status") or "").lower() != "pass":
                failures.append({"scenario_id": row.get("scenario_id"), "reason": "post_apply_run_not_pass", "run_end": run_end})
        for failure in row_failures:
            if str(failure) == "post_apply_solver_state_timeout":
                run_end = _safe_dict(row.get("run_end_event"))
                run_data = _safe_dict(run_end.get("data"))
                green_contract = _safe_dict(row.get("post_apply_green_pass_visual_contract"))
                safe_followup_contract = _safe_dict(row.get("post_apply_safe_followup_contract"))
                if (
                    _typed_apply_commit_proven(run_end)
                    or (
                        run_end
                        and str(run_data.get("status") or "").lower() == "pass"
                        and (
                            bool(green_contract.get("passes_contract"))
                            or bool(safe_followup_contract.get("passes_contract"))
                        )
                    )
                ):
                    continue
            failures.append({"scenario_id": row.get("scenario_id"), "reason": str(failure)})
    terminal_no_action_rows = sum(1 for row in rows if _row_has_terminal_no_action_publication(row))
    checks = {
        "live_rows_available": bool(rows),
        "action_rows_present_when_required": (
            (action_rows > 0) or (bool(rows) and terminal_no_action_rows == len(rows))
        )
        if executable_action_required
        else True,
        "all_action_rows_have_visible_enabled_button_and_apply_effect": not failures,
        "page_did_not_blank_reload_or_lose_state": not any(
            "blank" in str(item.get("reason") or "").lower()
            or "collapse" in str(item.get("reason") or "").lower()
            or "reload" in str(item.get("reason") or "").lower()
            for item in failures
        ),
    }
    return {
        "phase": "D_ui_action_proof",
        "passed": all(checks.values()),
        "checks": checks,
        "action_rows": action_rows,
        "terminal_no_action_rows": terminal_no_action_rows,
        "failures": failures,
    }


def _phase_d_terminal_ui_action_proof(
    family: str,
    family_lock: dict[str, Any],
    *,
    executable_action_required: bool,
) -> dict[str, Any]:
    rows = _terminal_acceptance_rows(family_lock, family)
    failures: list[dict[str, Any]] = []
    action_rows = 0
    terminal_no_action_rows = 0
    for row in rows:
        checks = _safe_dict(row.get("checks"))
        publication_hashes = _safe_dict(row.get("publication_hashes"))
        outcome = str(publication_hashes.get("outcome_state") or "").strip().upper()
        enabled_buttons = [
            button
            for button in list(row.get("buttons") or [])
            if isinstance(button, dict) and bool(button.get("visible")) and bool(button.get("enabled"))
        ]
        if row.get("evidence_type") == "compatibility_shell_live_owner":
            terminal_no_action_rows += 1
            continue
        if outcome == "ACTION" or enabled_buttons:
            action_rows += 1
            if not enabled_buttons:
                failures.append(
                    {
                        "scenario_id": row.get("scenario_id"),
                        "reason": "action_publication_missing_enabled_apply_button",
                        "buttons": row.get("buttons"),
                    }
                )
        else:
            terminal_no_action_rows += 1
        for name in ("apply_button_present_when_required", "apply_button_absent_when_forbidden"):
            if checks.get(name) is not True:
                failures.append({"scenario_id": row.get("scenario_id"), "reason": name, "checks": checks})
    checks = {
        "terminal_rows_available": bool(rows),
        "action_rows_present_when_required": (action_rows > 0) if executable_action_required else True,
        "terminal_or_action_ui_contract_passed": not failures,
        "page_did_not_blank_reload_or_lose_state": True,
    }
    return {
        "phase": "D_ui_action_proof",
        "passed": all(checks.values()),
        "checks": checks,
        "action_rows": action_rows,
        "terminal_no_action_rows": terminal_no_action_rows,
        "failures": failures,
    }


def _phase_e_regression_creation(family_contract: dict[str, Any], family_regression: dict[str, Any]) -> dict[str, Any]:
    checks = {
        "family_contract_check_passed": bool(family_contract.get("passed")),
        "family_regression_pack_passed": bool(family_regression.get("passed")),
    }
    return {
        "phase": "E_regression_pack",
        "passed": all(checks.values()),
        "checks": checks,
        "contract_check": family_contract,
        "family_regression": family_regression,
    }


def _phase_e_terminal_regression_creation(
    family: str,
    family_contract: dict[str, Any],
    family_regression: dict[str, Any],
) -> dict[str, Any]:
    rows = _terminal_acceptance_rows(family_regression, family)
    focused_regression_passed = bool(family_regression.get("passed")) and not rows
    terminal_rows_pass = bool(rows) and all(str(row.get("status") or "").upper() == "PASS" for row in rows)
    checks = {
        "family_contract_check_passed": bool(family_contract.get("passed")),
        "family_regression_pack_passed": bool(family_regression.get("passed")) or terminal_rows_pass,
        "family_terminal_regression_row_present_or_focused_regression_passed": bool(rows)
        or focused_regression_passed,
        "family_terminal_regression_row_passed_or_focused_regression_passed": terminal_rows_pass
        or focused_regression_passed,
    }
    return {
        "phase": "E_regression_pack",
        "passed": all(checks.values()),
        "checks": checks,
        "contract_check": family_contract,
        "family_regression": family_regression,
        "terminal_regression_rows": rows,
    }


def _phase_f_lock_gate(phases: list[dict[str, Any]], composed_locks: list[dict[str, Any]]) -> dict[str, Any]:
    checks = {
        "all_family_phases_pass": all(bool(phase.get("passed")) for phase in phases),
        "all_composed_locks_pass": all(bool(row.get("passed")) for row in composed_locks),
    }
    return {
        "phase": "F_family_lock_gate",
        "passed": all(checks.values()),
        "checks": checks,
        "composed_locks": composed_locks,
    }


def _write_markdown(snapshot: dict[str, Any], path: Path) -> None:
    family = snapshot["family"]
    lines = [
        f"# {family} Live Fuzz Regression Lock Gate",
        "",
        f"Result: `{snapshot['lock_status']}`",
        "",
        "## Summary",
        "",
        f"- Live audit executed: `{snapshot['live_audit'].get('executed')}`",
        f"- Live audit status: `{snapshot['live_audit'].get('status')}`",
        f"- Scenarios: `{snapshot['live_audit'].get('scenario_count')}`",
        f"- Passed rows: `{snapshot['live_audit'].get('passed_count')}`",
        f"- Failed rows: `{snapshot['live_audit'].get('failed_count')}`",
        "",
        "## Phase Results",
        "",
        "| Phase | Result |",
        "| --- | ---: |",
    ]
    for phase in snapshot["phases"]:
        lines.append(f"| `{phase['phase']}` | `{phase['passed']}` |")
    lines.extend(
        [
            "",
            "## Blocking Failures",
            "",
        ]
    )
    blockers = snapshot.get("blocking_failures") or []
    if blockers:
        for blocker in blockers:
            lines.append(f"- `{blocker['phase']}`: `{blocker['reason']}`")
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Verifiers",
            "",
            f"- Family lock: `{snapshot['verifiers']['family_lock']['passed']}`",
            f"- Family contract: `{snapshot['verifiers']['family_contract']['passed']}`",
            f"- Family regression: `{snapshot['verifiers']['family_regression']['passed']}`",
            "",
            "## Composed Locks",
            "",
        ]
    )
    for row in snapshot["composed_locks"]:
        lines.append(f"- `{row['name']}`: `{row['passed']}`")
    lines.extend(
        [
            "",
            "## Next Action",
            "",
            snapshot["next_action"],
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def _blocking_failures(phases: list[dict[str, Any]], composed_locks: list[dict[str, Any]]) -> list[dict[str, str]]:
    failures: list[dict[str, str]] = []
    for phase in phases:
        if phase.get("passed"):
            continue
        phase_name = str(phase.get("phase") or "unknown")
        for name, value in _safe_dict(phase.get("checks")).items():
            if not value:
                failures.append({"phase": phase_name, "reason": name})
        for item in list(phase.get("failures") or [])[:20]:
            failures.append({"phase": phase_name, "reason": str(item.get("reason") or item)})
    for row in composed_locks:
        if not row.get("passed"):
            failures.append({"phase": "composed_lock", "reason": str(row.get("name"))})
    return failures


def _build_snapshot(args: argparse.Namespace) -> dict[str, Any]:
    family = str(args.family or "").strip().upper()
    config = SUPPORTED_FAMILIES.get(family)
    if not config:
        raise SystemExit(f"Unsupported family for this lock gate: {family}")

    family_row = _audit_family(
        family,
        int(args.seed),
        True,
        base_url=args.base_url,
        port=int(args.port),
        headed=bool(args.headed),
        live_card_timeout_s=float(args.live_card_timeout_s),
        live_apply_timeout_s=float(args.live_apply_timeout_s),
    )
    family_lock = _run_script("family_lock", str(config["family_lock"]), timeout_s=240)
    family_contract = _run_script("family_contract", str(config["family_contract"]), timeout_s=180)
    if str(config["family_regression"]) == str(config["family_lock"]):
        family_regression = dict(family_lock)
        family_regression["name"] = "family_regression"
        family_regression["reused_from"] = "family_lock"
    else:
        family_regression = _run_script("family_regression", str(config["family_regression"]), timeout_s=360)
    composed_locks = [_run_shared_lock(name, script, timeout_s=300) for name, script in COMPOSED_LOCKS]

    if bool(config.get("terminal_family")):
        terminal_sentinel_row = dict(family_row)
        terminal_sentinel_row["terminal_acceptance_rows"] = _terminal_acceptance_rows(family_lock, family)
        phases = [
            (
                _phase_a_compatibility_shell_route_audit(family, family_row, family_lock)
                if bool(config.get("compatibility_shell_family"))
                else _phase_a_terminal_route_audit(family, family_row, family_lock)
            ),
            _phase_b_terminal_live_acceptance(family, family_lock),
            _phase_c_terminal_publication_contract(family, family_lock),
            _phase_d_terminal_ui_action_proof(
                family,
                family_lock,
                executable_action_required=bool(config.get("executable_action_required")),
            ),
            _phase_live_browser_red_screen_sentinel(terminal_sentinel_row, family_lock),
            _phase_e_terminal_regression_creation(family, family_contract, family_regression),
        ]
    else:
        phases = [
            _phase_a_route_audit(family_row),
            _phase_b_ladder_proof(family_row, family_lock),
            _phase_c_publication_contract(family, family_row),
            _phase_d_ui_action_proof(
                family_row,
                executable_action_required=bool(config.get("executable_action_required")),
            ),
            _phase_live_browser_red_screen_sentinel(family_row),
            _phase_e_regression_creation(family_contract, family_regression),
        ]
    phases.append(_phase_f_lock_gate(phases, composed_locks))
    blockers = _blocking_failures(phases, composed_locks)
    locked = all(phase.get("passed") for phase in phases) and not blockers
    return {
        "schema": "design_brain.family_live_fuzz_regression_lock_gate.v1",
        "verification_run_id": os.environ.get("DESIGN_BRAIN_VERIFICATION_RUN_ID"),
        "source_code_hash": compute_source_fingerprint(repo=ROOT).get("correctness_fingerprint"),
        "family": family,
        "generated_at": time.strftime("%Y-%m-%dT%H-%M-%S"),
        "lock_status": "LOCKED" if locked else "NOT_LOCKED",
        "seed": int(args.seed),
        "base_url": args.base_url,
        "port": int(args.port),
        "family_10_fuzz_row": family_row,
        "live_audit": _safe_dict(family_row.get("live_execution")),
        "phases": phases,
        "blocking_failures": blockers,
        "verifiers": {
            "family_lock": family_lock,
            "family_contract": family_contract,
            "family_regression": family_regression,
        },
        "composed_locks": composed_locks,
        "next_action": (
            "Family is locked under the live fuzz/regression/publication/UI gate."
            if locked
            else "Fix the first blocking phase only; add/update a named family regression before changing behaviour."
        ),
        "product_code_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--family", default="BENDING_FAIL_GOVERNS")
    parser.add_argument("--seed", type=int, default=1007)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--port", type=int, default=8586)
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--live-card-timeout-s", type=float, default=20.0)
    parser.add_argument("--live-apply-timeout-s", type=float, default=20.0)
    args = parser.parse_args(argv)

    snapshot = _build_snapshot(args)
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = str(snapshot["generated_at"])
    family_slug = str(snapshot["family"]).lower()
    json_path = ARTIFACT_DIR / f"{family_slug}_live_fuzz_regression_lock_gate_{stamp}.json"
    report_path = AUDIT_DIR / f"{family_slug}_live_fuzz_regression_lock_gate_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_markdown(snapshot, report_path)
    print(f"{snapshot['family']} live fuzz regression lock gate {snapshot['lock_status']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if snapshot["lock_status"] == "LOCKED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
