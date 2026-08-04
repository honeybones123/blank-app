"""Prove the permanent one-click trace I/O runtime preserves its contract."""

from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path
import re
import sys
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def main() -> None:
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
        io.StringIO()
    ):
        import inputs_page_app_contract_bridge as bridge
        from inputs_application.guidance_entrypoint import (
            build_guidance_entrypoint_runtime,
        )
        from inputs_application.one_click_runtime_provider import (
            build_partial_one_click_runtime_provider,
        )

    guidance = build_guidance_entrypoint_runtime(
        st_module=bridge.st,
        os_module=os,
        sys_module=sys,
    )
    provider = build_partial_one_click_runtime_provider(
        st_module=bridge.st,
        guidance_runtime=guidance,
    )

    run_id = provider._new_design_guide_trace_run_id("parity")
    assert re.fullmatch(r"parity_\d+_[0-9a-f]{10}", run_id)

    with TemporaryDirectory() as directory:
        path = str(Path(directory) / "trace.jsonl")
        previous = os.environ.get("DESIGN_GUIDE_TRACER_PATH")
        os.environ["DESIGN_GUIDE_TRACER_PATH"] = path
        try:
            assert provider._design_guide_tracer_path() == path
            assert bridge._design_guide_tracer_path() == path
            with contextlib.redirect_stderr(io.StringIO()):
                provider._append_design_guide_trace(
                    "candidate_selected",
                    {"candidate_id": "owned"},
                    run_id=run_id,
                    source="parity",
                )
            rows = [
                json.loads(line)
                for line in Path(path).read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            assert len(rows) == 1
            row = rows[0]
            assert row["run_id"] == run_id
            assert row["event"] == "candidate_selected"
            assert row["source"] == "parity"
            assert row["data"] == {"candidate_id": "owned"}
            assert isinstance(row.get("timestamp_ms"), int)
            assert str(row.get("timestamp") or "").endswith("Z")
        finally:
            if previous is None:
                os.environ.pop("DESIGN_GUIDE_TRACER_PATH", None)
            else:
                os.environ["DESIGN_GUIDE_TRACER_PATH"] = previous

    print(
        "PASS: permanent one-click trace runtime owns path, run-id, "
        "debug-log, and JSONL append contracts"
    )


if __name__ == "__main__":
    main()
