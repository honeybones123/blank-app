from __future__ import annotations

from pathlib import Path
import sys

import inputs_v2

from runtime_source_bootstrap import (
    LOCAL_INPUTS_V2_SRC,
    RUNTIME_ROOT,
    prefer_runtime_checkout_sources,
)


def test_runtime_and_tests_use_the_v2_source_from_this_checkout() -> None:
    expected_root = LOCAL_INPUTS_V2_SRC.resolve()
    imported_root = Path(inputs_v2.__file__).resolve().parents[1]

    assert imported_root == expected_root
    # Pytest may temporarily prepend the directory of a separately collected
    # package test. Re-applying the runtime boundary must deterministically
    # restore the checkout-owned source ordering.
    prefer_runtime_checkout_sources()
    assert Path(sys.path[0]).resolve() == expected_root
    assert Path(sys.path[1]).resolve() == RUNTIME_ROOT.resolve()


def test_source_preference_is_idempotent_and_has_one_owner() -> None:
    prefer_runtime_checkout_sources()
    prefer_runtime_checkout_sources()

    assert sys.path.count(str(LOCAL_INPUTS_V2_SRC)) == 1
    assert sys.path.count(str(RUNTIME_ROOT)) == 1

    app_source = (RUNTIME_ROOT / "app.py").read_text(encoding="utf-8")
    test_bootstrap = (RUNTIME_ROOT / "conftest.py").read_text(encoding="utf-8")
    assert "prefer_runtime_checkout_sources()" in app_source
    assert "prefer_runtime_checkout_sources()" in test_bootstrap
    assert "LOCAL_INPUTS_SRC" not in app_source
    assert "sys.path.insert" not in app_source
