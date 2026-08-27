"""Deterministic, program-owned identifiers for DeepResearch contracts."""

from __future__ import annotations

import hashlib
import json
from typing import Any


ID_PREFIXES = frozenset({"task", "brief", "approval", "subtask", "source", "evidence", "claim", "citation"})
ID_HEX_LENGTH = 24


def canonical_json(value: Any) -> str:
    """Serialize semantic input deterministically; callers must exclude runtime-only data."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha256_hex(value: str | bytes) -> str:
    """Return a full SHA-256 digest for stable content identity."""
    data = value.encode("utf-8") if isinstance(value, str) else value
    return hashlib.sha256(data).hexdigest()


def make_stable_id(kind: str, semantic_input: Any) -> str:
    """Create a deterministic type-prefixed ID; its truncation is not authentication."""
    if kind not in ID_PREFIXES:
        raise ValueError(f"unsupported DeepResearch ID kind: {kind}")
    return f"dr-{kind}-{sha256_hex(canonical_json(semantic_input))[:ID_HEX_LENGTH]}"
