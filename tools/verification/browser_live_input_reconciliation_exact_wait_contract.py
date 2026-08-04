"""Lock exact-state reconciliation across a temporary Inputs rerun shell."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.verification.helpers import browser_helpers


def main() -> int:
    originals = {
        "_set_number_input": browser_helpers._set_number_input,
        "_commit_number_input_like_user": browser_helpers._commit_number_input_like_user,
        "_input_dom_matches": browser_helpers._input_dom_matches,
        "_wait_for_settled_preclick_state": browser_helpers._wait_for_settled_preclick_state,
    }
    set_labels: list[str] = []
    final_waits: list[tuple[float, float, float]] = []

    try:
        browser_helpers._set_number_input = (
            lambda _page, label, _value: set_labels.append(str(label))
        )
        browser_helpers._commit_number_input_like_user = (
            lambda _page, **_kwargs: ({}, False, "none", {})
        )
        browser_helpers._input_dom_matches = lambda _page, _label, _value: False

        def _passing_final_wait(_page, *, mu, vu, timeout_s, **_kwargs):
            final_waits.append((float(mu), float(vu), float(timeout_s)))
            return {"published": True}, True, {"poll_cycles": 3}

        browser_helpers._wait_for_settled_preclick_state = _passing_final_wait
        state, meta = browser_helpers._apply_live_inputs(object(), mu=639.81, vu=153.86)

        assert state == {"published": True}
        assert set_labels == [browser_helpers.MU_LABEL, browser_helpers.VU_LABEL]
        assert final_waits == [(639.81, 153.86, 75.0)]
        assert meta["mu"]["awaiting_final_exact_state"] is True
        assert meta["vu"]["awaiting_final_exact_state"] is True

        browser_helpers._wait_for_settled_preclick_state = (
            lambda _page, **_kwargs: ({}, False, {"poll_cycles": 10})
        )
        try:
            browser_helpers._apply_live_inputs(object(), mu=639.81, vu=153.86)
        except RuntimeError as exc:
            assert "Combined Mu/Vu edit did not reconcile" in str(exc)
        else:
            raise AssertionError("Exact-state mismatch must remain a hard failure")
    finally:
        for name, value in originals.items():
            setattr(browser_helpers, name, value)

    print("PASS browser_live_input_reconciliation_exact_wait_contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
