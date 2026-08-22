"""Bounded presentation cache for the Bending diagram bundle.

The cache contains only serialised Plotly figure specifications.  It never
publishes engineering values and is never read by a calculation.  Callers
must resolve authoritative engineering state first, build deterministic
fingerprints from that state, and then use this module as a presentation
lookup.
"""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping, Sequence
import hashlib
import json
import math
from typing import Any


BENDING_DIAGRAM_CACHE_KEY = "_bending_diagram_bundle_cache_v1"
BENDING_DIAGRAM_CACHE_METRICS_KEY = "_bending_diagram_bundle_cache_metrics_v1"

_COMPONENT_LIMITS = {
    "section": 9,
    "side": 6,
    "moment": 6,
}
_BUNDLE_LIMIT = 4


def _canonical(value: Any) -> Any:
    """Return a deterministic JSON-compatible projection of ``value``."""

    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if math.isnan(value):
            return "NaN"
        if math.isinf(value):
            return "Infinity" if value > 0 else "-Infinity"
        return value
    if isinstance(value, Mapping):
        return {
            str(key): _canonical(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return sorted((_canonical(item) for item in value), key=repr)
    tolist = getattr(value, "tolist", None)
    if callable(tolist):
        try:
            return _canonical(tolist())
        except Exception:
            pass
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return [_canonical(item) for item in value]
    return str(value)


def _fingerprint(kind: str, payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        {
            "kind": str(kind),
            "version": 1,
            "payload": _canonical(payload),
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def section_stress_strain_fingerprint(payload: Mapping[str, Any]) -> str:
    return _fingerprint("bending-section-stress-strain", payload)


def side_view_fingerprint(payload: Mapping[str, Any]) -> str:
    return _fingerprint("bending-side-view", payload)


def bending_moment_fingerprint(payload: Mapping[str, Any]) -> str:
    return _fingerprint("bending-moment", payload)


def bending_diagram_bundle_fingerprint(
    *,
    section_fingerprints: Mapping[str, str],
    side_fingerprints: Mapping[str, str],
    moment_fingerprint: str,
) -> str:
    return _fingerprint(
        "bending-diagram-bundle",
        {
            "section": dict(section_fingerprints),
            "side": dict(side_fingerprints),
            "moment": str(moment_fingerprint),
        },
    )


def _new_cache() -> dict[str, Any]:
    return {
        "components": {
            kind: {"entries": {}, "order": []}
            for kind in _COMPONENT_LIMITS
        },
        "bundles": {"entries": {}, "order": []},
    }


def _cache(state: MutableMapping[str, Any]) -> dict[str, Any]:
    current = state.get(BENDING_DIAGRAM_CACHE_KEY)
    if not isinstance(current, dict):
        current = _new_cache()
        state[BENDING_DIAGRAM_CACHE_KEY] = current
    current.setdefault("components", {})
    for kind in _COMPONENT_LIMITS:
        current["components"].setdefault(kind, {"entries": {}, "order": []})
    current.setdefault("bundles", {"entries": {}, "order": []})
    return current


def _metric(state: MutableMapping[str, Any], key: str) -> None:
    metrics = dict(state.get(BENDING_DIAGRAM_CACHE_METRICS_KEY) or {})
    metrics[key] = int(metrics.get(key, 0) or 0) + 1
    state[BENDING_DIAGRAM_CACHE_METRICS_KEY] = metrics


def cache_metrics(state: Mapping[str, Any]) -> dict[str, int]:
    return {
        str(key): int(value or 0)
        for key, value in dict(
            state.get(BENDING_DIAGRAM_CACHE_METRICS_KEY) or {}
        ).items()
    }


def _touch(bucket: dict[str, Any], fingerprint: str) -> None:
    entries = bucket.setdefault("entries", {})
    order = [
        str(value)
        for value in bucket.setdefault("order", [])
        if str(value) in entries and str(value) != fingerprint
    ]
    order.append(fingerprint)
    bucket["order"] = order


def get_figure_json(
    state: MutableMapping[str, Any],
    *,
    kind: str,
    fingerprint: str,
) -> str | None:
    if kind not in _COMPONENT_LIMITS:
        raise ValueError(f"unsupported Bending diagram cache kind: {kind}")
    _metric(state, f"{kind}.lookup")
    bucket = _cache(state)["components"][kind]
    value = bucket["entries"].get(fingerprint)
    if not isinstance(value, str) or not value:
        _metric(state, f"{kind}.miss")
        return None
    _touch(bucket, fingerprint)
    _metric(state, f"{kind}.hit")
    return value


def put_figure_json(
    state: MutableMapping[str, Any],
    *,
    kind: str,
    fingerprint: str,
    figure_json: str,
) -> None:
    if kind not in _COMPONENT_LIMITS:
        raise ValueError(f"unsupported Bending diagram cache kind: {kind}")
    if not isinstance(figure_json, str) or not figure_json:
        raise ValueError("figure_json must be a non-empty Plotly JSON string")
    bucket = _cache(state)["components"][kind]
    bucket["entries"][fingerprint] = figure_json
    _touch(bucket, fingerprint)
    while len(bucket["order"]) > _COMPONENT_LIMITS[kind]:
        evicted = bucket["order"].pop(0)
        bucket["entries"].pop(evicted, None)
    _metric(state, f"{kind}.store")


def bundle_manifest(
    *,
    section_fingerprints: Mapping[str, str],
    side_fingerprints: Mapping[str, str],
    moment_fingerprint: str,
) -> dict[str, Any]:
    return {
        "section": {
            str(state): str(fingerprint)
            for state, fingerprint in section_fingerprints.items()
        },
        "side": {
            str(state): str(fingerprint)
            for state, fingerprint in side_fingerprints.items()
        },
        "moment": str(moment_fingerprint),
    }


def put_bundle_manifest(
    state: MutableMapping[str, Any],
    *,
    fingerprint: str,
    manifest: Mapping[str, Any],
) -> None:
    bucket = _cache(state)["bundles"]
    bucket["entries"][fingerprint] = _canonical(dict(manifest))
    _touch(bucket, fingerprint)
    while len(bucket["order"]) > _BUNDLE_LIMIT:
        evicted = bucket["order"].pop(0)
        bucket["entries"].pop(evicted, None)
    _metric(state, "bundle.store")


def get_bundle_manifest(
    state: MutableMapping[str, Any],
    *,
    fingerprint: str,
) -> dict[str, Any] | None:
    _metric(state, "bundle.lookup")
    bucket = _cache(state)["bundles"]
    manifest = bucket["entries"].get(fingerprint)
    if not isinstance(manifest, dict):
        _metric(state, "bundle.miss")
        return None
    section = manifest.get("section")
    side = manifest.get("side")
    required = []
    if isinstance(section, dict):
        required.extend(("section", str(value)) for value in section.values())
    if isinstance(side, dict):
        required.extend(("side", str(value)) for value in side.values())
    required.append(("moment", str(manifest.get("moment") or "")))
    components = _cache(state)["components"]
    if not required or any(
        not fingerprint_value
        or fingerprint_value not in components[kind]["entries"]
        for kind, fingerprint_value in required
    ):
        bucket["entries"].pop(fingerprint, None)
        bucket["order"] = [
            value for value in bucket["order"] if value != fingerprint
        ]
        _metric(state, "bundle.miss")
        return None
    _touch(bucket, fingerprint)
    _metric(state, "bundle.hit")
    return dict(manifest)


__all__ = [
    "BENDING_DIAGRAM_CACHE_KEY",
    "BENDING_DIAGRAM_CACHE_METRICS_KEY",
    "bending_diagram_bundle_fingerprint",
    "bending_moment_fingerprint",
    "bundle_manifest",
    "cache_metrics",
    "get_bundle_manifest",
    "get_figure_json",
    "put_bundle_manifest",
    "put_figure_json",
    "section_stress_strain_fingerprint",
    "side_view_fingerprint",
]
