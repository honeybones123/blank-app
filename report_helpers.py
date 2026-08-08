import io
import math
import os
import re
from datetime import datetime

import pandas as pd
import streamlit as st

from application.beam_summary_policy import (
    BEAM_STATUS_FAIL,
    BEAM_STATUS_NOT_RUN,
    BEAM_STATUS_PASS,
    BEAM_STATUS_WARN,
    classify_beam_check_rows,
    get_beam_overall_status,
    normalize_beam_status,
)
from state_and_helpers import (
    build_beam_schedule_rows,
    get_active_beam_record,
    get_active_beam_summary,
    summarize_longitudinal_rows,
)
from widgets_helpers import render_plotly_diagram


def _safe_float(value):
    try:
        out = float(value)
    except Exception:
        return None
    if math.isnan(out) or math.isinf(out):
        return None
    return out


def _display_value(value, digits: int = 2) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def _format_timestamp(value) -> str:
    if not value:
        return "Not run"
    return str(value).replace("T", " ")


def _status_rank(status: str) -> int:
    if str(status or "").strip().upper() == "INFO":
        return -1
    normalized = normalize_beam_status(status)
    if normalized == BEAM_STATUS_FAIL:
        return 3
    if normalized == BEAM_STATUS_WARN:
        return 2
    if normalized == BEAM_STATUS_PASS:
        return 1
    return 0


def format_report_status_label(
    status: str,
    *,
    strength_status: str | None = None,
    detailing_status: str | None = None,
) -> str:
    raw_text = str(status or "").strip().upper().replace("_", " ")
    if raw_text == "INFO":
        return "INFO"
    if raw_text == "PASS WITH WARNINGS":
        return "PASS WITH WARNINGS"

    normalized = normalize_beam_status(status)
    strength = normalize_beam_status(strength_status)
    detailing = normalize_beam_status(detailing_status)
    if (
        normalized == BEAM_STATUS_WARN
        and strength == BEAM_STATUS_PASS
        and detailing in {BEAM_STATUS_FAIL, BEAM_STATUS_WARN}
    ):
        return "PASS WITH WARNINGS"
    return normalized


def format_report_status_badge(
    status: str,
    *,
    strength_status: str | None = None,
    detailing_status: str | None = None,
) -> str:
    label = format_report_status_label(
        status,
        strength_status=strength_status,
        detailing_status=detailing_status,
    )
    if label == BEAM_STATUS_PASS:
        return "🟢 PASS"
    if label == BEAM_STATUS_FAIL:
        return "🔴 FAIL"
    if label == "PASS WITH WARNINGS":
        return "🟠 PASS WITH WARNINGS"
    if label == BEAM_STATUS_WARN:
        return "🟠 WARN"
    if label == "INFO":
        return "🔵 INFO"
    return "⚪ NOT_RUN"


def _report_ready_label(overall_status: str) -> str:
    return "Ready" if normalize_beam_status(overall_status) != BEAM_STATUS_NOT_RUN else "Needs analysis"


def _normalise_report_row(row: dict) -> dict:
    row = row if isinstance(row, dict) else {}
    calc = row.get("calculated")
    req = row.get("requirement")
    cap = row.get("capacity")
    act = row.get("action")
    if cap is None or str(cap).strip() == "":
        cap = calc if calc is not None and str(calc).strip() != "" else row.get("value", "-")
    if act is None or str(act).strip() == "":
        act = req if req is not None and str(req).strip() != "" else row.get("limit", "-")
    if calc is None or str(calc).strip() == "":
        calc = cap
    if req is None or str(req).strip() == "":
        req = act
    return {
        "uid": row.get("uid", ""),
        "title": row.get("title", ""),
        "row_type": row.get("row_type", ""),
        "calculated": calc,
        "requirement": req,
        "capacity": cap,
        "action": act,
        "value": cap,
        "limit": act,
        "util": row.get("util", "-"),
        "status": row.get("status", BEAM_STATUS_NOT_RUN),
        "ok": row.get("ok"),
        "route_page": row.get("route_page", ""),
        "is_primary": bool(row.get("is_primary", False)),
        "is_informational": bool(row.get("is_informational", False)),
    }


def _pick_primary_check(rows: list[dict] | None, fallback_title: str) -> dict:
    rows = [_normalise_report_row(row) for row in (rows or [])]
    for row in rows:
        if row.get("is_primary"):
            return row
    if rows:
        return rows[0]
    return {
        "title": fallback_title,
        "capacity": "-",
        "action": "-",
        "value": "-",
        "limit": "-",
        "util": "-",
        "status": BEAM_STATUS_NOT_RUN,
        "ok": None,
        "route_page": "",
        "is_primary": False,
    }


def _serviceability_status(crack_status: str, deflection_status: str) -> str:
    crack = normalize_beam_status(crack_status)
    deflection = normalize_beam_status(deflection_status)
    if BEAM_STATUS_FAIL in {crack, deflection}:
        return BEAM_STATUS_FAIL
    if BEAM_STATUS_WARN in {crack, deflection}:
        return BEAM_STATUS_WARN
    if crack == BEAM_STATUS_PASS and deflection == BEAM_STATUS_PASS:
        return BEAM_STATUS_PASS
    return BEAM_STATUS_NOT_RUN


def _worst_utilisation(*values) -> float | None:
    usable = [_safe_float(value) for value in values]
    usable = [value for value in usable if value is not None]
    return max(usable) if usable else None


def _rebar_layer_text(count, dia) -> str:
    count_val = int(count or 0)
    dia_val = int(dia or 0)
    if count_val <= 0 or dia_val <= 0:
        return "-"
    return f"{count_val}N{dia_val}"


def _ligature_text(lig_d, s_lig, lig_legs) -> str:
    dia_val = int(lig_d or 0)
    spacing_val = int(s_lig or 0)
    legs_val = int(lig_legs or 0)
    if dia_val <= 0 or spacing_val <= 0:
        return "-"
    leg_text = f", {legs_val} legs" if legs_val > 0 else ""
    return f"N{dia_val} @ {spacing_val}{leg_text}"


def _cover_text(top, bottom, side) -> str:
    top_val = _safe_float(top)
    bottom_val = _safe_float(bottom)
    side_val = _safe_float(side)
    values = [value for value in (top_val, bottom_val, side_val) if value is not None]
    if not values:
        return "-"
    if top_val == bottom_val == side_val:
        return f"{_display_value(top_val, 0)} mm"
    parts = []
    if top_val is not None:
        parts.append(f"top {_display_value(top_val, 0)}")
    if bottom_val is not None:
        parts.append(f"bot {_display_value(bottom_val, 0)}")
    if side_val is not None:
        parts.append(f"side {_display_value(side_val, 0)}")
    return ", ".join(parts) + " mm"


def _mm_to_m_text(value, digits: int = 3) -> str:
    num = _safe_float(value)
    if num is None:
        return "Not available"
    return f"{_display_value(num / 1000.0, digits)} m"


def _geometry_group() -> dict:
    sec_shape = st.session_state.get("sec_shape")
    rows = {"Section": sec_shape}
    if sec_shape == "T":
        rows["bw"] = f"{_display_value(_safe_float(st.session_state.get('bw')), 0)} mm"
        rows["bf"] = f"{_display_value(_safe_float(st.session_state.get('bf')), 0)} mm"
        rows["tf"] = f"{_display_value(_safe_float(st.session_state.get('tf')), 0)} mm"
    elif sec_shape == "I":
        rows["tw"] = f"{_display_value(_safe_float(st.session_state.get('tw')), 0)} mm"
        rows["bf"] = f"{_display_value(_safe_float(st.session_state.get('bf')), 0)} mm"
        rows["tf"] = f"{_display_value(_safe_float(st.session_state.get('tf')), 0)} mm"
    else:
        rows["b"] = f"{_display_value(_safe_float(st.session_state.get('b')), 0)} mm"
    rows["D"] = f"{_display_value(_safe_float(st.session_state.get('D')), 0)} mm"
    rows["Span"] = _mm_to_m_text(st.session_state.get("L"))
    rows["Cover"] = _cover_text(
        st.session_state.get("cover_top"),
        st.session_state.get("cover_bot"),
        st.session_state.get("cover_side"),
    )
    return rows


def _materials_group() -> dict:
    rows = {
        "f'c": f"{_display_value(_safe_float(st.session_state.get('fc')), 0)} MPa",
        "fsy": f"{_display_value(_safe_float(st.session_state.get('fsy')), 0)} MPa",
    }
    ec_val = _safe_float(st.session_state.get("Ec"))
    es_val = _safe_float(st.session_state.get("Es"))
    if ec_val is not None:
        rows["Ec"] = f"{_display_value(ec_val, 0)} MPa"
    if es_val is not None:
        rows["Es"] = f"{_display_value(es_val, 0)} MPa"
    return rows


def _reinforcement_group() -> dict:
    bottom = summarize_longitudinal_rows("bot", source=st.session_state)
    top = summarize_longitudinal_rows("top", source=st.session_state)
    return {
        "Bottom": bottom,
        "Top": top,
        "Ligatures": _ligature_text(
            st.session_state.get("lig_d"),
            st.session_state.get("s_lig"),
            st.session_state.get("lig_legs"),
        ),
    }


def _action_source_texts() -> dict:
    source = str(st.session_state.get("actions_source") or "").strip()
    design_source = str(st.session_state.get("design_actions_source") or "max").strip().lower()
    if source == "Teaching SFD/BMD page (|M|max, |V|max)":
        suffix = "section actions" if design_source == "section" else "max envelope"
        label = f"Design-page solver ({suffix})"
        return {"uls": label, "sls": label}
    if source == "Manual design actions (inputs below)":
        return {"uls": "Manual ULS input", "sls": "Manual/design SLS input"}
    if source:
        return {"uls": source, "sls": source}
    return {"uls": "", "sls": ""}


def _uls_actions_group() -> dict:
    rows = {}
    mu_star = _safe_float(st.session_state.get("Mu_star"))
    vu_star = _safe_float(st.session_state.get("Vu_star"))
    tu_star = _safe_float(st.session_state.get("Tu_star"))
    n_star = _safe_float(st.session_state.get("N_star"))
    p_star = _safe_float(st.session_state.get("P_star"))
    if mu_star is not None:
        rows["Mu*"] = f"{_display_value(mu_star, 2)} kNm"
    if vu_star is not None:
        rows["Vu*"] = f"{_display_value(vu_star, 2)} kN"
    if tu_star not in (None, 0.0):
        rows["Tu*"] = f"{_display_value(tu_star, 2)} kNm"
    if n_star not in (None, 0.0):
        rows["N*"] = f"{_display_value(n_star, 2)} kN"
    if p_star not in (None, 0.0):
        rows["P*"] = f"{_display_value(p_star, 2)} kN"
    source_text = _action_source_texts().get("uls")
    if source_text:
        rows["Source"] = source_text
    return rows


def _sls_actions_group() -> dict:
    rows = {}
    ms = _safe_float(st.session_state.get("sls_Mstar"))
    vs = _safe_float(st.session_state.get("sls_Vstar"))
    ns = _safe_float(st.session_state.get("sls_Nstar"))
    sigma_s = _safe_float(st.session_state.get("sigma_s_sls"))
    if ms is not None:
        rows["Ms"] = f"{_display_value(ms, 2)} kNm"
    if vs not in (None, 0.0):
        rows["Vs"] = f"{_display_value(vs, 2)} kN"
    if ns not in (None, 0.0):
        rows["Ns"] = f"{_display_value(ns, 2)} kN"
    if sigma_s is not None:
        rows["Service steel stress"] = f"{_display_value(sigma_s, 2)} MPa"
    source_text = _action_source_texts().get("sls")
    if source_text and source_text != _action_source_texts().get("uls"):
        rows["Source"] = source_text
    if not rows:
        rows["Status"] = "Not available"
    return rows


def _format_detail_title(title: str, route_page: str) -> str:
    text = str(title or "").strip()
    if route_page == "bending" and text == "Service bending moment":
        return "SLS bending action"
    return text or "-"


def _format_detail_limit(limit, title: str, route_page: str) -> str:
    text = str(limit or "").strip()
    if route_page == "bending" and str(title or "").strip() == "Service bending moment":
        if text in ("From design/manual SLS action", "SLS design / manual actions"):
            return "Action source"
    return text or "-"


def _detail_action_basis(section_name: str, actions: dict) -> str:
    uls = actions.get("uls", {}) if isinstance(actions, dict) else {}
    sls = actions.get("sls", {}) if isinstance(actions, dict) else {}
    section = str(section_name or "").strip().lower()
    if section == "bending":
        return f"ULS action basis: Mu* = {uls.get('Mu*', 'Not available')}"
    if section == "shear":
        return f"ULS action basis: Vu* = {uls.get('Vu*', 'Not available')}"
    if section == "crack":
        return f"SLS action basis: Ms = {sls.get('Ms', 'Not available')}"
    if section == "deflection":
        return f"SLS action basis: Ms = {sls.get('Ms', 'Not available')}"
    return ""


def _utilisation_severity(utilisation) -> str:
    util = _safe_float(utilisation)
    if util is None:
        return "Not available"
    if util > 1.0:
        return "FAIL"
    if util >= 0.70:
        return "NEAR LIMIT"
    return "OK"


def _action_source_context() -> dict:
    actions_mode = str(st.session_state.get("actions_mode") or "").strip().lower()
    actions_source = str(st.session_state.get("actions_source") or "").strip()
    if actions_mode == "design" or "TEACHING SFD/BMD PAGE" in actions_source.upper():
        mode = "design_page"
    elif actions_mode == "manual" or "MANUAL" in actions_source.upper():
        mode = "manual"
    else:
        mode = "unknown"

    if actions_source:
        label = actions_source
    elif mode == "design_page":
        label = "Design-page solver"
    elif mode == "manual":
        label = "Manual actions"
    else:
        label = "Not clearly identified"
    return {
        "action_source_mode": mode,
        "action_source_label": label,
    }


def _support_condition_from_case(case: str | None) -> str:
    text = str(case or "").strip()
    if text.startswith("Simple beam"):
        try:
            sc = (
                st.session_state.get("design_support_condition")
                or st.session_state.get("sfd_support_condition")
                or "Simply supported"
            )
            return str(sc).strip().replace("-", "–") or "Simply supported"
        except Exception:
            return "Simply supported"
    if text.startswith("Cantilever"):
        return "Fixed-Free"
    if text.startswith("Overhanging beam"):
        return "Pinned-Pinned (overhang)"
    try:
        from deflection_support import get_resolved_deflection_support_type

        fb = get_resolved_deflection_support_type(st.session_state)
        return fb or "Not available"
    except Exception:
        fallback = str(st.session_state.get("defl_support_type") or "").strip()
        return fallback or "Not available"


def _format_maybe_length(value, unit: str = "m") -> str:
    num = _safe_float(value)
    if num is None:
        return "Not available"
    return f"{_display_value(num, 3)} {unit}"


def _beam_display_name(beam_id: str | None, beam_label: str | None) -> str:
    beam_id_text = str(beam_id or "").strip()
    beam_label_text = str(beam_label or "").strip()
    match = re.search(r"(\d+)$", beam_id_text)
    if match:
        beam_ref = f"B{match.group(1)}"
        if beam_label_text:
            return f"{beam_ref} - {beam_label_text}"
        return f"{beam_ref} - Beam {match.group(1)}"
    if beam_label_text and beam_id_text:
        return f"{beam_id_text} - {beam_label_text}"
    return beam_label_text or beam_id_text or "Beam"


def _report_branding() -> dict:
    company_name = str(st.session_state.get("report_company_name") or "").strip()
    logo_bytes = st.session_state.get("report_company_logo_bytes")
    logo_name = str(st.session_state.get("report_company_logo_name") or "").strip()
    logo_type = str(st.session_state.get("report_company_logo_type") or "").strip()
    if not isinstance(logo_bytes, (bytes, bytearray)) or not logo_bytes:
        logo_bytes = None
    return {
        "company_name": company_name,
        "logo_file_present": bool(logo_bytes),
        "logo_image_data": bytes(logo_bytes) if logo_bytes else None,
        "logo_filename": logo_name,
        "logo_mime_type": logo_type,
    }


def _report_metadata(generated_at: str) -> dict:
    project_name = (
        st.session_state.get("active_project_name")
        or st.session_state.get("project_name")
        or ""
    )
    client_name = (
        st.session_state.get("client_name")
        or st.session_state.get("client")
        or ""
    )
    engineer_name = (
        st.session_state.get("engineer_name")
        or st.session_state.get("user_name")
        or ""
    )
    checked_by = str(st.session_state.get("checked_by") or "").strip()
    revision_number = int(st.session_state.get("report_revision", 1) or 1)
    revision_label = f"Rev {revision_number}"
    revision_description = str(st.session_state.get("report_revision_description") or "Initial design").strip()
    watermark_text = str(st.session_state.get("report_watermark_text") or "").strip()
    return {
        "project_name": project_name,
        "client_name": client_name,
        "engineer_name": engineer_name,
        "checked_by": checked_by,
        "date": _format_timestamp(generated_at),
        "revision_number": revision_number,
        "revision_label": revision_label,
        "revision_description": revision_description,
        "revision_history": [
            {
                "rev": revision_label,
                "date": _format_timestamp(generated_at),
                "description": revision_description,
            }
        ],
        "disclaimer": (
            "This report has been prepared based on the provided inputs and relevant design standards. "
            "It should be reviewed by a qualified engineer prior to construction."
        ),
        "signature_block": {
            "prepared_by": engineer_name,
            "checked_by": checked_by,
        },
        "watermark_text": watermark_text,
    }


def _analysis_context_groups(analysis_context: dict) -> dict:
    groups = {
        "Beam model": {
            "Action source": analysis_context.get("action_source_label", "Not clearly identified"),
        },
        "Loads": {},
        "Section extraction": {},
    }
    if analysis_context.get("action_source_mode") == "design_page":
        groups["Beam model"].update(
            {
                "Support condition": analysis_context.get("support_condition"),
                "Span": analysis_context.get("span"),
                "Total beam length": analysis_context.get("total_beam_length"),
            }
        )
        groups["Loads"].update(
            {
                "Loading condition": analysis_context.get("loading_condition"),
                "Active load combination": analysis_context.get("load_combination_label"),
            }
        )
        groups["Section extraction"].update(
            {
                "Section mode": analysis_context.get("section_mode"),
                "Section location": analysis_context.get("section_location"),
                "Source basis": analysis_context.get("source_basis"),
            }
        )
    return groups


def _build_load_summary(action_source_mode: str) -> list[dict]:
    if action_source_mode != "design_page":
        return []
    case = str(st.session_state.get("load_case") or st.session_state.get("sfd_case") or "").strip()
    if not case:
        return []

    rows = []
    w_uls = _safe_float(st.session_state.get("w_uls_kNm_per_m"))
    w_sls = _safe_float(st.session_state.get("w_sls_kNm_per_m"))
    g_udl = _safe_float(st.session_state.get("g_udl_kNm_per_m"))
    q_udl = _safe_float(st.session_state.get("q_udl_kNm_per_m"))
    p_uls = _safe_float(st.session_state.get("P_uls_kN"))
    p_sls = _safe_float(st.session_state.get("P_sls_kN"))
    g_point = _safe_float(st.session_state.get("G_point_kN"))
    q_point = _safe_float(st.session_state.get("Q_point_kN"))
    a_m = _safe_float(st.session_state.get("a_m"))
    a_over = _safe_float(st.session_state.get("a_overhang_m"))

    if "UDL" in case:
        rows.append({"Load": "Load type", "Value": "Uniformly distributed load"})
        if g_udl is not None:
            rows.append({"Load": "Dead load g", "Value": f"{_display_value(g_udl)} kN/m"})
        if q_udl is not None:
            rows.append({"Load": "Live load q", "Value": f"{_display_value(q_udl)} kN/m"})
        if "partial UDL" in case and a_m is not None:
            rows.append({"Load": "Loaded length a", "Value": f"{_display_value(a_m, 3)} m from left"})
    elif "point load" in case.lower() or "free end" in case.lower():
        rows.append({"Load": "Load type", "Value": "Point load"})
        if g_point is not None:
            rows.append({"Load": "Dead load G", "Value": f"{_display_value(g_point)} kN"})
        if q_point is not None:
            rows.append({"Load": "Live load Q", "Value": f"{_display_value(q_point)} kN"})
        if "overhang" in case.lower() and a_over is not None:
            rows.append({"Load": "Overhang length a", "Value": f"{_display_value(a_over, 3)} m"})
        elif a_m is not None:
            rows.append({"Load": "Load position a", "Value": f"{_display_value(a_m, 3)} m"})
    return rows


def _build_analysis_context(action_source: dict) -> dict:
    mode = action_source.get("action_source_mode", "unknown")
    label = action_source.get("action_source_label", "Not clearly identified")
    case = str(st.session_state.get("load_case") or st.session_state.get("sfd_case") or "").strip()
    section_source = str(st.session_state.get("design_actions_source") or "max").strip().lower()
    design_section_committed = bool(st.session_state.get("design_section_committed", False))
    committed_x = _safe_float(st.session_state.get("design_section_x_m"))
    cursor_x = _safe_float(st.session_state.get("section_cursor_x_m"))
    span_mm = _safe_float(st.session_state.get("L"))
    span_m = (span_mm / 1000.0) if span_mm is not None else None
    overhang = _safe_float(st.session_state.get("a_overhang_m"))
    total_length = (span_m + overhang) if (span_m is not None and overhang not in (None, 0.0)) else span_m

    if section_source == "section":
        if design_section_committed and committed_x is not None:
            section_mode = "User-selected section"
            section_location = f"x = {_display_value(committed_x, 3)} m from left support"
            section_basis = "Committed design section from beam-analysis page"
        elif cursor_x is not None:
            section_mode = "Preview section"
            section_location = f"x = {_display_value(cursor_x, 3)} m from left support"
            section_basis = "Current beam-analysis cursor location"
        else:
            section_mode = "Section-based extraction"
            section_location = "Not available"
            section_basis = "Beam-analysis section mode"
    else:
        section_mode = "Envelope maximum"
        section_location = "Not available"
        section_basis = "Absolute maxima from beam-analysis solver"

    return {
        "action_source_mode": mode,
        "action_source_label": label,
        "support_condition": _support_condition_from_case(case) if mode == "design_page" else "Not available",
        "span": _format_maybe_length(span_m),
        "total_beam_length": _format_maybe_length(total_length) if mode == "design_page" else "Not available",
        "loading_condition": case or "Not available",
        "load_combination_label": str(st.session_state.get("loads_edit_mode") or "").strip() or "Not available",
        "section_mode": section_mode if mode == "design_page" else "Not available",
        "section_location": section_location if mode == "design_page" else "Not available",
        "source_basis": section_basis if mode == "design_page" else label,
        "plot_source_page": "Teaching SFD/BMD page" if mode == "design_page" else "Not available",
        "load_summary": _build_load_summary(mode),
    }


def _design_basis_rows(beam_info: dict, action_source: dict, analysis_context: dict) -> dict:
    rows = {
        "Design code": beam_info.get("design_code", "AS 3600"),
        "Action source": action_source.get("action_source_label", "Not clearly identified"),
    }
    if action_source.get("action_source_mode") == "design_page":
        rows["Analysis basis"] = analysis_context.get("source_basis", "Beam-analysis solver")
    else:
        rows["Analysis basis"] = "Section-based member check"
    return rows


def _design_conclusion(checks: dict, summary_rows: list[dict]) -> dict:
    strength_label = checks.get("strength_status_label", BEAM_STATUS_NOT_RUN)
    detailing_label = checks.get("detailing_status_label", BEAM_STATUS_NOT_RUN)
    service_row = next((row for row in summary_rows if row.get("check") == "Serviceability"), {})
    service_label = service_row.get("status_label", BEAM_STATUS_NOT_RUN)
    governing = checks.get("governing_check", {})
    overall = checks.get("overall_status_label", BEAM_STATUS_NOT_RUN)

    if overall == BEAM_STATUS_FAIL:
        if checks.get("strength_status") == BEAM_STATUS_FAIL:
            headline = f"Beam is not adequate for strength. Governing family: {governing.get('check', 'Strength')}."
        elif service_row.get("status") == BEAM_STATUS_FAIL:
            headline = f"Beam is not adequate for serviceability. Governing family: {governing.get('check', 'Serviceability')}."
        else:
            headline = "Beam is not adequate and requires redesign."
    elif overall == "PASS WITH WARNINGS":
        headline = "Strength checks pass, but detailing/compliance warnings require review."
    elif overall == BEAM_STATUS_WARN:
        headline = f"Beam requires review. Governing family: {governing.get('check', 'Review item')}."
    elif overall == BEAM_STATUS_PASS:
        headline = "Beam is adequate for strength and serviceability."
    else:
        headline = "Design conclusion is not yet available."

    next_step = None
    if checks.get("strength_status") == BEAM_STATUS_FAIL:
        next_step = f"Prioritise {governing.get('check', 'strength')} redesign."
    elif service_row.get("status") in {BEAM_STATUS_FAIL, BEAM_STATUS_WARN}:
        next_step = f"Review {service_row.get('governing', 'serviceability')} first."
    elif checks.get("detailing_status") in {BEAM_STATUS_FAIL, BEAM_STATUS_WARN}:
        next_step = "Review detailing/compliance items before issue."

    return {
        "headline": headline,
        "strength": strength_label,
        "serviceability": service_label,
        "detailing": detailing_label,
        "next_step": next_step,
    }


def _priority_review_items(summary_rows: list[dict], notes: list[str], checks: dict) -> list[str]:
    priorities = []
    for check_name in ("Bending", "Shear", "Serviceability"):
        row = next((item for item in summary_rows if item.get("check") == check_name), None)
        if not row:
            continue
        status = normalize_beam_status(row.get("status"))
        if status in {BEAM_STATUS_FAIL, BEAM_STATUS_WARN}:
            priorities.append(row.get("governing") or check_name)
    if checks.get("detailing_status") in {BEAM_STATUS_FAIL, BEAM_STATUS_WARN}:
        for note in notes:
            priorities.append(note.split(":")[0].strip() or "Detailing/compliance review")
    deduped = []
    for item in priorities:
        if item and item not in deduped:
            deduped.append(item)
    return deduped[:5]


def _active_beam_current_statuses(summary: dict, row_groups: dict | None = None) -> dict:
    phi_mu = _safe_float(st.session_state.get("phi_Mu_cap"))
    mu_util = _safe_float(st.session_state.get("Mu_utilisation"))
    phi_vu = _safe_float(st.session_state.get("phi_Vu_cap"))
    vu_util = _safe_float(st.session_state.get("Vu_utilisation"))
    crack_util = _safe_float(st.session_state.get("crack_utilisation"))
    defl_util = _safe_float(st.session_state.get("deflection_utilisation"))
    sigma_allow = _safe_float(st.session_state.get("sigma_allow_table"))
    wmax_char = _safe_float(st.session_state.get("wmax_char"))
    defl_limit = _safe_float(st.session_state.get("deflection_limit_mm"))

    bending_status = summary.get("bending_status", BEAM_STATUS_NOT_RUN)
    shear_status = summary.get("shear_status", BEAM_STATUS_NOT_RUN)
    crack_status = summary.get("crack_status", BEAM_STATUS_NOT_RUN)
    deflection_status = summary.get("deflection_status", BEAM_STATUS_NOT_RUN)

    if (phi_mu is not None and phi_mu > 0.0) or (mu_util is not None and mu_util >= 0.0):
        bending_status = normalize_beam_status(utilisation=mu_util)
    if (phi_vu is not None and phi_vu > 0.0) or (vu_util is not None and vu_util >= 0.0):
        shear_status = normalize_beam_status(utilisation=vu_util)
    if (sigma_allow is not None and sigma_allow > 0.0) or (wmax_char is not None and wmax_char > 0.0):
        crack_pass = None
        if "passes_table" in st.session_state and "passes_w" in st.session_state:
            crack_pass = bool(st.session_state.get("passes_table")) and bool(st.session_state.get("passes_w"))
        crack_status = normalize_beam_status(utilisation=crack_util, pass_flag=crack_pass)
    if defl_limit is not None and defl_limit > 0.0:
        deflection_status = normalize_beam_status(utilisation=defl_util)

    statuses = {
        "bending_status": bending_status,
        "shear_status": shear_status,
        "crack_status": crack_status,
        "deflection_status": deflection_status,
    }
    if isinstance(row_groups, dict):
        classified = classify_beam_check_rows(
            bending_rows=row_groups.get("bending_rows"),
            shear_rows=row_groups.get("shear_rows"),
            crack_rows=row_groups.get("crack_rows"),
            deflection_rows=row_groups.get("deflection_rows"),
        )
        statuses["strength_status"] = classified["strength_status"]
        statuses["detailing_status"] = classified["detailing_status"]
        statuses["notes"] = classified.get("notes", [])
        statuses["overall_status"] = classified["overall_status"]
    else:
        statuses["strength_status"] = summary.get("strength_status", BEAM_STATUS_NOT_RUN)
        statuses["detailing_status"] = summary.get("detailing_status", BEAM_STATUS_NOT_RUN)
        statuses["notes"] = []
        statuses["overall_status"] = get_beam_overall_status(
            {
                **statuses,
                "strength_status": statuses["strength_status"],
                "detailing_status": statuses["detailing_status"],
            }
        )
    return statuses


def _build_serviceability_summary(check_summaries: dict, statuses: dict, results: dict) -> dict:
    crack = check_summaries.get("crack", {})
    deflection = check_summaries.get("deflection", {})
    crack_util = _worst_utilisation(crack.get("util"), results.get("crack_utilisation"))
    deflection_util = _worst_utilisation(deflection.get("util"), results.get("deflection_utilisation"))
    serviceability_status = _serviceability_status(
        statuses.get("crack_status"),
        statuses.get("deflection_status"),
    )

    if crack_util is not None or deflection_util is not None:
        if crack_util is None:
            governing_name = "Deflection"
        elif deflection_util is None:
            governing_name = "Crack"
        elif crack_util >= deflection_util:
            governing_name = "Crack"
        else:
            governing_name = "Deflection"
    elif normalize_beam_status(statuses.get("crack_status")) != BEAM_STATUS_NOT_RUN:
        governing_name = "Crack"
    elif normalize_beam_status(statuses.get("deflection_status")) != BEAM_STATUS_NOT_RUN:
        governing_name = "Deflection"
    else:
        governing_name = "Serviceability"

    governing_row = crack if governing_name == "Crack" else deflection
    governing_util = crack_util if governing_name == "Crack" else deflection_util
    if governing_name == "Crack":
        governing_value = results.get("crack_width")
        governing_limit = results.get("crack_limit")
    elif governing_name == "Deflection":
        governing_value = results.get("deflection_total_mm")
        governing_limit = results.get("deflection_limit_mm")
    else:
        governing_value = None
        governing_limit = None

    governing_value = governing_value if governing_value is not None else governing_row.get("value")
    governing_limit = governing_limit if governing_limit is not None else governing_row.get("limit")
    return {
        "title": governing_name,
        "value": _display_value(governing_value, 3 if governing_name == "Crack" else 2),
        "limit": _display_value(governing_limit, 3 if governing_name == "Crack" else 2),
        "util": governing_util,
        "util_text": _display_value(governing_util, 3),
        "status": serviceability_status,
        "status_label": format_report_status_label(serviceability_status),
        "demand_limit_pair": f"{_display_value(governing_value, 3 if governing_name == 'Crack' else 2)} / {_display_value(governing_limit, 3 if governing_name == 'Crack' else 2)}",
        "components": {
            "crack": {
                "value": _display_value(results.get("crack_width"), 3),
                "limit": _display_value(results.get("crack_limit"), 3),
                "util": _display_value(crack_util, 3),
                "status": format_report_status_label(statuses.get("crack_status")),
            },
            "deflection": {
                "value": _display_value(results.get("deflection_total_mm"), 2),
                "limit": _display_value(results.get("deflection_limit_mm"), 2),
                "util": _display_value(deflection_util, 3),
                "status": format_report_status_label(statuses.get("deflection_status")),
            },
        },
    }


def _build_high_level_rows(check_summaries: dict, statuses: dict, results: dict) -> list[dict]:
    bending_util = _worst_utilisation(
        check_summaries.get("bending", {}).get("util"),
        results.get("Mu_utilisation"),
    )
    shear_util = _worst_utilisation(
        check_summaries.get("shear", {}).get("util"),
        results.get("Vu_utilisation"),
    )
    serviceability = _build_serviceability_summary(check_summaries, statuses, results)
    rows = [
        {
            "check": "Bending",
            "governing": check_summaries.get("bending", {}).get("title", "Bending"),
            "utilisation": bending_util,
            "utilisation_text": _display_value(bending_util, 3),
            "severity": _utilisation_severity(bending_util),
            "status": statuses.get("bending_status", BEAM_STATUS_NOT_RUN),
            "status_label": format_report_status_label(statuses.get("bending_status")),
            "governing_reason": f"governed by {check_summaries.get('bending', {}).get('title', 'bending')}",
            "demand_limit_pair": (
                f"{_display_value(results.get('Mu_star'))} / {_display_value(results.get('phi_Mu_cap'))} kNm"
            ),
            "required_label": "Required Mu*",
            "required_value": f"{_display_value(results.get('Mu_star'), 2)} kNm",
            "provided_label": "Provided φMu",
            "provided_value": f"{_display_value(results.get('phi_Mu_cap'), 2)} kNm",
            "result": _display_value(results.get("phi_Mu_cap")),
            "value": _display_value(check_summaries.get("bending", {}).get("value")),
            "limit": _display_value(check_summaries.get("bending", {}).get("limit")),
        },
        {
            "check": "Shear",
            "governing": check_summaries.get("shear", {}).get("title", "Shear"),
            "utilisation": shear_util,
            "utilisation_text": _display_value(shear_util, 3),
            "severity": _utilisation_severity(shear_util),
            "status": statuses.get("shear_status", BEAM_STATUS_NOT_RUN),
            "status_label": format_report_status_label(statuses.get("shear_status")),
            "governing_reason": f"governed by {check_summaries.get('shear', {}).get('title', 'shear')}",
            "demand_limit_pair": (
                f"{_display_value(results.get('Vu_star'))} / {_display_value(results.get('phi_Vu_cap'))} kN"
            ),
            "required_label": "Required V*",
            "required_value": f"{_display_value(results.get('Vu_star'), 2)} kN",
            "provided_label": "Provided φVu",
            "provided_value": f"{_display_value(results.get('phi_Vu_cap'), 2)} kN",
            "result": _display_value(results.get("phi_Vu_cap")),
            "value": _display_value(check_summaries.get("shear", {}).get("value")),
            "limit": _display_value(check_summaries.get("shear", {}).get("limit")),
        },
        {
            "check": "Serviceability",
            "governing": serviceability.get("title", "Serviceability"),
            "utilisation": serviceability.get("util"),
            "utilisation_text": serviceability.get("util_text", "-"),
            "severity": _utilisation_severity(serviceability.get("util")),
            "status": serviceability.get("status", BEAM_STATUS_NOT_RUN),
            "status_label": serviceability.get("status_label", BEAM_STATUS_NOT_RUN),
            "governing_reason": f"governed by {serviceability.get('title', 'serviceability')}",
            "demand_limit_pair": serviceability.get("demand_limit_pair", "-"),
            "required_label": "Allowable",
            "required_value": serviceability.get("limit", "-"),
            "provided_label": "Provided",
            "provided_value": serviceability.get("value", "-"),
            "result": serviceability.get("value", "-"),
            "value": serviceability.get("value", "-"),
            "limit": serviceability.get("limit", "-"),
            "components": serviceability.get("components", {}),
        },
    ]
    return rows


def _governing_high_level_check(summary_rows: list[dict]) -> dict:
    usable = [row for row in (summary_rows or []) if _safe_float(row.get("utilisation")) is not None]
    if usable:
        governing = max(usable, key=lambda row: _safe_float(row.get("utilisation")) or -1.0)
        util = _safe_float(governing.get("utilisation"))
        return {
            "check": governing.get("check", "-"),
            "utilisation": util,
            "utilisation_text": _display_value(util, 3),
            "status": governing.get("status", BEAM_STATUS_NOT_RUN),
            "status_label": governing.get("status_label", BEAM_STATUS_NOT_RUN),
        }

    fallback = None
    for row in summary_rows or []:
        if normalize_beam_status(row.get("status")) != BEAM_STATUS_NOT_RUN:
            if fallback is None or _status_rank(row.get("status")) > _status_rank(fallback.get("status")):
                fallback = row
    if fallback:
        return {
            "check": fallback.get("check", "-"),
            "utilisation": None,
            "utilisation_text": "-",
            "status": fallback.get("status", BEAM_STATUS_NOT_RUN),
            "status_label": fallback.get("status_label", BEAM_STATUS_NOT_RUN),
        }
    return {
        "check": "Not available",
        "utilisation": None,
        "utilisation_text": "-",
        "status": BEAM_STATUS_NOT_RUN,
        "status_label": BEAM_STATUS_NOT_RUN,
    }


def _report_notes(statuses: dict) -> list[str]:
    notes = []
    for note in statuses.get("notes", []) or []:
        text = str(note).strip()
        if text and text not in notes:
            notes.append(text)
    if not notes and normalize_beam_status(statuses.get("overall_status")) == BEAM_STATUS_NOT_RUN:
        notes.append("Results are not yet available for the active beam.")
    return notes


def build_active_beam_report_data(
    *,
    report_mode: str = "standard",
    row_groups: dict | None = None,
) -> dict:
    """
    Build the active-beam report payload from current state only.
    No calculations are run here.
    """
    report_mode = "detailed" if str(report_mode).strip().lower() == "detailed" else "standard"
    record = get_active_beam_record() or {}
    summary = get_active_beam_summary()
    row_groups = row_groups if isinstance(row_groups, dict) else {}
    statuses = _active_beam_current_statuses(summary, row_groups=row_groups)
    generated_at = datetime.utcnow().isoformat(timespec="seconds")

    beam_id = record.get("beam_id") or st.session_state.get("active_beam_id") or "beam"
    beam_label = record.get("beam_label") or beam_id
    action_source = _action_source_context()
    include_beam_elevation = action_source.get("action_source_mode") == "design_page"

    bending_rows = [_normalise_report_row(row) for row in (row_groups.get("bending_rows") or [])]
    shear_rows = [_normalise_report_row(row) for row in (row_groups.get("shear_rows") or [])]
    crack_rows = [_normalise_report_row(row) for row in (row_groups.get("crack_rows") or [])]
    deflection_rows = [_normalise_report_row(row) for row in (row_groups.get("deflection_rows") or [])]

    results = {
        "Mu_star": _safe_float(st.session_state.get("Mu_star")),
        "phi_Mu_cap": _safe_float(st.session_state.get("phi_Mu_cap")),
        "Mu_utilisation": _safe_float(st.session_state.get("Mu_utilisation")),
        "Vu_star": _safe_float(st.session_state.get("Vu_star")),
        "phi_Vu_cap": _safe_float(st.session_state.get("phi_Vu_cap")),
        "Vu_utilisation": _safe_float(st.session_state.get("Vu_utilisation")),
        "crack_width": _safe_float(st.session_state.get("crack_width")),
        "crack_limit": _safe_float(st.session_state.get("wmax_char")),
        "crack_utilisation": _safe_float(st.session_state.get("crack_utilisation")),
        "deflection_total_mm": _safe_float(st.session_state.get("deflection_total_mm")),
        "deflection_limit_mm": _safe_float(st.session_state.get("deflection_limit_mm")),
        "deflection_utilisation": _safe_float(st.session_state.get("deflection_utilisation")),
    }

    check_summaries = {
        "bending": _pick_primary_check(bending_rows, "Bending"),
        "shear": _pick_primary_check(shear_rows, "Shear"),
        "crack": _pick_primary_check(crack_rows, "Crack"),
        "deflection": _pick_primary_check(deflection_rows, "Deflection"),
    }
    summary_rows = _build_high_level_rows(check_summaries, statuses, results)
    governing_check = _governing_high_level_check(summary_rows)
    notes = _report_notes(statuses)
    analysis_context = _build_analysis_context(action_source)
    display_name = _beam_display_name(beam_id, beam_label)
    metadata = _report_metadata(generated_at)
    branding = _report_branding()
    checks_payload = {
        "overall_status": statuses["overall_status"],
        "overall_status_label": format_report_status_label(
            statuses["overall_status"],
            strength_status=statuses["strength_status"],
            detailing_status=statuses["detailing_status"],
        ),
        "strength_status": statuses["strength_status"],
        "strength_status_label": format_report_status_label(statuses["strength_status"]),
        "detailing_status": statuses["detailing_status"],
        "detailing_status_label": format_report_status_label(statuses["detailing_status"]),
        "bending_status": statuses["bending_status"],
        "shear_status": statuses["shear_status"],
        "crack_status": statuses["crack_status"],
        "deflection_status": statuses["deflection_status"],
        "summaries": {
            **check_summaries,
            "serviceability": _build_serviceability_summary(check_summaries, statuses, results),
        },
        "summary_rows": summary_rows,
        "governing_check": governing_check,
        "details": {
            "bending": bending_rows,
            "shear": shear_rows,
            "crack": crack_rows,
            "deflection": deflection_rows,
        }
        if report_mode == "detailed"
        else {},
    }
    design_conclusion = _design_conclusion(checks_payload, summary_rows)
    priority_items = _priority_review_items(summary_rows, notes, checks_payload)

    return {
        "beam_info": {
            "beam_id": beam_id,
            "beam_label": beam_label,
            "display_name": display_name,
            "active_beam_id": st.session_state.get("active_beam_id"),
            "design_code": "AS 3600",
            "report_mode": report_mode,
            "action_source_mode": action_source.get("action_source_mode"),
            "action_source_label": action_source.get("action_source_label"),
        },
        "metadata": metadata,
        "branding": branding,
        "inputs": {
            "geometry": _geometry_group(),
            "materials": _materials_group(),
            "reinforcement": _reinforcement_group(),
        },
        "actions": {
            "uls": _uls_actions_group(),
            "sls": _sls_actions_group(),
        },
        "design_basis": _design_basis_rows(
            {
                "design_code": "AS 3600",
            },
            action_source,
            analysis_context,
        ),
        "analysis_context": analysis_context,
        "results": results,
        "checks": checks_payload,
        "design_conclusion": design_conclusion,
        "status": {
            "report_ready": normalize_beam_status(statuses["overall_status"]) != BEAM_STATUS_NOT_RUN,
            "report_ready_label": _report_ready_label(statuses["overall_status"]),
            "last_checked_at": summary.get("last_checked_at"),
        },
        "diagrams": {
            "include_section_diagram": True,
            "include_beam_elevation": include_beam_elevation,
        },
        "diagram_refs": {
            "section_2d": "inputs_page.section_summary_2d",
            "beam_elevation": "inputs_page.beam_3d_preview" if include_beam_elevation else None,
        },
        "notes": notes,
        "priority_items": priority_items,
        "generated_at": generated_at,
    }


def build_active_beam_report_data_from_state(report_mode: str = "standard") -> dict:
    from bending_checks_helpers import build_bending_check_rows_from_state
    from crack_checks_helpers import build_crack_check_rows_from_state
    from deflection_checks_helpers import build_deflection_check_rows_from_state
    from shear_checks_helpers import build_shear_check_rows_from_state

    bend_pack = build_bending_check_rows_from_state(st.session_state)
    shear_pack = build_shear_check_rows_from_state(st.session_state)
    crack_pack = build_crack_check_rows_from_state(st.session_state)
    deflection_pack = build_deflection_check_rows_from_state(st.session_state)

    return build_active_beam_report_data(
        report_mode=report_mode,
        row_groups={
            "bending_rows": [_normalise_report_row(row) for row in (bend_pack or {}).get("rows") or []],
            "shear_rows": [_normalise_report_row(row) for row in (shear_pack or {}).get("rows") or []],
            "crack_rows": [_normalise_report_row(row) for row in (crack_pack or {}).get("rows") or []],
            "deflection_rows": [_normalise_report_row(row) for row in (deflection_pack or {}).get("rows") or []],
        },
    )


def build_beam_schedule_export_rows() -> list[dict]:
    """
    Build export rows for all beams from stored params + cached summaries only.
    No live recalculation is performed.
    """
    rows = []
    for item in build_beam_schedule_rows():
        rows.append(
            {
                "beam_id": item.get("beam_id"),
                "beam_label": item.get("beam_label"),
                "active": bool(item.get("active")),
                "sec_shape": item.get("sec_shape"),
                "b": item.get("b"),
                "bf": item.get("bf"),
                "tf": item.get("tf"),
                "bw": item.get("bw"),
                "tw": item.get("tw"),
                "D": item.get("D"),
                "L": item.get("L"),
                "cover_top": item.get("cover_top"),
                "cover_bot": item.get("cover_bot"),
                "cover_side": item.get("cover_side"),
                "fc": item.get("fc"),
                "fsy": item.get("fsy"),
                "bottom_reo": item.get("bottom_reo"),
                "top_reo": item.get("top_reo"),
                "bot1_count": item.get("bot1_count"),
                "db_bot_1": item.get("db_bot_1"),
                "top1_count": item.get("top1_count"),
                "db_top_1": item.get("db_top_1"),
                "lig_d": item.get("lig_d"),
                "lig_legs": item.get("lig_legs"),
                "s_lig": item.get("s_lig"),
                "overall_status": normalize_beam_status(item.get("overall_status")),
                "strength_status": normalize_beam_status(item.get("strength_status")),
                "detailing_status": normalize_beam_status(item.get("detailing_status")),
                "bending_status": normalize_beam_status(item.get("bending_status")),
                "shear_status": normalize_beam_status(item.get("shear_status")),
                "crack_status": normalize_beam_status(item.get("crack_status")),
                "deflection_status": normalize_beam_status(item.get("deflection_status")),
                "last_checked_at": item.get("last_checked_at"),
            }
        )
    return rows


def format_active_beam_report_markdown(report_data: dict) -> str:
    beam = report_data.get("beam_info", {})
    metadata = report_data.get("metadata", {})
    branding = report_data.get("branding", {})
    checks = report_data.get("checks", {})
    inputs = report_data.get("inputs", {})
    actions = report_data.get("actions", {})
    design_basis = report_data.get("design_basis", {})
    analysis_context = report_data.get("analysis_context", {})
    design_conclusion = report_data.get("design_conclusion", {})
    summaries = checks.get("summary_rows", [])
    governing = checks.get("governing_check", {})
    notes = report_data.get("notes", []) or []
    priority_items = report_data.get("priority_items", []) or []
    report_mode = beam.get("report_mode", "standard")
    serviceability = (checks.get("summaries") or {}).get("serviceability", {})

    lines = [
        "# StructuralBase",
        "",
        "## Beam Design Report",
        "",
        f"Beam: {_display_value(beam.get('display_name', beam.get('beam_label')))}",
        f"Design code: {_display_value(beam.get('design_code'))}",
        f"Generated: {_display_value(report_data.get('generated_at'))}",
        f"Revision: {_display_value(metadata.get('revision_label'))}",
        "",
        "## Project Information",
    ]
    if branding.get("company_name"):
        lines.append(f"- Company: {branding.get('company_name')}")
    for label, value in (
        ("Project", metadata.get("project_name")),
        ("Client", metadata.get("client_name")),
        ("Engineer", metadata.get("engineer_name")),
        ("Date", metadata.get("date")),
        ("Revision", metadata.get("revision_label")),
    ):
        if value:
            lines.append(f"- {label}: {value}")

    lines.extend(
        [
            "",
            "## Revision History",
            "| Rev | Date | Description |",
            "| --- | --- | --- |",
        ]
    )
    for row in metadata.get("revision_history", []) or []:
        lines.append(
            f"| {row.get('rev', '-')} | {row.get('date', '-')} | {row.get('description', '-')} |"
        )

    lines.extend(
        [
            "",
            "## Governing Summary",
            f"- Overall status: {_display_value(checks.get('overall_status_label'))}",
            f"- Strength status: {_display_value(checks.get('strength_status_label'))}",
            f"- Detailing status: {_display_value(checks.get('detailing_status_label'))}",
            "",
            "## Design Conclusion",
            f"- {_display_value(design_conclusion.get('headline'))}",
            f"- Strength / ULS: {_display_value(design_conclusion.get('strength'))}",
            f"- Serviceability / SLS: {_display_value(design_conclusion.get('serviceability'))}",
            f"- Detailing / Compliance: {_display_value(design_conclusion.get('detailing'))}",
            "",
            "## Summary Table",
            "| Check | Utilisation | Status |",
            "| --- | ---: | --- |",
        ]
    )
    for row in summaries:
        lines.append(
            f"| {row.get('check', '-')} | {row.get('utilisation_text', '-')} | {row.get('status_label', '-')} |"
        )

    lines.extend(
        [
            "",
            "## Governing Note",
            f"Governing check: {governing.get('check', '-')} (utilisation = {governing.get('utilisation_text', '-')})",
            f"Reason: {_display_value(next((row.get('governing_reason') for row in summaries if row.get('check') == governing.get('check')), '-'))}",
            "",
            "## Design Basis",
            "| Item | Value |",
            "| --- | --- |",
        ]
    )
    for key, value in (design_basis or {}).items():
        lines.append(f"| {key} | {value} |")
    lines.extend(
        [
            "",
            "## Key Inputs",
        ]
    )
    for section_title in ("geometry", "materials", "reinforcement"):
        group = inputs.get(section_title, {})
        lines.extend(
            [
                f"### {section_title.title()}",
                "| Item | Value |",
                "| --- | --- |",
            ]
        )
        for key, value in (group or {}).items():
            lines.append(f"| {key} | {value} |")
        lines.append("")

    lines.extend(
        [
            "## Design Actions",
            "### ULS Design Actions",
            "| Item | Value |",
            "| --- | --- |",
        ]
    )
    for key, value in (actions.get("uls") or {}).items():
        lines.append(f"| {key} | {value} |")
    lines.extend(
        [
            "",
            "### SLS Design Actions",
            "| Item | Value |",
            "| --- | --- |",
        ]
    )
    for key, value in (actions.get("sls") or {}).items():
        lines.append(f"| {key} | {value} |")
    lines.append("")

    lines.extend(
        [
            "## Analysis Context",
            "| Item | Value |",
            "| --- | --- |",
            f"| Action source | {analysis_context.get('action_source_label', 'Not clearly identified')} |",
        ]
    )
    if analysis_context.get("action_source_mode") == "design_page":
        for key, value in (
            ("Support condition", analysis_context.get("support_condition")),
            ("Span", analysis_context.get("span")),
            ("Total beam length", analysis_context.get("total_beam_length")),
            ("Loading condition", analysis_context.get("loading_condition")),
            ("Active load combination", analysis_context.get("load_combination_label")),
            ("Section mode", analysis_context.get("section_mode")),
            ("Section location", analysis_context.get("section_location")),
            ("Source basis", analysis_context.get("source_basis")),
            ("Source page", analysis_context.get("plot_source_page")),
        ):
            lines.append(f"| {key} | {_display_value(value)} |")
        load_summary = analysis_context.get("load_summary") or []
        if load_summary:
            lines.extend(["", "### Loads on Beam", "| Load | Value |", "| --- | --- |"])
            for row in load_summary:
                lines.append(f"| {row.get('Load', '-')} | {row.get('Value', '-')} |")
    lines.append("")

    lines.extend(
        [
            "## Essential Diagrams",
            "- Cross-section and reinforcement diagram included in PDF output.",
        ]
    )
    if (report_data.get("diagrams") or {}).get("include_beam_elevation"):
        lines.append("- Beam elevation included because beam actions come from internal beam analysis.")
    lines.append("")

    lines.extend(
        [
            "## Key Results",
            "| Check | Governing result | Required / Allowable | Provided | Utilisation | Severity | Status |",
            "| --- | --- | --- | --- | ---: | --- | --- |",
        ]
    )
    for row in summaries:
        lines.append(
            f"| {row.get('check', '-')} | {row.get('governing', '-')} | {row.get('required_label', 'Required')}: {row.get('required_value', '-')} | {row.get('provided_label', 'Provided')}: {row.get('provided_value', '-')} | {row.get('utilisation_text', '-')} | {row.get('severity', '-')} | {row.get('status_label', '-')} |"
        )
    if serviceability.get("components"):
        lines.extend(
            [
                "",
                f"- Crack: Applied design action w = {serviceability['components']['crack']['value']} mm; Calculated capacity w′max = {serviceability['components']['crack']['limit']} mm; Utilisation = {serviceability['components']['crack']['util']} ({serviceability['components']['crack']['status']})",
                f"- Deflection: Applied design action δ = {serviceability['components']['deflection']['value']} mm; Calculated capacity δlim = {serviceability['components']['deflection']['limit']} mm; Utilisation = {serviceability['components']['deflection']['util']} ({serviceability['components']['deflection']['status']})",
            ]
        )

    if priority_items:
        lines.extend(["", "## Priority / Review Items"])
        for idx, item in enumerate(priority_items, start=1):
            lines.append(f"{idx}. {item}")

    if notes:
        lines.extend(["", "## Notes / Warnings"])
        lines.extend([f"- {note}" for note in notes])

    if report_mode == "detailed":
        lines.extend(["", "\\newpage", "", "## Detailed Check Appendix"])
        for section_name, rows in (checks.get("details") or {}).items():
            basis_note = _detail_action_basis(section_name, actions)
            lines.extend([f"### {section_name.title()}"])
            if basis_note:
                lines.append(f"- {basis_note}")
            lines.extend(
                [
                    "| Check | Calculated capacity | Applied design action | Utilisation | Status |",
                    "| --- | --- | --- | ---: | --- |",
                ]
            )
            if not rows:
                lines.append("| None | - | - | - | NOT_RUN |")
            else:
                for row in rows:
                    status_label = format_report_status_label(row.get("status"))
                    title = _format_detail_title(row.get("title"), row.get("route_page", section_name))
                    cap_cell = row.get("capacity") or row.get("value", "-")
                    act_cell = _format_detail_limit(
                        row.get("action") or row.get("limit"),
                        row.get("title"),
                        row.get("route_page", section_name),
                    )
                    lines.append(
                        f"| {title} | {cap_cell} | {act_cell} | {row.get('util', '-')} | {status_label} |"
                    )
            lines.append("")

    lines.extend(
        [
            "",
            "## Disclaimer",
            metadata.get("disclaimer", ""),
            "",
            "## Sign-Off",
            f"- Prepared by: {metadata.get('signature_block', {}).get('prepared_by') or '___________'}",
            f"- Checked by: {metadata.get('signature_block', {}).get('checked_by') or '___________'}",
            "- Signature: ___________",
            "- Date: ___________",
        ]
    )

    return "\n".join(lines).strip() + "\n"


def _status_fill_color(colors_module, label: str):
    if label == BEAM_STATUS_FAIL:
        return colors_module.HexColor("#f8d0d0")
    if label in {"PASS WITH WARNINGS", BEAM_STATUS_WARN}:
        return colors_module.HexColor("#fff3cd")
    if label == BEAM_STATUS_PASS:
        return colors_module.HexColor("#d5f5d5")
    if label == "INFO":
        return colors_module.HexColor("#dbeafe")
    return colors_module.HexColor("#f1f3f5")


def _status_text_color(colors_module, label: str):
    if label == BEAM_STATUS_FAIL:
        return colors_module.HexColor("#721c24")
    if label in {"PASS WITH WARNINGS", BEAM_STATUS_WARN}:
        return colors_module.HexColor("#856404")
    if label == BEAM_STATUS_PASS:
        return colors_module.HexColor("#155724")
    if label == "INFO":
        return colors_module.HexColor("#1d4ed8")
    return colors_module.HexColor("#495057")


def _df_from_group(group: dict) -> pd.DataFrame:
    return pd.DataFrame(
        [{"Item": key, "Value": value} for key, value in (group or {}).items()]
    )


def render_active_beam_report_preview(
    report_data: dict,
    *,
    section_figure_factory=None,
    beam_figure_factory=None,
):
    beam = report_data.get("beam_info", {})
    metadata = report_data.get("metadata", {})
    branding = report_data.get("branding", {})
    checks = report_data.get("checks", {})
    inputs = report_data.get("inputs", {})
    actions = report_data.get("actions", {})
    analysis_context = report_data.get("analysis_context", {})
    design_basis = report_data.get("design_basis", {})
    design_conclusion = report_data.get("design_conclusion", {})
    summary_rows = checks.get("summary_rows", [])
    governing = checks.get("governing_check", {})
    notes = report_data.get("notes", []) or []
    priority_items = report_data.get("priority_items", []) or []
    serviceability = (checks.get("summaries") or {}).get("serviceability", {})
    detailed_rows = checks.get("details", {}) if beam.get("report_mode") == "detailed" else {}

    st.markdown(
        """
        <style>
        .beam-report-card {
            border: 1px solid rgba(31,60,136,0.10);
            border-radius: 10px;
            padding: 0.85rem 1rem;
            background: #ffffff;
            margin-bottom: 0.9rem;
        }
        .beam-report-section {
            margin-top: 1rem;
        }
        .beam-report-kicker {
            color: #6c757d;
            font-size: 0.85rem;
            margin-bottom: 0.2rem;
        }
        .beam-report-title {
            color: #1f3c88;
            font-weight: 700;
            font-size: 1.2rem;
            margin-bottom: 0.15rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    header_col_brand, header_col_title = st.columns([1.0, 3.0], gap="medium")
    with header_col_brand:
        if branding.get("logo_file_present") and branding.get("logo_image_data"):
            st.image(branding.get("logo_image_data"), width=120)
        elif branding.get("company_name"):
            st.markdown(f"**{branding.get('company_name')}**")
        else:
            st.markdown("**StructuralBase**")
    with header_col_title:
        st.markdown(
            f"""
            <div class="beam-report-card">
                <div class="beam-report-kicker">StructuralBase</div>
                <div class="beam-report-title">Beam Design Report</div>
                <div>{beam.get("display_name", beam.get("beam_label", beam.get("beam_id", "-")))} | {beam.get("design_code", "AS 3600")}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    project_rows = {
        key: value
        for key, value in {
            "Project": metadata.get("project_name"),
            "Client": metadata.get("client_name"),
            "Engineer": metadata.get("engineer_name"),
            "Date": metadata.get("date"),
            "Revision": metadata.get("revision_label"),
        }.items()
        if value
    }
    if project_rows:
        st.markdown("#### Project Information")
        st.dataframe(_df_from_group(project_rows), hide_index=True, use_container_width=True)

    summary_cols = st.columns(3)
    summary_cols[0].markdown(f"**Overall**\n\n{format_report_status_badge(checks.get('overall_status'), strength_status=checks.get('strength_status'), detailing_status=checks.get('detailing_status'))}")
    summary_cols[1].markdown(f"**Strength**\n\n{format_report_status_badge(checks.get('strength_status'))}")
    summary_cols[2].markdown(f"**Detailing**\n\n{format_report_status_badge(checks.get('detailing_status'))}")

    st.caption(
        f"Governing check: {governing.get('check', '-')} (utilisation = {governing.get('utilisation_text', '-')})"
    )
    st.markdown('<div class="beam-report-section"></div>', unsafe_allow_html=True)
    st.markdown("#### Design Conclusion")
    st.write(design_conclusion.get("headline", "-"))

    summary_df = pd.DataFrame(
        [
            {
                "Check": row.get("check"),
                "Utilisation": row.get("utilisation_text"),
                "Severity": row.get("severity"),
                "Status": row.get("status_label"),
            }
            for row in summary_rows
        ]
    )
    st.dataframe(summary_df, hide_index=True, use_container_width=True)

    input_col_1, input_col_2 = st.columns(2, gap="large")
    with input_col_1:
        st.markdown("#### Geometry")
        st.dataframe(_df_from_group(inputs.get("geometry", {})), hide_index=True, use_container_width=True)
        st.markdown("#### Materials")
        st.dataframe(_df_from_group(inputs.get("materials", {})), hide_index=True, use_container_width=True)
    with input_col_2:
        st.markdown("#### Reinforcement")
        st.dataframe(_df_from_group(inputs.get("reinforcement", {})), hide_index=True, use_container_width=True)
        st.markdown("#### ULS Design Actions")
        st.dataframe(_df_from_group(actions.get("uls", {})), hide_index=True, use_container_width=True)
        st.markdown("#### SLS Design Actions")
        st.dataframe(_df_from_group(actions.get("sls", {})), hide_index=True, use_container_width=True)
        st.markdown("#### Design Basis")
        st.dataframe(_df_from_group(design_basis), hide_index=True, use_container_width=True)

    st.markdown('<div class="beam-report-section"></div>', unsafe_allow_html=True)
    st.markdown("#### Analysis Context")
    ctx_col_1, ctx_col_2, ctx_col_3 = st.columns(3, gap="large")
    context_groups = _analysis_context_groups(analysis_context)
    with ctx_col_1:
        st.markdown("##### Beam Model")
        st.dataframe(_df_from_group(context_groups.get("Beam model", {})), hide_index=True, use_container_width=True)
    with ctx_col_2:
        st.markdown("##### Loads")
        st.dataframe(_df_from_group(context_groups.get("Loads", {})), hide_index=True, use_container_width=True)
    with ctx_col_3:
        st.markdown("##### Section Extraction")
        st.dataframe(_df_from_group(context_groups.get("Section extraction", {})), hide_index=True, use_container_width=True)
    load_summary = analysis_context.get("load_summary") or []
    if load_summary:
        st.markdown("#### Loads On Beam")
        st.dataframe(pd.DataFrame(load_summary), hide_index=True, use_container_width=True)

    st.markdown('<div class="beam-report-section"></div>', unsafe_allow_html=True)
    st.markdown("#### Essential Diagrams")
    st.markdown("##### Section Diagram")
    try:
        render_plotly_diagram(
            section_figure_factory(),
            key="report_section_diagram",
            title="Report section diagram",
            config={"displayModeBar": False},
        )
    except Exception as exc:
        st.info(f"Section diagram unavailable: {exc}")
    if (report_data.get("diagrams") or {}).get("include_beam_elevation"):
        st.markdown("")
        st.markdown("##### Beam Elevation")
        try:
            render_plotly_diagram(
                beam_figure_factory(),
                key="report_beam_elevation_diagram",
                title="Report beam elevation",
                config={"displayModeBar": False},
            )
        except Exception as exc:
            st.info(f"Beam elevation unavailable: {exc}")

    key_results_df = pd.DataFrame(
        [
            {
                "Check": row.get("check"),
                "Governing": row.get("governing"),
                "Required / Allowable": f"{row.get('required_label', 'Required')}: {row.get('required_value', '-')}",
                "Provided": f"{row.get('provided_label', 'Provided')}: {row.get('provided_value', '-')}",
                "Utilisation": row.get("utilisation_text"),
                "Severity": row.get("severity"),
                "Status": row.get("status_label"),
            }
            for row in summary_rows
        ]
    )
    st.markdown('<div class="beam-report-section"></div>', unsafe_allow_html=True)
    st.markdown("#### Key Results")
    st.dataframe(key_results_df, hide_index=True, use_container_width=True)
    if serviceability.get("components"):
        st.caption(
            "Serviceability: "
            f"Crack w = {serviceability['components']['crack']['value']} mm (action); w′max = {serviceability['components']['crack']['limit']} mm (capacity) "
            f"({serviceability['components']['crack']['status']}), "
            f"Deflection δ = {serviceability['components']['deflection']['value']} mm (action); δlim = {serviceability['components']['deflection']['limit']} mm (capacity) "
            f"({serviceability['components']['deflection']['status']})"
        )

    if priority_items:
        st.markdown("#### Priority / Review Items")
        for idx, item in enumerate(priority_items, start=1):
            st.write(f"{idx}. {item}")

    if notes:
        st.markdown("#### Notes / Warnings")
        for note in notes:
            st.write(f"- {note}")

    if detailed_rows:
        st.markdown("---")
        st.markdown("## Detailed Check Appendix")
        for section_name, rows in detailed_rows.items():
            st.markdown(f"#### {section_name.title()}")
            basis_note = _detail_action_basis(section_name, actions)
            if basis_note:
                st.caption(basis_note)
            detail_df = pd.DataFrame(
                [
                    {
                        "Check": _format_detail_title(row.get("title"), row.get("route_page", section_name)),
                        "Calculated capacity": row.get("capacity") or row.get("value", "-"),
                        "Applied design action": _format_detail_limit(
                            row.get("action") or row.get("limit"),
                            row.get("title"),
                            row.get("route_page", section_name),
                        ),
                        "Utilisation": row.get("util", "-"),
                        "Status": format_report_status_label(row.get("status")),
                    }
                    for row in (rows or [])
                ]
            )
            if detail_df.empty:
                detail_df = pd.DataFrame(
                    [
                        {
                            "Check": "None",
                            "Calculated capacity": "-",
                            "Applied design action": "-",
                            "Utilisation": "-",
                            "Status": "NOT_RUN",
                        }
                    ]
                )
            st.dataframe(detail_df, hide_index=True, use_container_width=True)


def build_active_beam_report_pdf(
    report_data: dict,
    *,
    section_figure_factory=None,
    beam_figure_factory=None,
) -> bytes:
    """
    Build the active beam PDF using the refined final report structure.
    """
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.lib.utils import ImageReader
        from reportlab.pdfgen import canvas as pdf_canvas
        from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError as exc:
        raise ImportError(
            "reportlab is not installed. Please install it with: pip install reportlab"
        ) from exc

    from reporting.fig_export import export_box_diagram_png

    beam = report_data.get("beam_info", {})
    metadata = report_data.get("metadata", {})
    branding = report_data.get("branding", {})
    checks = report_data.get("checks", {})
    inputs = report_data.get("inputs", {})
    actions = report_data.get("actions", {})
    analysis_context = report_data.get("analysis_context", {})
    design_basis = report_data.get("design_basis", {})
    design_conclusion = report_data.get("design_conclusion", {})
    summary_rows = checks.get("summary_rows", [])
    governing = checks.get("governing_check", {})
    notes = report_data.get("notes", []) or []
    priority_items = report_data.get("priority_items", []) or []
    serviceability = (checks.get("summaries") or {}).get("serviceability", {})
    detailed_rows = checks.get("details", {}) if beam.get("report_mode") == "detailed" else {}
    project_name = (
        metadata.get("project_name")
        or st.session_state.get("active_project_name")
        or st.session_state.get("project_name")
        or "Untitled Project"
    )
    revision = metadata.get("revision_label") or f"Rev {st.session_state.get('report_revision', 1)}"
    display_name = beam.get("display_name", beam.get("beam_label", beam.get("beam_id", "-")))
    watermark_text = metadata.get("watermark_text", "")
    logo_bytes = branding.get("logo_image_data")
    company_name = str(branding.get("company_name") or "").strip()

    def _branding_box(image_bytes, max_width_mm: float, max_height_mm: float):
        if not image_bytes:
            return None
        try:
            reader = ImageReader(io.BytesIO(image_bytes))
            img_w, img_h = reader.getSize()
            if not img_w or not img_h:
                return None
            scale = min((max_width_mm * mm) / img_w, (max_height_mm * mm) / img_h, 1.0)
            return reader, img_w * scale, img_h * scale
        except Exception:
            return None

    class NumberedCanvas(pdf_canvas.Canvas):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._saved_page_states = []

        def showPage(self):
            self._saved_page_states.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            page_count = len(self._saved_page_states)
            for state in self._saved_page_states:
                self.__dict__.update(state)
                _draw_page_chrome(self, page_count)
                super().showPage()
            super().save()

    def _draw_page_chrome(canvas_obj, page_count: int):
        page_width, page_height = A4
        left_x = 16 * mm
        right_x = page_width - 16 * mm

        canvas_obj.saveState()
        canvas_obj.setStrokeColor(colors.HexColor("#d7dde5"))
        canvas_obj.setLineWidth(0.5)
        canvas_obj.line(left_x, page_height - 27 * mm, right_x, page_height - 27 * mm)
        canvas_obj.line(left_x, 15 * mm, right_x, 15 * mm)

        if watermark_text:
            canvas_obj.saveState()
            canvas_obj.setFillColor(colors.HexColor("#cfd8e3"))
            canvas_obj.setFont("Helvetica-Bold", 34)
            canvas_obj.translate(page_width / 2, page_height / 2)
            canvas_obj.rotate(45)
            canvas_obj.drawCentredString(0, 0, watermark_text)
            canvas_obj.restoreState()

        canvas_obj.setFillColor(colors.HexColor("#1f3c88"))
        header_logo = _branding_box(logo_bytes, 34.0, 16.0)
        text_left_x = left_x
        if header_logo:
            reader, draw_w, draw_h = header_logo
            logo_y = page_height - 21 * mm
            canvas_obj.drawImage(
                reader,
                left_x,
                logo_y,
                width=draw_w,
                height=draw_h,
                preserveAspectRatio=True,
                mask="auto",
            )
            text_left_x = left_x + draw_w + (4 * mm)

        canvas_obj.setFont("Helvetica-Bold", 9.5)
        canvas_obj.drawString(text_left_x, page_height - 12 * mm, company_name or "StructuralBase")
        canvas_obj.setFont("Helvetica-Bold", 11)
        canvas_obj.drawString(text_left_x, page_height - 17 * mm, "Beam Design Report")
        canvas_obj.setFillColor(colors.HexColor("#495057"))
        canvas_obj.setFont("Helvetica", 8.5)
        canvas_obj.drawString(
            text_left_x,
            page_height - 22 * mm,
            f"StructuralBase | {display_name} | {beam.get('design_code', 'AS 3600')}",
        )

        canvas_obj.setFont("Helvetica", 8.5)
        canvas_obj.drawRightString(right_x, page_height - 12 * mm, f"Date: {metadata.get('date') or str(report_data.get('generated_at', '-')).replace('T', ' ')}")
        canvas_obj.drawRightString(right_x, page_height - 17 * mm, f"Project: {project_name}")
        canvas_obj.drawRightString(right_x, page_height - 22 * mm, f"Revision: {revision}")

        canvas_obj.setFillColor(colors.HexColor("#6c757d"))
        canvas_obj.setFont("Helvetica", 7.5)
        canvas_obj.drawString(left_x, 9 * mm, "Generated by StructuralBase | AS 3600:2018")
        canvas_obj.drawRightString(right_x, 9 * mm, f"Page {canvas_obj._pageNumber} of {page_count}")
        canvas_obj.restoreState()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=32 * mm,
        bottomMargin=22 * mm,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Heading1"],
        fontSize=19,
        textColor=colors.HexColor("#1f3c88"),
        spaceAfter=8,
    )
    heading_style = ParagraphStyle(
        "ReportHeading",
        parent=styles["Heading2"],
        fontSize=12.5,
        textColor=colors.HexColor("#2f4858"),
        fontName="Helvetica-Bold",
        spaceBefore=14,
        spaceAfter=6,
    )
    subheading_style = ParagraphStyle(
        "ReportSubheading",
        parent=styles["Heading3"],
        fontSize=10.5,
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#34495e"),
        spaceBefore=10,
        spaceAfter=4,
    )
    cover_title_style = ParagraphStyle(
        "CoverTitle",
        parent=styles["Title"],
        fontSize=24,
        leading=28,
        alignment=1,
        textColor=colors.HexColor("#1f3c88"),
        spaceAfter=10,
    )
    cover_subtitle_style = ParagraphStyle(
        "CoverSubtitle",
        parent=styles["Heading2"],
        fontSize=16,
        alignment=1,
        textColor=colors.HexColor("#34495e"),
        spaceAfter=8,
    )
    center_meta_style = ParagraphStyle(
        "CenterMeta",
        parent=styles["Normal"],
        fontSize=10,
        alignment=1,
        textColor=colors.HexColor("#495057"),
        spaceAfter=6,
    )
    subtle_style = ParagraphStyle(
        "Subtle",
        parent=styles["Normal"],
        fontSize=9,
        textColor=colors.HexColor("#6c757d"),
        spaceAfter=4,
    )
    normal_style = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontSize=9.25,
        leading=12,
        spaceAfter=4,
        textColor=colors.HexColor("#212529"),
    )

    story = [
        Spacer(1, 45 * mm),
    ]
    cover_logo = _branding_box(logo_bytes, 42.0, 20.0)
    if cover_logo:
        _, draw_w, draw_h = cover_logo
        story.append(Image(io.BytesIO(logo_bytes), width=draw_w, height=draw_h))
        story[-1].hAlign = "CENTER"
        story.append(Spacer(1, 6 * mm))
    story.extend([
        Paragraph(company_name or "StructuralBase", cover_subtitle_style),
        Paragraph("Beam Design Report", cover_title_style),
        Paragraph(display_name, cover_subtitle_style),
        Paragraph(f"Design code: {beam.get('design_code', 'AS 3600')}", center_meta_style),
    ])
    for value in (
        metadata.get("project_name") and f"Project: {metadata.get('project_name')}",
        metadata.get("client_name") and f"Client: {metadata.get('client_name')}",
        metadata.get("engineer_name") and f"Engineer: {metadata.get('engineer_name')}",
        metadata.get("date") and f"Date: {metadata.get('date')}",
        metadata.get("revision_label") and f"Revision: {metadata.get('revision_label')}",
    ):
        if value:
            story.append(Paragraph(value, center_meta_style))
    story.extend([Spacer(1, 12 * mm), PageBreak()])

    story.extend(
        [
            Paragraph("Beam Design Report", title_style),
            Paragraph(display_name, styles["Heading2"]),
            Paragraph(company_name or "StructuralBase", subtle_style),
            Paragraph(
                f"Design code: {beam.get('design_code', 'AS 3600')} | Generated: {report_data.get('generated_at', '-')}",
                subtle_style,
            ),
            Paragraph("Project Information", heading_style),
        ]
    )
    project_info_rows = [
        [label, value]
        for label, value in (
            ("Project", metadata.get("project_name")),
            ("Client", metadata.get("client_name")),
            ("Engineer", metadata.get("engineer_name")),
            ("Date", metadata.get("date")),
            ("Revision", metadata.get("revision_label")),
        )
        if value
    ]
    if project_info_rows:
        project_info_table = Table(project_info_rows, colWidths=[42 * mm, 123 * mm])
        project_info_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f8fafc")),
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#dde3ea")),
                    ("PADDING", (0, 0), (-1, -1), 4.5),
                ]
            )
        )
        story.append(project_info_table)
        story.append(Spacer(1, 4))

    story.append(Paragraph("Revision History", heading_style))
    revision_history = metadata.get("revision_history") or [{"rev": revision, "date": metadata.get("date", "-"), "description": "Initial design"}]
    revision_rows = [["Rev", "Date", "Description"]]
    for row in revision_history:
        revision_rows.append([row.get("rev", "-"), row.get("date", "-"), row.get("description", "-")])
    revision_table = Table(revision_rows, colWidths=[20 * mm, 38 * mm, 107 * mm], repeatRows=1)
    revision_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2f6")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#dde3ea")),
                ("PADDING", (0, 0), (-1, -1), 4.5),
            ]
        )
    )
    story.append(revision_table)

    story.append(Paragraph("Governing Summary", heading_style))
    gov_table_rows = [[
        "Overall Status",
        "Strength Status",
        "Detailing Status",
    ], [
        checks.get("overall_status_label", BEAM_STATUS_NOT_RUN),
        checks.get("strength_status_label", BEAM_STATUS_NOT_RUN),
        checks.get("detailing_status_label", BEAM_STATUS_NOT_RUN),
    ]]
    gov_table = Table(gov_table_rows, colWidths=[55 * mm, 50 * mm, 50 * mm])
    gov_table_style = TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#edf3fb")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cfd8e3")),
            ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#c5d2e3")),
            ("PADDING", (0, 0), (-1, -1), 7),
        ]
    )
    for col_idx, label in enumerate(gov_table_rows[1]):
        gov_table_style.add("BACKGROUND", (col_idx, 1), (col_idx, 1), _status_fill_color(colors, str(label)))
        gov_table_style.add("TEXTCOLOR", (col_idx, 1), (col_idx, 1), _status_text_color(colors, str(label)))
        gov_table_style.add("FONTNAME", (col_idx, 1), (col_idx, 1), "Helvetica-Bold")
    gov_table.setStyle(gov_table_style)
    story.append(gov_table)

    story.append(Paragraph("Design Conclusion", heading_style))
    story.append(Paragraph(str(design_conclusion.get("headline", "-")), normal_style))
    if design_conclusion.get("next_step"):
        story.append(Paragraph(f"Next step: {design_conclusion.get('next_step')}", subtle_style))

    story.append(Paragraph("Summary Table", heading_style))
    summary_table_rows = [["Check", "Utilisation", "Status"]]
    for row in summary_rows:
        summary_table_rows.append(
            [
                row.get("check", "-"),
                row.get("utilisation_text", "-"),
                row.get("status_label", "-"),
            ]
        )
    summary_table = Table(summary_table_rows, colWidths=[60 * mm, 35 * mm, 60 * mm], repeatRows=1)
    summary_style = TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2f6")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#d8dee6")),
            ("ALIGN", (1, 1), (1, -1), "RIGHT"),
            ("PADDING", (0, 0), (-1, -1), 5),
        ]
    )
    for row_idx, row in enumerate(summary_rows, start=1):
        summary_style.add("BACKGROUND", (2, row_idx), (2, row_idx), _status_fill_color(colors, row.get("status_label", "")))
        summary_style.add("TEXTCOLOR", (2, row_idx), (2, row_idx), _status_text_color(colors, row.get("status_label", "")))
        summary_style.add("FONTNAME", (2, row_idx), (2, row_idx), "Helvetica-Bold")
    summary_table.setStyle(summary_style)
    story.append(summary_table)

    story.append(
        Paragraph(
            f"Governing check: {governing.get('check', '-')} (utilisation = {governing.get('utilisation_text', '-')})",
            normal_style,
        )
    )
    governing_row = next((row for row in summary_rows if row.get("check") == governing.get("check")), {})
    if governing_row.get("governing_reason"):
        story.append(Paragraph(f"Reason: {governing_row.get('governing_reason')}", subtle_style))

    def _append_group_table(title: str | None, group: dict):
        if title:
            story.append(Paragraph(title, subheading_style))
        rows = [[key, value] for key, value in (group or {}).items()]
        if not rows:
            rows = [["-", "-"]]
        table = Table(rows, colWidths=[55 * mm, 110 * mm])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f8fafc")),
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#dde3ea")),
                    ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("PADDING", (0, 0), (-1, -1), 4.5),
                ]
            )
        )
        story.append(table)
        story.append(Spacer(1, 3))

    story.append(Paragraph("Key Inputs", heading_style))
    _append_group_table("Geometry", inputs.get("geometry", {}))
    _append_group_table("Materials", inputs.get("materials", {}))
    _append_group_table("Reinforcement", inputs.get("reinforcement", {}))
    story.append(Paragraph("Design Basis", heading_style))
    _append_group_table(None, design_basis)
    story.append(Paragraph("Design Actions", heading_style))
    _append_group_table("ULS Design Actions", actions.get("uls", {}))
    _append_group_table("SLS Design Actions", actions.get("sls", {}))
    story.append(Paragraph("Analysis Context", heading_style))
    context_groups = _analysis_context_groups(analysis_context)
    _append_group_table("Beam Model", context_groups.get("Beam model", {}))
    _append_group_table("Loads", context_groups.get("Loads", {}))
    _append_group_table("Section Extraction", context_groups.get("Section extraction", {}))
    load_summary = analysis_context.get("load_summary") or []
    if load_summary:
        load_summary_table = Table(
            [["Load", "Value"]] + [[row.get("Load", "-"), row.get("Value", "-")] for row in load_summary],
            colWidths=[55 * mm, 110 * mm],
            repeatRows=1,
        )
        load_summary_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2f6")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#dde3ea")),
                    ("ALIGN", (1, 1), (1, -1), "RIGHT"),
                    ("PADDING", (0, 0), (-1, -1), 4.5),
                ]
            )
        )
        story.append(Paragraph("Loads on Beam", heading_style))
        story.append(load_summary_table)
        story.append(Spacer(1, 4))

    story.append(Paragraph("Essential Diagrams", heading_style))
    temp_paths = []
    try:
        sec_diag = export_box_diagram_png(
            fig_or_callable=section_figure_factory,
            key=f"{beam.get('beam_id', 'beam')}_section_pdf",
            caption="Section diagram",
            w_mm=110.0,
            h_mm=68.0,
        )
        if sec_diag and sec_diag.get("path"):
            temp_paths.append(sec_diag["path"])
            story.append(Spacer(1, 4))
            sec_image = Image(sec_diag["path"], width=124 * mm, height=76 * mm)
            sec_image.hAlign = "CENTER"
            story.append(sec_image)
            story.append(Paragraph("Cross-section + reinforcement diagram", subtle_style))
            story.append(Spacer(1, 8))
        else:
            story.append(Paragraph("Section diagram unavailable.", normal_style))

        if (report_data.get("diagrams") or {}).get("include_beam_elevation"):
            beam_diag = export_box_diagram_png(
                fig_or_callable=beam_figure_factory,
                key=f"{beam.get('beam_id', 'beam')}_elevation_pdf",
                caption="Beam elevation",
                w_mm=110.0,
                h_mm=55.0,
            )
            if beam_diag and beam_diag.get("path"):
                temp_paths.append(beam_diag["path"])
                story.append(Spacer(1, 8))
                beam_image = Image(beam_diag["path"], width=124 * mm, height=62 * mm)
                beam_image.hAlign = "CENTER"
                story.append(beam_image)
                story.append(Paragraph("Beam elevation / action source diagram", subtle_style))
                story.append(Spacer(1, 8))
    except Exception:
        story.append(Paragraph("Diagram export unavailable.", normal_style))

    story.append(Paragraph("Key Results", heading_style))
    key_results_rows = [["Check", "Governing", "Required / Allowable", "Provided", "Utilisation", "Severity", "Status"]]
    for row in summary_rows:
        key_results_rows.append(
            [
                row.get("check", "-"),
                row.get("governing", "-"),
                f"{row.get('required_label', 'Required')}\n{row.get('required_value', '-')}",
                f"{row.get('provided_label', 'Provided')}\n{row.get('provided_value', '-')}",
                row.get("utilisation_text", "-"),
                row.get("severity", "-"),
                row.get("status_label", "-"),
            ]
        )
    key_results_table = Table(
        key_results_rows,
        colWidths=[20 * mm, 28 * mm, 40 * mm, 40 * mm, 16 * mm, 20 * mm, 24 * mm],
        repeatRows=1,
    )
    key_results_style = TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2f6")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#d8dee6")),
            ("ALIGN", (2, 1), (5, -1), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("PADDING", (0, 0), (-1, -1), 4.5),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ]
    )
    for row_idx, row in enumerate(summary_rows, start=1):
        key_results_style.add("BACKGROUND", (6, row_idx), (6, row_idx), _status_fill_color(colors, row.get("status_label", "")))
        key_results_style.add("TEXTCOLOR", (6, row_idx), (6, row_idx), _status_text_color(colors, row.get("status_label", "")))
        key_results_style.add("FONTNAME", (6, row_idx), (6, row_idx), "Helvetica-Bold")
    key_results_table.setStyle(key_results_style)
    story.append(key_results_table)

    if serviceability.get("components"):
        story.append(
            Paragraph(
                "Serviceability components: "
                f"Crack w = {serviceability['components']['crack']['value']} mm (action); w′max = {serviceability['components']['crack']['limit']} mm (capacity) "
                f"({serviceability['components']['crack']['status']}), "
                f"Deflection δ = {serviceability['components']['deflection']['value']} mm (action); δlim = {serviceability['components']['deflection']['limit']} mm (capacity) "
                f"({serviceability['components']['deflection']['status']}).",
                subtle_style,
            )
        )

    if notes:
        story.append(Paragraph("Notes / Warnings", heading_style))
        for note in notes:
            story.append(Paragraph(f"- {note}", normal_style))
    if priority_items:
        story.append(Paragraph("Priority / Review Items", heading_style))
        for idx, item in enumerate(priority_items, start=1):
            story.append(Paragraph(f"{idx}. {item}", normal_style))

    story.append(Paragraph("Disclaimer", heading_style))
    story.append(Paragraph(metadata.get("disclaimer", ""), subtle_style))
    story.append(Spacer(1, 6))

    story.append(Paragraph("Sign-Off", heading_style))
    signature_rows = [
        ["Prepared by", metadata.get("signature_block", {}).get("prepared_by") or "___________"],
        ["Checked by", metadata.get("signature_block", {}).get("checked_by") or "___________"],
        ["Signature", "___________"],
        ["Date", "___________"],
    ]
    signature_table = Table(signature_rows, colWidths=[42 * mm, 123 * mm])
    signature_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f8fafc")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#dde3ea")),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(signature_table)

    if beam.get("report_mode") == "detailed":
        story.append(PageBreak())
        story.append(Paragraph("Detailed Check Appendix", heading_style))
        story.append(Spacer(1, 4))
        for section_name, rows in (detailed_rows or {}).items():
            story.append(Paragraph(section_name.title(), subheading_style))
            basis_note = _detail_action_basis(section_name, actions)
            if basis_note:
                story.append(Paragraph(basis_note, subtle_style))
            detail_rows = [["Check", "Calculated capacity", "Applied design action", "Utilisation", "Status"]]
            if not rows:
                detail_rows.append(["None", "-", "-", "-", "NOT_RUN"])
            else:
                for row in rows:
                    status_label = format_report_status_label(row.get("status"))
                    title = _format_detail_title(row.get("title"), row.get("route_page", section_name))
                    cap_cell = row.get("capacity") or row.get("value", "-")
                    act_cell = _format_detail_limit(
                        row.get("action") or row.get("limit"),
                        row.get("title"),
                        row.get("route_page", section_name),
                    )
                    detail_rows.append(
                        [
                            title,
                            cap_cell,
                            act_cell,
                            row.get("util", "-"),
                            status_label,
                        ]
                    )
            detail_table = Table(
                detail_rows,
                colWidths=[60 * mm, 30 * mm, 30 * mm, 22 * mm, 28 * mm],
                repeatRows=1,
            )
            detail_style = TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2f6")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d8dee6")),
                    ("ALIGN", (1, 1), (3, -1), "RIGHT"),
                    ("PADDING", (0, 0), (-1, -1), 4.25),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                ]
            )
            for row_idx in range(1, len(detail_rows)):
                label = str(detail_rows[row_idx][4])
                if label in {BEAM_STATUS_PASS, BEAM_STATUS_FAIL, BEAM_STATUS_WARN, "PASS WITH WARNINGS", BEAM_STATUS_NOT_RUN}:
                    detail_style.add("BACKGROUND", (4, row_idx), (4, row_idx), _status_fill_color(colors, label))
                    detail_style.add("TEXTCOLOR", (4, row_idx), (4, row_idx), _status_text_color(colors, label))
                    detail_style.add("FONTNAME", (4, row_idx), (4, row_idx), "Helvetica-Bold")
                else:
                    detail_style.add("TEXTCOLOR", (0, row_idx), (-1, row_idx), colors.HexColor("#6c757d"))
            detail_table.setStyle(detail_style)
            story.append(detail_table)

    try:
        doc.build(story, canvasmaker=NumberedCanvas)
        return buffer.getvalue()
    finally:
        buffer.close()
        for path in temp_paths:
            try:
                if path and os.path.exists(path):
                    os.remove(path)
            except Exception:
                pass
