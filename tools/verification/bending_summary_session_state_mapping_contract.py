from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bending_checks_helpers import build_bending_check_rows_from_state
from calculations.design_actions import (
    derive_design_action_session_updates,
    resolve_design_actions_from_state,
)
from ui.summary_rows import build_bending_clickable_summary_rows


class SessionStateLike:
    """Tiny mapping-like object matching the part of Streamlit session_state used here."""

    def __init__(self, data: dict):
        self._data = dict(data)

    def get(self, key, default=None):
        return self._data.get(key, default)

    def items(self):
        return self._data.items()


def _bending_state() -> dict:
    return {
        "actions_mode": "manual",
        "actions_source": "Manual design actions (inputs below)",
        "uls_Mstar": 50.0,
        "uls_Mstar_pos_manual": 50.0,
        "uls_Mstar_neg_manual": 0.0,
        "uls_Vstar": 0.0,
        "uls_Nstar": 0.0,
        "sls_Mstar": 20.0,
        "sls_Mstar_pos_manual": 20.0,
        "sls_Mstar_neg_manual": 0.0,
        "sls_Vstar": 0.0,
        "b": 450.0,
        "D": 750.0,
        "fc": 40.0,
        "fsy": 500.0,
        "phi_bend": 0.8,
        "Ast_bot": 1256.0,
        "Ast_top": 628.0,
        "d": 690.0,
        "do": 60.0,
        "cover_bot": 40.0,
        "db_bot": 20.0,
        "nb_bot": 4.0,
        "rowgap_bot": 0.0,
        "lig_d": 10.0,
    }


def test_design_action_resolver_accepts_mapping_like_state() -> None:
    state = SessionStateLike(_bending_state())
    actions = resolve_design_actions_from_state(state)
    assert actions["Mu"] == 50.0
    assert actions["Mu_pos"] == 50.0
    assert actions["has_sagging_case"] is True
    assert actions["source"] == "manual_uls"

    updates = derive_design_action_session_updates(state)
    assert updates["Mu_star"] == 50.0
    assert updates["Mu_star_kNm_signed"] == 50.0


def test_bending_summary_accepts_streamlit_session_state_like_mapping() -> None:
    state = SessionStateLike(_bending_state())
    pack = build_bending_check_rows_from_state(state)
    rows = build_bending_clickable_summary_rows(pack["rows"])
    uids = [row["uid"] for row in rows]

    assert "bend_strength_pos" in uids
    assert "bend_service_moment" in uids
    primary = next(row for row in rows if row.get("is_primary"))
    assert primary["uid"] == "bend_strength_pos"
    assert primary["action"] == "Mu*(+) = 50.0 kNm"
    assert primary["status"] == "PASS"
    assert pack["summary_Mu_star_kNm"] == 50.0


def test_bending_page_keeps_direct_session_state_summary_call() -> None:
    source = (ROOT / "bending_page.py").read_text(encoding="utf-8")
    assert "build_bending_check_rows_from_state(st.session_state)" in source


def main() -> int:
    test_design_action_resolver_accepts_mapping_like_state()
    test_bending_summary_accepts_streamlit_session_state_like_mapping()
    test_bending_page_keeps_direct_session_state_summary_call()
    print("bending_summary_session_state_mapping_contract: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
