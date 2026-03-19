"""Main Person B semantic skill extraction pipeline."""

from __future__ import annotations

import re
from typing import Dict, Iterable, List, Sequence

from shared.aliases import normalize_skill_name
from shared.skills import SKILLS

from .fusion import fuse_skill_outputs
from .semantic_matcher import (
    TECH_KEYWORDS,
    TextUnit,
    get_skill_store,
    is_informative_text,
    match_semantic_skills,
)


SECTION_LABELS = {
    "achievements": "other",
    "certifications": "skills",
    "education": "other",
    "experience": "experience",
    "professional experience": "experience",
    "employment": "experience",
    "projects": "projects",
    "project experience": "projects",
    "skills": "skills",
    "technical skills": "skills",
    "summary": "other",
}
PHRASE_SPLIT_PATTERN = re.compile(r"[,:;|/]+|\b(?:and|with|using|via|including|through)\b", re.IGNORECASE)
SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?])\s+")


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\u2022", " ").replace("•", " ")).strip()


def _normalize_context(context: str | None) -> str:
    if not context:
        return "unknown"
    normalized = re.sub(r"[^a-z\s]", " ", context.lower())
    normalized = " ".join(normalized.split())
    return SECTION_LABELS.get(normalized, "unknown")


def _is_section_heading(line: str) -> str | None:
    candidate = re.sub(r"[^a-zA-Z\s]", " ", line).lower()
    candidate = " ".join(candidate.split())
    return candidate if candidate in SECTION_LABELS else None


def _normalize_input_text(text: str) -> str:
    return text if isinstance(text, str) else ""


def _split_sentences_by_section(text: str) -> List[TextUnit]:
    current_context = "unknown"
    sentence_units: List[TextUnit] = []

    for raw_line in text.splitlines():
        line = _clean_text(raw_line)
        if not line:
            continue

        heading = _is_section_heading(line)
        if heading:
            current_context = _normalize_context(heading)
            continue

        for sentence in SENTENCE_SPLIT_PATTERN.split(line):
            cleaned_sentence = _clean_text(sentence)
            if not cleaned_sentence:
                continue
            sentence_units.append(TextUnit(text=cleaned_sentence, context=current_context, origin="sentence"))

    if sentence_units:
        return sentence_units

    fallback_sentences = SENTENCE_SPLIT_PATTERN.split(_clean_text(text))
    return [
        TextUnit(text=_clean_text(sentence), context="unknown", origin="sentence")
        for sentence in fallback_sentences
        if _clean_text(sentence)
    ]


def _extract_phrases(sentences: Sequence[TextUnit]) -> List[TextUnit]:
    phrase_units: List[TextUnit] = []
    for sentence in sentences:
        segments = [segment.strip() for segment in PHRASE_SPLIT_PATTERN.split(sentence.text)]
        for segment in segments:
            phrase = _clean_text(segment)
            word_count = len(phrase.split())
            if 2 <= word_count <= 12:
                phrase_units.append(TextUnit(text=phrase, context=sentence.context, origin="phrase"))
    return phrase_units


def _dedupe_units(units: Iterable[TextUnit]) -> List[TextUnit]:
    deduped: List[TextUnit] = []
    seen = set()
    for unit in units:
        normalized_text = " ".join(unit.text.lower().split())
        if normalized_text in seen:
            continue
        seen.add(normalized_text)
        deduped.append(TextUnit(text=normalized_text, context=_normalize_context(unit.context), origin=unit.origin))
    return deduped


def _contains_known_skill_token(text: str) -> bool:
    lowered_text = text.lower()
    for skill in SKILLS:
        canonical_skill = normalize_skill_name(skill)
        tokens = canonical_skill.replace(".", " ").replace("-", " ").split()
        if len(canonical_skill) > 2 and canonical_skill in lowered_text:
            return True
        if len(canonical_skill) <= 2 and re.search(rf"\b{re.escape(canonical_skill)}\b", lowered_text):
            return True
        if any(token in lowered_text for token in tokens if len(token) > 2):
            return True
    return any(keyword in lowered_text for keyword in TECH_KEYWORDS)


def _filter_text_units(units: Sequence[TextUnit]) -> List[TextUnit]:
    filtered: List[TextUnit] = []
    for unit in units:
        minimum_words = 2 if unit.origin == "phrase" else 3
        if len(unit.text.split()) < minimum_words:
            continue
        if is_informative_text(unit.text) or _contains_known_skill_token(unit.text):
            filtered.append(unit)
    return _dedupe_units(filtered)


def _normalize_keyword_output(keyword_output: dict | None) -> dict:
    if not isinstance(keyword_output, dict):
        return {}
    normalized_output: Dict[str, dict] = {}
    valid_skills = {normalize_skill_name(skill) for skill in SKILLS}

    for skill, payload in keyword_output.items():
        canonical_skill = normalize_skill_name(skill)
        if canonical_skill not in valid_skills or not isinstance(payload, dict):
            continue
        normalized_output[canonical_skill] = payload
    return normalized_output


def run_semantic_pipeline(text: str, keyword_output: dict) -> dict:
    """
    Run the production-ready Person B semantic pipeline.

    Returns the strict schema only:
    {
        "python": {
            "confidence": 0.92,
            "source": ["keyword", "semantic"]
        }
    }
    """
    normalized_text = _normalize_input_text(text)
    normalized_keyword_output = _normalize_keyword_output(keyword_output)

    if not normalized_text.strip():
        return fuse_skill_outputs(normalized_keyword_output, {}, SKILLS)

    sentence_units = _split_sentences_by_section(normalized_text)
    phrase_units = _extract_phrases(sentence_units)
    text_units = _filter_text_units([*sentence_units, *phrase_units])

    if not text_units:
        return fuse_skill_outputs(normalized_keyword_output, {}, SKILLS)

    try:
        skill_store = get_skill_store(SKILLS)
        semantic_output = match_semantic_skills(text_units, skill_store)
    except Exception:
        # Graceful fallback when semantic model/dependencies are unavailable.
        semantic_output = {}
    return fuse_skill_outputs(normalized_keyword_output, semantic_output, SKILLS)


def run_semantic_pipeline_batch(items: Sequence[tuple[str, dict]]) -> List[dict]:
    """Optional batch helper for ATS-style bulk resume processing."""
    return [run_semantic_pipeline(text, keyword_output) for text, keyword_output in items]
