from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import inputs_page_app_contract_bridge as bridge  # noqa: E402
from inputs_application.engineering_predicates import (  # noqa: E402
    parse_util_value,
    shear_demands_negligible,
    shear_reinforcement_is_active,
)


def main() -> int:
    for value in (None, "", "—", 0, 0.91, "1.23", "bad"):
        assert parse_util_value(value) == bridge._parse_util_value(value)
    for state in (
        None,
        {},
        {"lig_legs": 0, "lig_d": 0, "s_lig": 200},
        {"lig_legs": 2, "lig_d": 10, "s_lig": 200},
        {"lig_legs": "bad", "lig_d": 10, "s_lig": 200},
    ):
        assert shear_reinforcement_is_active(state) == bridge._shear_reinforcement_is_active(state)
    for actions in (
        None,
        {},
        {"Vu": 0.0, "Tu": 0.0},
        {"Vu": 10.0, "Tu": 0.0},
        {"Vu": "bad", "Tu": 0.0},
    ):
        assert shear_demands_negligible(actions) == bridge._shear_demands_negligible(actions)
    print("inputs application engineering predicates parity PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
