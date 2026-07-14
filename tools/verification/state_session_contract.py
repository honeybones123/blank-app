from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import jump_nav
import session_state_final_log
import state_and_helpers


class _AttrDict(dict):
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError as exc:
            raise AttributeError(key) from exc

    def __setattr__(self, key, value):
        self[key] = value


def test_beam_status_contracts() -> None:
    assert state_and_helpers.normalize_beam_status("PASS") == "PASS"
    assert state_and_helpers.normalize_beam_status("fail") == "FAIL"
    assert state_and_helpers.normalize_beam_status("warning") == "WARN"
    assert state_and_helpers.normalize_beam_status("", utilisation=0.75) == "PASS"
    assert state_and_helpers.normalize_beam_status("", utilisation=0.95) == "WARN"
    assert state_and_helpers.normalize_beam_status("", utilisation=1.01) == "FAIL"
    assert state_and_helpers.normalize_beam_status("", pass_flag=False) == "FAIL"

    assert state_and_helpers.get_beam_overall_status({"strength_status": "PASS", "detailing_status": "PASS"}) == "PASS"
    assert state_and_helpers.get_beam_overall_status({"strength_status": "FAIL", "detailing_status": "PASS"}) == "FAIL"
    assert state_and_helpers.get_beam_overall_status({"bending_status": "PASS", "shear_status": "WARN"}) == "WARN"

    summary = state_and_helpers.make_not_run_beam_summary()
    assert summary["overall_status"] == "NOT_RUN"
    assert summary["strength_status"] == "NOT_RUN"
    assert summary["detailing_status"] == "NOT_RUN"


def test_longitudinal_row_key_contracts() -> None:
    assert state_and_helpers.LONGITUDINAL_REO_MAX_ROWS == 4
    assert state_and_helpers._longitudinal_row_key("bottom", 2, "bars") == "bottom_row_2_bars"
    keys = state_and_helpers._longitudinal_row_param_keys("top")
    assert "top_row_1_bars" in keys
    assert "top_row_4_dia" in keys
    tab_keys = state_and_helpers._longitudinal_row_tab_keys("bending", "bottom")
    assert tab_keys["bending_bottom_row_1_bars"] == "bottom_row_1_bars"


def test_fingerprint_and_cache_contracts() -> None:
    a = state_and_helpers.stable_fingerprint_for_payload({"b": 2, "a": [1, {"x": 3}]})
    b = state_and_helpers.stable_fingerprint_for_payload({"a": [1, {"x": 3}], "b": 2})
    assert a == b
    assert isinstance(a, tuple)


def test_session_state_final_log_counter_contracts() -> None:
    original_session_state = session_state_final_log.st.session_state
    try:
        session_state_final_log.st.session_state = {"_session_state_final_log_enabled": True}
        counters = session_state_final_log.get_ssl_counters()
        assert counters["router_hydrate_count"] == 0
        session_state_final_log.ssl_increment("router_hydrate_count", 2)
        assert session_state_final_log.get_ssl_counters()["router_hydrate_count"] == 2
        session_state_final_log.ssl_set_flag("render_time_shear_normalisation", True)
        assert session_state_final_log.get_ssl_counters()["render_time_shear_normalisation"] is True
    finally:
        session_state_final_log.st.session_state = original_session_state


def test_jump_nav_query_contract() -> None:
    original_session_state = jump_nav.st.session_state
    original_query_params = jump_nav.st.query_params
    try:
        jump_nav.st.session_state = _AttrDict()
        jump_nav.st.query_params = {"page": "bending", "jump": "bend_strength_pos"}
        assert jump_nav.get_jump_uid() == "bend_strength_pos"
        assert jump_nav.st.session_state["jump_to"] == "bend_strength_pos"
        assert jump_nav.st.session_state["step_open_bend_strength_pos"] is True
        assert "page" in jump_nav.st.query_params
        assert "jump" not in jump_nav.st.query_params

        assert jump_nav.get_jump_uid() == "bend_strength_pos"
    finally:
        jump_nav.st.session_state = original_session_state
        jump_nav.st.query_params = original_query_params


def main() -> int:
    test_beam_status_contracts()
    test_longitudinal_row_key_contracts()
    test_fingerprint_and_cache_contracts()
    test_session_state_final_log_counter_contracts()
    test_jump_nav_query_contract()
    print("state_session_contract: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
