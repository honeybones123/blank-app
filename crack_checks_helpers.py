from typing import Dict, Any


def build_crack_check_rows_from_state(st_state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Pure helper: reads state and calls crack_core.compute_crack_results(publish=False).
    """
    from crack_core import compute_crack_results

    out = compute_crack_results(publish=False)

    w = float(out.get("w_calc", 0.0) or 0.0)
    wlim = float(out.get("wmax_char", 0.0) or 0.0)
    util = float(out.get("crack_utilisation", 0.0) or 0.0)

    ok = (util <= 1.0) if wlim > 0 else None
    status = "PASS" if ok else "FAIL" if ok is False else "—"

    rows = [
        {
            "uid": "crack_width",
            "title": "Crack width check",
            "value": f"w = {w:.3f} mm",
            "limit": f"wmax = {wlim:.3f} mm" if wlim > 0 else "—",
            "util": f"{util:.2f}" if wlim > 0 else "—",
            "status": status,
            "route_page": "crack",
        }
    ]

    return {
        "summary_w_mm": w,
        "summary_wlim_mm": wlim,
        "summary_util": util,
        "rows": rows,
    }
