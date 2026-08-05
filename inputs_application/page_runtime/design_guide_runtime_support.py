"""Permanent support owned by the typed Inputs Design Guide runtime.

Generated mechanically from the last archived page closure; this module has no runtime dependency on that archive.
"""


from __future__ import annotations


from inputs_application.design_brain_composition import build_publication_cta
from inputs_application.guidance_runtime_config import DESIGN_GUIDE_REFERENCE_D_KEY
from inputs_application.guidance_runtime_config import DESIGN_GUIDE_SESSION_ANCHOR_D_KEY
from inputs_application.guidance_runtime_config import REO_BAR_DIAS
from inputs_application.guidance_runtime_config import REO_SPACINGS
from inputs_application.recommendation_envelope import recommendation_updates
from inputs_application.recommendation_store import RecommendationStore
from inputs_application.policy_constants import DESIGN_GUIDE_APPLY_BANNER_KEY
from inputs_application.policy_constants import DESIGN_GUIDE_APPLY_BANNER_META_KEY
from inputs_application.policy_constants import DESIGN_GUIDE_DEBUG_BUNDLE_KEY
from inputs_application.policy_constants import DESIGN_GUIDE_FIRST_TARGET_BAND_STEP_KEY
from inputs_application.policy_constants import DESIGN_GUIDE_HISTORY_ANCHOR_KEY
from inputs_application.policy_constants import DESIGN_GUIDE_PENDING_STEP_CTX_KEY
from inputs_application.policy_constants import DESIGN_GUIDE_PRIMARY_PAYLOAD_BINDING_AUDIT_KEY
from inputs_application.policy_constants import DESIGN_GUIDE_RANK_TRACE_KEY
from inputs_application.policy_constants import DESIGN_GUIDE_RECO_TRACE_KEY
from inputs_application.policy_constants import DESIGN_GUIDE_STEP_HISTORY_KEY
from inputs_page_modules.design_guide.guidance_item_dedupe import _compound_geometry_deltas
from inputs_page_modules.guidance_compute import CANONICAL_NO_SHEAR_SLIG_MM
from inputs_page_modules.guidance_compute import DESIGN_GUIDE_ALGORITHM_VERSION
from inputs_page_modules.guidance_compute import SHARED_DEFAULTS
from inputs_page_modules.guidance_compute import _VAGUE_CANONICAL_TITLE_LABELS
from inputs_page_modules.guidance_compute import _agent_debug_log
from inputs_page_modules.guidance_compute import _bottom_reo_state_label
from inputs_page_modules.guidance_compute import _build_design_actions_context
from inputs_page_modules.guidance_compute import _candidate_cache_key
from inputs_page_modules.guidance_compute import _compound_subfamilies_from_updates
from inputs_page_modules.guidance_compute import _design_optimisation_goal
from inputs_page_modules.guidance_compute import _governing_focus_from_overview
from inputs_page_modules.guidance_compute import _guidance_action_updates
from inputs_page_modules.guidance_compute import _guidance_change_lines_for_updates
from inputs_page_modules.guidance_compute import _guidance_item_is_resolved_one_click
from inputs_page_modules.guidance_compute import _guidance_state_snapshot
from inputs_page_modules.guidance_compute import _guidance_update_map
from inputs_page_modules.guidance_compute import _parse_util_value
from inputs_page_modules.guidance_compute import _proposed_change_lines_for_guidance_item
from inputs_page_modules.guidance_compute import _resolve_design_actions_from_state
from inputs_page_modules.guidance_compute import math
from inputs_page_modules.guidance_compute import re
from inputs_page_modules.guidance_compute import stable_fingerprint_for_payload
from inputs_page_modules.recommendation_compute import _design_width_value
from inputs_page_modules.recommendation_compute import _float_from_state
from inputs_page_modules.recommendation_compute import _int_from_state
from inputs_page_modules.recommendation_compute import _resolve_geometry_width_context
from inputs_page_modules.recommendation_compute import _shear_state_label
from inputs_page_modules.session import build_inputs_design_guide_step_history_debug_summary
from inputs_page_modules.session import build_inputs_design_guide_step_history_reset_plan
from inputs_page_modules.session import build_inputs_design_guide_transient_ui_clear_plan
from state_and_helpers import effective_depth_with_links_mm
import html
import json
import streamlit as st


_FINAL_PUBLICATION_CTA_AUTHORITY = "FinalDesignGuidePublication.cta"


DESIGN_GUIDE_REF_BEAM_ID_KEY = "_design_guide_ref_beam_id"


DESIGN_GUIDE_REFERENCE_B_KEY = "design_guide_reference_b"


DESIGN_GUIDE_LAST_USER_GEOM_KEY = "design_guide_last_user_geometry"


DESIGN_GUIDE_LAST_AUTO_GEOM_KEY = "design_guide_last_applied_auto_geometry"


DESIGN_GUIDE_GUIDANCE_CACHE_FP_KEY = "_design_guide_cached_fingerprint"


DESIGN_GUIDE_GUIDANCE_CACHE_ITEMS_KEY = "_design_guide_cached_items"


DESIGN_GUIDE_GUIDANCE_CACHE_DEBUG_KEY = "_design_guide_cached_debug"


DESIGN_GUIDE_SIMPLE_CACHE_FP_KEY = "_design_guide_fp"


DESIGN_GUIDE_SIMPLE_CACHE_ITEMS_KEY = "_design_guide_cache"


def _clear_design_guide_transient_ui_state(
    *,
    clear_history: bool = False,
    preserve_apply_banner: bool = False,
) -> None:
    transient_keys = [
        DESIGN_GUIDE_APPLY_BANNER_META_KEY,
        DESIGN_GUIDE_GUIDANCE_CACHE_FP_KEY,
        DESIGN_GUIDE_GUIDANCE_CACHE_ITEMS_KEY,
        DESIGN_GUIDE_GUIDANCE_CACHE_DEBUG_KEY,
        DESIGN_GUIDE_SIMPLE_CACHE_FP_KEY,
        DESIGN_GUIDE_SIMPLE_CACHE_ITEMS_KEY,
        DESIGN_GUIDE_PENDING_STEP_CTX_KEY,
    ]
    clear_plan = build_inputs_design_guide_transient_ui_clear_plan(
        base_transient_keys=tuple(transient_keys),
        apply_banner_key=DESIGN_GUIDE_APPLY_BANNER_KEY,
        always_clear_keys=(
            DESIGN_GUIDE_DEBUG_BUNDLE_KEY,
            DESIGN_GUIDE_RECO_TRACE_KEY,
            DESIGN_GUIDE_RANK_TRACE_KEY,
        ),
        history_keys=(
            DESIGN_GUIDE_STEP_HISTORY_KEY,
            DESIGN_GUIDE_FIRST_TARGET_BAND_STEP_KEY,
            DESIGN_GUIDE_HISTORY_ANCHOR_KEY,
        ),
        clear_history=bool(clear_history),
        preserve_apply_banner=bool(preserve_apply_banner),
    )
    for key in clear_plan.all_keys:
        st.session_state.pop(key, None)


def _get_design_guide_fp(state: dict | None = None) -> tuple:
    current_state = state if isinstance(state, dict) else _shared_state_snapshot()
    return _design_guide_cache_fingerprint(current_state)


def _design_guide_cache_fingerprint(state: dict) -> tuple:
    return (
        "dg_cache_v2026_04_27_in_target_local_cleanup_all_families",
        DESIGN_GUIDE_ALGORITHM_VERSION,
        str(_design_optimisation_goal(state)),
        str(state.get("sec_shape")),
        float(state.get("b", 0.0) or 0.0),
        float(state.get("D", 0.0) or 0.0),
        float(state.get("fc", 0.0) or 0.0),
        float(state.get("fsy", 0.0) or 0.0),
        float(state.get("uls_Mstar", 0.0) or 0.0),
        float(state.get("uls_Vstar", 0.0) or 0.0),
        float(state.get("uls_Nstar", 0.0) or 0.0),
        float(state.get("Tu_star", 0.0) or 0.0),
        int(state.get("bot_row_count", 0) or 0),
        int(state.get("bot1_count", 0) or 0),
        float(state.get("db_bot_1", 0.0) or 0.0),
        int(state.get("bot2_count", 0) or 0),
        float(state.get("db_bot_2", 0.0) or 0.0),
        float(state.get("lig_d", 0.0) or 0.0),
        int(state.get("lig_legs", 0) or 0),
        float(state.get("s_lig", 0.0) or 0.0),
        tuple(_resolve_design_actions_from_state(state).get("signature", ())),
    )


def _reset_design_guide_reco_trace() -> None:
    st.session_state[DESIGN_GUIDE_RECO_TRACE_KEY] = []


def _design_guide_history_anchor_from_state(state: dict) -> tuple:
    return (
        str(_design_optimisation_goal(state)),
        str(st.session_state.get(DESIGN_GUIDE_REF_BEAM_ID_KEY) or ""),
        tuple(_resolve_design_actions_from_state(state).get("signature", ())),
    )


def _maybe_reset_design_guide_step_history(state: dict) -> None:
    anchor = _design_guide_history_anchor_from_state(state)
    prev = st.session_state.get(DESIGN_GUIDE_HISTORY_ANCHOR_KEY)
    reset_plan = build_inputs_design_guide_step_history_reset_plan(
        current_anchor=anchor,
        previous_anchor=prev,
    )
    if reset_plan.reset_history:
        st.session_state[DESIGN_GUIDE_STEP_HISTORY_KEY] = []
        st.session_state[DESIGN_GUIDE_FIRST_TARGET_BAND_STEP_KEY] = None
    st.session_state[DESIGN_GUIDE_HISTORY_ANCHOR_KEY] = reset_plan.current_anchor


def _design_guide_step_history_debug_summary() -> dict:
    hist = list(st.session_state.get(DESIGN_GUIDE_STEP_HISTORY_KEY) or [])
    first = st.session_state.get(DESIGN_GUIDE_FIRST_TARGET_BAND_STEP_KEY)
    summary = build_inputs_design_guide_step_history_debug_summary(
        history=hist,
        first_target_band_step=first,
    )
    return dict(summary.payload)


def _sync_auto_design_mode_tracking(state: dict | None = None) -> None:
    current_mode = _design_optimisation_goal(state)
    previous_mode = st.session_state.get("_prev_auto_design_mode")
    if previous_mode is None:
        st.session_state["_prev_auto_design_mode"] = current_mode
        return
    if current_mode != previous_mode:
        st.session_state["_force_auto_redesign"] = True
        st.session_state["_prev_auto_design_mode"] = current_mode
        st.session_state["_auto_design_reason"] = "mode_changed"


def _shared_state_snapshot() -> dict:
    return {
        key: st.session_state.get(key, default)
        for key, default in SHARED_DEFAULTS.items()
    }


def _sync_design_guide_geometry_reference(state: dict) -> None:
    bid = str(st.session_state.get("active_beam_id") or "")
    prev = str(st.session_state.get(DESIGN_GUIDE_REF_BEAM_ID_KEY) or "")
    d_now = float(_float_from_state(state, "D", float(SHARED_DEFAULTS.get("D", 600.0))))
    _, _, w_now = _resolve_geometry_width_context(state)
    w_now = float(w_now or 0.0)
    if bid and bid != prev:
        st.session_state[DESIGN_GUIDE_REF_BEAM_ID_KEY] = bid
        st.session_state[DESIGN_GUIDE_REFERENCE_D_KEY] = d_now
        st.session_state[DESIGN_GUIDE_REFERENCE_B_KEY] = w_now
    if st.session_state.get(DESIGN_GUIDE_SESSION_ANCHOR_D_KEY) is None:
        st.session_state[DESIGN_GUIDE_SESSION_ANCHOR_D_KEY] = d_now


def _guidance_card_why_body(item: dict) -> str:
    w = item.get("guidance_why")
    if isinstance(w, str) and w.strip():
        t = w.strip()
        if t.lower().startswith("why:"):
            return t[4:].strip() or t
        return t
    r = str(item.get("reasoning") or "").strip()
    if not r:
        return ""
    if r.lower().startswith("why:"):
        return r[4:].strip() or r
    return r


def _design_guide_text_html(text: object) -> str:
    """Escape display copy while preserving intentional line breaks and bullets."""
    raw = str(text or "").strip()
    if not raw:
        return ""
    html_lines: list[str] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            html_lines.append("")
        elif stripped.startswith("- "):
            html_lines.append("&bull; " + html.escape(stripped[2:]))
        else:
            html_lines.append(html.escape(line))
    return "<br>".join(html_lines)


DESIGN_GUIDE_INTENTS = frozenset(
    {
        "required_fix",
        "efficiency_tightening",
        "optional_cleanup",
        "already_efficient",
        "advisory_warning",
    }
)


def _final_publication_cta_authority_payload(
    *,
    item: dict,
    debug: dict | None,
    button_contract: dict,
    action_payload: dict | None,
    source_precedence: dict | None,
) -> dict:
    cta = build_publication_cta()(
        item=dict(item or {}),
        debug=dict(debug or {}),
        button_contract=dict(button_contract or {}),
        action_payload=dict(action_payload or {}),
        candidate_search_evidence=dict((item or {}).get("candidate_search_evidence") or {}),
        source_precedence=dict(source_precedence or {}),
    )
    cta_payload = cta.to_dict() if hasattr(cta, "to_dict") else dict(cta or {})
    return {
        "authority": _FINAL_PUBLICATION_CTA_AUTHORITY,
        "cta": dict(cta_payload),
        "cta_hash": stable_fingerprint_for_payload(cta_payload),
    }


def _set_design_guide_primary_payload_binding_audit(**updates: object) -> dict:
    audit = dict(st.session_state.get(DESIGN_GUIDE_PRIMARY_PAYLOAD_BINDING_AUDIT_KEY) or {})
    preserved_when_blank = {
        "queued_apply_candidate_id",
        "applied_candidate_id",
        "queued_apply_updates",
        "applied_updates",
        "applied_changed_keys",
        "actual_changed_updates",
        "stale_candidate_changed_keys",
    }
    for key, value in updates.items():
        if (
            key in preserved_when_blank
            and audit.get(key) not in (None, {}, [])
            and value in (None, {}, [])
        ):
            continue
        audit[key] = value
    ids = [
        str(audit.get("visible_primary_candidate_id") or "").strip(),
        str(audit.get("button_contract_candidate_id") or "").strip(),
        str(audit.get("queued_apply_candidate_id") or "").strip(),
        str(audit.get("applied_candidate_id") or "").strip(),
    ]
    present_ids = [value for value in ids if value]
    if present_ids:
        audit["payload_binding_match"] = len(set(present_ids)) == 1
    maps = [
        audit.get("visible_updates"),
        audit.get("button_contract_updates"),
        audit.get("queued_apply_updates"),
        audit.get("applied_updates"),
    ]
    present_maps = [dict(value or {}) for value in maps if isinstance(value, dict) and value]
    if present_maps:
        audit["payload_update_match"] = all(candidate == present_maps[0] for candidate in present_maps[1:])
    st.session_state[DESIGN_GUIDE_PRIMARY_PAYLOAD_BINDING_AUDIT_KEY] = dict(audit)
    return audit


def _guidance_card_proposed_change_html(item: dict, state: dict) -> str:
    lines = _proposed_change_lines_for_guidance_item(item, state)
    if not lines:
        return ""
    inner = "<br>".join(html.escape(x) for x in lines)
    return (
        f"<div class='fast-guidance-proposed'>"
        f"<strong>Proposed change</strong><br>{inner}"
        f"</div>"
    )


def _guidance_compact_change_text(change_lines: list[str]) -> str:
    lines = [str(x).strip() for x in (change_lines or []) if str(x).strip()]
    if not lines:
        return "No direct design changes identified."
    return " | ".join(lines[:3])


def _guidance_item_payload(item: dict | None) -> dict:
    if not isinstance(item, dict):
        return {}
    payload = item.get("action_payload")
    return dict(payload) if isinstance(payload, dict) else {}


def _guidance_single_sentence(text: str) -> str:
    raw = " ".join(str(text or "").strip().split())
    if not raw:
        return ""
    for marker in (". ", "! ", "? "):
        if marker in raw:
            return raw.split(marker, 1)[0].strip() + marker.strip()
    if raw.endswith((".", "!", "?")):
        return raw
    return raw + "."


def _guidance_compact_why_text(item: dict) -> str:
    payload = dict(item.get("action_payload") or {})
    why_explicit = str(item.get("guidance_why_text_compact") or payload.get("guidance_why_text_compact") or "").strip()
    if why_explicit:
        if why_explicit.lower().startswith("why:"):
            return why_explicit
        return f"Why: {why_explicit}"
    why_raw = str(_guidance_card_why_body(item) or "").strip()
    if why_raw.lower().startswith("why:"):
        why_raw = why_raw[4:].strip()
    why_one = _guidance_single_sentence(why_raw)
    if not why_one:
        return "Why: This update targets the governing check and improves utilisation."
    return f"Why: {why_one}"


def _guidance_compact_alternatives_text(item: dict) -> str:
    payload = dict(item.get("action_payload") or {})
    alt_raw = str(payload.get("guidance_alternatives_text_compact") or "").strip()
    if not alt_raw:
        sec = str(item.get("secondary_action") or "").strip()
        if sec and sec.lower() not in {"none", "n/a", "no secondary action required."}:
            alt_raw = sec
    if not alt_raw:
        return ""
    if alt_raw.lower().startswith("other options:"):
        return alt_raw
    return f"Other options: {alt_raw}"


def _guidance_primary_compact_lines_html(item: dict, state: dict) -> str:
    payload = _guidance_item_payload(item)
    payload_change_lines = payload.get("guidance_change_lines")
    if isinstance(payload_change_lines, list) and payload_change_lines:
        change_lines = [str(x).strip() for x in payload_change_lines if str(x).strip()]
    else:
        direct_change_lines = item.get("guidance_change_lines")
        if isinstance(direct_change_lines, list) and direct_change_lines:
            change_lines = [str(x).strip() for x in direct_change_lines if str(x).strip()]
        else:
            change_lines = _proposed_change_lines_for_guidance_item(item, state)
    change_summary = str(
        payload.get("guidance_change_summary_compact")
        or _guidance_compact_change_text(change_lines)
    ).strip()
    why_text = _guidance_compact_why_text(item)
    alt_text = _guidance_compact_alternatives_text(item)
    is_resolved = _guidance_item_is_resolved_one_click(item)
    truth = dict(item.get("display_truth") or {})
    expected_util = _parse_util_value(truth.get("displayed_util"))
    expected_text = (
        f"Expected util: {expected_util:.2f}"
        if (
            is_resolved
            and expected_util is not None
            and str(truth.get("display_truth_source") or item.get("display_truth_source") or "") == "candidate_preview"
        )
        else ""
    )
    lines = [
        f"<div class='fast-guidance-reason'>{_design_guide_text_html('Change: ' + change_summary)}</div>",
        f"<div class='fast-guidance-reason'>{_design_guide_text_html(why_text)}</div>",
    ]
    if expected_text:
        lines.insert(1, f"<div class='fast-guidance-reason'>{_design_guide_text_html(expected_text)}</div>")
    if alt_text:
        lines.append(f"<div class='fast-guidance-secondary'>{_design_guide_text_html(alt_text)}</div>")
    return "".join(lines)


def _compound_guidance_title_reasoning_why(
    state: dict,
    updates: dict,
    subfamilies: list[str],
    *,
    strengthening: bool,
) -> tuple[str, str, str]:
    """Returns (title_main, reasoning_with_why_prefix, guidance_why_plain)."""
    sf = set(subfamilies)
    eps = 0.5
    d0, d1, w0, w1 = _compound_geometry_deltas(state, updates) if updates else (0.0, 0.0, 0.0, 0.0)
    grow_d = d1 > d0 + eps
    grow_w = w1 > w0 + eps

    if strengthening:
        if sf >= {"geometry", "bottom_reo", "shear"}:
            title = "Increase section size, bottom reinforcement, and shear reinforcement"
            why = (
                "Flexure and shear both need attention. Updating section geometry, bottom steel, "
                "and shear reinforcement together gives the cleanest one-step strengthening move."
            )
            return (title, f"Why: {why}", why)
        if sf >= {"geometry", "bottom_reo"}:
            if grow_d and grow_w:
                title = "Increase depth, width, and bottom reinforcement"
            elif grow_d and not grow_w:
                title = "Increase depth and bottom reinforcement"
            elif grow_w and not grow_d:
                title = "Increase width and bottom reinforcement"
            else:
                title = "Adjust section and bottom reinforcement"
            why = (
                "Bending demand is above capacity. Changing the section together with bottom steel is the most direct "
                "way to bring capacity in line with the applied actions."
            )
            return (
                title,
                f"Why: {why}",
                why,
            )
        if sf >= {"shear", "bottom_reo"}:
            title = "Reduce shear links and adjust bottom reinforcement"
            why = (
                "Shear links look heavier than needed for the applied shear. Reducing links and rebalancing longitudinal "
                "steel keeps detailing consistent with demand."
            )
            return (title, f"Why: {why}", why)
        if sf >= {"geometry", "shear"}:
            title = "Adjust section geometry and shear reinforcement"
            why = (
                "Flexure and shear both need attention. Updating geometry and shear reinforcement together avoids fixing "
                "one check while leaving the other marginal."
            )
            return (title, f"Why: {why}", why)
        why = "Several inputs need to move together to reach a compliant, coherent design."
        return (
            "Apply combined strengthening update",
            f"Why: {why}",
            why,
        )
    if sf >= {"geometry", "bottom_reo"}:
        title = "Reduce section size and rebalance bottom reinforcement"
        why = (
            "Utilisation is below the target band. A small section trim with a light steel rebalance moves the design "
            "toward efficient use without large jumps."
        )
        return (title, f"Why: {why}", why)
    if sf >= {"shear", "bottom_reo"}:
        title = "Reduce shear links and trim bottom reinforcement"
        why = (
            "The section is conservative on shear and steel. Relaxing links and trimming bottom steel tightens the design "
            "without increasing member size."
        )
        return (title, f"Why: {why}", why)
    if sf >= {"geometry", "shear"}:
        title = "Tighten geometry and shear reinforcement"
        why = (
            "Reserve is available on both flexure-related geometry and shear. Coordinated reductions keep detailing "
            "consistent while lifting utilisation toward the target band."
        )
        return (title, f"Why: {why}", why)
    why = "Combined adjustments move several checks together toward the target utilisation band."
    return (
        "Apply coordinated efficiency update",
        f"Why: {why}",
        why,
    )


def _infer_families_mentioned_in_label(label: str) -> frozenset[str]:
    """Heuristic: which compound update families does this string appear to describe."""
    if not str(label or "").strip():
        return frozenset()
    s = str(label).strip().lower()
    if s.startswith("trial:"):
        s = s.split(":", 1)[-1].strip()
    out: set[str] = set()
    # Shear link layout (e.g. "2-leg N10 @ 200")
    if re.search(r"\d+\s*-\s*leg", s) or re.search(r"\bn\s*\d+\s*@", s) or re.search(r"\bn\d+\s*@\s*\d+", s):
        out.add("shear")
    if "shear link" in s or "stirrup" in s or "link spacing" in s:
        out.add("shear")
    # Geometry
    if (
        "depth:" in s
        or "width:" in s
        or re.search(r"\d+\s*→\s*\d+", s)
        or "increase depth" in s
        or "increase width" in s
        or "section width" in s
        or "section depth" in s
    ):
        out.add("geometry")
    if re.search(r"\b\d+\s*x\s*\d+\s*mm\b", s):
        out.add("geometry")
    # Bottom reinforcement
    if ("bottom" in s and ("bar" in s or "reo" in s or "steel" in s or "reinforcement" in s)) or re.search(
        r"\b\d+\s*\+\s*\d+\s*x\s*n\d+",
        s,
    ):
        out.add("bottom_reo")
    return frozenset(out)


def _label_consistent_with_updates_families(label: str, expected: frozenset[str]) -> bool:
    """True if the label does not claim update families outside those implied by actual updates."""
    s = str(label or "").strip().lower()
    if not s:
        return False
    if s in _VAGUE_CANONICAL_TITLE_LABELS:
        return False
    mentioned = _infer_families_mentioned_in_label(label)
    if not mentioned:
        return True
    return mentioned <= expected


def _derived_guidance_title_from_updates(state: dict, updates: dict) -> str:
    """Human-facing title derived only from updates (compound helper + change lines)."""
    subfamilies = _compound_subfamilies_from_updates(updates)
    base = _guidance_state_snapshot(state or {})
    if len(subfamilies) >= 2:
        t, _, _ = _compound_guidance_title_reasoning_why(
            base,
            updates,
            subfamilies,
            strengthening=True,
        )
        dt = str(t or "").strip()
        if dt and dt != "Apply combined strengthening update":
            return dt
    lines = _guidance_change_lines_for_updates(base, updates)
    if lines:
        if len(lines) == 1:
            return str(lines[0]).strip()
        return _guidance_compact_change_text(lines[:2])
    if len(subfamilies) >= 2:
        t, _, _ = _compound_guidance_title_reasoning_why(
            base,
            updates,
            subfamilies,
            strengthening=True,
        )
        if str(t or "").strip():
            return str(t).strip()
    if len(subfamilies) == 1:
        return {
            "geometry": "Adjust section geometry",
            "bottom_reo": "Adjust bottom reinforcement",
            "shear": "Adjust shear reinforcement",
        }.get(subfamilies[0], "Apply recommendation")
    return "Apply recommendation"


def _design_guide_focus_label(focus: str | None) -> str:
    mapping = {
        "bending": "Bending",
        "shear": "Shear",
        "geometry": "Geometry",
        "crack": "Crack control",
        "deflection": "Deflection",
        "general": "Overall design",
    }
    return mapping.get(str(focus or "general").strip().lower(), "Overall design")


def _overview_debug_summary(state: dict, overview: dict | None) -> dict:
    resolved_overview = overview or {}
    bending_pack = ((resolved_overview.get("packs") or {}).get("bending") or {})
    utils = dict(resolved_overview.get("utils") or {})
    return {
        "bottom_reo_label": _bottom_reo_state_label(state),
        "Ast_bot": float((_effective_bottom_design_state(state) or {}).get("Ast_bot", 0.0) or 0.0),
        "summary_phiMu_kNm": float(bending_pack.get("summary_phiMu_kNm", 0.0) or 0.0),
        "summary_Mu_star_kNm": float(bending_pack.get("summary_Mu_star_kNm", 0.0) or 0.0),
        "bending_util": None if utils.get("bending") is None else float(utils.get("bending")),
        "worst_util": float(resolved_overview.get("worst_util", 0.0) or 0.0),
        "governing_focus": _design_guide_focus_label(_governing_focus_from_overview(resolved_overview)),
        "design_guide_shear_truth_source": resolved_overview.get("design_guide_shear_truth_source"),
        "stage3_shear_truth_debug": resolved_overview.get("stage3_shear_truth_debug"),
        "stage3_remaining_issue_class": resolved_overview.get("stage3_remaining_issue_class"),
    }


def _effective_bottom_design_state(state: dict, bottom_updates: dict | None = None) -> dict:
    from bending_core import _effective_depth_centroid_pure

    D = _float_from_state(state, "D", 600.0)
    cover_bot = _float_from_state(state, "cover_bot", 40.0)
    rowgap_bot = _float_from_state(state, "rowgap_bot", 60.0)
    b = _design_width_value(state)

    if bottom_updates:
        db_bot = float(bottom_updates["db_bot_1"])
        nb_bot = int(bottom_updates["bot1_count"]) + int(bottom_updates["bot2_count"])
        Ast_bot = (nb_bot * math.pi * db_bot**2) / 4.0
    else:
        db_bot = _float_from_state(
            state,
            "db_bot",
            _float_from_state(state, "db_bot_1", 20.0),
        )
        nb_bot = _int_from_state(state, "nb_bot", 0)
        Ast_bot = _float_from_state(state, "Ast_bot", 0.0)

    lig_diameter = _float_from_state(state, "lig_d", 10.0)
    bar_diameter = float(db_bot or 0.0)
    d_centroid = effective_depth_with_links_mm(
        D_mm=D,
        cover_to_ligs_mm=cover_bot,
        lig_diameter_mm=lig_diameter,
        bar_diameter_mm=bar_diameter,
    )

    return {
        "Ast_bot": float(Ast_bot),
        "db_bot": float(db_bot),
        "nb_bot": int(nb_bot),
        "d_centroid": float(d_centroid),
    }


def _starter_shear_diameter(state: dict) -> int:
    current_dia = _int_from_state(state, "lig_d", 0)
    if current_dia > 0:
        return int(current_dia)
    practical_dias = [dia for dia in REO_BAR_DIAS if dia <= 16]
    return int(practical_dias[0] if practical_dias else 10)


def _starter_shear_spacing(state: dict) -> float:
    current_spacing = _float_from_state(state, "s_lig", 0.0)
    if current_spacing > 0.0 and REO_SPACINGS:
        return float(min(REO_SPACINGS, key=lambda value: abs(float(value) - current_spacing)))
    if 200 in REO_SPACINGS:
        return 200.0
    return float(REO_SPACINGS[min(len(REO_SPACINGS) - 1, len(REO_SPACINGS) // 2)] if REO_SPACINGS else 200.0)


def _normalise_invalid_shear_state_updates(
    base_state: dict,
    updates: dict,
    *,
    source: str,
) -> dict:
    resolved_state = dict(base_state or {})
    normalised_updates = dict(updates or {})
    resolved_state.update(normalised_updates)
    lig_legs = _int_from_state(resolved_state, "lig_legs", 0)
    lig_d = _int_from_state(resolved_state, "lig_d", 0)
    if lig_legs <= 0:
        # Keep inactive-links state canonical so "remove links" survives execution/commit.
        normalised_updates["lig_legs"] = 0
        normalised_updates["lig_d"] = 0
        canonical_no_shear_spacing = float(CANONICAL_NO_SHEAR_SLIG_MM)
        s_lig = _float_from_state(resolved_state, "s_lig", canonical_no_shear_spacing)
        if abs(float(s_lig) - canonical_no_shear_spacing) > 1e-9:
            normalised_updates["s_lig"] = canonical_no_shear_spacing
        return normalised_updates
    if lig_legs >= 2 and lig_d <= 0:
        starter_dia = int(_starter_shear_diameter(resolved_state))
        _agent_debug_log(
            "Invalid shear state: ligatures active but lig_d <= 0",
            {
                "source": source,
                "lig_legs": lig_legs,
                "lig_d_before": lig_d,
                "lig_d_after": starter_dia,
                "s_lig": _float_from_state(resolved_state, "s_lig", 0.0),
            },
            location="inputs_page.py:shear_state_normalisation",
            hypothesis_id="H_SHEAR_INVALID",
        )
        if bool(st.session_state.get("_dev_mode")):
            assert starter_dia > 0, "Invalid shear state: ligatures active but diameter is zero"
        normalised_updates["lig_d"] = starter_dia
    s_lig = _float_from_state(resolved_state, "s_lig", 0.0)
    if lig_legs >= 2 and s_lig <= 0.0:
        starter_spacing = float(_starter_shear_spacing(resolved_state))
        normalised_updates["s_lig"] = starter_spacing
    return normalised_updates


def _is_design_guide_good_utilisation_band(util: object) -> bool:
    if util is None:
        return False
    try:
        u = float(util)
    except (TypeError, ValueError):
        return False
    return (not math.isnan(u)) and 0.80 <= u <= 0.95


def _is_design_guide_terminal_safe_item(item: dict) -> bool:
    _ts = str(item.get("design_guide_terminal_state") or "").strip()
    if _ts in ("optimal", "very_low_demand"):
        return True
    title = str(item.get("title_main") or "")
    primary = str(item.get("primary_action") or "")
    hay = f"{title} {primary}".lower()
    needles = (
        "no further safe local reductions",
        "no further local reductions",
        "no further recommendations",
        "critical case solved",
        "reducing non-critical provisions has reached a safe limit",
        "geometry locked for optimisation",
        "geometry locked. optimisation is limited",
    )
    return any(n in hay for n in needles)


_ONE_CLICK_CTA_BLOCKING_REASONS = frozenset(
    {
        "partial_failure_coverage",
        "no_full_coverage_candidate",
        "no_multi_domain_target_candidate",
        "candidate_preview_has_fail_status",
    }
)


_RECOMMENDATION_NON_COMMIT_STATUSES = frozenset(
    {
        "blocked",
        "failed",
        "no_action",
        "no_actionable_full_coverage_candidate",
        "rejected",
    }
)


def _build_recommendation_envelope(
    *,
    updates: dict | None = None,
    source: str = "",
    status: str = "",
    blocked_reason: str | None = None,
    commit_eligible: bool | None = None,
    preview: dict | None = None,
    audit: dict | None = None,
    required_domains: list | tuple | set | None = None,
) -> dict:
    """
    Layer 7/8 boundary for Design Guide actions.

    Guidance may propose updates, but presentation may only render a normal CTA when this
    envelope says the action is commit-eligible.
    """
    updates_d = dict(updates or {}) if isinstance(updates, dict) else {}
    status_norm = str(status or "").strip()
    reason_norm = str(blocked_reason or "").strip()
    if commit_eligible is None:
        commit_eligible = bool(updates_d) and not reason_norm and status_norm not in _RECOMMENDATION_NON_COMMIT_STATUSES
    if isinstance(required_domains, str):
        domains_iter = [required_domains]
    else:
        domains_iter = list(required_domains or []) if required_domains is not None else []
    ordered_domains = [
        str(d or "").strip().lower()
        for d in domains_iter
        if str(d or "").strip()
    ]
    envelope_status = status_norm or ("ready" if commit_eligible else "blocked" if reason_norm else "advisory")
    return {
        "version": 1,
        "source": str(source or "").strip() or None,
        "status": envelope_status,
        "updates": updates_d,
        "commit_eligible": bool(commit_eligible),
        "blocked_reason": reason_norm or None,
        "required_domains": ordered_domains,
        "preview": dict(preview or {}) if isinstance(preview, dict) else {},
        "audit": dict(audit or {}) if isinstance(audit, dict) else {},
    }


def _recommendation_envelope_from_pending(recommendation: dict | None) -> dict:
    if not isinstance(recommendation, dict):
        return {}
    envelope = recommendation.get("recommendation_envelope")
    if isinstance(envelope, dict):
        return dict(envelope)
    meta = dict(recommendation.get("meta") or {})
    status = str(meta.get("status") or recommendation.get("status") or "").strip()
    reason = str(
        recommendation.get("blocked_reason")
        or meta.get("blocked_reason")
        or meta.get("reason")
        or ""
    ).strip()
    return _build_recommendation_envelope(
        updates=recommendation_updates(recommendation),
        source=str(recommendation.get("_source") or recommendation.get("source") or "legacy_pending"),
        status=status,
        blocked_reason=reason or None,
    )


def _recommendation_commit_eligible(recommendation: dict | None) -> bool:
    envelope = _recommendation_envelope_from_pending(recommendation)
    return bool(envelope.get("commit_eligible"))


def _recommendation_blocked_reason(recommendation: dict | None) -> str | None:
    envelope = _recommendation_envelope_from_pending(recommendation)
    reason = str(envelope.get("blocked_reason") or "").strip()
    if reason:
        return reason
    if isinstance(recommendation, dict) and not bool(envelope.get("commit_eligible")):
        status = str(envelope.get("status") or "").strip()
        if status in _RECOMMENDATION_NON_COMMIT_STATUSES:
            return status
    return None


def _design_guide_fail_fingerprints_equivalent(a: dict | None, b: dict | None) -> bool:
    """Treat tiny util drift as equivalent when the failing state is otherwise unchanged."""

    def _norm_keys(v: dict | None) -> list[str]:
        return sorted(str(x or "").strip().lower() for x in list((v or {}).get("fail_keys") or []) if str(x or "").strip())

    def _norm_status(v: dict | None, key: str) -> str:
        return str((v or {}).get(key) or "").strip().upper()

    def _util_close(x: object, y: object) -> bool:
        ux = _parse_util_value(x)
        uy = _parse_util_value(y)
        if ux is None or uy is None:
            return ux is None and uy is None
        if not (math.isfinite(float(ux)) and math.isfinite(float(uy))):
            return ux == uy
        return abs(float(ux) - float(uy)) <= 1e-6

    da = dict(a or {})
    db = dict(b or {})
    return (
        _norm_keys(da) == _norm_keys(db)
        and _norm_status(da, "shear_status") == _norm_status(db, "shear_status")
        and _norm_status(da, "bending_status") == _norm_status(db, "bending_status")
        and _util_close(da.get("shear_util"), db.get("shear_util"))
        and _util_close(da.get("bending_util"), db.get("bending_util"))
    )


def _one_click_feedback_cta_state(
    overview: dict | None,
    *,
    clear_stale: bool = True,
) -> dict:
    feedback = st.session_state.get("_one_click_run_feedback")
    if not isinstance(feedback, dict):
        feedback = {}
    status = str(feedback.get("status") or "").strip()
    reason = str(feedback.get("reason") or "").strip()
    feedback_fp = dict(feedback.get("current_fail_fingerprint") or {})
    current_fp = _current_design_guide_fail_fingerprint(overview)
    blocks_primary_cta = bool(reason in _ONE_CLICK_CTA_BLOCKING_REASONS)
    fingerprints_match = bool(
        feedback_fp
        and (
            feedback_fp == current_fp
            or _design_guide_fail_fingerprints_equivalent(feedback_fp, current_fp)
        )
    )
    matches_current_state = bool(
        status in {"blocked", "rejected"}
        and blocks_primary_cta
        and fingerprints_match
    )
    stale_cleared = False
    if (
        clear_stale
        and status in {"blocked", "rejected"}
        and blocks_primary_cta
        and feedback_fp
        and not fingerprints_match
    ):
        st.session_state.pop("_one_click_run_feedback", None)
        feedback = {}
        status = ""
        reason = ""
        feedback_fp = {}
        stale_cleared = True
    return {
        "feedback": dict(feedback),
        "status": status,
        "reason": reason,
        "feedback_fail_fingerprint": dict(feedback_fp),
        "current_fail_fingerprint": dict(current_fp),
        "blocks_primary_cta": bool(blocks_primary_cta),
        "matches_current_state": bool(matches_current_state),
        "stale_cleared": bool(stale_cleared),
        "stale_clear_reason": "fail_fingerprint_changed" if stale_cleared else None,
    }


def _design_guide_primary_uses_success_style(item: dict) -> bool:
    """Green 'done' card: resolved safe/complete only, not active fix recommendations."""
    bucket = str(item.get("bucket") or "")
    if bucket == "fail":
        return False
    if bucket == "start":
        return False
    has_apply = bool(item.get("action_type"))
    if has_apply and bucket in ("fail", "warn", "efficiency"):
        return False
    if bucket == "warn" and not _is_design_guide_terminal_safe_item(item):
        return False
    terminal = _is_design_guide_terminal_safe_item(item)
    good_band = _is_design_guide_good_utilisation_band(item.get("util"))
    if terminal:
        return True
    if good_band and bucket == "pass":
        return True
    return False


def _suppress_redundant_guidance_items(
    guidance_items: list[dict],
    recommendation_result: dict | None,
) -> tuple[list[dict], dict]:
    """
    Remove secondary items that materially duplicate the primary recommendation move.
    """
    _ = recommendation_result
    items = list(guidance_items or [])
    if not items:
        return items, {
            "suppressed": False,
            "reason": "no_items",
            "suppressed_titles": [],
            "subset_suppressed": False,
            "subset_suppressed_titles": [],
            "primary_update_keys": [],
            "secondary_update_keys": [],
        }

    primary_item = items[0]
    kept = [primary_item]
    suppressed_titles = []
    subset_suppressed_titles = []
    primary_updates = _guidance_update_map(primary_item)
    primary_update_keys = sorted(str(k) for k in primary_updates.keys())
    secondary_update_keys: list[list[str]] = []

    for item in items[1:]:
        secondary_updates = _guidance_update_map(item)
        primary_keys = set(primary_updates.keys())
        secondary_keys = set(secondary_updates.keys())
        secondary_is_exact_match = bool(primary_updates) and secondary_updates == primary_updates
        secondary_is_subset = bool(primary_updates) and bool(secondary_updates) and secondary_keys.issubset(primary_keys)
        if secondary_is_subset:
            for k, v in secondary_updates.items():
                if primary_updates.get(k) != v:
                    secondary_is_subset = False
            break
        if secondary_is_exact_match or secondary_is_subset:
            title = str(item.get("title_main") or "")
            suppressed_titles.append(title)
            secondary_update_keys.append(sorted(str(k) for k in secondary_updates.keys()))
            if secondary_is_subset and not secondary_is_exact_match:
                subset_suppressed_titles.append(title)
            continue
        kept.append(item)

    return kept, {
        "suppressed": bool(suppressed_titles),
        "reason": "overlapping_update_subset" if suppressed_titles else "none",
        "suppressed_titles": suppressed_titles,
        "subset_suppressed": bool(subset_suppressed_titles),
        "subset_suppressed_titles": subset_suppressed_titles,
        "primary_update_keys": primary_update_keys,
        "secondary_update_keys": secondary_update_keys,
    }


DESIGN_GUIDE_TITLE_ALIGNMENT_LOG_EVENT = "design_guide_title_alignment_verification"


def _selector_final_winner_label_from_guidance_debug(dbg: dict | None) -> str | None:
    """Best-effort selector / rank-trace winner label for post-hoc alignment checks (debug only)."""
    if not isinstance(dbg, dict):
        return None
    for key in ("selected_title", "surfaced_selected_title"):
        v = dbg.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    oc = dbg.get("one_click_critical_candidate_label")
    if isinstance(oc, str) and oc.strip():
        return oc.strip()
    rt = dbg.get("rank_trace")
    if not isinstance(rt, list):
        return None
    for entry in reversed(rt):
        if not isinstance(entry, dict):
            continue
        ads = entry.get("auto_design_final_selector")
        if isinstance(ads, dict):
            lab = ads.get("final_winner_label")
            if isinstance(lab, str) and lab.strip():
                return lab.strip()
    return None


def _design_guide_render_plan(
    guidance_items: list[dict],
    recommendation_result: dict | None,
    collapse_meta: dict | None,
) -> dict:
    items = list(guidance_items or [])
    collapse = dict(collapse_meta or {})

    primary_only = False
    visible_items = list(items)
    reason = "normal"

    rr_title = str((recommendation_result or {}).get("title") or "").strip()
    top_title = str((items[0] or {}).get("title_main") or "").strip() if items else ""

    if items:
        primary_only = True
        visible_items = items[:1]
        reason = "primary_visible_card_only"
    elif bool(collapse.get("collapsed")) and recommendation_result and len(items) <= 1:
        primary_only = True
        visible_items = []
        reason = "collapsed_primary_only"
    elif recommendation_result and len(items) == 1 and rr_title and top_title and rr_title == top_title:
        primary_only = True
        visible_items = []
        reason = "single_primary_duplicate_suppressed"

    return {
        "render_primary_only": bool(primary_only),
        "visible_guidance_items": list(visible_items),
        "reason": reason,
        "input_count": len(items),
        "visible_count": len(visible_items),
    }


def _recommendation_fingerprint_state(state: dict) -> dict:
    fingerprint_state = {
        key: state.get(key, default)
        for key, default in SHARED_DEFAULTS.items()
    }
    fingerprint_state["_resolved_design_actions"] = _resolve_design_actions_from_state(state)
    return fingerprint_state


def _recommendation_cache_fingerprint(state: dict) -> str:
    fingerprint_state = _recommendation_fingerprint_state(state)
    try:
        return json.dumps(fingerprint_state, sort_keys=True, default=str)
    except Exception:
        return str(sorted((str(key), str(value)) for key, value in fingerprint_state.items()))


def _describe_guidance_step(before_state: dict, after_state: dict, action_type: str, updates: dict) -> str:
    if "D" in updates:
        before_depth = int(float(before_state.get("D", 0.0) or 0.0))
        after_depth = int(float(after_state.get("D", 0.0) or 0.0))
        verb = "Reduced" if after_depth < before_depth else "Increased"
        return f"{verb} depth D from {before_depth} to {after_depth} mm."
    width_key, width_label, _ = _resolve_geometry_width_context(after_state)
    if width_key in updates:
        before_width = int(float(before_state.get(width_key, 0.0) or 0.0))
        after_width = int(float(after_state.get(width_key, 0.0) or 0.0))
        width_short = "b" if width_key == "b" else width_key
        verb = "Reduced" if after_width < before_width else "Increased"
        return f"{verb} {width_short} from {before_width} to {after_width} mm."
    if any(key in updates for key in ("bot1_count", "bot2_count", "db_bot_1", "db_bot_2", "Ast_bot")):
        return f"Updated bottom reinforcement from {_bottom_reo_state_label(before_state)} to {_bottom_reo_state_label(after_state)}."
    if any(key in updates for key in ("s_lig", "lig_legs", "lig_d")):
        return f"Updated shear reinforcement from {_shear_state_label(before_state)} to {_shear_state_label(after_state)}."
    load_keys = ("g_udl_kNm_per_m", "g_kNm", "g_line_kNm")
    if any(key in updates for key in load_keys):
        parts: list[str] = []
        for key in load_keys:
            if key not in updates:
                continue
            try:
                b0 = float(before_state.get(key, 0.0) or 0.0)
                a0 = float(after_state.get(key, 0.0) or 0.0)
                parts.append(f"{key} {b0:.3f} → {a0:.3f} kN/m")
            except Exception:
                parts.append(str(key))
        if parts:
            return "Adjusted sustained load inputs: " + "; ".join(parts) + "."
    return f"Applied {action_type.replace('_', ' ')}."
    st.rerun()


_ENABLE_GLOBAL_EVAL_CACHE = False


def _current_design_guide_fail_fingerprint(overview: dict | None) -> dict:
    ov = dict(overview or {})
    statuses = dict(ov.get("statuses") or {})
    utils = dict(ov.get("utils") or {})

    fail_keys = sorted(
        [
            str(k)
            for k, v in statuses.items()
            if str(v or "").strip().upper() == "FAIL"
        ],
    )

    shear_status = str(statuses.get("shear") or "").strip().upper()
    shear_util = _parse_util_value(utils.get("shear"))
    bending_status = str(statuses.get("bending") or "").strip().upper()
    bending_util = _parse_util_value(utils.get("bending"))

    return {
        "fail_keys": list(fail_keys),
        "shear_status": shear_status,
        "shear_util": shear_util,
        "bending_status": bending_status,
        "bending_util": bending_util,
    }


def _guidance_card_label(item: dict) -> str:
    if item["bucket"] == "start":
        return "START"
    if item["bucket"] in ("fail", "warn"):
        return "NEXT"
    if item["bucket"] == "efficiency":
        return "RECOMMEND"
    return "GOOD"


def _guidance_before_after_text(item: dict, state: dict) -> str | None:
    action_type = item.get("action_type")
    if not action_type:
        return None
    expensive_action_types = {
        "apply_mode_recommendation",
        "apply_bottom_recommendation",
        "apply_geometry_recommendation",
        "apply_shear_recommendation",
        "apply_compound_guidance",
        "reduce_bottom_reinforcement",
        "increase_link_spacing",
        "reduce_number_of_legs",
    }
    if action_type in expensive_action_types:
        return None
    updates = _guidance_action_updates(action_type, item.get("action_payload") or {}, state=state)
    if not updates:
        return None
    after_state = dict(state)
    after_state.update(updates)
    return _describe_guidance_step(state, after_state, action_type, updates)


def _apply_guidance_ui_state(
    current_state: dict,
    *,
    preserve_apply_banner: bool = True,
) -> dict:
    """
    Layer 1 UI/session side effects for guidance panel orchestration.
    """
    design_context = _build_design_actions_context(current_state)
    guidance_state = dict(design_context.get("state") or _guidance_state_snapshot(current_state))
    cache_fp = _candidate_cache_key(guidance_state)
    if _ENABLE_GLOBAL_EVAL_CACHE:
        RecommendationStore(st.session_state).reset_evaluation_cache(
            fingerprint=cache_fp
        )
    _sync_design_guide_geometry_reference(guidance_state)
    _maybe_reset_design_guide_step_history(guidance_state)
    _clear_design_guide_transient_ui_state(
        clear_history=False,
        preserve_apply_banner=preserve_apply_banner,
    )
    return {
        "guidance_state": guidance_state,
        "guidance_cache_fp": cache_fp,
    }


__all__ = [
    "DESIGN_GUIDE_INTENTS",
    "DESIGN_GUIDE_LAST_AUTO_GEOM_KEY",
    "DESIGN_GUIDE_LAST_USER_GEOM_KEY",
    "DESIGN_GUIDE_REFERENCE_B_KEY",
    "DESIGN_GUIDE_TITLE_ALIGNMENT_LOG_EVENT",
    "_apply_guidance_ui_state",
    "_derived_guidance_title_from_updates",
    "_design_guide_primary_uses_success_style",
    "_design_guide_render_plan",
    "_design_guide_step_history_debug_summary",
    "_design_guide_text_html",
    "_final_publication_cta_authority_payload",
    "_get_design_guide_fp",
    "_guidance_before_after_text",
    "_guidance_card_label",
    "_guidance_card_proposed_change_html",
    "_guidance_card_why_body",
    "_guidance_primary_compact_lines_html",
    "_label_consistent_with_updates_families",
    "_normalise_invalid_shear_state_updates",
    "_one_click_feedback_cta_state",
    "_overview_debug_summary",
    "_recommendation_blocked_reason",
    "_recommendation_cache_fingerprint",
    "_recommendation_commit_eligible",
    "_reset_design_guide_reco_trace",
    "_selector_final_winner_label_from_guidance_debug",
    "_set_design_guide_primary_payload_binding_audit",
    "_suppress_redundant_guidance_items",
    "_sync_auto_design_mode_tracking",
]
