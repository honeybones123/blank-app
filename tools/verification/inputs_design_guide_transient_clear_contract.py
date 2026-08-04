from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import inputs_page_app_contracts as contracts  # noqa: E402
from inputs_page_modules.design_guide.transient_clear import (  # noqa: E402
    clear_design_guide_transient_ui_state,
)


def main() -> int:
    keys = (
        contracts.DESIGN_GUIDE_APPLY_BANNER_KEY,
        contracts.DESIGN_GUIDE_APPLY_BANNER_META_KEY,
        contracts.DESIGN_GUIDE_PENDING_STEP_CTX_KEY,
        contracts.DESIGN_GUIDE_DEBUG_BUNDLE_KEY,
        contracts.DESIGN_GUIDE_RECO_TRACE_KEY,
        contracts.DESIGN_GUIDE_RANK_TRACE_KEY,
        contracts.DESIGN_GUIDE_STEP_HISTORY_KEY,
        contracts.DESIGN_GUIDE_FIRST_TARGET_BAND_STEP_KEY,
        contracts.DESIGN_GUIDE_HISTORY_ANCHOR_KEY,
    )
    session = {key: "stale" for key in keys}
    session["unrelated"] = "keep"
    cleared = clear_design_guide_transient_ui_state(
        session,
        clear_history=True,
        preserve_apply_banner=False,
    )
    assert set(keys).issubset(cleared)
    assert not any(key in session for key in keys)
    assert session["unrelated"] == "keep"
    print("inputs Design Guide transient clear contract PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
