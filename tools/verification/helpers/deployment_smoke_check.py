"""HTTP-level release smoke checks for the deployed Runtime shell.

This deliberately does not execute or mutate the application.  It verifies
that the artifact served by the deployment is a healthy Runtime shell and
that its cache metadata is newer than the release being accepted.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import json
from pathlib import Path
import time
from typing import Any, Callable
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DEFAULT_PAGES = ("inputs", "design", "bending", "shear", "creep", "shrinkage", "crack", "deflection")
# The first HTTP response is Streamlit's generic shell; page headings arrive
# over the websocket and are covered by the live interaction audit.
SHELL_MARKERS = ("Streamlit",)
ERROR_MARKERS = ("Traceback", "ImportError", "ModuleNotFoundError", "stException")


def _parse_http_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        try:
            return parsedate_to_datetime(value).astimezone(timezone.utc)
        except (TypeError, ValueError, IndexError):
            return None


def check_response(
    *,
    url: str,
    body: str,
    status: int,
    headers: dict[str, str],
    elapsed_ms: float,
    minimum_last_modified: datetime | None = None,
    expected_etag: str | None = None,
    require_release_metadata: bool = False,
) -> dict[str, Any]:
    normalized_headers = {str(key).lower(): str(value) for key, value in headers.items()}
    content_type = normalized_headers.get("content-type", "")
    etag = normalized_headers.get("etag")
    last_modified = normalized_headers.get("last-modified")
    errors = [marker for marker in ERROR_MARKERS if marker in body]
    missing_markers = [marker for marker in SHELL_MARKERS if marker not in body]
    parsed_last_modified = _parse_http_date(last_modified)
    failures: list[str] = []
    if status != 200:
        failures.append(f"http_status:{status}")
    if "text/html" not in content_type.lower():
        failures.append("content_type_not_html")
    if errors:
        failures.append("error_marker:" + ",".join(errors))
    if missing_markers:
        failures.append("missing_shell_marker:" + ",".join(missing_markers))
    if require_release_metadata and not etag:
        failures.append("missing_etag")
    if require_release_metadata and (not last_modified or parsed_last_modified is None):
        failures.append("missing_or_invalid_last_modified")
    if minimum_last_modified and (parsed_last_modified is None or parsed_last_modified < minimum_last_modified):
        failures.append("stale_last_modified")
    if expected_etag and etag != expected_etag:
        failures.append("etag_mismatch")
    return {
        "url": url,
        "ok": not failures,
        "status": status,
        "content_type": content_type,
        "etag": etag,
        "last_modified": last_modified,
        "elapsed_ms": round(elapsed_ms, 3),
        "failures": failures,
    }


def check_page(
    base_url: str,
    page: str,
    *,
    opener: Callable[..., Any] = urlopen,
    minimum_last_modified: datetime | None = None,
    expected_etag: str | None = None,
    require_release_metadata: bool = False,
) -> dict[str, Any]:
    url = base_url.rstrip("/") + "/?" + urlencode({"page": page, "fresh": "1", "cid": "deployment-smoke"})
    started = time.perf_counter()
    try:
        request = Request(url, headers={"Cache-Control": "no-cache"})
        with opener(request, timeout=30) as response:
            body = response.read().decode("utf-8", errors="replace")
            headers = {str(k): str(v) for k, v in response.headers.items()}
            return check_response(
                url=url,
                body=body,
                status=int(response.status),
                headers=headers,
                elapsed_ms=(time.perf_counter() - started) * 1000.0,
                minimum_last_modified=minimum_last_modified,
                expected_etag=expected_etag,
                require_release_metadata=require_release_metadata,
            )
    except Exception as exc:
        return {"url": url, "ok": False, "elapsed_ms": round((time.perf_counter() - started) * 1000.0, 3), "failures": [f"request:{type(exc).__name__}:{exc}"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--pages", nargs="+", default=DEFAULT_PAGES, choices=DEFAULT_PAGES)
    parser.add_argument("--minimum-last-modified", help="ISO-8601 timestamp; reject older artifacts")
    parser.add_argument("--expected-etag")
    parser.add_argument("--require-release-metadata", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    minimum = _parse_http_date(args.minimum_last_modified)
    pages = [check_page(args.base_url, page, minimum_last_modified=minimum, expected_etag=args.expected_etag, require_release_metadata=args.require_release_metadata) for page in args.pages]
    result = {"ok": all(item["ok"] for item in pages), "base_url": args.base_url, "pages": pages}
    rendered = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
