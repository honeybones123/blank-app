"""Lock auto-design routing to an explicit typed dependency contract."""

from __future__ import annotations

import ast
from dataclasses import is_dataclass
import io
from pathlib import Path
import sys
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def main() -> None:
    source_path = ROOT / "inputs_page_modules" / "auto_design_routing.py"
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "handle_inputs_auto_design"
    )
    keyword_names = {arg.arg for arg in function.args.kwonlyargs}
    assert "runtime" in keyword_names
    assert "legacy_page" not in keyword_names
    assert "legacy_page" not in source

    from inputs_page_modules.auto_design_routing import (
        AutoDesignRoutingRuntime,
        handle_inputs_auto_design,
    )

    assert is_dataclass(AutoDesignRoutingRuntime)
    assert AutoDesignRoutingRuntime.__dataclass_params__.frozen
    calls: list[tuple] = []
    runtime = AutoDesignRoutingRuntime(
        append_design_guide_trace=lambda *args, **kwargs: calls.append(
            ("trace", args, kwargs)
        ),
        attach_recommendation_envelope=lambda recommendation, **kwargs: recommendation,
        clear_auto_design_runtime_latches=lambda reason: {"reason": reason},
        reconcile_design_action_widgets_with_shared=lambda prefix: [],
        reconcile_inputs_shear_widgets_with_shared=lambda: [],
        resolve_design_actions_from_state=lambda state: {},
        resolved_inputs_summary_state=lambda: ({}, {}),
        run_one_click_auto_design=lambda **kwargs: {},
        set_design_guide_live_breadcrumb=lambda label, extra=None: calls.append(
            ("breadcrumb", label, extra)
        ),
        shared_state_snapshot=lambda: {},
    )
    st_module = SimpleNamespace(
        session_state={},
        rerun=lambda: calls.append(("rerun",)),
    )
    handle_inputs_auto_design(
        st_module=st_module,
        stderr=io.StringIO(),
        time_module=SimpleNamespace(time=lambda: 1.0),
        runtime=runtime,
        auto_design_auto_invoke_key="_invoke",
        auto_design_request_source_key="_source",
        record_rerun_trigger_fn=lambda *args, **kwargs: None,
        persist_active_beam_from_shared_fn=lambda: None,
        persist_state_snapshot_fn=lambda: None,
    )
    assert calls == [("breadcrumb", "DG HANDLE AUTO DESIGN ENTRY", None)]
    print(
        "PASS: auto-design route uses a frozen explicit runtime and preserves "
        "the idle transaction"
    )


if __name__ == "__main__":
    main()
