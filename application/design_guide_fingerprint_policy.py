"""Application-owned Design Guide cache and Apply-state fingerprints."""

from __future__ import annotations

import json
from typing import Any, Callable, Iterable


DESIGN_GUIDE_PUBLICATION_CACHE_PREFIX = "dg_publication_cache_v2026_05_09_stale_payload_guard"
DEFAULT_DESIGN_GUIDE_ALGORITHM_VERSION = "active_strength_repair_publication_v29"

_EXPLICIT_KEYS = (
    "beam_type", "sec_shape", "b", "bw", "D", "d", "L", "span", "span_L_m",
    "bf", "tf", "tw", "bf_bot", "tf_bot", "cover_top", "cover_bot", "cover_side",
    "fc", "fsy", "fsyv", "Es", "Ec", "uls_Mstar", "uls_Vstar", "uls_Nstar",
    "Tu_star", "sls_Mstar", "sls_Vstar", "actions_mode", "actions_source",
    "loads_edit_mode", "bot_row_count", "bot1_layout_mode", "bot1_count",
    "bot1_spacing", "db_bot_1", "bot2_layout_mode", "bot2_count", "bot2_spacing",
    "db_bot_2", "bot_row_1_mode", "bot_row_1_bars", "bot_row_1_spacing",
    "bot_row_1_dia", "bot_row_2_mode", "bot_row_2_bars", "bot_row_2_spacing",
    "bot_row_2_dia", "top_row_count", "top1_layout_mode", "top1_count", "top1_spacing",
    "db_top_1", "top2_layout_mode", "top2_count", "top2_spacing", "db_top_2",
    "top_row_1_mode", "top_row_1_bars", "top_row_1_spacing", "top_row_1_dia",
    "top_row_2_mode", "top_row_2_bars", "top_row_2_spacing", "top_row_2_dia",
    "lig_d", "lig_legs", "s_lig", "link_d", "link_legs", "link_spacing",
    "crack_limit", "deflection_limit", "creep_coeff", "shrinkage_strain", "results_version",
)
_KEY_TOKENS = (
    "action", "beam", "bot", "cover", "crack", "creep", "deflect", "depth", "dia",
    "fc", "fsy", "geometry", "lig", "link", "load", "mstar", "nstar", "reo",
    "service", "shrink", "sls", "span", "top", "tu_star", "vstar", "width",
)
_PREFIXES = ("actions_", "bot_flange_", "bot_row_", "load_", "sfd_", "sls_", "top_flange_", "top_row_", "uls_")
_SKIP_PREFIXES = ("_", "ast_", "final_", "published_", "shear_", "shear_governing_", "shear_truth_", "ybar_", "zbot_", "ztop_")
_SKIP_TOKENS = ("_coords", "_resolved", "cache", "capacity", "governing", "publication", "truth", "util")
_SKIP_KEYS = {"actions_sls", "actions_uls", "b_crack", "bot_entry", "db_bot", "db_top", "nb_bot", "nb_top", "s_bar_bot", "s_bar_top", "s_bot", "s_top", "top_entry"}


def _stable_fingerprint_for_payload(payload: dict | None) -> tuple:
    serialised: list[tuple[str, str]] = []
    for key, value in sorted(dict(payload or {}).items(), key=lambda item: str(item[0])):
        try:
            encoded = json.dumps(value, sort_keys=True, default=str)
        except Exception:
            encoded = repr(value)
        serialised.append((str(key), encoded))
    return tuple(serialised)


def design_guide_publication_fingerprint_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return tuple(
            (str(key), design_guide_publication_fingerprint_value(item))
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        )
    if isinstance(value, (list, tuple, set)):
        return tuple(design_guide_publication_fingerprint_value(item) for item in value)
    return str(value)


def canonical_effective_depth_for_publication(source: dict | None) -> float | None:
    values = dict(source or {})
    try:
        depth = float(values.get("D", 0.0) or 0.0)
        cover = float(values.get("cover_bot", 0.0) or 0.0)
        lig_d = float(values.get("lig_d", 0.0) or 0.0)
    except (TypeError, ValueError):
        return None
    if depth <= 0.0:
        return None
    primary_dia = 0.0
    for row in (1, 2, 3, 4):
        count_raw = values.get(f"bot_row_{row}_bars", values.get(f"bot{row}_count", 0))
        try:
            active = int(float(count_raw or 0)) > 0
        except (TypeError, ValueError):
            active = bool(count_raw)
        if not active:
            continue
        dia_raw = values.get(f"bot_row_{row}_dia", values.get(f"db_bot_{row}", 0.0))
        try:
            dia = float(dia_raw or 0.0)
        except (TypeError, ValueError):
            dia = 0.0
        if dia > 0.0:
            primary_dia = dia
            break
    if primary_dia <= 0.0:
        for key in ("bot_row_1_dia", "db_bot_1", "db_bot"):
            try:
                primary_dia = float(values.get(key, 0.0) or 0.0)
            except (TypeError, ValueError):
                primary_dia = 0.0
            if primary_dia > 0.0:
                break
    return float(depth - (cover + lig_d + 0.5 * primary_dia))


def design_guide_publication_state_payload_from_plain_data(
    state: dict | None,
    *,
    session_controls: dict | None = None,
    design_actions_signature: Iterable[Any] | None = None,
    optimisation_goal: str | None = None,
) -> dict:
    source = dict(state or {})
    for row in (2, 3, 4):
        bot_count = source.get(f"bot{row}_count", source.get(f"bot_row_{row}_bars", 0))
        try:
            bot_active = int(bot_count or 0) > 0
        except Exception:
            bot_active = bool(bot_count)
        if not bot_active:
            source[f"db_bot_{row}"] = 0
            source[f"bot_row_{row}_dia"] = 0
        top_count = source.get(f"top{row}_count", source.get(f"top_row_{row}_bars", 0))
        try:
            top_active = int(top_count or 0) > 0
        except Exception:
            top_active = bool(top_count)
        if not top_active:
            source[f"db_top_{row}"] = 0
            source[f"top_row_{row}_dia"] = 0
    effective_depth = canonical_effective_depth_for_publication(source)
    if effective_depth is not None:
        source["d"] = effective_depth
    payload: dict = {}
    for key in _EXPLICIT_KEYS:
        if key in source:
            payload[key] = design_guide_publication_fingerprint_value(source.get(key))
    for key in sorted(source.keys(), key=str):
        key_text = str(key)
        key_norm = key_text.lower()
        if key_norm.startswith("design_guide_") or key_norm.startswith("_design_guide"):
            continue
        if key_norm in _SKIP_KEYS or key_norm.startswith(_SKIP_PREFIXES):
            continue
        if any(token in key_norm for token in _SKIP_TOKENS) or key_text in payload:
            continue
        if key_norm.startswith(_PREFIXES) or any(token in key_norm for token in _KEY_TOKENS):
            payload[key_text] = design_guide_publication_fingerprint_value(source.get(key))
    if session_controls:
        payload["session_controls"] = design_guide_publication_fingerprint_value(dict(session_controls))
    payload["design_actions_signature"] = tuple(design_actions_signature or ())
    payload["optimisation_goal"] = str(optimisation_goal or "")
    return payload


def design_guide_cache_fingerprint_from_plain_data(
    state: dict | None,
    *,
    session_controls: dict | None = None,
    design_actions_signature: Iterable[Any] | None = None,
    optimisation_goal: str | None = None,
    algorithm_version: str = DEFAULT_DESIGN_GUIDE_ALGORITHM_VERSION,
) -> tuple:
    return (
        DESIGN_GUIDE_PUBLICATION_CACHE_PREFIX,
        str(algorithm_version or DEFAULT_DESIGN_GUIDE_ALGORITHM_VERSION),
        _stable_fingerprint_for_payload(
            design_guide_publication_state_payload_from_plain_data(
                state,
                session_controls=session_controls,
                design_actions_signature=design_actions_signature,
                optimisation_goal=optimisation_goal,
            )
        ),
    )


def _publication_int_from_state(state: dict, key: str, default: int) -> int:
    value = state.get(key)
    if value is None:
        return int(default)
    try:
        return int(value)
    except Exception:
        return int(default)


def design_guide_primary_apply_state_fingerprint_from_state(
    state: dict | None,
    *,
    cache_fingerprint: Callable[[dict], Any] = design_guide_cache_fingerprint_from_plain_data,
    fallback_state: dict | None = None,
) -> str:
    source = dict(state or {})
    try:
        bot2_count = _publication_int_from_state(
            source,
            "bot2_count",
            _publication_int_from_state(source, "bot_row_2_bars", 0),
        )
        bot_row_2_bars = _publication_int_from_state(source, "bot_row_2_bars", bot2_count)
        if bot2_count <= 0 and bot_row_2_bars <= 0:
            source["db_bot_2"] = 0
            source["bot_row_2_dia"] = 0
        return str(cache_fingerprint(source))
    except Exception:
        return str(cache_fingerprint(dict(fallback_state if fallback_state is not None else state or {})))


__all__ = [
    "DEFAULT_DESIGN_GUIDE_ALGORITHM_VERSION",
    "DESIGN_GUIDE_PUBLICATION_CACHE_PREFIX",
    "canonical_effective_depth_for_publication",
    "design_guide_cache_fingerprint_from_plain_data",
    "design_guide_primary_apply_state_fingerprint_from_state",
    "design_guide_publication_fingerprint_value",
    "design_guide_publication_state_payload_from_plain_data",
]
