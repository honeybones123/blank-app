from __future__ import annotations

import importlib.util
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "verification" / "helpers" / "deployment_smoke_check.py"


def _module():
    spec = importlib.util.spec_from_file_location("deployment_smoke_check", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _headers():
    return {
        "Content-Type": "text/html; charset=utf-8",
        "ETag": '"release-1"',
        "Last-Modified": "2026-08-16T00:00:00Z",
    }


def test_healthy_shell_requires_no_error_markers():
    module = _module()
    result = module.check_response(
        url="https://example.test/?page=inputs",
        body="<html>Streamlit StructuralBase Beam Inputs</html>",
        status=200,
        headers=_headers(),
        elapsed_ms=12.5,
        minimum_last_modified=datetime(2026, 8, 15, tzinfo=timezone.utc),
    )
    assert result["ok"] is True


def test_stale_or_mismatched_artifact_fails_closed():
    module = _module()
    result = module.check_response(
        url="https://example.test/",
        body="<html>Streamlit StructuralBase Beam Inputs</html>",
        status=200,
        headers=_headers(),
        elapsed_ms=1.0,
        minimum_last_modified=datetime(2026, 8, 17, tzinfo=timezone.utc),
        expected_etag='"release-2"',
    )
    assert result["ok"] is False
    assert "stale_last_modified" in result["failures"]
    assert "etag_mismatch" in result["failures"]


def test_deployment_errors_are_reported():
    module = _module()
    result = module.check_response(
        url="https://example.test/",
        body="Traceback ImportError",
        status=500,
        headers={"Content-Type": "text/plain"},
        elapsed_ms=3.0,
    )
    assert result["ok"] is False
    assert "http_status:500" in result["failures"]
    assert any(item.startswith("error_marker:") for item in result["failures"])
