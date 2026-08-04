"""Prove the live Design Guide coordinator dependency set is complete."""

from __future__ import annotations

import ast
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    from inputs_application.page_runtime import build_inputs_page_runtime
    from inputs_page_modules.design_guide import current_coordinators

    build_inputs_page_runtime()
    provider = current_coordinators._CURRENT_COORDINATOR_PROVIDER
    required = tuple(
        current_coordinators._CURRENT_COORDINATOR_PROVIDER_NAMES
    )
    missing = []
    for name in required:
        try:
            getattr(provider, name)
        except AttributeError:
            missing.append(name)
    assert not missing, f"missing Design Guide runtime dependencies: {missing}"

    support_path = (
        ROOT
        / "inputs_application"
        / "page_runtime"
        / "design_guide_runtime_support.py"
    )
    support_source = support_path.read_text(encoding="utf-8")
    ast.parse(support_source)
    assert "artifacts" not in support_source
    assert "legacy_inputs_page_removed" not in support_source
    print(
        "PASS: all "
        f"{len(required)} live Design Guide coordinator dependencies resolve "
        "from permanent runtime modules; production has no archived-page import"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
