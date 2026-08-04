"""Lock natural user-facing locked-geometry wording in the browser gate."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.browser_live_design_guide_fuzz_verifier import (  # noqa: E402
    _visible_text_has_lock_blocker,
)


def main() -> int:
    assert _visible_text_has_lock_blocker("Geometry is locked.")
    assert _visible_text_has_lock_blocker("Section depth is locked.")
    assert _visible_text_has_lock_blocker("Section width is locked.")
    assert not _visible_text_has_lock_blocker(
        "No repair was found, but no user constraint is identified."
    )
    print(
        "PASS: browser gate recognises natural locked-geometry wording "
        "without weakening the exact-lock requirement"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
