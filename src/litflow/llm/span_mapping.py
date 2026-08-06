from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass


SAFE_NORMALIZATION_PROFILE = "safe_nfkc_alnum_v1"


@dataclass(frozen=True)
class SpanMapping:
    status: str
    method: str = ""
    start: int | None = None
    end: int | None = None
    evidence_text: str = ""
    occurrence_count: int = 0
    roundtrip_verified: bool = False
    normalization_profile: str = ""
    local_features: tuple[str, ...] = ()
    error_type: str = ""
    message: str = ""


def map_verbatim_span(quote_hint: str, chunk_text: str, *, normalized_matches: list[tuple[int, int]] | None = None) -> SpanMapping:
    """Map one quote hint to one continuous source span without fuzzy matching."""
    if not quote_hint:
        return SpanMapping("not_found", error_type="evidence_anchor_not_found", message="empty quote_hint")
    exact_count = chunk_text.count(quote_hint)
    if exact_count == 1:
        start = chunk_text.index(quote_hint)
        return _success("exact_match", quote_hint, chunk_text, start, start + len(quote_hint), 1)
    if exact_count > 1:
        return _ambiguous("multiple exact matches", exact_count)

    matches = normalized_matches if normalized_matches is not None else normalized_whitespace_matches(quote_hint, chunk_text)
    if len(matches) == 1:
        start, end = matches[0]
        result = _success("normalized_whitespace_match", quote_hint, chunk_text, start, end, 1)
        if result.roundtrip_verified:
            return result
    if len(matches) > 1:
        return _ambiguous("multiple normalized whitespace matches", len(matches))

    safe_matches = safe_span_matches(quote_hint, chunk_text)
    if len(safe_matches) == 1:
        start, end = safe_matches[0]
        result = _success("safe_normalized_match", quote_hint, chunk_text, start, end, 1)
        if result.roundtrip_verified:
            return result
    if len(safe_matches) > 1:
        return _ambiguous("multiple safe normalized matches", len(safe_matches))
    return SpanMapping("not_found", error_type="evidence_anchor_not_found", message="quote_hint not found in declared chunk")


def safe_span_matches(hint: str, text: str) -> list[tuple[int, int]]:
    normalized_hint, _, _ = safe_normalize(hint)
    normalized_text, mapping, _ = safe_normalize(text)
    if not normalized_hint:
        return []
    matches: list[tuple[int, int]] = []
    start = normalized_text.find(normalized_hint)
    while start >= 0:
        end = start + len(normalized_hint)
        matches.append((mapping[start][0], mapping[end - 1][1]))
        start = normalized_text.find(normalized_hint, start + 1)
    return matches


def normalized_whitespace_matches(quote_hint: str, chunk_text: str) -> list[tuple[int, int]]:
    hint_tokens = [match.group(0).casefold() for match in re.finditer(r"\S+", quote_hint)]
    chunk_tokens = [(match.group(0).casefold(), match.start(), match.end()) for match in re.finditer(r"\S+", chunk_text)]
    if not hint_tokens or len(hint_tokens) > len(chunk_tokens):
        return []
    width = len(hint_tokens)
    return [
        (chunk_tokens[index][1], chunk_tokens[index + width - 1][2])
        for index in range(len(chunk_tokens) - width + 1)
        if [token for token, _, _ in chunk_tokens[index : index + width]] == hint_tokens
    ]


def safe_normalize(value: str) -> tuple[str, list[tuple[int, int]], set[str]]:
    flags: set[str] = set()
    chars: list[str] = []
    mapping: list[tuple[int, int]] = []
    index = 0
    while index < len(value):
        char = value[index]
        if char == "\x00":
            flags.add("nul_character")
            index += 1
            continue
        if char == "\u00ad":
            flags.add("soft_hyphen")
            index += 1
            continue
        if char in {"\u200b", "\u200c", "\u200d", "\ufeff"}:
            flags.add("zero_width")
            index += 1
            continue
        if char == "-" and index > 0 and value[index - 1].isalpha():
            next_index = index + 1
            while next_index < len(value) and value[next_index].isspace():
                next_index += 1
            gap = value[index + 1 : next_index]
            if next_index < len(value) and value[next_index].isalpha() and ("\n" in gap or "\r" in gap):
                flags.add("linebreak_dehyphenation")
                index = next_index
                continue
        normalized = unicodedata.normalize("NFKC", char)
        if normalized != char:
            flags.add("unicode_nfkc")
            if char in {"ﬁ", "ﬂ", "ﬀ", "ﬃ", "ﬄ"}:
                flags.add("unicode_ligature")
        for normalized_char in normalized:
            if normalized_char.isalnum():
                chars.append(normalized_char.casefold())
                mapping.append((index, index + 1))
            else:
                if normalized_char in {"'", '"', "-", "–", "—", "‐", "‑"}:
                    flags.add("punctuation_change")
                if not chars or chars[-1] != " ":
                    chars.append(" ")
                    mapping.append((index, index + 1))
        index += 1
    while chars and chars[0] == " ":
        chars.pop(0)
        mapping.pop(0)
    while chars and chars[-1] == " ":
        chars.pop()
        mapping.pop()
    return "".join(chars), mapping, flags


def _success(method: str, hint: str, text: str, start: int, end: int, occurrences: int) -> SpanMapping:
    span = text[start:end] if 0 <= start <= end <= len(text) else ""
    roundtrip = bool(span and text[start:end] == span and safe_normalize(span)[0] == safe_normalize(hint)[0])
    features = tuple(sorted(safe_normalize(hint)[2] | safe_normalize(span)[2]))
    return SpanMapping(
        "ok" if roundtrip else "not_found", method=method if roundtrip else "", start=start if roundtrip else None,
        end=end if roundtrip else None, evidence_text=span if roundtrip else "", occurrence_count=occurrences,
        roundtrip_verified=roundtrip, normalization_profile=SAFE_NORMALIZATION_PROFILE if roundtrip else "",
        local_features=features if roundtrip else (),
        error_type="" if roundtrip else "evidence_anchor_not_found",
        message="" if roundtrip else "safe span round-trip verification failed",
    )


def _ambiguous(message: str, occurrences: int) -> SpanMapping:
    return SpanMapping("ambiguous", occurrence_count=occurrences, error_type="evidence_anchor_ambiguous", message=message)


def span_sha256(mapping: SpanMapping) -> str:
    return hashlib.sha256(mapping.evidence_text.encode("utf-8")).hexdigest() if mapping.evidence_text else ""
