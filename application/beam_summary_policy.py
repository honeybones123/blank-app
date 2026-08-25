"""Pure beam summary status and check-classification policy."""

from __future__ import annotations

import math

BEAM_STATUS_PASS = "PASS"
BEAM_STATUS_FAIL = "FAIL"
BEAM_STATUS_WARN = "WARN"
BEAM_STATUS_NOT_RUN = "NOT_RUN"

def _safe_summary_float(value):
    try:
        out = float(value)
    except Exception:
        return None
    if math.isnan(out) or math.isinf(out):
        return None
    return out

def make_not_run_beam_summary() -> dict:
    return {
        "overall_status": BEAM_STATUS_NOT_RUN,
        "strength_status": BEAM_STATUS_NOT_RUN,
        "detailing_status": BEAM_STATUS_NOT_RUN,
        "bending_status": BEAM_STATUS_NOT_RUN,
        "shear_status": BEAM_STATUS_NOT_RUN,
        "crack_status": BEAM_STATUS_NOT_RUN,
        "deflection_status": BEAM_STATUS_NOT_RUN,
        "last_checked_at": None,
        "Mu_star": None,
        "phi_Mu_cap": None,
        "Mu_utilisation": None,
        "Vu_star": None,
        "phi_Vu_cap": None,
        "Vu_utilisation": None,
        "crack_utilisation": None,
        "deflection_utilisation": None,
        "batch_design_utilisation": None,
        "batch_pre_optimisation_utilisation": None,
        "batch_pre_optimisation_phiMu_kNm": None,
        "batch_pre_optimisation_phiVu_kN": None,
    }

def normalize_beam_status(raw_status=None, *, utilisation=None, pass_flag=None) -> str:
    if isinstance(pass_flag, bool):
        if not pass_flag:
            return BEAM_STATUS_FAIL
        util = _safe_summary_float(utilisation)
        if util is not None and util >= 0.9:
            return BEAM_STATUS_WARN
        return BEAM_STATUS_PASS

    text = str(raw_status or "").strip().upper()
    if text == "INFO":
        return BEAM_STATUS_NOT_RUN
    if text in {BEAM_STATUS_PASS, BEAM_STATUS_FAIL, BEAM_STATUS_WARN, BEAM_STATUS_NOT_RUN}:
        return text
    if ("FAIL" in text) or (text == "NG"):
        return BEAM_STATUS_FAIL
    if ("WARN" in text) or ("NEAR LIMIT" in text) or (text == "CHECK"):
        return BEAM_STATUS_WARN
    if ("PASS" in text) or (text == "OK"):
        util = _safe_summary_float(utilisation)
        if util is not None and util >= 0.9:
            return BEAM_STATUS_WARN
        return BEAM_STATUS_PASS

    util = _safe_summary_float(utilisation)
    if util is None:
        return BEAM_STATUS_NOT_RUN
    if util > 1.0:
        return BEAM_STATUS_FAIL
    if util >= 0.9:
        return BEAM_STATUS_WARN
    if util >= 0.0:
        return BEAM_STATUS_PASS
    return BEAM_STATUS_NOT_RUN

def get_beam_overall_status(summary) -> str:
    summary = summary if isinstance(summary, dict) else {}
    strength_status = normalize_beam_status(summary.get("strength_status"))
    detailing_status = normalize_beam_status(summary.get("detailing_status"))
    if strength_status != BEAM_STATUS_NOT_RUN or detailing_status != BEAM_STATUS_NOT_RUN:
        if strength_status == BEAM_STATUS_FAIL:
            return BEAM_STATUS_FAIL
        if strength_status == BEAM_STATUS_WARN:
            return BEAM_STATUS_WARN
        if detailing_status == BEAM_STATUS_FAIL:
            return BEAM_STATUS_FAIL
        if detailing_status == BEAM_STATUS_WARN:
            return BEAM_STATUS_WARN
        if strength_status == BEAM_STATUS_PASS:
            return BEAM_STATUS_PASS

    statuses = [
        normalize_beam_status(summary.get("bending_status")),
        normalize_beam_status(summary.get("shear_status")),
        normalize_beam_status(summary.get("crack_status")),
        normalize_beam_status(summary.get("deflection_status")),
    ]
    if not statuses or all(status == BEAM_STATUS_NOT_RUN for status in statuses):
        return BEAM_STATUS_NOT_RUN
    if any(status == BEAM_STATUS_FAIL for status in statuses):
        return BEAM_STATUS_FAIL
    if any(status == BEAM_STATUS_WARN for status in statuses):
        return BEAM_STATUS_WARN
    if any(status == BEAM_STATUS_NOT_RUN for status in statuses):
        return BEAM_STATUS_NOT_RUN
    return BEAM_STATUS_PASS

def _sanitize_beam_summary(summary) -> dict:
    cleaned = make_not_run_beam_summary()
    if not isinstance(summary, dict):
        return cleaned

    cleaned["overall_status"] = normalize_beam_status(summary.get("overall_status"))
    cleaned["strength_status"] = normalize_beam_status(summary.get("strength_status"))
    cleaned["detailing_status"] = normalize_beam_status(summary.get("detailing_status"))
    cleaned["bending_status"] = normalize_beam_status(summary.get("bending_status"))
    cleaned["shear_status"] = normalize_beam_status(summary.get("shear_status"))
    cleaned["crack_status"] = normalize_beam_status(summary.get("crack_status"))
    cleaned["deflection_status"] = normalize_beam_status(summary.get("deflection_status"))
    cleaned["overall_status"] = get_beam_overall_status(cleaned)
    cleaned["last_checked_at"] = summary.get("last_checked_at")
    for key in (
        "Mu_star",
        "phi_Mu_cap",
        "Mu_utilisation",
        "Vu_star",
        "phi_Vu_cap",
        "Vu_utilisation",
        "crack_utilisation",
        "deflection_utilisation",
        "batch_design_utilisation",
        "batch_pre_optimisation_utilisation",
        "batch_pre_optimisation_phiMu_kNm",
        "batch_pre_optimisation_phiVu_kN",
    ):
        cleaned[key] = _safe_summary_float(summary.get(key))
    return cleaned

def _rollup_statuses(statuses: list[str]) -> str:
    normalized = [normalize_beam_status(status) for status in (statuses or [])]
    normalized = [status for status in normalized if status != BEAM_STATUS_NOT_RUN]
    if not normalized:
        return BEAM_STATUS_NOT_RUN
    if any(status == BEAM_STATUS_FAIL for status in normalized):
        return BEAM_STATUS_FAIL
    if any(status == BEAM_STATUS_WARN for status in normalized):
        return BEAM_STATUS_WARN
    return BEAM_STATUS_PASS

def classify_beam_check_rows(
    bending_rows: list[dict] | None = None,
    shear_rows: list[dict] | None = None,
    crack_rows: list[dict] | None = None,
    deflection_rows: list[dict] | None = None,
) -> dict:
    """
    Separate primary strength outcomes from detailing/code-compliance outcomes.
    This keeps summary status conservative: detailing failures downgrade overall PASS to WARN.
    """
    bending_rows = bending_rows or []
    shear_rows = shear_rows or []
    crack_rows = crack_rows or []
    deflection_rows = deflection_rows or []

    strength_statuses = []
    detailing_statuses = []
    notes = []
    saw_bending_strength_row = False
    saw_ductility_row = False
    ductility_status_missing_or_not_run = False
    saw_shear_strength_row = False
    shear_status_missing_or_not_run = False

    bending_strength_titles = {
        "Flexural strength capacity",
        "Positive bending",
        "Negative bending",
    }
    bending_detail_titles = {
        "Minimum tensile reinforcement",
        "Minimum design capacity requirement",
        "Ductility limit",
    }
    shear_strength_titles = {
        "Sectional shear capacity",
        "Web-crushing strength",
    }

    def _add_status(rows, *, strength_titles=None, detail_titles=None, default_to_strength=False):
        nonlocal saw_bending_strength_row, saw_ductility_row, ductility_status_missing_or_not_run
        nonlocal saw_shear_strength_row, shear_status_missing_or_not_run
        for row in rows:
            if (row or {}).get("is_informational"):
                continue
            title = str((row or {}).get("title") or "")
            status = normalize_beam_status((row or {}).get("status"))
            if strength_titles and title in strength_titles and title in bending_strength_titles:
                saw_bending_strength_row = True
            if strength_titles and title in strength_titles and title in shear_strength_titles:
                saw_shear_strength_row = True
                if status == BEAM_STATUS_NOT_RUN:
                    shear_status_missing_or_not_run = True
            if title == "Ductility limit":
                saw_ductility_row = True
                if status == BEAM_STATUS_NOT_RUN:
                    ductility_status_missing_or_not_run = True
            if status == BEAM_STATUS_NOT_RUN:
                continue
            if strength_titles and title in strength_titles:
                strength_statuses.append(status)
            elif detail_titles and title in detail_titles:
                detailing_statuses.append(status)
                if status in {BEAM_STATUS_FAIL, BEAM_STATUS_WARN}:
                    notes.append(f"{title}: {status}")
            elif default_to_strength:
                strength_statuses.append(status)
            else:
                detailing_statuses.append(status)
                if status in {BEAM_STATUS_FAIL, BEAM_STATUS_WARN}:
                    notes.append(f"{title}: {status}")

    _add_status(bending_rows, strength_titles=bending_strength_titles, detail_titles=bending_detail_titles)
    _add_status(shear_rows, strength_titles=shear_strength_titles, default_to_strength=False)
    _add_status(crack_rows, default_to_strength=True)
    _add_status(deflection_rows, default_to_strength=True)

    if saw_bending_strength_row and (not saw_ductility_row or ductility_status_missing_or_not_run):
        detailing_statuses.append(BEAM_STATUS_WARN)
        notes.append("Ductility limit: NOT_RUN")
    if saw_shear_strength_row and shear_status_missing_or_not_run:
        detailing_statuses.append(BEAM_STATUS_WARN)
        notes.append("Sectional shear capacity: NOT_RUN")

    strength_status = _rollup_statuses(strength_statuses)
    detailing_status = _rollup_statuses(detailing_statuses)
    overall_status = get_beam_overall_status(
        {
            "strength_status": strength_status,
            "detailing_status": detailing_status,
        }
    )
    return {
        "strength_status": strength_status,
        "detailing_status": detailing_status,
        "overall_status": overall_status,
        "notes": notes,
    }

__all__ = [
    "BEAM_STATUS_FAIL", "BEAM_STATUS_NOT_RUN", "BEAM_STATUS_PASS",
    "BEAM_STATUS_WARN", "classify_beam_check_rows",
    "get_beam_overall_status", "make_not_run_beam_summary",
    "normalize_beam_status",
]


