"""Prove application-owned shear normalization and reconciliation parity."""

from __future__ import annotations

import contextlib
import copy
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
        from inputs_application.shear_state_normalization import (
            normalize_invalid_shear_state_updates,
        )
        from inputs_application.shear_widget_reconciliation import (
            ShearWidgetReconciliationRuntime,
            reconcile_shear_widgets_with_shared,
        )

    cases = (
        ({"lig_legs": 0, "lig_d": 12, "s_lig": 100.0}, {}),
        ({"lig_legs": 2, "lig_d": 0, "s_lig": 200.0}, {}),
        ({"lig_legs": 2, "lig_d": 10, "s_lig": 0.0}, {}),
        (
            {"lig_legs": 2, "lig_d": 10, "s_lig": 200.0},
            {"lig_legs": 0, "lig_d": 10, "s_lig": 100.0},
        ),
        (
            {"lig_legs": 0, "lig_d": 0, "s_lig": 200.0},
            {"lig_legs": 2, "lig_d": 0, "s_lig": 0.0},
        ),
    )
    for base, updates in cases:
        expected = bridge._normalise_invalid_shear_state_updates(
            copy.deepcopy(base),
            copy.deepcopy(updates),
            source="parity",
        )
        actual = normalize_invalid_shear_state_updates(
            copy.deepcopy(base),
            copy.deepcopy(updates),
            source="parity",
        )
        assert actual == expected, (base, updates, actual, expected)

    shared = {"lig_legs": 0, "lig_d": 0, "s_lig": 200.0}
    writes: list[tuple[str, object, str]] = []
    seeds: list[str] = []

    def set_shared(key: str, value: object, *, source: str) -> None:
        shared[key] = value
        writes.append((key, value, source))

    changed = reconcile_shear_widgets_with_shared(
        session_state={
            "inputs_lig_d": 0,
            "inputs_lig_legs": 2,
            "inputs_s_lig": 0.0,
        },
        runtime=ShearWidgetReconciliationRuntime(
            append_trace=lambda *args, **kwargs: None,
            request_widget_seed=seeds.append,
            set_shared=set_shared,
            shared_state_snapshot=lambda: dict(shared),
        ),
    )
    assert changed == ["lig_legs", "lig_d"], changed
    assert shared == {"lig_legs": 2, "lig_d": 10, "s_lig": 200.0}, shared
    assert seeds == ["handle_auto_design:inputs_shear_reconcile"], seeds
    print(
        "PASS: shear normalization has exact 5/5 bridge parity and the typed "
        "reconciliation transaction is application-owned"
    )


if __name__ == "__main__":
    main()
