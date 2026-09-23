"""World-model prediction-correctness metrics, aligned with WorldEvolver.

WorldEvolver measures world-model prediction accuracy on the Word2World
benchmark with three metrics, and reports its Selective Foresight calibration
against Exact Match and Token F1:

    (1) Exact Match     normalized string matching between predicted and
                        reference observations
    (2) Token F1        lexical overlap after tokenization, micro-averaged
    (3) Cosine Similarity  semantic similarity (they use Qwen3-Embedding-8B)

Why this module exists: the earlier round of this pre-experiment used ONLY
cosine similarity, computed with all-MiniLM-L6-v2. Measured on our own data,
two completely unrelated ALFWorld observations already score a median cosine
of 0.399 (p90 = 0.593) because the observations are templated
("You arrive at X. On X you see ..."), while our actual predictions scored a
median of 0.646. That is very little dynamic range, so any correlation
computed against it is unreliable -- which is why the "confidence does not
track correctness" finding from that round has to be re-established with
these stronger metrics rather than taken at face value.

Normalization follows the standard SQuAD convention (lowercase, strip
articles, punctuation and redundant whitespace); WorldEvolver says
"normalized string matching" without specifying, and this is the usual
meaning. `fact_f1` additionally implements the ITP-style fact-level score
over ALFWorld's `object N` mentions, which is closer to what actually
matters for planning than raw lexical overlap.
"""
from __future__ import annotations

import re
import string
from collections import Counter
from typing import Dict, Iterable, Optional, Sequence

_ARTICLES = re.compile(r"\b(a|an|the)\b", re.UNICODE)
_PUNCT_TABLE = str.maketrans("", "", string.punctuation)
# ALFWorld names every entity as "<noun> <index>", e.g. "drawer 7", "mug 1".
_ENTITY = re.compile(r"\b([a-z]+ \d+)\b")


def normalize_text(s: str) -> str:
    """SQuAD-style normalization: lowercase, drop punctuation and articles,
    collapse whitespace."""
    s = (s or "").lower()
    s = s.translate(_PUNCT_TABLE)
    s = _ARTICLES.sub(" ", s)
    return " ".join(s.split())


def exact_match(prediction: str, reference: str) -> float:
    """1.0 iff the normalized strings are identical."""
    return float(normalize_text(prediction) == normalize_text(reference))


def token_f1(prediction: str, reference: str) -> float:
    """Token-overlap F1 over normalized whitespace tokens.

    Returns 0.0 when either side is empty but not both -- and 1.0 when both
    are empty, matching SQuAD's convention (two empty strings agree).
    """
    p_tokens = normalize_text(prediction).split()
    r_tokens = normalize_text(reference).split()
    if not p_tokens or not r_tokens:
        return float(p_tokens == r_tokens)

    common = Counter(p_tokens) & Counter(r_tokens)
    n_same = sum(common.values())
    if n_same == 0:
        return 0.0
    precision = n_same / len(p_tokens)
    recall = n_same / len(r_tokens)
    return 2 * precision * recall / (precision + recall)


def entities(s: str) -> set:
    """The `<noun> <index>` entities mentioned in a piece of ALFWorld text."""
    return set(_ENTITY.findall((s or "").lower()))


def fact_f1(prediction: str, reference: str) -> float:
    """F1 over the ALFWorld entities each text mentions (ITP-style Fact-F1).

    Lexical overlap rewards a prediction for reproducing the boilerplate of an
    observation; this only rewards it for naming the right things. Empty on
    both sides counts as agreement, mirroring `token_f1`.
    """
    p, r = entities(prediction), entities(reference)
    if not p or not r:
        return float(p == r)
    inter = len(p & r)
    if inter == 0:
        return 0.0
    precision, recall = inter / len(p), inter / len(r)
    return 2 * precision * recall / (precision + recall)


def all_metrics(
    prediction: str,
    reference: str,
    embedder=None,
) -> Dict[str, float]:
    """Every correctness metric at once. `embedder` is optional so callers
    that do not want the (comparatively slow, and weakest) cosine term can
    skip it."""
    out = {
        "exact_match": exact_match(prediction, reference),
        "token_f1": token_f1(prediction, reference),
        "fact_f1": fact_f1(prediction, reference),
    }
    if embedder is not None:
        from preexperiments.common.embeddings import cosine_sim

        out["cosine"] = cosine_sim(
            embedder.encode_one(prediction or ""), embedder.encode_one(reference or "")
        )
    return out


# ---------------------------------------------------------------------------
# Risk-coverage curve (WorldEvolver Figure 11)
# ---------------------------------------------------------------------------

def risk_coverage(
    confidences: Sequence[float],
    scores: Sequence[float],
    quantiles: Iterable[float] = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0),
) -> Dict[float, Optional[float]]:
    """Mean `score` over the top-`q` fraction of items ranked by confidence.

    This is how WorldEvolver validates its confidence signal (Figure 11:
    "Exact Match on the top-confidence prefix"), and it is the right tool
    here for a reason specific to our data: our confidence values are heavily
    tied (89 of 150 self-reported values were exactly 0.95), which cripples a
    rank correlation but leaves a coverage curve perfectly readable. A useful
    confidence signal produces a curve that DECREASES as coverage grows.
    """
    pairs = [(c, s) for c, s in zip(confidences, scores)
             if c == c and s == s]  # drop NaNs
    if not pairs:
        return {q: None for q in quantiles}
    pairs.sort(key=lambda t: -t[0])
    n = len(pairs)
    out = {}
    for q in quantiles:
        k = max(1, int(round(q * n)))
        out[q] = sum(s for _, s in pairs[:k]) / k
    return out
