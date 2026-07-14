from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import auth_bridge
import auth_streamlit
import projects_store
import supabase_client


class _FakeResult:
    def __init__(self, data):
        self.data = data
        self.error = None


class _FakeQuery:
    def __init__(self):
        self.operations: list[tuple[str, object]] = []
        self.payload: dict | None = None

    def insert(self, row):
        self.operations.append(("insert", dict(row)))
        self.payload = dict(row)
        return self

    def update(self, patch):
        self.operations.append(("update", dict(patch)))
        self.payload = dict(patch)
        return self

    def eq(self, key, value):
        self.operations.append(("eq", (key, value)))
        return self

    def execute(self):
        return _FakeResult([dict(self.payload or {}, id="fake-project")])


class _FakeSupabase:
    def __init__(self):
        self.table_names: list[str] = []
        self.last_query: _FakeQuery | None = None

    def table(self, name):
        self.table_names.append(name)
        self.last_query = _FakeQuery()
        return self.last_query


def _without_supabase_env() -> dict[str, str | None]:
    keys = [
        "SUPABASE_URL",
        "SUPABASE_SERVICE_ROLE_KEY",
        "SUPABASE_ANON_KEY",
        "SUPABASE_PROJECTS_TABLE",
    ]
    original = {key: os.environ.get(key) for key in keys}
    for key in keys:
        os.environ.pop(key, None)
    return original


def _restore_env(original: dict[str, str | None]) -> None:
    for key, value in original.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def test_missing_env_contracts() -> None:
    original = _without_supabase_env()
    try:
        assert auth_bridge.get_supabase_admin() is None
        assert auth_streamlit.get_user_id_from_token() == ""
        try:
            supabase_client.get_supabase()
        except RuntimeError as exc:
            assert "Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY" in str(exc)
        else:
            raise AssertionError("get_supabase should fail without required env vars")
        assert supabase_client.projects_table_name() == "projects"
    finally:
        _restore_env(original)


def test_projects_table_name_contract() -> None:
    original = _without_supabase_env()
    try:
        os.environ["SUPABASE_PROJECTS_TABLE"] = "  beam_projects  "
        assert supabase_client.projects_table_name() == "beam_projects"
        os.environ["SUPABASE_PROJECTS_TABLE"] = "   "
        assert supabase_client.projects_table_name() == "projects"
    finally:
        _restore_env(original)


def test_project_module_is_forced_on_create_and_update() -> None:
    fake = _FakeSupabase()
    original_get_supabase = projects_store.get_supabase
    original_table_name = projects_store.projects_table_name
    original_session_state = projects_store.st.session_state
    try:
        projects_store.get_supabase = lambda: fake
        projects_store.projects_table_name = lambda: "projects"
        projects_store.st.session_state = {}

        created = projects_store.create_project(
            user_id="user-1",
            name="Demo",
            payload={"span": 2000},
            meta={},
        )
        assert created["module"] == "beam"
        assert fake.table_names[-1] == "projects"

        projects_store.st.session_state = {"module": " Beam "}
        updated = projects_store.update_project(
            project_id="project-1",
            user_id="user-1",
            payload={"module": "custom", "span": 2400},
            meta={},
        )
        assert updated["module"] == "custom"
    finally:
        projects_store.get_supabase = original_get_supabase
        projects_store.projects_table_name = original_table_name
        projects_store.st.session_state = original_session_state


def test_query_param_user_resolution_uses_safe_none_paths() -> None:
    original_get_admin = auth_bridge.get_supabase_admin
    original_query_params = auth_bridge.st.query_params
    original_session_state = auth_bridge.st.session_state
    try:
        auth_bridge.get_supabase_admin = lambda: None
        auth_bridge.st.query_params = {"sb_access_token": "token"}
        auth_bridge.st.session_state = {}
        assert auth_bridge.resolve_user_from_query_param() is None
        auth_bridge.ensure_logged_in_state()
        assert auth_bridge.st.session_state["sb_user"] is None
        assert "user_id" not in auth_bridge.st.session_state
    finally:
        auth_bridge.get_supabase_admin = original_get_admin
        auth_bridge.st.query_params = original_query_params
        auth_bridge.st.session_state = original_session_state


def main() -> int:
    test_missing_env_contracts()
    test_projects_table_name_contract()
    test_project_module_is_forced_on_create_and_update()
    test_query_param_user_resolution_uses_safe_none_paths()
    print("auth_storage_contract: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
