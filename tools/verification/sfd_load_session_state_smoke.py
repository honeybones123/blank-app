from __future__ import annotations

import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8", errors="replace")


def main() -> int:
    state_source = _read("state_and_helpers.py")
    sfd_source = _read("sfd_bmd_page.py")
    app_source = _read("app.py")
    summary_source = _read("ui/summary_sections.py")

    failures: list[str] = []

    for idx in range(1, 7):
        for load_kind in ("G", "Q", "x"):
            widget_key = f'"load_{load_kind}_point_{idx}"'
            if widget_key not in state_source:
                failures.append(f"missing_TAB_KEYS_widget:{widget_key}")
        for shared_kind in ("G", "Q", "x"):
            shared_key = f'"design_point_{shared_kind}_{idx}"'
            if shared_key not in state_source:
                failures.append(f"missing_SHARED_DEFAULTS_key:{shared_key}")
            snapshot_section = state_source.split("BEAM_PROJECT_PARAM_KEYS = [", 1)[-1].split("]", 1)[0]
            if shared_key not in snapshot_section:
                failures.append(f"missing_beam_snapshot_key:{shared_key}")

    required_sfd_snippets = [
        "def _on_design_load_mode_change()",
        'set_shared("loads_edit_toggle"',
        'set_shared("loads_edit_mode"',
        "on_change=_on_design_load_mode_change",
        'st.session_state["loads_edit_toggle"] = bool(use_sls)',
        "has_sagging_case = True",
    ]
    for snippet in required_sfd_snippets:
        if snippet not in sfd_source:
            failures.append(f"missing_sfd_load_contract_snippet:{snippet}")

    for shared_key in (
        '"loads_edit_mode"',
        '"loads_edit_toggle"',
        '"w_sls_kNm_per_m"',
        '"w_uls_kNm_per_m"',
        '"P_sls_kN"',
        '"P_uls_kN"',
    ):
        if shared_key not in app_source.split("design_load_result_keys", 1)[-1]:
            failures.append(f"missing_design_guard_key:{shared_key}")

    if "def sync_load_edit_mode_from_toggle(" not in state_source:
        failures.append("missing_shared_load_mode_toggle_sync_helper")
    if "sync_load_edit_mode_from_toggle(active_slug=selected_slug)" not in app_source:
        failures.append("router_does_not_sync_load_mode_before_proxy_load")

    if 'k.startswith("design_point_")' not in state_source:
        failures.append("design_point_zero_values_not_allowed")

    if ".summary-card-stack * { font-family: inherit; }" not in summary_source:
        failures.append("summary_card_font_contract_missing")

    if failures:
        print("sfd_load_session_state_smoke: FAIL")
        for failure in failures:
            print(f" - {failure}")
        return 1

    print("sfd_load_session_state_smoke: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
