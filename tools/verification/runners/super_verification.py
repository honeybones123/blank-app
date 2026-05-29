from __future__ import annotations

import argparse
import json
import subprocess
import sys
import traceback
from datetime import datetime
from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
TOOLS = REPO / "tools"
RUNNERS = TOOLS / "verification" / "runners"
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tools.verification.helpers.overdesign_assertions import (  # noqa: E402
    assert_no_unresolved_material_overdesign,
    assert_visible_output_matches_one_click_contract,
)

MAX_CAPTURED_RUNNER_TEXT = 20000
CHILD_RUNNER_TIMEOUT_SECONDS = 7200
TIMESTAMP = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
REQUIRED_BROWSER_MODE_MESSAGE = "Required browser-visible contract case did not run in browser_live mode"
EXPECTED_MATRIX_CHOOSER_CASE_COUNT = 27


def _float_or_none(value) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def run_script(cmd: list[str]) -> tuple[str, str, str]:
    try:
        result = subprocess.run(  # noqa: S603
            cmd,
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=CHILD_RUNNER_TIMEOUT_SECONDS,
        )
        status = "PASS" if result.returncode == 0 else "FAIL"
        return status, _trim_runner_text(result.stdout or ""), _trim_runner_text(result.stderr or "")
    except Exception:
        return "CRASH", "", _trim_runner_text(traceback.format_exc())


def _trim_runner_text(text: str) -> str:
    if len(text) <= MAX_CAPTURED_RUNNER_TEXT:
        return text
    omitted = len(text) - MAX_CAPTURED_RUNNER_TEXT
    return f"[... omitted {omitted} chars ...]\n{text[-MAX_CAPTURED_RUNNER_TEXT:]}"


def get_latest_artifact(pattern: str, *, newer_than: float | None = None) -> Path | None:
    roots = [
        REPO,
        Path.cwd(),
        Path(r"C:\Users\jono\Documents\Codex\2026-04-21-files-mentioned-by-the-user-shared"),
    ]
    candidates: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        try:
            if not root.exists():
                continue
            for path in root.rglob(pattern):
                if path.is_file() and path not in seen:
                    if newer_than is not None and path.stat().st_mtime < newer_than:
                        continue
                    seen.add(path)
                    candidates.append(path)
        except Exception:
            continue
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def load_json(path: Path | None) -> tuple[dict, str | None]:
    if path is None:
        return {}, "missing_artifact"
    try:
        return json.loads(path.read_text(encoding="utf-8-sig")), None
    except Exception:
        return {}, traceback.format_exc()


def _gate_validity_reasons(
    *,
    source_data: dict | None = None,
    runner_status: str | None = None,
) -> list[str]:
    data = dict(source_data or {})
    reasons: list[str] = []
    if runner_status and runner_status != "PASS":
        reasons.append(f"runner_status:{runner_status}")
    top_level_verdict = str(data.get("verdict") or data.get("status") or "").strip().upper()
    if top_level_verdict in {"FAIL", "INVALID", "CRASH"}:
        reasons.append(f"top_level_verdict:{top_level_verdict}")
    verifier_validity = str(data.get("verifier_validity_status") or "").strip().upper()
    if verifier_validity == "INVALID":
        reasons.append("verifier_validity_status:INVALID")
    one_click_status = str(data.get("one_click_contract_status") or "").strip().upper()
    if one_click_status and one_click_status != "PASS":
        reasons.append(f"one_click_contract_status:{one_click_status}")
    for key, value in data.items():
        if not str(key).lower().endswith("returncode"):
            continue
        try:
            if value is not None and int(value) != 0:
                reasons.append(f"{key}:{value}")
        except (TypeError, ValueError):
            reasons.append(f"{key}:{value}")
    return reasons


def _apply_gate_validity(
    gate: dict,
    *,
    source_data: dict | None = None,
    runner_status: str | None = None,
) -> dict:
    gate = dict(gate)
    if runner_status is not None:
        gate["runner_status"] = runner_status
    reasons = _gate_validity_reasons(source_data=source_data, runner_status=runner_status)
    if source_data:
        for key in ("verdict", "verifier_validity_status", "one_click_contract_status"):
            if key in source_data:
                gate[f"source_{key}"] = source_data.get(key)
        for key, value in source_data.items():
            if str(key).lower().endswith("returncode"):
                gate[key] = value
    if reasons:
        existing = list(gate.get("gate_validity_fail_reasons") or [])
        gate["gate_validity_fail_reasons"] = existing + [
            reason for reason in reasons if reason not in existing
        ]
        gate["status"] = "FAIL"
        try:
            gate["fail_count"] = max(int(gate.get("fail_count", 0) or 0), 1)
        except (TypeError, ValueError):
            gate["fail_count"] = 1
    return gate


def _gate_passed(gate: dict) -> bool:
    return str(gate.get("status") or "").upper() == "PASS" and not gate.get("gate_validity_fail_reasons")


def _required_browser_mode_failures(
    cases: list[dict],
    *,
    required_case_ids: set[str] | None = None,
    require_all_cases: bool = False,
) -> list[dict]:
    failures: list[dict] = []
    for case in cases:
        case_id = str(case.get("case_id") or case.get("name") or "")
        if not require_all_cases and required_case_ids is not None and case_id not in required_case_ids:
            continue
        browser_mode = str(case.get("browser_mode") or "").strip()
        if browser_mode != "browser_live":
            failures.append(
                {
                    "case_id": case_id,
                    "browser_mode": browser_mode or "missing",
                    "message": REQUIRED_BROWSER_MODE_MESSAGE,
                }
            )
    return failures


def _case_identifier(case: dict) -> str:
    return str(case.get("case_id") or case.get("name") or case.get("id") or "unknown")


def _guidance_text_blob(case: dict) -> str:
    chunks: list[str] = []
    for key in (
        "selected_action",
        "advisory_reason",
        "final_explanation",
        "run_end_stop_reason",
        "failure_reason",
    ):
        value = case.get(key)
        if value is not None:
            chunks.append(str(value))
    for key in (
        "offline_guidance_primary",
        "offline_guidance_debug",
        "pre_click_guidance_primary",
        "post_click_guidance_primary",
        "decision_trace",
    ):
        value = case.get(key)
        if isinstance(value, dict):
            chunks.append(json.dumps(value, default=str))
    chunks.append(json.dumps(case, default=str))
    return "\n".join(chunks).lower()


def _unresolved_signal(case: dict) -> bool:
    blob = _guidance_text_blob(case)
    return any(
        phrase in blob
        for phrase in (
            "cleanup proof unresolved",
            "proof unresolved",
            "no_actionable_cleanup_candidate",
            "cleanup is advisory",
            "valid shear cleanup exists",
            "real optimiser gap",
            "no material one-click update",
        )
    )


def _engineering_blocker_signal(case: dict) -> bool:
    blob = _guidance_text_blob(case)
    return any(
        phrase in blob
        for phrase in (
            "minimum geometry",
            "minimum reinforcement",
            "minimum detailing",
            "spacing",
            "ductility",
            "locked",
            "cannot fit",
            "cover",
            "bar arrangement",
            "code",
            "discrete",
            "catalogue",
            "exact blocker",
            "exhaustive",
        )
    )


def _case_statuses(case: dict) -> dict:
    summary = dict(case.get("pre_click_summary") or case.get("visible_summary_before") or {})
    statuses = summary.get("statuses")
    if isinstance(statuses, dict):
        return {str(k).lower(): str(v).upper() for k, v in statuses.items()}
    parsed: dict[str, str] = {}
    visible = case.get("visible_summary_before")
    if isinstance(visible, dict):
        for family in ("bending", "shear"):
            row = visible.get(family)
            if isinstance(row, dict) and row.get("status"):
                parsed[family] = str(row.get("status")).upper()
    return parsed


def _case_utils(case: dict) -> dict:
    summary = dict(case.get("pre_click_summary") or {})
    utils = summary.get("utils")
    if isinstance(utils, dict):
        return {str(k).lower(): _float_or_none(v) for k, v in utils.items()}
    utils = case.get("family_utils")
    if isinstance(utils, dict):
        return {str(k).lower(): _float_or_none(v) for k, v in utils.items()}
    return {}


def _case_has_resolved_target_band_action(case: dict) -> bool:
    primaries = [
        dict(case.get("pre_click_guidance_primary") or {}),
        dict(case.get("offline_guidance_primary") or {}),
        dict(case.get("post_click_guidance_primary") or {}),
    ]
    trace = dict(case.get("decision_trace") or {})
    for primary in primaries:
        updates = dict(primary.get("updates") or {})
        evidence = dict(primary.get("candidate_search_evidence") or {})
        if not updates:
            updates = dict(evidence.get("selected_candidate_updates") or {})
        reaches_target = bool(
            primary.get("resolved_candidate_reaches_target_band")
            or primary.get("reaches_target_band")
            or evidence.get("best_target_band_candidate_id")
            or int(evidence.get("target_band_candidate_count") or 0) > 0
        )
        executor_backed = bool(
            updates
            and (
                primary.get("resolved_one_click")
                or primary.get("action_type")
                or evidence.get("selected_candidate_id")
            )
        )
        if executor_backed and reaches_target:
            return True
    return bool(trace.get("selected_primary_direct_target_band"))


def _classify_unresolved_case(source: str, case: dict, *, default_required: bool = False) -> dict | None:
    if not _unresolved_signal(case):
        return None
    if _case_has_resolved_target_band_action(case):
        return None
    primary_title_blob = " ".join(
        str((case.get(key) or {}).get("title") or (case.get(key) or {}).get("title_main") or "")
        for key in ("pre_click_guidance_primary", "offline_guidance_primary", "post_click_guidance_primary")
        if isinstance(case.get(key), dict)
    ).lower()
    if (
        "blocked by discrete detailing limits" in primary_title_blob
        or "blocked by discrete target-band limits" in primary_title_blob
    ) and _engineering_blocker_signal(case):
        return None
    cid = _case_identifier(case)
    blob = _guidance_text_blob(case)
    statuses = _case_statuses(case)
    utils = _case_utils(case)
    active_failure = any(status == "FAIL" for status in statuses.values())
    low_controllable = any(value is not None and value < 0.70 for value in utils.values())
    material_families = list(case.get("materially_overprovided_families") or [])
    valid_candidate_blocked = "valid shear cleanup exists" in blob
    real_gap = "real optimiser gap" in blob
    generic_unresolved = "cleanup proof unresolved" in blob or "no material one-click update" in blob
    forbidden_generic_unresolved = bool(
        generic_unresolved
        or "bounded evidence budget" in blob
        or "generic_unresolved_cleanup_card_forbidden" in blob
        or "design guide needs a verified cleanup result" in blob
    )
    has_blocker = _engineering_blocker_signal(case)
    required = bool(
        default_required
        or active_failure
        or material_families
        or valid_candidate_blocked
        or real_gap
        or forbidden_generic_unresolved
        or (low_controllable and not has_blocker)
    )
    return {
        "source": source,
        "case_id": cid,
        "status": "REQUIRED" if required else "ADVISORY",
        "reason": (
            "unresolved_required"
            if required
            else "unresolved_advisory_with_engineering_blocker_or_non_required_context"
        ),
        "active_failure": active_failure,
        "low_controllable_family": low_controllable,
        "materially_overprovided_families": material_families,
        "has_engineering_blocker_signal": has_blocker,
        "forbidden_generic_unresolved": forbidden_generic_unresolved,
        "title": (
            str((case.get("pre_click_guidance_primary") or {}).get("title") or "")
            or str((case.get("offline_guidance_primary") or {}).get("title") or "")
            or str(case.get("selected_action") or "")
        ),
    }


def _split_unresolved_cases(
    cases: list[dict],
    source: str,
    *,
    default_required: bool = False,
) -> tuple[list[dict], list[dict]]:
    required: list[dict] = []
    advisory: list[dict] = []
    for case in cases:
        entry = _classify_unresolved_case(source, case, default_required=default_required)
        if not entry:
            continue
        if entry["status"] == "REQUIRED":
            required.append(entry)
        else:
            advisory.append(entry)
    return required, advisory


def parse_golden(data: dict) -> dict:
    cases = list(data.get("cases") or data.get("steps") or [])
    summary = dict(data.get("summary") or {})
    pass_count = int(summary.get("PASS_count", 0) or 0)
    fail_count = int(summary.get("FAIL_count", 0) or 0)
    expected_no_commit = int(summary.get("EXPECTED_NO_COMMIT_count", 0) or 0)
    stale_flags = 0
    alignment_failures = 0
    not_reaching_band = 0
    for case in cases:
        validation = dict(case.get("validation") or {})
        stale = dict(case.get("stale_state_flags") or {})
        if bool(validation.get("stale_state_issue")) or any(bool(v) for v in stale.values()):
            stale_flags += 1
        align = dict(case.get("truth_layer_alignment") or {})
        post_publish_aligned = validation.get("post_publish_aligned")
        if (align and not bool(align.get("aligned", True))) or post_publish_aligned is False:
            alignment_failures += 1
        stop_reason = str(
            case.get("run_end_stop_reason")
            or validation.get("stop_reason")
            or (((case.get("run_end_event") or {}).get("data") or {}).get("stop_reason"))
            or ""
        ).strip()
        if stop_reason in {"best_available_out_of_band_candidate", "legitimate_constrained_stop"}:
            not_reaching_band += 1
        no_commit_expected = bool(validation.get("no_commit_expected"))
        if no_commit_expected:
            expected_no_commit += 1
        final_statuses = dict(validation.get("final_statuses") or {})
        already_settled_pass = (
            not bool(validation.get("button_found", True))
            and not bool(validation.get("run_end_present", True))
            and not bool(validation.get("telemetry_gap", False))
            and validation.get("post_publish_aligned") is not False
            and not bool(validation.get("stale_state_issue", False))
            and final_statuses
            and all(status in {"PASS", "INFO", "NEAR LIMIT", "—", "-"} for status in final_statuses.values())
        )
        case_failed = (
            bool(case.get("click_error"))
            or not bool(validation.get("pre_actions_match", True))
            or not bool(validation.get("post_actions_match", True))
            or not bool(validation.get("pre_shared_match", True))
            or not bool(validation.get("post_shared_match", True))
            or not bool(validation.get("stale_feedback_cleared", True))
            or (not bool(validation.get("button_found", True)) and not already_settled_pass)
            or (not bool(validation.get("run_end_present", True)) and not already_settled_pass)
            or bool(validation.get("telemetry_gap", False))
            or post_publish_aligned is False
            or bool(validation.get("stale_state_issue", False))
        )
        if case_failed and not no_commit_expected:
            fail_count += 1
        elif not case_failed and not no_commit_expected:
            pass_count += 1
    return {
        "artifact": str(data.get("_artifact_path") or ""),
        "total_cases": int(summary.get("total_cases", len(cases)) or len(cases)),
        "pass_count": pass_count,
        "fail_count": fail_count,
        "expected_no_commit_count": expected_no_commit,
        "stale_state_flags": stale_flags,
        "truth_layer_alignment_failures": alignment_failures,
        "cases_not_reaching_target_band": not_reaching_band,
        "status": "PASS" if fail_count == 0 else "FAIL",
    }


def parse_contract(data: dict) -> dict:
    summary = dict(data.get("summary") or {})
    cases = [dict(c) for c in list(data.get("cases") or [])]
    browser_mode_failures = _required_browser_mode_failures(cases, require_all_cases=True)
    material_overdesign_failures = [
        f"{case.get('case_id')}:{reason}"
        for case in cases
        for reason in list(case.get("material_overdesign_audit_failures") or [])
    ]
    fail_count = int(summary.get("FAIL_count", 0) or 0)
    effective_fail_count = fail_count + len(browser_mode_failures) + len(material_overdesign_failures)
    return {
        "artifact": str(data.get("_artifact_path") or ""),
        "total_cases": int(summary.get("total_cases", 0) or 0),
        "pass_count": int(summary.get("PASS_count", 0) or 0),
        "fail_count": effective_fail_count,
        "raw_fail_count": fail_count,
        "required_browser_mode_failures": browser_mode_failures,
        "required_browser_mode_failure_count": len(browser_mode_failures),
        "material_overdesign_audit_failures": material_overdesign_failures,
        "actionable_card_rejected_after_click": int(
            summary.get("cases_with_actionable_card_but_rejected_click", 0) or 0
        ),
        "non_governing_cleanup_rejection": int(
            summary.get("cases_with_non_governing_cleanup_rejection", 0) or 0
        ),
        "no_actionable_candidates": int(summary.get("cases_with_no_actionable_candidates", 0) or 0),
        "source_action_type_mismatch": int(
            summary.get("cases_with_source_action_type_mismatch", 0) or 0
        ),
        "misleading_best_available_out_of_band_candidate": int(
            summary.get("cases_with_misleading_best_available_out_of_band_candidate", 0) or 0
        ),
        "hidden_secondary_driving_cta": 0,
        "status": "PASS" if effective_fail_count == 0 else "FAIL",
    }


def parse_optimisation(data: dict) -> dict:
    summary = dict(data.get("summary") or {})
    cases = [dict(case) for case in list(data.get("cases") or [])]
    advisory_only = int(
        summary.get(
            "shear_optimisation_advisory_only",
            summary.get("cases_where_shear_optimisation_is_advisory_only", 0),
        )
        or 0
    )
    real_gap = int(
        summary.get(
            "real_optimiser_gap",
            summary.get("cases_where_this_is_a_real_optimiser_gap", 0),
        )
        or 0
    )
    material_overdesign_audit_failure_count = int(summary.get("material_overdesign_audit_failure_count", 0) or 0)
    unresolved_required, unresolved_advisory = _split_unresolved_cases(cases, "shear_overdesign")
    if not advisory_only and not real_gap and cases:
        for case in cases:
            trace = dict(case.get("decision_trace") or {})
            final_threshold_blocker = (
                "unresolved_meaningful_family_util_below_0.85"
                in str(trace.get("advisory_reason") or case.get("advisory_reason") or "")
            )
            if (
                bool(trace.get("contract_gate_blocked"))
                or trace.get("advisory_reason")
            ) and not final_threshold_blocker:
                advisory_only += 1
            explanation = str(trace.get("final_explanation") or "").lower()
            if "real optimiser gap" in explanation:
                real_gap += 1
    if real_gap:
        existing_required = {case["case_id"] for case in unresolved_required}
        for case in cases:
            blob = _guidance_text_blob(dict(case))
            if "valid shear cleanup exists" not in blob and "real optimiser gap" not in blob:
                continue
            entry = _classify_unresolved_case(
                "shear_overdesign",
                dict(case),
                default_required=True,
            )
            if entry and entry["case_id"] not in existing_required:
                unresolved_required.append(entry)
                existing_required.add(entry["case_id"])
    effective_fail_count = real_gap + material_overdesign_audit_failure_count + len(unresolved_required)
    return {
        "artifact": str(data.get("_artifact_path") or ""),
        "total_cases": int(summary.get("total_cases", len(cases)) or len(cases)),
        "no_shear_reduction_candidates_generated": int(
            summary.get("no_shear_reduction_candidates_generated", 0) or 0
        ),
        "candidates_generated_but_filtered": int(
            summary.get("candidates_generated_but_filtered", 0) or 0
        ),
        "valid_candidates_survived_but_not_selected": int(
            summary.get("valid_candidates_survived_but_not_selected", 0) or 0
        ),
        "blocked_by_non_governing_cleanup": int(
            summary.get("blocked_by_non_governing_cleanup", 0) or 0
        ),
        "blocked_by_no_resolved_one_click_candidate": int(
            summary.get("blocked_by_no_resolved_one_click_candidate", 0) or 0
        ),
        "blocked_by_minimum_detailing_spacing_limits": int(
            summary.get("blocked_by_minimum_detailing_spacing_limits", 0) or 0
        ),
        "advisory_only_shear_optimisation": advisory_only,
        "real_optimiser_gap": real_gap,
        "material_overdesign_audit_failure_count": material_overdesign_audit_failure_count,
        "unresolved_required_cases": unresolved_required,
        "unresolved_advisory_cases": unresolved_advisory,
        "unresolved_required_count": len(unresolved_required),
        "unresolved_advisory_count": len(unresolved_advisory),
        "fail_count": effective_fail_count,
        "status": "PASS" if effective_fail_count == 0 else "FAIL",
    }


def parse_optimisation_expectation(data: dict) -> dict:
    summary = dict(data.get("summary") or {})
    cases = [dict(c) for c in list(data.get("cases") or [])]
    material_overdesign_failures = [
        f"{case.get('case_id')}:{reason}"
        for case in cases
        for reason in list(case.get("material_overdesign_audit_failures") or [])
    ]
    fail_count = int(summary.get("FAIL_count", 0) or 0)
    unresolved_required, unresolved_advisory = _split_unresolved_cases(
        cases,
        "optimisation_expectation",
    )
    effective_fail_count = fail_count + len(material_overdesign_failures) + len(unresolved_required)
    return {
        "artifact": str(data.get("_artifact_path") or ""),
        "total_cases": int(summary.get("total_cases", 0) or 0),
        "pass_count": int(summary.get("PASS_count", 0) or 0),
        "fail_count": effective_fail_count,
        "raw_fail_count": fail_count,
        "material_overdesign_audit_failures": material_overdesign_failures,
        "unresolved_required_cases": unresolved_required,
        "unresolved_advisory_cases": unresolved_advisory,
        "unresolved_required_count": len(unresolved_required),
        "unresolved_advisory_count": len(unresolved_advisory),
        "unsafe_accepted_count": int(summary.get("unsafe_accepted_count", 0) or 0),
        "below_target_incorrectly_accepted_count": int(
            summary.get("below_target_incorrectly_accepted_count", 0) or 0
        ),
        "practical_blocker_explained_count": int(
            summary.get("practical_blocker_explained_count", 0) or 0
        ),
        "optimisation_applied_count": int(summary.get("optimisation_applied_count", 0) or 0),
        "remaining_overdesign_unexplained_count": int(
            summary.get("remaining_overdesign_unexplained_count", 0) or 0
        ),
        "in_target_band_actionable_final_tightening_count": int(
            summary.get("in_target_band_actionable_final_tightening_count", 0) or 0
        ),
        "unnecessary_strengthening_count": int(
            summary.get("unnecessary_strengthening_count", 0) or 0
        ),
        "unnecessary_shear_strengthening_count": int(
            summary.get("unnecessary_shear_strengthening_count", 0) or 0
        ),
        "unnecessary_strengthening_cases": list(summary.get("unnecessary_strengthening_cases") or []),
        "status": "PASS" if effective_fail_count == 0 else "FAIL",
    }


def parse_summary_truth(data: dict) -> dict:
    summary = dict(data.get("summary") or {})
    fail_count = int(summary.get("FAIL_count", 0) or 0)
    return {
        "artifact": str(data.get("_artifact_path") or ""),
        "total_cases": int(summary.get("total_cases", 0) or 0),
        "pass_count": int(summary.get("PASS_count", 0) or 0),
        "fail_count": fail_count,
        "false_pass_count": int(summary.get("false_pass_count", 0) or 0),
        "false_fail_count": int(summary.get("false_fail_count", 0) or 0),
        "missing_governing_status_count": int(summary.get("missing_governing_status_count", 0) or 0),
        "misleading_target_band_count": int(summary.get("misleading_target_band_count", 0) or 0),
        "ductility_false_pass_count": int(summary.get("ductility_false_pass_count", 0) or 0),
        "ductility_unknown_accepted_count": int(summary.get("ductility_unknown_accepted_count", 0) or 0),
        "status": "PASS" if fail_count == 0 else "FAIL",
    }


def parse_ductility_expectation(data: dict) -> dict:
    summary = dict(data.get("summary") or {})
    false_pass = int(summary.get("ductility_false_pass_count", 0) or 0)
    unknown_accepted = int(summary.get("ductility_unknown_accepted_count", 0) or 0)
    fail_count = false_pass + unknown_accepted
    return {
        "artifact": str(data.get("_artifact_path") or ""),
        "false_pass_count": false_pass,
        "unknown_accepted_count": unknown_accepted,
        "fail_count": fail_count,
        "status": "PASS" if fail_count == 0 else "FAIL",
    }


def parse_matrix_chooser(data: dict) -> dict:
    cases = [dict(case) for case in list(data.get("cases") or [])]
    browser_mode_failures = _required_browser_mode_failures(cases, require_all_cases=True)
    fail_count = int(data.get("fail_count", data.get("matrix_chooser_fail", 1)) or 0)
    total_cases = int(data.get("total_cases", data.get("matrix_chooser_total", 0)) or 0)
    skipped_count = max(EXPECTED_MATRIX_CHOOSER_CASE_COUNT - total_cases, 0)
    skipped_cases = [
        {
            "source": "matrix_chooser",
            "case_id": f"missing_matrix_case_{index + 1}",
            "status": "SKIPPED",
            "reason": "active_matrix_case_not_covered_by_matrix_chooser_verifier",
        }
        for index in range(skipped_count)
    ]
    status = str(data.get("matrix_chooser_status") or data.get("status") or data.get("verdict") or "").upper()
    if status != "PASS":
        status = "FAIL"
    if fail_count or browser_mode_failures or skipped_count:
        status = "FAIL"
    return {
        "artifact": str(data.get("_artifact_path") or data.get("matrix_chooser_artifact") or ""),
        "status": status,
        "matrix_chooser_required_gate": True,
        "matrix_chooser_status": status,
        "matrix_chooser_total": total_cases,
        "matrix_chooser_pass": int(data.get("matrix_chooser_pass", data.get("pass_count", 0)) or 0),
        "matrix_chooser_fail": fail_count,
        "total_cases": total_cases,
        "pass_count": int(data.get("pass_count", data.get("matrix_chooser_pass", 0)) or 0),
        "fail_count": fail_count + skipped_count,
        "failures": list(data.get("failures") or []),
        "fail_reasons": list(data.get("fail_reasons") or []),
        "required_browser_mode_failures": browser_mode_failures,
        "required_browser_mode_failure_count": len(browser_mode_failures),
        "unresolved_required_cases": [],
        "unresolved_advisory_cases": [],
        "unresolved_skipped_cases": skipped_cases,
        "unresolved_required_count": 0,
        "unresolved_advisory_count": 0,
        "unresolved_skipped_count": skipped_count,
    }


def parse_real_user_terminal_case(data: dict) -> dict:
    target_case_ids = {
        "BENDING_LOW_SHEAR_IN_TARGET_TERMINAL",
        "BENDING_LOW_SHEAR_IN_TARGET_LOCAL_CLEANUP",
        "SHEAR_LOW_BENDING_IN_TARGET_LOCAL_CLEANUP",
        "SERVICEABILITY_LOW_BENDING_IN_TARGET_LOCAL_CLEANUP",
        "GEOMETRY_LOW_REO_OR_SHEAR_IN_TARGET_LOCAL_CLEANUP",
    }
    cases = list(data.get("cases") or [])
    parsed_cases = {str(c.get("case_id")): dict(c) for c in cases if str(c.get("case_id")) in target_case_ids}
    browser_mode_failures = _required_browser_mode_failures(
        list(parsed_cases.values()),
        required_case_ids=target_case_ids,
    )
    fail_reasons: list[str] = []
    for target_case_id in sorted(target_case_ids):
        case = parsed_cases.get(target_case_id, {})
        if not case:
            fail_reasons.append(f"missing_required_case:{target_case_id}")
            continue
        browser_mode = str(case.get("browser_mode") or "")
        if browser_mode != "browser_live":
            fail_reasons.append(f"{REQUIRED_BROWSER_MODE_MESSAGE}:case_id={target_case_id}:browser_mode={browser_mode or 'missing'}")
        if case.get("verdict") != "PASS":
            fail_reasons.append(f"required_case_failed:{target_case_id}:{case.get('fail_reasons')}")
        for reason in assert_no_unresolved_material_overdesign(target_case_id, case):
            fail_reasons.append(f"real_user_unresolved_material_overdesign:{target_case_id}:{reason}")
        for reason in assert_visible_output_matches_one_click_contract(target_case_id, case):
            fail_reasons.append(f"real_user_visible_output_contract:{target_case_id}:{reason}")
        family_utils = dict(case.get("family_utils") or {})
        material = list(case.get("materially_overprovided_families") or [])
        has_material_non_governing = bool(material)
        if any(float(v) < 0.70 for v in family_utils.values() if isinstance(v, (int, float))):
            if case.get("materially_overprovided_families") is None:
                fail_reasons.append(f"materially_overprovided_families_missing:{target_case_id}")
            if has_material_non_governing and not material:
                fail_reasons.append(f"materially_overprovided_families_empty:{target_case_id}")
            if case.get("local_cleanup_search_ran") is not True:
                fail_reasons.append(f"local_cleanup_search_not_run:{target_case_id}")
            if case.get("safe_local_cleanup_count") is None:
                fail_reasons.append(f"safe_local_cleanup_count_missing:{target_case_id}")
        if target_case_id.endswith("_LOCAL_CLEANUP"):
            if target_case_id == "BENDING_LOW_SHEAR_IN_TARGET_LOCAL_CLEANUP" and "bending" not in [str(v).lower() for v in material]:
                fail_reasons.append("local_cleanup_required_family_missing:bending")
            if target_case_id == "SHEAR_LOW_BENDING_IN_TARGET_LOCAL_CLEANUP" and "shear" not in [str(v).lower() for v in material]:
                fail_reasons.append("local_cleanup_required_family_missing:shear")
            if target_case_id == "SERVICEABILITY_LOW_BENDING_IN_TARGET_LOCAL_CLEANUP" and not (
                {"crack", "deflection", "serviceability"} & {str(v).lower() for v in material}
            ):
                family_utils = dict(case.get("family_utils") or {})
                has_meaningful_serviceability = any(
                    str(family).lower() in {"crack", "deflection", "serviceability"}
                    and _float_or_none(util) is not None
                    and float(_float_or_none(util) or 0.0) > 1e-9
                    for family, util in family_utils.items()
                )
                if has_meaningful_serviceability:
                    fail_reasons.append("local_cleanup_required_family_missing:serviceability")
            if case.get("local_cleanup_search_ran") is not True:
                fail_reasons.append(f"local_cleanup_search_not_run:{target_case_id}")
            if case.get("local_cleanup_search_exhaustive") is not True:
                fail_reasons.append(f"local_cleanup_search_not_exhaustive:{target_case_id}")
            inventory_count = case.get("candidate_inventory_count", case.get("local_cleanup_candidate_inventory_count"))
            unsupported = list(case.get("unsupported_cleanup_families") or [])
            exact_blockers = dict(case.get("post_click_exact_blockers_by_family") or {})
            material_families = [str(family).strip().lower() for family in material if str(family).strip()]
            exact_blocked_material_families = bool(material_families) and all(
                family in {str(key).strip().lower() for key in exact_blockers}
                for family in material_families
            )
            exact_blocker_terminal = bool(
                exact_blocked_material_families
                and case.get("post_click_accepted_green_valid") is True
                and not list(case.get("post_click_unresolved_low_util_families") or [])
            )
            if (
                case.get("local_cleanup_search_exhaustive") is True
                and int(inventory_count or 0) <= 0
                and not unsupported
                and not exact_blocker_terminal
            ):
                fail_reasons.append(f"local_cleanup_exhaustive_without_real_candidates:{target_case_id}")
            safe_count = case.get("safe_local_cleanup_count")
            if safe_count is None:
                fail_reasons.append(f"safe_local_cleanup_count_missing:{target_case_id}")
            else:
                selected_title = str(case.get("selected_action_title") or "").lower()
                cta_enabled = bool(case.get("one_click_button_enabled_before"))
                button = dict(case.get("button_contract") or {})
                safe_count_int = int(safe_count or 0)
                if safe_count_int > 0:
                    if "design is efficient" in selected_title and "target band achieved" in selected_title:
                        fail_reasons.append("terminal_no_action_with_safe_local_cleanup")
                    if case.get("terminal_state_blocked_by_local_cleanup") is not True:
                        fail_reasons.append("terminal_state_not_blocked_by_local_cleanup")
                    if not cta_enabled:
                        fail_reasons.append("local_cleanup_cta_not_enabled")
                    if button.get("preview_pass") is not True:
                        fail_reasons.append("local_cleanup_cta_preview_not_pass")
                else:
                    if cta_enabled:
                        fail_reasons.append("local_cleanup_absent_but_cta_enabled")
                    if not exact_blocker_terminal:
                        if case.get("terminal_state_reason") != "governing_in_target_no_safe_local_cleanup":
                            fail_reasons.append("terminal_state_reason_missing_no_safe_local_cleanup")
                        if not list(case.get("local_cleanup_blocked_reasons") or []):
                            fail_reasons.append("local_cleanup_blocked_reasons_missing")
    status = "PASS" if not fail_reasons and len(parsed_cases) == len(target_case_ids) else "FAIL"
    terminal_case = parsed_cases.get("BENDING_LOW_SHEAR_IN_TARGET_TERMINAL", {})
    cleanup_case = parsed_cases.get("BENDING_LOW_SHEAR_IN_TARGET_LOCAL_CLEANUP", {})
    browser_mode = str(terminal_case.get("browser_mode") or "")
    browser_mode_failures = _required_browser_mode_failures(
        list(parsed_cases.values()),
        required_case_ids=target_case_ids,
    )
    return {
        "artifact": str(data.get("_artifact_path") or ""),
        "case_id": "BENDING_LOW_SHEAR_IN_TARGET_TERMINAL",
        "required_case_ids": sorted(target_case_ids),
        "status": status,
        "browser_mode": browser_mode,
        "required_browser_mode_failures": browser_mode_failures,
        "required_browser_mode_failure_count": len(browser_mode_failures),
        "verdict": terminal_case.get("verdict"),
        "fail_reasons": fail_reasons,
        "visible_summary_before": terminal_case.get("visible_summary_before"),
        "selected_action_title": terminal_case.get("selected_action_title"),
        "selected_action_family": terminal_case.get("selected_action_family"),
        "one_click_button_enabled_before": terminal_case.get("one_click_button_enabled_before"),
        "design_guide_decision_trace": terminal_case.get("design_guide_decision_trace"),
        "local_cleanup_case": {
            "browser_mode": cleanup_case.get("browser_mode"),
            "verdict": cleanup_case.get("verdict"),
            "visible_summary_before": cleanup_case.get("visible_summary_before"),
            "selected_action_title": cleanup_case.get("selected_action_title"),
            "selected_action_family": cleanup_case.get("selected_action_family"),
            "one_click_button_enabled_before": cleanup_case.get("one_click_button_enabled_before"),
            "family_utils": cleanup_case.get("family_utils"),
            "materially_overprovided_families": cleanup_case.get("materially_overprovided_families"),
            "local_cleanup_search_ran": cleanup_case.get("local_cleanup_search_ran"),
            "local_cleanup_search_exhaustive": cleanup_case.get("local_cleanup_search_exhaustive"),
            "safe_local_cleanup_count": cleanup_case.get("safe_local_cleanup_count"),
            "terminal_state_reason": cleanup_case.get("terminal_state_reason"),
            "terminal_state_blocked_by_local_cleanup": cleanup_case.get("terminal_state_blocked_by_local_cleanup"),
        },
    }


def parse_local_cleanup_effectiveness(data: dict) -> dict:
    summary = dict(data.get("summary") or {})
    cases = list(data.get("cases") or [])
    fail_reasons: list[str] = []
    if summary.get("requires_post_click_green_or_accepted") is not True:
        fail_reasons.append("local_cleanup_missing_required_post_click_green_accepted_gate")
    if summary.get("requires_target_band_or_exact_blocker") is not True:
        fail_reasons.append("local_cleanup_missing_required_target_band_or_exact_blocker_gate")
    if summary.get("can_pass_without_intended_family_improvement") is not False:
        fail_reasons.append("local_cleanup_can_pass_without_intended_family_improvement")
    if summary.get("can_pass_with_post_click_cta_still_visible") is not False:
        fail_reasons.append("local_cleanup_can_pass_with_post_click_cta_still_visible")
    if summary.get("requires_accepted_green_no_unresolved_overprovided_families") is not True:
        fail_reasons.append("local_cleanup_missing_accepted_green_unresolved_overprovided_gate")
    if summary.get("can_pass_with_shear_util_below_0_70_without_blocker") is not False:
        fail_reasons.append("local_cleanup_can_pass_with_shear_under_0_70_without_blocker")
    if float(summary.get("final_accepted_min_family_util") or 0.0) < 0.85:
        fail_reasons.append("local_cleanup_final_accepted_min_family_util_below_0_85")
    if summary.get("requires_all_meaningful_family_utils_ge_0_85_or_exact_blocker") is not True:
        fail_reasons.append("local_cleanup_missing_meaningful_family_util_0_85_gate")
    if summary.get("can_pass_with_shear_util_below_0_85_without_blocker") is not False:
        fail_reasons.append("local_cleanup_can_pass_with_shear_under_0_85_without_blocker")
    if summary.get("can_pass_with_accepted_green_unresolved_low_util_families") is not False:
        fail_reasons.append("local_cleanup_can_pass_accepted_green_with_unresolved_low_util_families")
    if summary.get("requires_primary_payload_binding_match") is not True:
        fail_reasons.append("local_cleanup_missing_primary_payload_binding_gate")
    if summary.get("requires_primary_payload_update_match") is not True:
        fail_reasons.append("local_cleanup_missing_primary_payload_update_gate")
    for counter_key in (
        "payload_candidate_binding_failures",
        "payload_update_binding_failures",
        "legacy_fallback_primary_apply_failures",
        "stale_apply_payload_failures",
    ):
        if int(summary.get(counter_key, 0) or 0) != 0:
            fail_reasons.append(f"local_cleanup_{counter_key}:{summary.get(counter_key)}")
    for case in cases:
        case_id = str(case.get("case_id") or "")
        for reason in assert_no_unresolved_material_overdesign(case_id, case):
            fail_reasons.append(f"local_cleanup_unresolved_material_overdesign:{case_id}:{reason}")
        for reason in assert_visible_output_matches_one_click_contract(case_id, case):
            fail_reasons.append(f"local_cleanup_visible_output_contract:{case_id}:{reason}")
        if str(case.get("browser_mode") or "") != "browser_live":
            fail_reasons.append(f"{REQUIRED_BROWSER_MODE_MESSAGE}:case_id={case_id}:browser_mode={case.get('browser_mode') or 'missing'}")
        if case.get("primary_cta_enabled") and not case.get("executable"):
            fail_reasons.append(f"local_cleanup_primary_not_executable:{case_id}")
        if case.get("primary_cta_enabled") and "intended_family_not_improved" in list(case.get("fail_reasons") or []):
            fail_reasons.append(f"local_cleanup_intended_family_not_improved:{case_id}")
        if case.get("primary_cta_enabled") and "cleanup_click_no_visible_effect" in list(case.get("fail_reasons") or []):
            fail_reasons.append(f"local_cleanup_click_no_visible_effect:{case_id}")
        if case.get("primary_cta_enabled") and "preview_passed_but_button_contract_rejected" in list(case.get("fail_reasons") or []):
            fail_reasons.append(f"local_cleanup_preview_button_contract_mismatch:{case_id}")
        if case.get("click_attempted"):
            if case.get("post_click_primary_cta_visible") or case.get("post_click_primary_cta_enabled"):
                fail_reasons.append(f"local_cleanup_post_click_cta_still_visible:{case_id}")
            if not (case.get("post_click_accepted_green") or case.get("post_click_valid_blocker_if_not_target")):
                fail_reasons.append(f"local_cleanup_post_click_not_accepted_or_blocked:{case_id}")
            if not (case.get("post_click_in_target_band") or case.get("post_click_valid_blocker_if_not_target")):
                fail_reasons.append(f"local_cleanup_post_click_not_target_or_blocker:{case_id}")
            unresolved = list(case.get("post_click_unresolved_overprovided_families") or [])
            if unresolved:
                fail_reasons.append(f"local_cleanup_post_click_unresolved_overprovided_families:{case_id}:{unresolved}")
            low_unresolved = list(case.get("post_click_unresolved_low_util_families") or [])
            if low_unresolved:
                fail_reasons.append(f"local_cleanup_post_click_unresolved_low_util_families:{case_id}:{low_unresolved}")
            if case.get("post_click_accepted_green") and case.get("post_click_accepted_green_valid") is not True:
                fail_reasons.append(f"local_cleanup_accepted_green_unresolved_overprovided:{case_id}")
            if case.get("payload_binding_match") is not True:
                fail_reasons.append(f"local_cleanup_payload_binding_mismatch:{case_id}")
            if case.get("payload_update_match") is not True:
                fail_reasons.append(f"local_cleanup_payload_update_mismatch:{case_id}")
            ids = [
                str(case.get("visible_primary_candidate_id") or "").strip(),
                str(case.get("button_contract_candidate_id") or "").strip(),
                str(case.get("queued_apply_candidate_id") or "").strip(),
                str(case.get("applied_candidate_id") or "").strip(),
            ]
            if not all(ids) or len(set(ids)) != 1:
                fail_reasons.append(f"local_cleanup_payload_candidate_ids_not_identical:{case_id}:{ids}")
            maps = [
                dict(case.get("visible_updates") or case.get("proposed_updates") or {}),
                dict(case.get("button_contract_updates") or {}),
                dict(case.get("queued_apply_updates") or {}),
                dict(case.get("applied_updates") or {}),
            ]
            if not all(maps) or any(candidate != maps[0] for candidate in maps[1:]):
                fail_reasons.append(f"local_cleanup_payload_update_maps_not_identical:{case_id}")
            if case.get("legacy_fallback_used") is True:
                fail_reasons.append(f"local_cleanup_primary_used_legacy_fallback:{case_id}")
            if case.get("stale_apply_payload_blocked") is True or list(case.get("stale_candidate_changed_keys") or []):
                fail_reasons.append(f"local_cleanup_stale_payload_applied_or_blocked:{case_id}")
    fail_count = int(summary.get("FAIL_count", 0) or 0) + len(fail_reasons)
    return {
        "artifact": str(data.get("_artifact_path") or ""),
        "total_cases": int(summary.get("total_cases", len(cases)) or len(cases)),
        "pass_count": int(summary.get("PASS_count", 0) or 0),
        "fail_count": fail_count,
        "raw_fail_count": int(summary.get("FAIL_count", 0) or 0),
        "non_executable_primary_failures": int(summary.get("non_executable_primary_failures", 0) or 0),
        "advisory_primary_failures": int(summary.get("advisory_primary_failures", 0) or 0),
        "preview_button_contract_mismatch_failures": int(summary.get("preview_button_contract_mismatch_failures", 0) or 0),
        "click_no_effect_failures": int(summary.get("click_no_effect_failures", 0) or 0),
        "intended_family_not_improved_failures": int(summary.get("intended_family_not_improved_failures", 0) or 0),
        "requires_post_click_green_or_accepted": bool(summary.get("requires_post_click_green_or_accepted")),
        "requires_target_band_or_exact_blocker": bool(summary.get("requires_target_band_or_exact_blocker")),
        "can_pass_without_intended_family_improvement": bool(summary.get("can_pass_without_intended_family_improvement")),
        "can_pass_with_post_click_cta_still_visible": bool(summary.get("can_pass_with_post_click_cta_still_visible")),
        "requires_accepted_green_no_unresolved_overprovided_families": bool(summary.get("requires_accepted_green_no_unresolved_overprovided_families")),
        "can_pass_with_shear_util_below_0_70_without_blocker": bool(summary.get("can_pass_with_shear_util_below_0_70_without_blocker")),
        "final_accepted_min_family_util": float(summary.get("final_accepted_min_family_util") or 0.0),
        "requires_all_meaningful_family_utils_ge_0_85_or_exact_blocker": bool(summary.get("requires_all_meaningful_family_utils_ge_0_85_or_exact_blocker")),
        "can_pass_with_shear_util_below_0_85_without_blocker": bool(summary.get("can_pass_with_shear_util_below_0_85_without_blocker")),
        "can_pass_with_accepted_green_unresolved_low_util_families": bool(summary.get("can_pass_with_accepted_green_unresolved_low_util_families")),
        "post_click_not_accepted_failures": int(summary.get("post_click_not_accepted_failures", 0) or 0),
        "post_click_cta_still_visible_failures": int(summary.get("post_click_cta_still_visible_failures", 0) or 0),
        "post_click_target_or_blocker_failures": int(summary.get("post_click_target_or_blocker_failures", 0) or 0),
        "post_click_unresolved_overprovided_failures": int(summary.get("post_click_unresolved_overprovided_failures", 0) or 0),
        "post_click_unresolved_low_util_failures": int(summary.get("post_click_unresolved_low_util_failures", 0) or 0),
        "accepted_green_unresolved_overprovided_failures": int(summary.get("accepted_green_unresolved_overprovided_failures", 0) or 0),
        "accepted_green_shear_under_0_70_no_blocker_failures": int(summary.get("accepted_green_shear_under_0_70_no_blocker_failures", 0) or 0),
        "accepted_green_shear_under_0_85_no_blocker_failures": int(summary.get("accepted_green_shear_under_0_85_no_blocker_failures", 0) or 0),
        "requires_primary_payload_binding_match": bool(summary.get("requires_primary_payload_binding_match")),
        "requires_primary_payload_update_match": bool(summary.get("requires_primary_payload_update_match")),
        "payload_candidate_binding_failures": int(summary.get("payload_candidate_binding_failures", 0) or 0),
        "payload_update_binding_failures": int(summary.get("payload_update_binding_failures", 0) or 0),
        "legacy_fallback_primary_apply_failures": int(summary.get("legacy_fallback_primary_apply_failures", 0) or 0),
        "stale_apply_payload_failures": int(summary.get("stale_apply_payload_failures", 0) or 0),
        "post_click_new_failure_failures": int(summary.get("post_click_new_failure_failures", 0) or 0),
        "incoherent_candidate_failures": int(summary.get("incoherent_candidate_failures", 0) or 0),
        "fail_reasons": fail_reasons,
        "status": "PASS" if fail_count == 0 else "FAIL",
    }


def top_issues(
    golden: dict,
    contract: dict,
    optimisation: dict,
    expectation: dict,
    summary_truth: dict,
    ductility: dict,
) -> list[str]:
    issues: list[str] = []
    if golden.get("fail_count", 0):
        issues.append(f"Golden ladder still has {golden['fail_count']} failing cases.")
    if golden.get("stale_state_flags", 0):
        issues.append(f"Golden ladder reports {golden['stale_state_flags']} stale-state flags.")
    if golden.get("truth_layer_alignment_failures", 0):
        issues.append(
            f"Golden ladder reports {golden['truth_layer_alignment_failures']} truth-layer alignment failures."
        )
    if contract.get("fail_count", 0):
        issues.append(f"Recommendation contract still has {contract['fail_count']} failing cases.")
    if contract.get("actionable_card_rejected_after_click", 0):
        issues.append(
            f"{contract['actionable_card_rejected_after_click']} actionable cards were rejected after click."
        )
    if optimisation.get("real_optimiser_gap", 0):
        issues.append(f"{optimisation['real_optimiser_gap']} real optimiser gaps remain.")
    if optimisation.get("valid_candidates_survived_but_not_selected", 0):
        issues.append(
            f"{optimisation['valid_candidates_survived_but_not_selected']} cases had valid shear candidates that were not selected."
        )
    if expectation.get("below_target_incorrectly_accepted_count", 0):
        issues.append(
            f"{expectation['below_target_incorrectly_accepted_count']} below-target designs were accepted without explanation."
        )
    if expectation.get("remaining_overdesign_unexplained_count", 0):
        issues.append(
            f"{expectation['remaining_overdesign_unexplained_count']} safe overdesign cases remain unexplained."
        )
    if expectation.get("in_target_band_actionable_final_tightening_count", 0):
        issues.append(
            f"{expectation['in_target_band_actionable_final_tightening_count']} in-band cases still exposed final tightening as actionable."
        )
    if expectation.get("unnecessary_strengthening_count", 0):
        issues.append(
            f"{expectation['unnecessary_strengthening_count']} cases strengthened unnecessarily."
        )
    if summary_truth.get("false_pass_count", 0):
        issues.append(f"{summary_truth['false_pass_count']} summary cases reported a false PASS.")
    if summary_truth.get("misleading_target_band_count", 0):
        issues.append(
            f"{summary_truth['misleading_target_band_count']} cases claimed 'within target band' outside the real band."
        )
    if summary_truth.get("missing_governing_status_count", 0):
        issues.append(
            f"{summary_truth['missing_governing_status_count']} cases were missing a governing status in final aggregation."
        )
    if ductility.get("fail_count", 0):
        issues.append(f"{ductility['fail_count']} ductility expectation failures remain.")
    while len(issues) < 3:
        issues.append("No additional material issue recorded.")
    return issues[:3]


GATE_OUTPUT_NAMES = {
    "golden": "golden",
    "golden_matrix_gate": "design_guide_golden_matrix",
    "contract": "recommendation_contract",
    "optimisation": "shear_overdesign",
    "optimisation_expectation": "optimisation_expectation",
    "ductility_expectation": "ductility_expectation",
    "summary_truth": "summary_truth",
    "matrix_chooser": "matrix_chooser",
    "real_user_terminal_case": "real_user_design_guide",
    "local_cleanup_apply_effectiveness": "local_cleanup_apply_effectiveness",
    "required_browser_mode_gate": "required_browser_mode_gate",
}


def _repo_rel(path: str | Path | None) -> str | None:
    if not path:
        return None
    p = Path(path)
    try:
        return p.resolve().relative_to(REPO.resolve()).as_posix()
    except Exception:
        return str(path)


def _json_safe_gate(gate: dict, run_dir: Path, gate_name: str) -> dict:
    safe = dict(gate)
    logs_dir = run_dir / "child_artifacts"
    for stream_name in ("stdout", "stderr"):
        text = str(safe.pop(stream_name, "") or "")
        if not text:
            continue
        log_path = logs_dir / f"{gate_name}_{stream_name}.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(_trim_runner_text(text), encoding="utf-8")
        safe[f"{stream_name}_log"] = _repo_rel(log_path)
    return safe


def _child_artifact_paths(result: dict) -> dict[str, str]:
    paths: dict[str, str] = {}
    for key, output_name in GATE_OUTPUT_NAMES.items():
        artifact = result.get(key, {}).get("artifact")
        if artifact:
            paths[output_name] = _repo_rel(artifact) or str(artifact)
    return paths


def _collect_unresolved_summary(result: dict) -> dict:
    required: list[dict] = []
    advisory: list[dict] = []
    skipped: list[dict] = []
    for key, output_name in GATE_OUTPUT_NAMES.items():
        gate = dict(result.get(key) or {})
        for case in list(gate.get("unresolved_required_cases") or []):
            entry = dict(case)
            entry.setdefault("source", output_name)
            required.append(entry)
        for case in list(gate.get("unresolved_advisory_cases") or []):
            entry = dict(case)
            entry.setdefault("source", output_name)
            advisory.append(entry)
        for case in list(gate.get("unresolved_skipped_cases") or []):
            entry = dict(case)
            entry.setdefault("source", output_name)
            skipped.append(entry)
    return {
        "unresolved_required_count": len(required),
        "unresolved_advisory_count": len(advisory),
        "unresolved_skipped_count": len(skipped),
        "unresolved_required_cases": required,
        "unresolved_advisory_cases": advisory,
        "unresolved_skipped_cases": skipped,
    }


def _gate_list(result: dict) -> list[dict]:
    gates: list[dict] = []
    for key, output_name in GATE_OUTPUT_NAMES.items():
        gate = dict(result.get(key) or {})
        gates.append(
            {
                "name": output_name,
                "result_key": key,
                "status": gate.get("status") or "UNKNOWN",
                "runner_status": gate.get("runner_status"),
                "artifact": _repo_rel(gate.get("artifact")),
                "fail_count": gate.get("fail_count", gate.get("failure_count")),
                "total_cases": gate.get("total_cases"),
                "source_verdict": gate.get("source_verdict"),
                "verifier_validity_status": gate.get("source_verifier_validity_status"),
                "one_click_contract_status": gate.get("source_one_click_contract_status"),
                "gate_validity_fail_reasons": list(gate.get("gate_validity_fail_reasons") or []),
                "unresolved_required_count": gate.get("unresolved_required_count"),
                "unresolved_advisory_count": gate.get("unresolved_advisory_count"),
                "unresolved_skipped_count": gate.get("unresolved_skipped_count"),
            }
        )
    return gates


def _compact_proof_lines(result: dict) -> dict:
    local = dict(result.get("local_cleanup_apply_effectiveness") or {})
    return {
        "requires_post_click_green_or_accepted": local.get("requires_post_click_green_or_accepted"),
        "requires_target_band_or_exact_blocker": local.get("requires_target_band_or_exact_blocker"),
        "can_pass_without_intended_family_improvement": local.get("can_pass_without_intended_family_improvement"),
        "can_pass_with_post_click_cta_still_visible": local.get("can_pass_with_post_click_cta_still_visible"),
        "requires_accepted_green_no_unresolved_overprovided_families": local.get(
            "requires_accepted_green_no_unresolved_overprovided_families"
        ),
        "final_accepted_min_family_util": local.get("final_accepted_min_family_util"),
        "requires_all_meaningful_family_utils_ge_0_85_or_exact_blocker": local.get(
            "requires_all_meaningful_family_utils_ge_0_85_or_exact_blocker"
        ),
        "can_pass_with_shear_util_below_0_85_without_blocker": local.get(
            "can_pass_with_shear_util_below_0_85_without_blocker"
        ),
        "can_pass_with_accepted_green_unresolved_low_util_families": local.get(
            "can_pass_with_accepted_green_unresolved_low_util_families"
        ),
        "requires_primary_payload_binding_match": local.get("requires_primary_payload_binding_match"),
        "requires_primary_payload_update_match": local.get("requires_primary_payload_update_match"),
    }


def _failure_details(gate: dict) -> dict:
    return {
        "status": gate.get("status"),
        "artifact": _repo_rel(gate.get("artifact")),
        "fail_count": gate.get("fail_count", gate.get("failure_count")),
        "fail_reasons": list(gate.get("fail_reasons") or []),
        "required_browser_mode_failures": list(gate.get("required_browser_mode_failures") or []),
        "failures": list(gate.get("failures") or []),
        "gate_validity_fail_reasons": list(gate.get("gate_validity_fail_reasons") or []),
        "unresolved_required_cases": list(gate.get("unresolved_required_cases") or []),
        "unresolved_advisory_cases": list(gate.get("unresolved_advisory_cases") or []),
        "unresolved_skipped_cases": list(gate.get("unresolved_skipped_cases") or []),
        "error": gate.get("error"),
    }


def _write_super_summary_md(summary: dict) -> str:
    lines = [
        "# Super Verification Summary",
        "",
        f"Verdict: **{summary['overall_verdict']}**",
        f"Safe to freeze: **{'YES' if summary['safe_to_freeze'] else 'NO'}**",
        f"Generated: {summary['generated_at']}",
        f"Runtime seconds: {summary['runtime_seconds']:.1f}",
        "",
        "## Gates",
        "",
        "| Gate | Status | Runner | Validity | Failures | Artifact |",
        "| --- | --- | --- | --- | ---: | --- |",
    ]
    for gate in summary["gates"]:
        fail_count = gate.get("fail_count")
        validity = gate.get("verifier_validity_status") or ""
        lines.append(
            f"| {gate['name']} | {gate.get('status') or 'UNKNOWN'} | {gate.get('runner_status') or ''} | {validity} | {'' if fail_count is None else fail_count} | `{gate.get('artifact') or ''}` |"
        )
    lines.extend(["", "## Blocking Issues", ""])
    for issue in summary.get("blocking_issues") or ["None"]:
        lines.append(f"- {issue}")
    lines.extend(["", "## Warnings", ""])
    for warning in summary.get("warnings") or ["None"]:
        lines.append(f"- {warning}")
    lines.extend(
        [
            "",
            "## Unresolved Cases",
            "",
            f"- Required unresolved cases: {summary.get('unresolved_required_count', 0)}",
            f"- Advisory unresolved cases: {summary.get('unresolved_advisory_count', 0)}",
            f"- Skipped unresolved cases: {summary.get('unresolved_skipped_count', 0)}",
        ]
    )
    for case in list(summary.get("unresolved_required_cases") or [])[:10]:
        lines.append(f"- REQUIRED `{case.get('source')}` / `{case.get('case_id')}`: {case.get('reason')}")
    for case in list(summary.get("unresolved_skipped_cases") or [])[:10]:
        lines.append(f"- SKIPPED `{case.get('source')}` / `{case.get('case_id')}`: {case.get('reason')}")
    proof = summary.get("compact_proof_lines") or {}
    lines.extend(
        [
            "",
            "## Proof Lines",
            "",
            f"- Requires post-click green/accepted: {proof.get('requires_post_click_green_or_accepted')}",
            f"- Requires target band or exact blocker: {proof.get('requires_target_band_or_exact_blocker')}",
            f"- Can pass without intended-family improvement: {proof.get('can_pass_without_intended_family_improvement')}",
            f"- Can pass with post-click CTA still visible: {proof.get('can_pass_with_post_click_cta_still_visible')}",
            f"- Requires all meaningful family utils >= 0.85 or exact blocker: {proof.get('requires_all_meaningful_family_utils_ge_0_85_or_exact_blocker')}",
            f"- Requires primary payload binding match: {proof.get('requires_primary_payload_binding_match')}",
            "",
            "## Child Artifacts",
            "",
        ]
    )
    for name, path in sorted((summary.get("child_artifact_paths") or {}).items()):
        lines.append(f"- {name}: `{path}`")
    return "\n".join(lines) + "\n"


def write_super_artifacts(
    result: dict,
    *,
    run_started_at: datetime,
    write_full_raw: bool = False,
) -> tuple[Path, Path, Path]:
    run_dir = REPO / "artifacts" / "verification" / "latest" / "super_verification_runs" / TIMESTAMP
    gates_dir = run_dir / "gates"
    failures_dir = run_dir / "failures"
    child_dir = run_dir / "child_artifacts"
    raw_dir = run_dir / "raw"
    for directory in (gates_dir, failures_dir, child_dir):
        directory.mkdir(parents=True, exist_ok=True)

    for key, output_name in GATE_OUTPUT_NAMES.items():
        gate = dict(result.get(key) or {})
        safe_gate = _json_safe_gate(gate, run_dir, output_name)
        (gates_dir / f"{output_name}.json").write_text(
            json.dumps(safe_gate, indent=2),
            encoding="utf-8",
        )
        if safe_gate.get("status") != "PASS":
            (failures_dir / f"{output_name}_failures.json").write_text(
                json.dumps(_failure_details(safe_gate), indent=2),
                encoding="utf-8",
            )

    child_artifacts = _child_artifact_paths(result)
    (child_dir / "artifacts.json").write_text(json.dumps(child_artifacts, indent=2), encoding="utf-8")

    runtime_seconds = (datetime.now() - run_started_at).total_seconds()
    summary = {
        "timestamp": TIMESTAMP,
        "generated_at": datetime.now().isoformat(),
        "run_started_at": run_started_at.isoformat(),
        "runtime_seconds": runtime_seconds,
        "requested_port": result.get("requested_port"),
        "overall_verdict": result.get("overall_verdict"),
        "safe_to_freeze": result.get("safe_to_freeze"),
        "matrix_chooser_status": result.get("matrix_chooser", {}).get("status"),
        "matrix_chooser_total": result.get("matrix_chooser", {}).get("total_cases"),
        "matrix_chooser_pass": result.get("matrix_chooser", {}).get("pass_count"),
        "matrix_chooser_fail": result.get("matrix_chooser", {}).get("fail_count"),
        "matrix_chooser_artifact": _repo_rel(result.get("matrix_chooser", {}).get("artifact")),
        "matrix_chooser_required_gate": True,
        "unresolved_required_count": result.get("unresolved_required_count", 0),
        "unresolved_advisory_count": result.get("unresolved_advisory_count", 0),
        "unresolved_skipped_count": result.get("unresolved_skipped_count", 0),
        "unresolved_required_cases": list(result.get("unresolved_required_cases") or []),
        "unresolved_advisory_cases": list(result.get("unresolved_advisory_cases") or []),
        "unresolved_skipped_cases": list(result.get("unresolved_skipped_cases") or []),
        "gates": _gate_list(result),
        "blocking_issues": [] if result.get("safe_to_freeze") else list(result.get("top_issues") or []),
        "top_issues": list(result.get("top_issues") or []),
        "warnings": list(result.get("warnings") or []),
        "child_artifact_paths": child_artifacts,
        "compact_proof_lines": _compact_proof_lines(result),
    }
    summary_path = run_dir / "super_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (run_dir / "super_summary.md").write_text(_write_super_summary_md(summary), encoding="utf-8")

    if write_full_raw:
        raw_dir.mkdir(parents=True, exist_ok=True)
        (raw_dir / "super_full_raw.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    compatibility = {
        "timestamp": TIMESTAMP,
        "overall_verdict": result.get("overall_verdict"),
        "safe_to_freeze": result.get("safe_to_freeze"),
        "matrix_chooser_status": result.get("matrix_chooser", {}).get("status"),
        "matrix_chooser_total": result.get("matrix_chooser", {}).get("total_cases"),
        "matrix_chooser_pass": result.get("matrix_chooser", {}).get("pass_count"),
        "matrix_chooser_fail": result.get("matrix_chooser", {}).get("fail_count"),
        "matrix_chooser_artifact": _repo_rel(result.get("matrix_chooser", {}).get("artifact")),
        "matrix_chooser_required_gate": True,
        "unresolved_required_count": result.get("unresolved_required_count", 0),
        "unresolved_advisory_count": result.get("unresolved_advisory_count", 0),
        "unresolved_skipped_count": result.get("unresolved_skipped_count", 0),
        "unresolved_required_cases": list(result.get("unresolved_required_cases") or []),
        "unresolved_advisory_cases": list(result.get("unresolved_advisory_cases") or []),
        "unresolved_skipped_cases": list(result.get("unresolved_skipped_cases") or []),
        "path_to_run_directory": _repo_rel(run_dir),
        "path_to_super_summary_json": _repo_rel(summary_path),
        "child_artifact_paths": child_artifacts,
        "blocking_issues": [] if result.get("safe_to_freeze") else list(result.get("top_issues") or []),
        "warnings": list(result.get("warnings") or []),
        "gates": _gate_list(result),
        "compact_proof_lines": _compact_proof_lines(result),
    }
    compatibility_path = REPO / "artifacts" / "verification" / "latest" / f"super_verification_{TIMESTAMP}.json"
    compatibility_path.write_text(json.dumps(compatibility, indent=2), encoding="utf-8")
    return compatibility_path, run_dir, summary_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the full verification aggregator.")
    parser.add_argument("--port", type=int, default=8524)
    parser.add_argument("--write-full-raw", action="store_true", help="Write full raw super debug JSON under the run directory.")
    args = parser.parse_args(argv)
    run_started_at = datetime.now()

    result: dict = {
        "timestamp": TIMESTAMP,
        "requested_port": args.port,
        "golden": {},
        "contract": {},
        "optimisation": {},
        "optimisation_expectation": {},
        "ductility_expectation": {},
        "summary_truth": {},
        "matrix_chooser": {},
        "golden_matrix_gate": {},
        "real_user_terminal_case": {},
        "local_cleanup_apply_effectiveness": {},
        "previous_fixed_groups_gate": {},
        "required_browser_mode_gate": {},
        "overall_verdict": "RED",
        "safe_to_freeze": False,
    }

    previous_started_at = datetime.now().timestamp()
    previous_status, previous_out, previous_err = run_script(
        [sys.executable, str(TOOLS / "run_design_guide_previous_fixes_gate.py"), "--port", str(args.port)]
    )
    previous_path = get_latest_artifact("previous_fixes_gate_*.json", newer_than=previous_started_at)
    previous_raw, previous_load_err = load_json(previous_path)
    result["previous_fixed_groups_gate"] = {
        "artifact": str(previous_path) if previous_path else None,
        "status": previous_status,
        "stdout": previous_out,
        "stderr": previous_err,
        "error": previous_load_err,
        "blocked_by_previous_fixed_groups_regression": previous_status != "PASS",
    }
    if previous_status != "PASS":
        result["overall_verdict"] = "RED"
        result["safe_to_freeze"] = False
        result["top_issues"] = ["blocked by previous-fixed-groups regression."]
        artifact_path, run_dir, summary_path = write_super_artifacts(
            result,
            run_started_at=run_started_at,
            write_full_raw=args.write_full_raw,
        )
        print("SUPER VERIFICATION SUMMARY")
        print("Previous fixed groups gate: FAIL")
        print("Overall verdict: RED")
        print("Safe to freeze: NO")
        print(f"Run directory: {_repo_rel(run_dir)}")
        print(f"Summary artifact: {_repo_rel(summary_path)}")
        print(f"Compatibility artifact: {_repo_rel(artifact_path)}")
        print("")
        print("Top issues:")
        print("1. blocked by previous-fixed-groups regression.")
        return 1

    golden_matrix_started_at = datetime.now().timestamp()
    golden_matrix_status, golden_matrix_out, golden_matrix_err = run_script(
        [sys.executable, str(TOOLS / "run_design_guide_golden_matrix.py"), "--port", str(args.port)]
    )
    golden_matrix_path = get_latest_artifact("golden_matrix_*.json", newer_than=golden_matrix_started_at)
    golden_matrix_raw, golden_matrix_load_err = load_json(golden_matrix_path)
    result["golden_matrix_gate"] = {
        "artifact": str(golden_matrix_path) if golden_matrix_path else None,
        "status": golden_matrix_status,
        "stdout": golden_matrix_out,
        "stderr": golden_matrix_err,
        "error": golden_matrix_load_err,
        "blocked_by_golden_matrix_regression": golden_matrix_status != "PASS",
        "total_cases": golden_matrix_raw.get("total_cases") if isinstance(golden_matrix_raw, dict) else None,
        "pass_count": golden_matrix_raw.get("passed_cases") if isinstance(golden_matrix_raw, dict) else None,
        "fail_count": golden_matrix_raw.get("failed_cases") if isinstance(golden_matrix_raw, dict) else None,
    }
    if golden_matrix_status != "PASS":
        result["overall_verdict"] = "RED"
        result["safe_to_freeze"] = False
        result["top_issues"] = ["blocked by golden matrix regression."]
        artifact_path, run_dir, summary_path = write_super_artifacts(
            result,
            run_started_at=run_started_at,
            write_full_raw=args.write_full_raw,
        )
        print("SUPER VERIFICATION SUMMARY")
        print("Previous fixed groups gate: PASS")
        print("Golden matrix gate: FAIL")
        print("Overall verdict: RED")
        print("Safe to freeze: NO")
        print(f"Run directory: {_repo_rel(run_dir)}")
        print(f"Summary artifact: {_repo_rel(summary_path)}")
        print(f"Compatibility artifact: {_repo_rel(artifact_path)}")
        print("")
        print("Top issues:")
        print("1. blocked by golden matrix regression.")
        return 1

    golden_path = get_latest_artifact("full_golden_ladder_rerun_*.json")
    golden_raw, golden_err = load_json(golden_path)
    if golden_path:
        golden_raw["_artifact_path"] = str(golden_path)
    if golden_err:
        result["golden"] = {
            "artifact": str(golden_path) if golden_path else None,
            "status": "CRASH",
            "error": golden_err,
        }
    else:
        result["golden"] = _apply_gate_validity(parse_golden(golden_raw), source_data=golden_raw)

    contract_started_at = datetime.now().timestamp()
    contract_status, contract_out, contract_err = run_script(
        [sys.executable, str(RUNNERS / "recommendation_contract_ladder.py"), "--port", str(args.port)]
    )
    contract_path = get_latest_artifact("recommendation_contract_ladder_*.json", newer_than=contract_started_at)
    contract_raw, contract_load_err = load_json(contract_path)
    if contract_path:
        contract_raw["_artifact_path"] = str(contract_path)
    if contract_load_err:
        result["contract"] = {
            "artifact": str(contract_path) if contract_path else None,
            "status": "CRASH",
            "runner_status": contract_status,
            "stdout": contract_out,
            "stderr": contract_err,
            "error": contract_load_err,
        }
    else:
        contract_parsed = parse_contract(contract_raw)
        contract_parsed["stdout"] = contract_out
        contract_parsed["stderr"] = contract_err
        result["contract"] = _apply_gate_validity(
            contract_parsed,
            source_data=contract_raw,
            runner_status=contract_status,
        )

    opt_started_at = datetime.now().timestamp()
    opt_status, opt_out, opt_err = run_script(
        [sys.executable, str(RUNNERS / "shear_overdesign_ladder.py"), "--port", str(args.port)]
    )
    opt_path = get_latest_artifact("shear_overdesign_debug_ladder_*.json", newer_than=opt_started_at)
    opt_raw, opt_load_err = load_json(opt_path)
    if opt_path:
        opt_raw["_artifact_path"] = str(opt_path)
    if opt_load_err:
        result["optimisation"] = {
            "artifact": str(opt_path) if opt_path else None,
            "status": "CRASH",
            "runner_status": opt_status,
            "stdout": opt_out,
            "stderr": opt_err,
            "error": opt_load_err,
        }
    else:
        opt_parsed = parse_optimisation(opt_raw)
        opt_parsed["stdout"] = opt_out
        opt_parsed["stderr"] = opt_err
        result["optimisation"] = _apply_gate_validity(
            opt_parsed,
            source_data=opt_raw,
            runner_status=opt_status,
        )

    expectation_started_at = datetime.now().timestamp()
    expectation_status, expectation_out, expectation_err = run_script(
        [sys.executable, str(RUNNERS / "optimisation_expectation_ladder.py"), "--port", str(args.port)]
    )
    expectation_path = get_latest_artifact("optimisation_expectation_ladder_*.json", newer_than=expectation_started_at)
    expectation_raw, expectation_load_err = load_json(expectation_path)
    if expectation_path:
        expectation_raw["_artifact_path"] = str(expectation_path)
    if expectation_load_err:
        result["optimisation_expectation"] = {
            "artifact": str(expectation_path) if expectation_path else None,
            "status": "CRASH",
            "runner_status": expectation_status,
            "stdout": expectation_out,
            "stderr": expectation_err,
            "error": expectation_load_err,
        }
    else:
        expectation_parsed = parse_optimisation_expectation(expectation_raw)
        expectation_parsed["stdout"] = expectation_out
        expectation_parsed["stderr"] = expectation_err
        result["optimisation_expectation"] = _apply_gate_validity(
            expectation_parsed,
            source_data=expectation_raw,
            runner_status=expectation_status,
        )

    summary_started_at = datetime.now().timestamp()
    summary_status, summary_out, summary_err = run_script(
        [sys.executable, str(RUNNERS / "summary_truth_ladder.py")]
    )
    summary_path = get_latest_artifact("summary_truth_ladder_*.json", newer_than=summary_started_at)
    summary_raw, summary_load_err = load_json(summary_path)
    if summary_path:
        summary_raw["_artifact_path"] = str(summary_path)
    if summary_load_err:
        result["summary_truth"] = {
            "artifact": str(summary_path) if summary_path else None,
            "status": "CRASH",
            "runner_status": summary_status,
            "stdout": summary_out,
            "stderr": summary_err,
            "error": summary_load_err,
        }
        result["ductility_expectation"] = {
            "artifact": str(summary_path) if summary_path else None,
            "status": "CRASH",
            "runner_status": summary_status,
            "stdout": summary_out,
            "stderr": summary_err,
            "error": summary_load_err,
        }
    else:
        summary_parsed = parse_summary_truth(summary_raw)
        summary_parsed["stdout"] = summary_out
        summary_parsed["stderr"] = summary_err
        result["summary_truth"] = _apply_gate_validity(
            summary_parsed,
            source_data=summary_raw,
            runner_status=summary_status,
        )

        ductility_parsed = parse_ductility_expectation(summary_raw)
        ductility_parsed["stdout"] = summary_out
        ductility_parsed["stderr"] = summary_err
        result["ductility_expectation"] = _apply_gate_validity(
            ductility_parsed,
            source_data=summary_raw,
            runner_status=summary_status,
        )

    matrix_started_at = datetime.now().timestamp()
    matrix_status, matrix_out, matrix_err = run_script(
        [sys.executable, str(RUNNERS / "matrix_chooser_verifier.py"), "--port", str(args.port)]
    )
    matrix_path = get_latest_artifact("matrix_chooser_verifier_*.json", newer_than=matrix_started_at)
    matrix_raw, matrix_load_err = load_json(matrix_path)
    if matrix_path:
        matrix_raw["_artifact_path"] = str(matrix_path)
    if matrix_load_err:
        result["matrix_chooser"] = {
            "artifact": str(matrix_path) if matrix_path else None,
            "status": "CRASH",
            "runner_status": matrix_status,
            "stdout": matrix_out,
            "stderr": matrix_err,
            "error": matrix_load_err,
            "matrix_chooser_required_gate": True,
        }
    else:
        matrix_parsed = parse_matrix_chooser(matrix_raw)
        matrix_parsed["stdout"] = matrix_out
        matrix_parsed["stderr"] = matrix_err
        result["matrix_chooser"] = _apply_gate_validity(
            matrix_parsed,
            source_data=matrix_raw,
            runner_status=matrix_status,
        )

    real_user_started_at = datetime.now().timestamp()
    real_user_status, real_user_out, real_user_err = run_script(
        [
            sys.executable,
            str(RUNNERS / "real_user_design_guide_ladder.py"),
            "--port",
            str(args.port),
            "--case",
            "BENDING_LOW_SHEAR_IN_TARGET_TERMINAL",
            "--case",
            "BENDING_LOW_SHEAR_IN_TARGET_LOCAL_CLEANUP",
            "--case",
            "SHEAR_LOW_BENDING_IN_TARGET_LOCAL_CLEANUP",
            "--case",
            "SERVICEABILITY_LOW_BENDING_IN_TARGET_LOCAL_CLEANUP",
            "--case",
            "GEOMETRY_LOW_REO_OR_SHEAR_IN_TARGET_LOCAL_CLEANUP",
        ]
    )
    real_user_path = get_latest_artifact("real_user_design_guide_ladder_*.json", newer_than=real_user_started_at)
    real_user_raw, real_user_load_err = load_json(real_user_path)
    if real_user_path:
        real_user_raw["_artifact_path"] = str(real_user_path)
    if real_user_load_err:
        result["real_user_terminal_case"] = {
            "artifact": str(real_user_path) if real_user_path else None,
            "status": "CRASH",
            "runner_status": real_user_status,
            "stdout": real_user_out,
            "stderr": real_user_err,
            "error": real_user_load_err,
        }
    else:
        real_user_parsed = parse_real_user_terminal_case(real_user_raw)
        real_user_parsed["stdout"] = real_user_out
        real_user_parsed["stderr"] = real_user_err
        result["real_user_terminal_case"] = _apply_gate_validity(
            real_user_parsed,
            source_data=real_user_raw,
            runner_status=real_user_status,
        )

    cleanup_started_at = datetime.now().timestamp()
    cleanup_status, cleanup_out, cleanup_err = run_script(
        [
            sys.executable,
            str(RUNNERS / "local_cleanup_apply_effectiveness_ladder.py"),
            "--port",
            str(args.port),
        ]
    )
    cleanup_path = get_latest_artifact("local_cleanup_apply_effectiveness_ladder_*.json", newer_than=cleanup_started_at)
    cleanup_raw, cleanup_load_err = load_json(cleanup_path)
    if cleanup_path:
        cleanup_raw["_artifact_path"] = str(cleanup_path)
    if cleanup_load_err:
        result["local_cleanup_apply_effectiveness"] = {
            "artifact": str(cleanup_path) if cleanup_path else None,
            "status": "CRASH",
            "runner_status": cleanup_status,
            "stdout": cleanup_out,
            "stderr": cleanup_err,
            "error": cleanup_load_err,
        }
    else:
        cleanup_parsed = parse_local_cleanup_effectiveness(cleanup_raw)
        cleanup_parsed["stdout"] = cleanup_out
        cleanup_parsed["stderr"] = cleanup_err
        result["local_cleanup_apply_effectiveness"] = _apply_gate_validity(
            cleanup_parsed,
            source_data=cleanup_raw,
            runner_status=cleanup_status,
        )

    required_browser_mode_failures = []
    required_browser_mode_failures.extend(list(result.get("contract", {}).get("required_browser_mode_failures") or []))
    required_browser_mode_failures.extend(list(result.get("matrix_chooser", {}).get("required_browser_mode_failures") or []))
    required_browser_mode_failures.extend(
        list(result.get("real_user_terminal_case", {}).get("required_browser_mode_failures") or [])
    )
    result["required_browser_mode_gate"] = {
        "status": "PASS" if not required_browser_mode_failures else "FAIL",
        "message": REQUIRED_BROWSER_MODE_MESSAGE,
        "failure_count": len(required_browser_mode_failures),
        "failures": required_browser_mode_failures,
        "diagnostic_offline_fallback_allowed_but_not_green_gate": True,
    }
    result.update(_collect_unresolved_summary(result))

    golden_fail = 0 if _gate_passed(result["golden"]) else 1
    contract_fail = 0 if _gate_passed(result["contract"]) else 1
    optimisation_gate_fail = 0 if _gate_passed(result["optimisation"]) else 1
    optimiser_gap = int(result["optimisation"].get("real_optimiser_gap", 1) or 0) if optimisation_gate_fail == 0 else 1
    expectation_fail = (
        int(result["optimisation_expectation"].get("fail_count", 1) or 0)
        if _gate_passed(result["optimisation_expectation"])
        else 1
    )
    unsafe_accepted = int(result["optimisation_expectation"].get("unsafe_accepted_count", 0) or 0)
    below_target_bad = int(
        result["optimisation_expectation"].get("below_target_incorrectly_accepted_count", 0) or 0
    )
    remaining_overdesign_unexplained = int(
        result["optimisation_expectation"].get("remaining_overdesign_unexplained_count", 0) or 0
    )
    unnecessary_strengthening = int(
        result["optimisation_expectation"].get("unnecessary_strengthening_count", 0) or 0
    )
    advisory_only = int(result["optimisation"].get("advisory_only_shear_optimisation", 0) or 0)
    summary_false_pass = int(result["summary_truth"].get("false_pass_count", 0) or 0)
    summary_missing = int(result["summary_truth"].get("missing_governing_status_count", 0) or 0)
    misleading_target = int(result["summary_truth"].get("misleading_target_band_count", 0) or 0)
    summary_truth_fail = (
        int(result["summary_truth"].get("fail_count", 1) or 0)
        if _gate_passed(result["summary_truth"])
        else 1
    )
    ductility_fail = (
        int(result["ductility_expectation"].get("fail_count", 1) or 0)
        if _gate_passed(result["ductility_expectation"])
        else 1
    )
    matrix_chooser_fail = 0 if _gate_passed(result["matrix_chooser"]) else 1
    real_user_terminal_fail = 0 if _gate_passed(result["real_user_terminal_case"]) else 1
    local_cleanup_effectiveness_fail = (
        0 if _gate_passed(result["local_cleanup_apply_effectiveness"]) else 1
    )
    required_browser_mode_fail = 0 if _gate_passed(result["required_browser_mode_gate"]) else 1
    unresolved_required_fail = 1 if int(result.get("unresolved_required_count", 0) or 0) else 0
    unresolved_advisory_fail = 1 if int(result.get("unresolved_advisory_count", 0) or 0) else 0
    unresolved_skipped_fail = 1 if int(result.get("unresolved_skipped_count", 0) or 0) else 0

    if (
        golden_fail == 0
        and contract_fail == 0
        and optimiser_gap == 0
        and expectation_fail == 0
        and summary_truth_fail == 0
        and ductility_fail == 0
        and matrix_chooser_fail == 0
        and real_user_terminal_fail == 0
        and local_cleanup_effectiveness_fail == 0
        and required_browser_mode_fail == 0
        and unresolved_required_fail == 0
        and unresolved_advisory_fail == 0
        and unresolved_skipped_fail == 0
    ):
        verdict = "GREEN"
    elif (
        golden_fail == 0
        and contract_fail == 0
        and unsafe_accepted == 0
        and below_target_bad == 0
        and remaining_overdesign_unexplained == 0
        and unnecessary_strengthening == 0
        and summary_false_pass == 0
        and summary_missing == 0
        and misleading_target == 0
        and ductility_fail == 0
        and matrix_chooser_fail == 0
        and real_user_terminal_fail == 0
        and local_cleanup_effectiveness_fail == 0
        and required_browser_mode_fail == 0
        and unresolved_required_fail == 0
        and unresolved_advisory_fail == 0
        and unresolved_skipped_fail == 0
    ):
        verdict = "AMBER"
    else:
        verdict = "RED"
    result["overall_verdict"] = verdict
    result["safe_to_freeze"] = verdict == "GREEN"
    result["warnings"] = []
    if advisory_only:
        result["warnings"].append(
            f"{advisory_only} shear optimisation cases are advisory-only but child gates classify them as non-freeze-blocking."
        )
    if result.get("unresolved_advisory_count"):
        result["warnings"].append(
            f"{result['unresolved_advisory_count']} unresolved Design Guide cases are advisory-only."
        )
    issues = top_issues(
        result["golden"],
        result["contract"],
        result["optimisation"],
        result["optimisation_expectation"],
        result["summary_truth"],
        result["ductility_expectation"],
    )
    if real_user_terminal_fail:
        issues.insert(
            0,
            "Required real-user Design Guide terminal/local-cleanup cases did not pass in browser_live mode.",
        )
    if matrix_chooser_fail:
        issues.insert(0, "Required matrix chooser Design Guide cases did not pass in browser_live mode.")
    if local_cleanup_effectiveness_fail:
        issues.insert(0, "Local cleanup primary CTA is not proven executable and effective.")
    if required_browser_mode_fail:
        issues.insert(0, REQUIRED_BROWSER_MODE_MESSAGE)
    if unresolved_skipped_fail:
        issues.insert(0, f"{result['unresolved_skipped_count']} required matrix cases were skipped.")
    if unresolved_advisory_fail:
        issues.insert(0, f"{result['unresolved_advisory_count']} unresolved advisory Design Guide cases remain.")
    if unresolved_required_fail:
        issues.insert(0, f"{result['unresolved_required_count']} unresolved required Design Guide cases remain.")
    for key, gate_name in reversed(list(GATE_OUTPUT_NAMES.items())):
        gate = dict(result.get(key) or {})
        reasons = list(gate.get("gate_validity_fail_reasons") or [])
        if reasons:
            issues.insert(0, f"{gate_name} verifier validity failed: {', '.join(str(r) for r in reasons[:3])}.")
    result["top_issues"] = issues[:3]

    artifact_path, run_dir, summary_path = write_super_artifacts(
        result,
        run_started_at=run_started_at,
        write_full_raw=args.write_full_raw,
    )

    golden_status = "PASS" if _gate_passed(result["golden"]) else "FAIL"
    contract_status_txt = "PASS" if _gate_passed(result["contract"]) else "FAIL"
    optimisation_status = "PASS" if _gate_passed(result["optimisation"]) else "FAIL"
    expectation_status_txt = "PASS" if _gate_passed(result["optimisation_expectation"]) else "FAIL"
    ductility_status_txt = "PASS" if _gate_passed(result["ductility_expectation"]) else "FAIL"
    summary_truth_status_txt = "PASS" if _gate_passed(result["summary_truth"]) else "FAIL"
    matrix_chooser_status_txt = "PASS" if _gate_passed(result["matrix_chooser"]) else "FAIL"
    real_user_status_txt = "PASS" if _gate_passed(result["real_user_terminal_case"]) else "FAIL"
    local_cleanup_status_txt = "PASS" if _gate_passed(result["local_cleanup_apply_effectiveness"]) else "FAIL"
    browser_mode_status_txt = "PASS" if _gate_passed(result["required_browser_mode_gate"]) else "FAIL"

    print("SUPER VERIFICATION SUMMARY")
    print(f"Golden ladder: {golden_status}")
    print(f"Recommendation contract: {contract_status_txt}")
    print(f"Shear optimisation coverage: {optimisation_status}")
    print(f"Optimisation expectation: {expectation_status_txt}")
    print(f"Ductility expectation: {ductility_status_txt}")
    print(f"Summary truth: {summary_truth_status_txt}")
    print(f"Matrix chooser: {matrix_chooser_status_txt}")
    print(f"Real-user terminal Design Guide: {real_user_status_txt}")
    print(f"Local cleanup apply effectiveness: {local_cleanup_status_txt}")
    print(f"Required browser mode gate: {browser_mode_status_txt}")
    print(f"Overall verdict: {result['overall_verdict']}")
    print(f"Safe to freeze: {'YES' if result['safe_to_freeze'] else 'NO'}")
    print(f"Run directory: {_repo_rel(run_dir)}")
    print(f"Summary artifact: {_repo_rel(summary_path)}")
    print(f"Compatibility artifact: {_repo_rel(artifact_path)}")
    print("")
    print("Top issues:")
    print(f"1. {result['top_issues'][0]}")
    print(f"2. {result['top_issues'][1]}")
    print(f"3. {result['top_issues'][2]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
