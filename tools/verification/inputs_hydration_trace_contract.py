from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs_page_modules.session.hydration_trace import inputs_hydration_trace_log  # noqa: E402


def main() -> int:
    assert inputs_hydration_trace_log("before", state={"b": 300}) is None
    assert inputs_hydration_trace_log("after", changed=True) is None
    print("inputs hydration trace no-op contract PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
