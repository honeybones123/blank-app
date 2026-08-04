from typing import Any, Dict

from calculations.crack_control import pick_governing_check_row
from engineering_check_ui import sync_legacy_value_limit


def build_crack_check_rows_from_state(st_state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Pure helper: reads state and calls crack_core.compute_crack_results(publish=False).
    """
    from crack_core import compute_crack_results

    out = compute_crack_results(publish=False)

    sigma_sr = float(out.get("sigma_sr", 0.0) or 0.0)
    sigma_allow = float(out.get("sigma_allow_table", 0.0) or 0.0)
    w = float(out.get("w_calc", 0.0) or 0.0)
    wlim = float(out.get("wmax_char", 0.0) or 0.0)
    util_table = (sigma_sr / sigma_allow) if sigma_allow > 0 else 0.0
    util_w = float(out.get("crack_utilisation", 0.0) or 0.0)

    passes_table = bool(out.get("passes_table", False))
    passes_w = bool(out.get("passes_w", False))

    def _status_from_util(u: float | None):
        if u is None:
            return "—"
        if u <= 1.0:
            return "NEAR LIMIT" if u >= 0.9 else "PASS"
        return "FAIL"

    rows = [
        sync_legacy_value_limit({
            "uid": "crk_step_4",
            "title": "Governing outcome",
            "capacity": "Table stress + direct width",
            "action": "Both checks pass" if (passes_table and passes_w) else "One or more checks fail",
            "util": "—",
            "status": "INFO",
            "is_informational": True,
            "route_page": "crack",
        }),
        sync_legacy_value_limit({
            "uid": "crk_step_2",
            "title": "Table-based crack control check",
            "capacity": f"σ_allow = {sigma_allow:.1f} MPa" if sigma_allow > 0 else "—",
            "action": f"σ_sr = {sigma_sr:.1f} MPa",
            "util": f"{util_table:.2f}" if sigma_allow > 0 else "—",
            "status": _status_from_util(util_table) if sigma_allow > 0 else "—",
            "route_page": "crack",
        }),
        sync_legacy_value_limit({
            "uid": "crk_step_3",
            "title": "Direct crack width check",
            "capacity": f"w'max = {wlim:.3f} mm" if wlim > 0 else "—",
            "action": f"w = {w:.3f} mm",
            "util": f"{util_w:.2f}" if wlim > 0 else "—",
            "status": _status_from_util(util_w) if wlim > 0 else "—",
            "route_page": "crack",
        }),
    ]

    return {
        "summary_w_mm": w,
        "summary_wlim_mm": wlim,
        "summary_util": util_w,
        "rows": rows,
    }
