from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

from litflow.rag.bm25 import _tokenize


def detect_language(text: str) -> dict[str, Any]:
    cjk = sum("\u4e00" <= char <= "\u9fff" for char in text)
    latin = sum(char.isascii() and char.isalpha() for char in text)
    total = max(len(text), 1)
    cjk_ratio = cjk / total
    latin_ratio = latin / total
    if cjk_ratio >= 0.1 and latin_ratio >= 0.02:
        language = "mixed"
    elif cjk_ratio >= 0.1:
        language = "zh"
    else:
        language = "en"
    return {"source_language": language, "cjk_ratio": round(cjk_ratio, 6), "latin_ratio": round(latin_ratio, 6), "detection_rule": "cjk_ratio_0.1_latin_ratio_0.02_v1"}


def mixed_tokenize(text: str, language: str) -> list[str]:
    if language == "en":
        return _tokenize(text)
    technical = re.findall(r"(?:\d+[A-Za-z]|[A-Za-z]\d+)(?:/(?:\d+[A-Za-z]|[A-Za-z]\d+))+|[A-Za-z][A-Za-z0-9]*@\d+(?:\.\d+)?|[A-Za-z][A-Za-z0-9]*(?:-[A-Za-z0-9]+)+|[A-Za-z]+\d+[A-Za-z0-9]*|[A-Za-z]{2,}|\d+(?:\.\d+)?", text)
    chinese = []
    for sequence in re.findall(r"[\u4e00-\u9fff]+", text):
        chinese.extend(sequence[index : index + 2] for index in range(max(len(sequence) - 1, 1)))
    return [token.casefold() for token in [*chinese, *technical] if token]


class MixedBM25Index:
    def __init__(self, passages: list[dict[str, Any]], *, k1: float = 1.5, b: float = 0.75) -> None:
        self.passages = passages
        self.k1 = k1
        self.b = b

    def search_branch(self, query_text: str, source_language: str, *, top_k: int = 10) -> list[dict[str, Any]]:
        branch = [passage for passage in self.passages if passage["source_language"] == source_language]
        tokens = [mixed_tokenize(passage["text"], source_language) for passage in branch]
        query_tokens = mixed_tokenize(query_text, source_language)
        if not branch or not query_tokens:
            return []
        lengths = [len(item) for item in tokens]
        avgdl = sum(lengths) / len(lengths)
        frequency = Counter(token for item in tokens for token in set(item))
        scored = []
        for passage, doc_tokens, length in zip(branch, tokens, lengths):
            terms = Counter(doc_tokens)
            score = 0.0
            for token in query_tokens:
                df = frequency.get(token, 0)
                if not df or token not in terms:
                    continue
                idf = math.log(1 + (len(branch) - df + 0.5) / (df + 0.5))
                score += idf * terms[token] * (self.k1 + 1) / (terms[token] + self.k1 * (1 - self.b + self.b * length / avgdl))
            if score > 0:
                scored.append({"passage_id": passage["passage_id"], "score": round(score, 12), "source_language": source_language})
        scored.sort(key=lambda item: (-item["score"], item["passage_id"]))
        return [{**item, "rank": index} for index, item in enumerate(scored[:top_k], 1)]


def route_query(query: dict[str, str]) -> list[tuple[str, str]]:
    language = query["query_language"]
    if language == "zh":
        routes = [("zh", query["query_text"])]
        if query.get("translated_query"):
            routes.append(("en", query["translated_query"]))
        return routes
    routes = [("en", query["query_text"])]
    if query.get("translated_query"):
        routes.append(("zh", query["translated_query"]))
    return routes


def rrf_merge(branches: list[list[dict[str, Any]]], *, rrf_k: int, top_k: int) -> list[dict[str, Any]]:
    scores: dict[str, float] = {}
    languages: dict[str, set[str]] = {}
    for branch in branches:
        for item in branch:
            passage_id = item["passage_id"]
            scores[passage_id] = scores.get(passage_id, 0.0) + 1 / (rrf_k + item["rank"])
            languages.setdefault(passage_id, set()).add(item["source_language"])
    ranked = sorted(scores, key=lambda passage_id: (-scores[passage_id], passage_id))[:top_k]
    return [{"passage_id": passage_id, "rrf_score": round(scores[passage_id], 12), "source_languages": sorted(languages[passage_id]), "rank": index} for index, passage_id in enumerate(ranked, 1)]
