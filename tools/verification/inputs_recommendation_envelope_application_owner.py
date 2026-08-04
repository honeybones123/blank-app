"""Prove the application-owned recommendation envelope matches compatibility."""

from __future__ import annotations

import contextlib
import io
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def main() -> None:
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
        io.StringIO()
    ):
        import inputs_page_app_contract_bridge as bridge
        from inputs_application.recommendation_envelope import (
            attach_recommendation_envelope,
        )

    cases = (
        (
            {"title": "Ready", "updates": {"D": 650}},
            {"source": "auto_design", "status": "ready"},
        ),
        (
            {"title": "Blocked", "updates": {}},
            {
                "source": "auto_design",
                "status": "blocked",
                "blocked_reason": "unsafe",
                "commit_eligible": False,
                "preview": {"D": 650},
                "audit": {"passed": False},
                "required_domains": {"shear", "bending"},
            },
        ),
        (
            {
                "title": "Resolved",
                "resolved_candidate": {"updates": {"lig_d": 10, "lig_legs": 2}},
            },
            {
                "source": "guidance",
                "status": "ready",
                "required_domains": ["shear"],
            },
        ),
    )
    for recommendation, kwargs in cases:
        expected = bridge._attach_recommendation_envelope(
            recommendation,
            **kwargs,
        )
        actual = attach_recommendation_envelope(recommendation, **kwargs)
        assert actual == expected, (recommendation, actual, expected)
    print("PASS: application recommendation envelope has exact 3/3 parity")


if __name__ == "__main__":
    main()
