"""Deterministic, program-owned identifiers for DeepResearch contracts."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import Any


ID_PREFIXES = frozenset({"task", "brief", "approval", "subtask", "source", "evidence", "claim", "citation", "run", "event", "operation", "attempt", "plan", "policy", "runtime"})
ID_HEX_LENGTH = 24


def _canonicalize(value: Any) -> Any:
    if isinstance(value, Enum):
        return _canonicalize(value.value)
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None or value.utcoffset().total_seconds() != 0:
            raise ValueError("datetime must be timezone-aware UTC")
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("Decimal must be finite")
        return format(value, "f")
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("float must be finite")
        return value
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise TypeError("canonical JSON object keys must be strings")
        return {key: _canonicalize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_canonicalize(item) for item in value]
    raise TypeError(f"unsupported canonical JSON value: {type(value).__name__}")


def canonical_json_bytes(value: Any) -> bytes:
    """Serialize one deterministic UTF-8 JSON value without a trailing newline."""
    normalized = _canonicalize(value)
    return json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def canonical_json(value: Any) -> str:
    """Serialize semantic input deterministically; callers must exclude runtime-only data."""
    return canonical_json_bytes(value).decode("utf-8")


def sha256_hex(value: str | bytes) -> str:
    """Return a full SHA-256 digest for stable content identity."""
    data = value.encode("utf-8") if isinstance(value, str) else value
    return hashlib.sha256(data).hexdigest()


def make_stable_id(kind: str, semantic_input: Any) -> str:
    """Create a deterministic type-prefixed ID; its truncation is not authentication."""
    if kind not in ID_PREFIXES:
        raise ValueError(f"unsupported DeepResearch ID kind: {kind}")
    return f"dr-{kind}-{sha256_hex(canonical_json_bytes(semantic_input))[:ID_HEX_LENGTH]}"
