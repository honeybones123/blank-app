from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs_page_modules.session.widget_cache_clear import (  # noqa: E402
    clear_inputs_widget_cache_for_shared_updates,
)


def main() -> int:
    session = {
        "inputs_db_bot_1": 20,
        "inputs_nb_or_s_bot_1": 4,
        "_cached_inputs_db_bot_1": 20,
        "inputs_s_lig": 150,
        "inputs_lig_d": 12,
        "inputs_lig_legs": 2,
        "_hydrated_from_shared_map": {
            "inputs_db_bot_1": 20,
            "inputs_nb_or_s_bot_1": 4,
            "inputs_s_lig": 150,
        },
        "unrelated": "keep",
    }
    cleared = clear_inputs_widget_cache_for_shared_updates(
        session,
        {"db_bot_1": 24, "s_lig": 200},
    )
    assert {
        "inputs_db_bot_1",
        "inputs_nb_or_s_bot_1",
        "inputs_s_lig",
        "inputs_lig_d",
        "inputs_lig_legs",
    }.issubset(cleared)
    assert session["_hydrated_from_shared_map"] == {}
    assert session["unrelated"] == "keep"
    assert not any(key in session for key in cleared)
    print("inputs widget cache clear contract PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
