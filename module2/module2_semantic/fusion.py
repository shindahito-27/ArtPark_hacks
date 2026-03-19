"""Adaptive fusion logic for keyword and semantic skill signals."""

from __future__ import annotations

from typing import Dict, Iterable, List, Set

from shared.aliases import normalize_skill_name


DEFAULT_KEYWORD_WEIGHT = 0.6
DEFAULT_SEMANTIC_WEIGHT = 0.4
HIGH_CONFIDENCE_KEYWORD_THRESHOLD = 0.9
HIGH_CONFIDENCE_KEYWORD_WEIGHTS = (0.8, 0.2)
SEMANTIC_ONLY_BOOST_THRESHOLD = 0.8
SEMANTIC_ONLY_BOOST_AMOUNT = 0.05
MATCH_COUNT_BOOST_PER_EXTRA = 0.03
MATCH_COUNT_BOOST_CAP = 0.12


def _canonical_skills(skills: Iterable[str]) -> Set[str]:
    return {normalize_skill_name(skill) for skill in skills}


def _clip_score(score: float) -> float:
    return max(0.0, min(1.0, score))


def _match_count_boost(match_count: int) -> float:
    if match_count <= 1:
        return 0.0
    return min((match_count - 1) * MATCH_COUNT_BOOST_PER_EXTRA, MATCH_COUNT_BOOST_CAP)


def fuse_skill_outputs(
    keyword_output: Dict[str, dict] | None,
    semantic_output: Dict[str, Dict[str, float]] | None,
    valid_skills: Iterable[str],
) -> Dict[str, Dict[str, object]]:
    """Merge keyword and semantic outputs into the strict final schema."""
    allowed_skills = _canonical_skills(valid_skills)
    keyword_output = keyword_output or {}
    semantic_output = semantic_output or {}

    keyword_scores: Dict[str, float] = {}
    for skill, payload in keyword_output.items():
        canonical_skill = normalize_skill_name(skill)
        if canonical_skill not in allowed_skills or not isinstance(payload, dict):
            continue
        try:
            keyword_scores[canonical_skill] = _clip_score(float(payload.get("keyword_score", 0.0)))
        except (TypeError, ValueError):
            continue

    semantic_scores: Dict[str, float] = {}
    semantic_match_counts: Dict[str, int] = {}
    for skill, payload in semantic_output.items():
        canonical_skill = normalize_skill_name(skill)
        if canonical_skill not in allowed_skills or not isinstance(payload, dict):
            continue
        try:
            semantic_scores[canonical_skill] = _clip_score(float(payload.get("semantic_score", 0.0)))
            semantic_match_counts[canonical_skill] = int(payload.get("match_count", 1))
        except (TypeError, ValueError):
            continue

    merged_skills = sorted(set(keyword_scores) | set(semantic_scores))
    final_output: Dict[str, Dict[str, object]] = {}

    for skill in merged_skills:
        keyword_score = keyword_scores.get(skill)
        semantic_score = semantic_scores.get(skill)
        match_count = semantic_match_counts.get(skill, 1)
        sources: List[str] = []

        if keyword_score is not None:
            sources.append("keyword")
        if semantic_score is not None:
            sources.append("semantic")

        if keyword_score is not None and semantic_score is not None:
            if keyword_score > HIGH_CONFIDENCE_KEYWORD_THRESHOLD:
                keyword_weight, semantic_weight = HIGH_CONFIDENCE_KEYWORD_WEIGHTS
            else:
                keyword_weight, semantic_weight = DEFAULT_KEYWORD_WEIGHT, DEFAULT_SEMANTIC_WEIGHT
            confidence = (keyword_weight * keyword_score) + (semantic_weight * semantic_score)
            confidence += _match_count_boost(match_count)
        elif keyword_score is not None:
            confidence = keyword_score
        else:
            confidence = semantic_score if semantic_score is not None else 0.0
            if confidence > SEMANTIC_ONLY_BOOST_THRESHOLD:
                confidence += SEMANTIC_ONLY_BOOST_AMOUNT
            confidence += _match_count_boost(match_count)

        final_output[skill] = {
            "confidence": round(_clip_score(confidence), 4),
            "source": sources,
        }

    return final_output
