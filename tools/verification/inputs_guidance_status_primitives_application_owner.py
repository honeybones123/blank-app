"""Verify application ownership and exact parity of guidance status primitives."""

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
        from inputs_page_modules.guidance_compute import (
            _application_guidance_bucket,
            _application_merge_guidance_state,
            _application_overall_status_from_rows,
            build_guidance_compute_runtime,
        )

    row_cases = (
        [],
        [{"status": "INFO", "is_informational": True}],
        [{"status": "PASS"}],
        [{"status": "CHECK"}],
        [{"status": "FAIL"}],
        [{"status": "OK"}, {"status": "WARN"}],
        [{"status": "PASS"}, {"status": "NG"}],
    )
    for rows in row_cases:
        assert _application_overall_status_from_rows(
            rows
        ) == bridge._overall_status_from_rows(rows)

    bucket_cases = (
        ("START", None),
        ("EFFICIENCY", None),
        ("FAIL", None),
        ("NEAR LIMIT", None),
        ("PASS", 1.01),
        ("PASS", 0.95),
        ("PASS", 0.75),
    )
    for status, util in bucket_cases:
        assert _application_guidance_bucket(
            status,
            util,
        ) == bridge._guidance_bucket(status, util)

    state = {"D": 600.0, "b": 300.0}
    updates = {"D": 650.0, "s_lig": 150.0}
    assert _application_merge_guidance_state(
        state,
        updates,
    ) == bridge._merge_guidance_state(state, updates)

    runtime = build_guidance_compute_runtime(bridge)
    application_callbacks = {
        _application_guidance_bucket,
        _application_merge_guidance_state,
        _application_overall_status_from_rows,
    }
    bound_callbacks = (
        runtime.bending_guidance.guidance_bucket,
        runtime.bending_guidance.overall_status_from_rows,
        runtime.crack_guidance.guidance_bucket,
        runtime.crack_guidance.merge_guidance_state,
        runtime.crack_guidance.overall_status_from_rows,
        runtime.deflection_guidance.guidance_bucket,
        runtime.deflection_guidance.overall_status_from_rows,
        runtime.shear_guidance.guidance_bucket,
        runtime.shear_guidance.overall_status_from_rows,
    )
    assert all(callback in application_callbacks for callback in bound_callbacks)

    print(
        "PASS: 9 runtime bindings use application-owned status primitives "
        "with exact 7/7 row, 7/7 bucket, and merge parity"
    )


if __name__ == "__main__":
    main()
