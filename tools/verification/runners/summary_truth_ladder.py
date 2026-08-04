from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import inputs_page
from state_and_helpers import BEAM_STATUS_FAIL, BEAM_STATUS_PASS, BEAM_STATUS_WARN, classify_beam_check_rows
from tools.verification.recipes.one_click_recipe_defs import BASE_BEAM, TARGET_BAND, build_state


TIMESTAMP = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
TARGET_LOW = float(TARGET_BAND["min"])
TARGET_HIGH = float(TARGET_BAND["max"])


REAL_CASES = [
    {
        "case_id": "ALL_PASS_BASELINE",
        "mode": "real",
        "mu": 45.0,
        "vu": 0.0,
        "changes": {},
        "expect_required": {
            "bending": True,
            "shear": False,
            "ductility": True,
            "spacing_detailing": False,
            "serviceability": True,
        },
    },
    {
        "case_id": "BENDING_CAPACITY_FAIL",
        "mode": "real",
        "mu": 300.0,
        "vu": 0.0,
        "changes": {},
        "expect_required": {
            "bending": True,
            "shear": False,
            "ductility": True,
            "spacing_detailing": False,
            "serviceability": True,
        },
    },
    {
        "case_id": "SHEAR_CAPACITY_FAIL",
        "mode": "real",
        "mu": 0.0,
        "vu": 300.0,
        "changes": {},
        "expect_required": {
            "bending": False,
            "shear": True,
            "ductility": False,
            "spacing_detailing": False,
            "serviceability": True,
        },
    },
    {
        "case_id": "BENDING_CAPACITY_PASS_DUCTILITY_FAIL",
        "mode": "real",
        "mu": 100.0,
        "vu": 0.0,
        "changes": {
            "b": 250.0,
            "bw": 250.0,
            "D": 350.0,
            "bot1_count": 5,
            "db_bot_1": 24.0,
            "bot_row_count": 1,
            "bot_row_1_bars": 5,
            "bot_row_1_dia": 24.0,
        },
        "expect_required": {
            "bending": True,
            "shear": False,
            "ductility": True,
            "spacing_detailing": False,
            "serviceability": True,
        },
    },
    {
        "case_id": "OPTIMISED_BUT_STILL_OUTSIDE_TARGET",
        "mode": "real",
        "mu": 35.0,
        "vu": 0.0,
        "changes": {},
        "expect_required": {
            "bending": True,
            "shear": False,
            "ductility": True,
            "spacing_detailing": False,
            "serviceability": True,
        },
    },
]


SYNTHETIC_CASES = [
    {
        "case_id": "UNKNOWN_SHEAR_STATUS_UNDERDESIGN_ACCEPTED",
        "mode": "synthetic",
        "banner_title": None,
        "worst_util": 0.55,
        "bending_rows": [
            {"title": "Positive bending", "status": "PASS", "util": "0.55"},
            {"title": "Ductility limit", "status": "PASS", "util": "0.60"},
        ],
        "shear_rows": [
            {"title": "Sectional shear capacity", "status": "—", "util": "—"},
        ],
        "crack_rows": [{"title": "Governing outcome", "status": "PASS", "util": "0.05"}],
        "deflection_rows": [{"title": "Total deflection (short + long-term)", "status": "PASS", "util": "0.05"}],
        "expect_required": {
            "bending": True,
            "shear": True,
            "ductility": True,
            "spacing_detailing": False,
            "serviceability": True,
        },
    },
    {
        "case_id": "SHEAR_CAPACITY_PASS_DETAILING_FAIL",
        "mode": "synthetic",
        "banner_title": None,
        "worst_util": 0.60,
        "bending_rows": [
            {"title": "Positive bending", "status": "PASS", "util": "0.40"},
            {"title": "Ductility limit", "status": "PASS", "util": "0.45"},
        ],
        "shear_rows": [
            {"title": "Sectional shear capacity", "status": "PASS", "util": "0.60"},
            {"title": "Minimum shear reinforcement", "status": "FAIL", "util": "—"},
        ],
        "crack_rows": [{"title": "Governing outcome", "status": "PASS", "util": "0.10"}],
        "deflection_rows": [{"title": "Total deflection (short + long-term)", "status": "PASS", "util": "0.05"}],
        "expect_required": {
            "bending": True,
            "shear": True,
            "ductility": True,
            "spacing_detailing": True,
            "serviceability": True,
        },
    },
    {
        "case_id": "UNKNOWN_DUCTILITY_STATUS",
        "mode": "synthetic",
        "banner_title": None,
        "worst_util": 0.42,
        "bending_rows": [
            {"title": "Positive bending", "status": "PASS", "util": "0.42"},
            {"title": "Ductility limit", "status": "—", "util": "—"},
        ],
        "shear_rows": [{"title": "Sectional shear capacity", "status": "PASS", "util": "0.00"}],
        "crack_rows": [{"title": "Governing outcome", "status": "PASS", "util": "0.05"}],
        "deflection_rows": [{"title": "Total deflection (short + long-term)", "status": "PASS", "util": "0.05"}],
        "expect_required": {
            "bending": True,
            "shear": False,
            "ductility": True,
            "spacing_detailing": False,
            "serviceability": True,
        },
    },
]


FOCUSED_CASE_ALIASES: dict[str, str | dict[str, Any]] = {
    "A_M45_V0": "ALL_PASS_BASELINE",
    "B_M0_V150": {
        "case_id": "B_M0_V150",
        "mode": "real",
        "mu": 0.0,
        "vu": 150.0,
        "changes": {},
        "expect_required": {
            "bending": False,
            "shear": True,
            "ductility": False,
            "spacing_detailing": False,
            "serviceability": True,
        },
    },
}


def _resolve_requested_cases(
    all_cases: list[dict[str, Any]], requested_case_ids: set[str]
) -> tuple[list[dict[str, Any]], list[str]]:
    if not requested_case_ids:
        return list(all_cases), []

    cases_by_id = {str(case.get("case_id") or ""): case for case in all_cases}
    selected_cases: list[dict[str, Any]] = []
    missing_case_ids: list[str] = []

    for requested_id in sorted(requested_case_ids):
        if requested_id in cases_by_id:
            selected_cases.append(cases_by_id[requested_id])
            continue

        alias = FOCUSED_CASE_ALIASES.get(requested_id)
        if isinstance(alias, str) and alias in cases_by_id:
            alias_case = dict(cases_by_id[alias])
            alias_case["case_id"] = requested_id
            alias_case["alias_of"] = alias
            selected_cases.append(alias_case)
            continue
        if isinstance(alias, dict):
            selected_cases.append(dict(alias))
            continue

        missing_case_ids.append(requested_id)

    return selected_cases, missing_case_ids


def _float_or_none(value: Any) -> float | None:
    try:
        if value in (None, "", "—", "â€”", "-"):
            return None
        return float(value)
    except Exception:
        return None


def _manual_actions(mu: float, vu: float) -> dict[str, Any]:
    return {
        "uls_Mstar": float(mu),
        "load_Mstar_proxy": float(mu),
        "load_Mstar_pos_proxy": float(mu),
        "uls_Mstar_pos_manual": float(mu),
        "uls_Mstar_neg_manual": 0.0,
        "Mu_star": float(mu),
        "Mu_star_manual": float(mu),
        "load_Mstar_neg_proxy": 0.0,
        "uls_Vstar": float(vu),
        "load_Vstar_proxy": float(vu),
        "Vu_star": float(vu),
        "Vu_star_manual": float(vu),
        "uls_Nstar": 0.0,
        "load_Nstar_proxy": 0.0,
        "N_star": 0.0,
        "Tu_star": 0.0,
        "sls_Mstar": 0.0,
        "sls_Vstar": 0.0,
        "sls_Nstar": 0.0,
    }


def _status_bucket(status: Any) -> str:
    text = str(status or "").strip().upper()
    if text in {"PASS", "OK"}:
        return "pass"
    if text in {"FAIL", "NG"}:
        return "fail"
    if text in {"WARN", "NEAR LIMIT", "CHECK"}:
        return "warn"
    if text in {"INFO"}:
        return "info"
    return "unknown"


def _row(title: str, status: Any, util: Any) -> dict[str, Any]:
    return {
        "title": title,
        "status": status,
        "util": util,
        "is_informational": str(status or "").strip().upper() == "INFO",
    }


def _find_row(rows: list[dict[str, Any]], *titles: str) -> dict[str, Any] | None:
    title_set = {str(title) for title in titles}
    for row in rows:
        if str(row.get("title") or "") in title_set:
            return row
    return None


def _rollup_serviceability(crack_rows: list[dict[str, Any]], deflection_rows: list[dict[str, Any]]) -> str | None:
    statuses = []
    for rows in (crack_rows, deflection_rows):
        for row in rows:
            if row.get("is_informational"):
                continue
            statuses.append(str(row.get("status") or ""))
    if not statuses:
        return None
    if any(_status_bucket(status) == "fail" for status in statuses):
        return BEAM_STATUS_FAIL
    if any(_status_bucket(status) in {"warn", "unknown"} for status in statuses):
        return BEAM_STATUS_WARN
    return BEAM_STATUS_PASS


def _guidance_title_for_state(state: dict[str, Any], overview: dict[str, Any] | None = None) -> str | None:
    if os.environ.get("SUMMARY_TRUTH_FULL_GUIDANCE_TITLE_PROBE", "").strip().lower() not in {
        "1",
        "true",
        "yes",
        "on",
    }:
        ov = overview if isinstance(overview, dict) else {}
        worst_util = _float_or_none(ov.get("worst_util"))
        if worst_util is None:
            return None
        utils = {
            str(key): util
            for key, value in dict(ov.get("utils") or {}).items()
            if (util := _float_or_none(value)) is not None
        }
        if bool(ov.get("any_fail")) and utils:
            family, util = max(utils.items(), key=lambda item: item[1])
            return f"{family.replace('_', ' ').title()} capacity is low (utilisation = {util:.2f})"
        if TARGET_LOW <= float(worst_util) <= TARGET_HIGH:
            return "Design is efficient - target band achieved"
        if float(worst_util) < TARGET_LOW:
            return f"Design outside target band - efficiency cleanup available (utilisation = {worst_util:.2f})"
        return f"Design outside target band - strengthening required (utilisation = {worst_util:.2f})"
    try:
        payload = inputs_page._compute_design_guidance_items(
            state,
            guidance_debug_verbose=False,
            debug_enabled=False,
        )
        items = list(payload.get("guidance_items") or [])
        if items:
            return str(items[0].get("title") or "").strip() or None
    except Exception:
        return None
    return None


def _evaluate_real_case(case: dict[str, Any]) -> dict[str, Any]:
    base = dict(BASE_BEAM)
    base.update(dict(case.get("changes") or {}))
    base.update(_manual_actions(float(case["mu"]), float(case["vu"])))
    state = build_state(base)
    candidate = inputs_page.evaluate_candidate_full(state, source="summary_truth")
    overview = dict(candidate.get("overview") or {})
    packs = dict(overview.get("packs") or {})
    bending_rows = list((packs.get("bending") or {}).get("rows") or [])
    shear_rows = list((packs.get("shear") or {}).get("rows") or [])
    crack_rows = list((packs.get("crack") or {}).get("rows") or [])
    deflection_rows = list((packs.get("deflection") or {}).get("rows") or [])
    return {
        "mode": "real",
        "state": state,
        "overview": overview,
        "bending_rows": bending_rows,
        "shear_rows": shear_rows,
        "crack_rows": crack_rows,
        "deflection_rows": deflection_rows,
        "banner_title": _guidance_title_for_state(state, overview),
        "banner_title_probe_mode": "fast_summary_truth",
        "worst_util": _float_or_none(overview.get("worst_util")),
    }


def _evaluate_synthetic_case(case: dict[str, Any]) -> dict[str, Any]:
    bending_rows = [_row(r["title"], r["status"], r.get("util")) for r in list(case.get("bending_rows") or [])]
    shear_rows = [_row(r["title"], r["status"], r.get("util")) for r in list(case.get("shear_rows") or [])]
    crack_rows = [_row(r["title"], r["status"], r.get("util")) for r in list(case.get("crack_rows") or [])]
    deflection_rows = [_row(r["title"], r["status"], r.get("util")) for r in list(case.get("deflection_rows") or [])]
    return {
        "mode": "synthetic",
        "state": None,
        "overview": {},
        "bending_rows": bending_rows,
        "shear_rows": shear_rows,
        "crack_rows": crack_rows,
        "deflection_rows": deflection_rows,
        "banner_title": case.get("banner_title"),
        "worst_util": _float_or_none(case.get("worst_util")),
    }


def _derive_case(case: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    bending_rows = list(payload["bending_rows"])
    shear_rows = list(payload["shear_rows"])
    crack_rows = list(payload["crack_rows"])
    deflection_rows = list(payload["deflection_rows"])

    displayed_summary_status = classify_beam_check_rows(
        bending_rows=bending_rows,
        shear_rows=shear_rows,
        crack_rows=crack_rows,
        deflection_rows=deflection_rows,
    ).get("overall_status")

    bending_row = _find_row(bending_rows, "Positive bending", "Flexural strength capacity", "Negative bending")
    ductility_row = _find_row(bending_rows, "Ductility limit")
    shear_row = _find_row(shear_rows, "Sectional shear capacity")
    spacing_row = _find_row(
        shear_rows,
        "Minimum shear reinforcement",
        "Link spacing (provided / required / effective)",
        "Spacing/detailing limit",
    )
    serviceability_status = _rollup_serviceability(crack_rows, deflection_rows)

    checks = {
        "bending": str((bending_row or {}).get("status") or ""),
        "shear": str((shear_row or {}).get("status") or ""),
        "ductility": str((ductility_row or {}).get("status") or ""),
        "spacing_detailing": str((spacing_row or {}).get("status") or ""),
        "serviceability": str(serviceability_status or ""),
    }
    expect_required = dict(case.get("expect_required") or {})
    required_values = []
    for key in ("bending", "shear", "ductility", "spacing_detailing", "serviceability"):
        if expect_required.get(key):
            required_values.append((key, checks.get(key) or ""))

    fail_keys = [key for key, status in required_values if _status_bucket(status) == "fail"]
    warn_keys = [key for key, status in required_values if _status_bucket(status) == "warn"]
    unknown_keys = [key for key, status in required_values if _status_bucket(status) == "unknown"]

    if fail_keys:
        expected_overall_status = BEAM_STATUS_FAIL
    elif warn_keys or unknown_keys:
        expected_overall_status = BEAM_STATUS_WARN
    else:
        expected_overall_status = BEAM_STATUS_PASS

    governing_candidates = []
    for key, row in (
        ("bending", bending_row),
        ("shear", shear_row),
        ("ductility", ductility_row),
        ("spacing_detailing", spacing_row),
    ):
        util = _float_or_none((row or {}).get("util"))
        if util is not None:
            governing_candidates.append(
                {
                    "family": key,
                    "name": str((row or {}).get("title") or key),
                    "status": str((row or {}).get("status") or ""),
                    "util": util,
                }
            )
    governing = max(governing_candidates, key=lambda item: item["util"]) if governing_candidates else None
    governing_family = governing["family"] if governing else None
    governing_check_name = governing["name"] if governing else None
    governing_check_status = governing["status"] if governing else ""

    misleading_target_band = bool(
        payload.get("banner_title")
        and "within target band" in str(payload.get("banner_title") or "").lower()
        and payload.get("worst_util") is not None
        and not (TARGET_LOW <= float(payload["worst_util"]) <= TARGET_HIGH)
    )

    false_pass = displayed_summary_status == BEAM_STATUS_PASS and expected_overall_status != BEAM_STATUS_PASS
    false_fail = displayed_summary_status == BEAM_STATUS_FAIL and expected_overall_status == BEAM_STATUS_PASS
    missing_governing_status = bool(governing_check_name and _status_bucket(governing_check_status) == "unknown")
    ductility_false_pass = expect_required.get("ductility") and _status_bucket(checks["ductility"]) == "fail" and displayed_summary_status == BEAM_STATUS_PASS
    ductility_unknown_accepted = expect_required.get("ductility") and _status_bucket(checks["ductility"]) == "unknown" and displayed_summary_status == BEAM_STATUS_PASS

    verdict = "FAIL" if any(
        [
            false_pass,
            false_fail,
            missing_governing_status,
            misleading_target_band,
            ductility_false_pass,
            ductility_unknown_accepted,
        ]
    ) else "PASS"

    mismatch_reasons = []
    if false_pass:
        mismatch_reasons.append("summary_false_pass")
    if false_fail:
        mismatch_reasons.append("summary_false_fail")
    if missing_governing_status:
        mismatch_reasons.append("missing_governing_status")
    if misleading_target_band:
        mismatch_reasons.append("misleading_target_band")
    if ductility_false_pass:
        mismatch_reasons.append("failed_required_ductility_accepted")
    if ductility_unknown_accepted:
        mismatch_reasons.append("unknown_required_ductility_accepted")

    return {
        "case_id": case["case_id"],
        "evaluation_mode": payload["mode"],
        "inputs": {
            "Mu": case.get("mu"),
            "Vu": case.get("vu"),
        },
        "displayed_summary_status": displayed_summary_status,
        "displayed_banner_title": payload.get("banner_title"),
        "governing_family": governing_family,
        "governing_check_name": governing_check_name,
        "governing_check_status": governing_check_status,
        "bending_status": checks["bending"] or None,
        "shear_status": checks["shear"] or None,
        "ductility_status": checks["ductility"] or None,
        "spacing_detailing_status": checks["spacing_detailing"] or None,
        "serviceability_status": checks["serviceability"] or None,
        "final_expected_overall_status": expected_overall_status,
        "mismatch_reason": ", ".join(mismatch_reasons) or None,
        "worst_util": payload.get("worst_util"),
        "target_low": TARGET_LOW,
        "target_high": TARGET_HIGH,
        "verdict": verdict,
        "debug": {
            "required_statuses": required_values,
            "fail_keys": fail_keys,
            "warn_keys": warn_keys,
            "unknown_keys": unknown_keys,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8524, help="Accepted for command compatibility; not used.")
    parser.add_argument("--case", action="append", dest="case_ids", default=None)
    parser.add_argument("--cases", default=None, help="Comma-separated case_id list.")
    parser.add_argument("--list-cases", action="store_true")
    args = parser.parse_args(argv)

    all_cases = REAL_CASES + SYNTHETIC_CASES
    all_case_ids = [str(case.get("case_id") or "") for case in all_cases]
    if args.list_cases:
        print("\n".join(all_case_ids + sorted(FOCUSED_CASE_ALIASES)))
        return 0
    requested_case_ids = {
        str(case_id).strip()
        for case_id in (args.case_ids or [])
        if str(case_id).strip()
    }
    requested_case_ids.update(
        str(case_id).strip()
        for case_id in str(args.cases or "").split(",")
        if str(case_id).strip()
    )
    selected_cases, missing_case_ids = _resolve_requested_cases(all_cases, requested_case_ids)
    if missing_case_ids:
        raise SystemExit(f"Unknown summary truth case(s): {', '.join(missing_case_ids)}")

    cases_out = []
    false_pass_count = 0
    false_fail_count = 0
    missing_governing_status_count = 0
    misleading_target_band_count = 0
    ductility_false_pass_count = 0
    ductility_unknown_accepted_count = 0

    for case in selected_cases:
        payload = _evaluate_real_case(case) if case["mode"] == "real" else _evaluate_synthetic_case(case)
        result = _derive_case(case, payload)
        cases_out.append(result)
        reasons = set(str(result.get("mismatch_reason") or "").split(", "))
        if "summary_false_pass" in reasons:
            false_pass_count += 1
        if "summary_false_fail" in reasons:
            false_fail_count += 1
        if "missing_governing_status" in reasons:
            missing_governing_status_count += 1
        if "misleading_target_band" in reasons:
            misleading_target_band_count += 1
        if "failed_required_ductility_accepted" in reasons:
            ductility_false_pass_count += 1
        if "unknown_required_ductility_accepted" in reasons:
            ductility_unknown_accepted_count += 1

    pass_count = sum(1 for case in cases_out if case["verdict"] == "PASS")
    fail_count = sum(1 for case in cases_out if case["verdict"] == "FAIL")
    summary_truth_status = "PASS" if fail_count == 0 else "FAIL"
    ductility_status = "PASS" if (ductility_false_pass_count == 0 and ductility_unknown_accepted_count == 0) else "FAIL"

    summary = {
        "total_cases": len(cases_out),
        "PASS_count": pass_count,
        "FAIL_count": fail_count,
        "false_pass_count": false_pass_count,
        "false_fail_count": false_fail_count,
        "missing_governing_status_count": missing_governing_status_count,
        "misleading_target_band_count": misleading_target_band_count,
        "ductility_false_pass_count": ductility_false_pass_count,
        "ductility_unknown_accepted_count": ductility_unknown_accepted_count,
        "summary_truth_status": summary_truth_status,
        "ductility_expectation_status": ductility_status,
    }

    result = {
        "timestamp": TIMESTAMP,
        "summary": summary,
        "cases": cases_out,
    }
    artifact_dir = REPO_ROOT / "artifacts" / "verification" / "latest"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_dir / f"summary_truth_ladder_{TIMESTAMP}.json"
    artifact_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print(f"summary_truth_ladder: {artifact_path.name}")
    print(f"total={summary['total_cases']} PASS={summary['PASS_count']} FAIL={summary['FAIL_count']}")
    print(
        "false_pass={false_pass} false_fail={false_fail} missing_governing={missing} misleading_target_band={misleading}".format(
            false_pass=false_pass_count,
            false_fail=false_fail_count,
            missing=missing_governing_status_count,
            misleading=misleading_target_band_count,
        )
    )
    print(
        "ductility_false_pass={fail_pass} ductility_unknown_accepted={unknown}".format(
            fail_pass=ductility_false_pass_count,
            unknown=ductility_unknown_accepted_count,
        )
    )
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    _exit_code = main()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(_exit_code)
