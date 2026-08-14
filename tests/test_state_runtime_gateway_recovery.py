from __future__ import annotations

import state_and_helpers
import state_runtime_gateway


def test_application_composition_can_restore_gateway_after_module_reload() -> None:
    previous = state_runtime_gateway._bindings
    try:
        state_runtime_gateway._bindings = None
        assert not state_runtime_gateway.state_runtime_gateway_configured()

        state_and_helpers.ensure_state_runtime_gateway_configured()

        assert state_runtime_gateway.state_runtime_gateway_configured()
        assert state_runtime_gateway._bindings is not None
    finally:
        state_runtime_gateway._bindings = previous
