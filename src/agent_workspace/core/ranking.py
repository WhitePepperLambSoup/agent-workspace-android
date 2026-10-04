from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Iterable, Sequence

_TOKEN_PATTERN = re.compile(r"[\w\u4e00-\u9fff]+", re.UNICODE)


def tokenize(text: str) -> list[str]:
    """Tokenize into lowercase word tokens plus CJK character bigrams."""
    tokens: list[str] = []
    for match in _TOKEN_PATTERN.finditer(text.casefold()):
        token = match.group(0)
        if re.fullmatch(r"[\u4e00-\u9fff]+", token):
            if len(token) == 1:
                tokens.append(token)
            else:
                tokens.extend(token[index : index + 2] for index in range(len(token) - 1))
        else:
            tokens.append(token)
    return tokens


def bm25_score(
    query_terms: Sequence[str],
    document_terms: Sequence[str],
    corpus_documents: Sequence[Sequence[str]],
    *,
    k1: float = 1.2,
    b: float = 0.75,
) -> float:
    """Rank a document against a query with BM25 over an in-memory corpus."""
    if not query_terms or not document_terms or not corpus_documents:
        return 0.0
    document_frequency: Counter[str] = Counter()
    for terms in corpus_documents:
        document_frequency.update(set(terms))
    total_documents = len(corpus_documents)
    document_counts = Counter(document_terms)
    document_length = len(document_terms)
    average_length = sum(len(terms) for terms in corpus_documents) / total_documents
    if average_length <= 0:
        return 0.0
    score = 0.0
    for term in query_terms:
        frequency = document_frequency.get(term, 0)
        if frequency <= 0:
            continue
        idf = math.log(1.0 + (total_documents - frequency + 0.5) / (frequency + 0.5))
        term_frequency = document_counts.get(term, 0)
        if term_frequency <= 0:
            continue
        denominator = term_frequency + k1 * (1.0 - b + b * document_length / average_length)
        score += idf * term_frequency * (k1 + 1.0) / denominator
    return score


def rank_by_bm25(
    query: str,
    documents: Sequence[str],
) -> list[int]:
    """Return document indices sorted by descending BM25 relevance."""
    query_terms = tokenize(query)
    corpus = [tokenize(document) for document in documents]
    scored = [(bm25_score(query_terms, terms, corpus), index) for index, terms in enumerate(corpus)]
    scored.sort(key=lambda pair: (-pair[0], pair[1]))
    return [index for _, index in scored]


def semantic_cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if not left or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot / (left_norm * right_norm)


def rank_by_embeddings(
    query_vector: Sequence[float],
    document_vectors: Iterable[Sequence[float]],
) -> list[int]:
    scored = [
        (semantic_cosine_similarity(query_vector, vector), index)
        for index, vector in enumerate(document_vectors)
    ]
    scored.sort(key=lambda pair: (-pair[0], pair[1]))
    return [index for _, index in scored]
