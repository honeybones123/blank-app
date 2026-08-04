"""Lock browser red-screen scanning to browser-facing artifact evidence."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification.browser_red_screen_sentinel import (  # noqa: E402
    browser_red_screen_findings,
)
from tools.verification.design_brain_shared_path_release_lock import (  # noqa: E402
    _browser_surface_only,
)


def main() -> int:
    verifier_diagnostic = {
        "status": "PASS",
        "workflows": [
            {
                "root_cause_candidate": {
                    "traceback": (
                        "Traceback (most recent call last): verifier checkpoint "
                        "write failed"
                    )
                },
                "browser_state": {"body_text": "Inputs page ready"},
            }
        ],
    }
    assert not browser_red_screen_findings(
        _browser_surface_only(verifier_diagnostic)
    )

    rendered_failure = {
        "status": "FAIL",
        "workflows": [
            {
                "browser_state": {
                    "body_text": (
                        "Traceback (most recent call last): rendered app failed"
                    )
                }
            }
        ],
    }
    findings = browser_red_screen_findings(
        _browser_surface_only(rendered_failure)
    )
    assert any(row.get("reason") == "python_traceback" for row in findings)
    print("shared-path browser-surface sentinel contract PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
