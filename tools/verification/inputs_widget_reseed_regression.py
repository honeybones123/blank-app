"""Focused regression for post-Apply Inputs widget reseeding.

This is intentionally source-level: importing the Streamlit page would create
widgets and is not needed to prove the destructive queue behavior is absent.
"""

from __future__ import annotations

import ast
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
STATE_HELPERS = ROOT / "state_and_helpers.py"
COMMON = ROOT / "inputs_application" / "page_runtime" / "common.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"


def _function_source(path: Path, name: str) -> str:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return ast.get_source_segment(source, node) or ""
    raise AssertionError(f"missing function {name} in {path}")


def main() -> int:
    queue_source = _function_source(COMMON, "_queue_inputs_refresh")
    finalize_source = _function_source(STATE_HELPERS, "finalize_auto_design_publish")

    checks = {
        "shared_queue_does_not_clear_reseed_flag":
            'pop("_force_inputs_widget_reseed_once"' not in queue_source,
        "finalizer_sets_generic_reseed_flag":
            'st.session_state["_force_inputs_widget_reseed_once"] = True' in finalize_source,
        "geometry_and_width_keys_are_shared": all(
            needle in STATE_HELPERS.read_text(encoding="utf-8")
            for needle in ('"b":', '"D":', '"optimisation_lock_width"')
        ),
    }
    failures = [name for name, passed in checks.items() if not passed]
    result = {
        "status": "FAIL" if failures else "PASS",
        "checks": checks,
        "failures": failures,
        "scope": "post-Apply widget reseed and summary/diagram synchronization",
        "behavior_change_intended": False,
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    path = ARTIFACT_DIR / f"inputs_widget_reseed_regression_{stamp}.json"
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
