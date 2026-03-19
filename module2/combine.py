from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Dict, Iterable, List, Set


MODULE2_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = MODULE2_DIR.parent
DEFAULT_KEYWORD_JSON = MODULE2_DIR / "module2_Keyword" / "layer_a_keywords.json"
DEFAULT_SEMANTIC_JSON = MODULE2_DIR / "module2_semantic" / "layer_a_semantic_resume.json"
DEFAULT_OUTPUT_JSON = MODULE2_DIR / "layer_a_combined_scored.json"


import sys

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from shared.aliases import normalize_skill_name  # noqa: E402


CONTEXT_WEIGHTS = {
    "skills": 2.0,
    "project": 5.5,
    "experience": 7.0,
    "education": 1.0,
    "general": 1.0,
    "other": 1.0,
    "unknown": 1.0,
}

# Skill-type preference multipliers.
# Hard skills get more preference, soft skills get less preference.
HARD_SKILL_MULTIPLIER = 1.2
SOFT_SKILL_MULTIPLIER = 0.7

# Education contribution from CGPA.
# Rule requested: 10 CGPA should contribute 5 points.
CGPA_TO_EDUCATION_SCORE_MULTIPLIER = 0.5

# Small context bonus on top of weighted mentions.
CONTEXT_BONUS = {
    "skills": 0.5,
    "project": 1.0,
    "experience": 2.0,
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Combine module2 keyword + semantic JSON and score each skill."
    )
    parser.add_argument("--keyword-json", type=Path, default=DEFAULT_KEYWORD_JSON)
    parser.add_argument("--semantic-json", type=Path, default=DEFAULT_SEMANTIC_JSON)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    return parser.parse_args()


def _load_json(path: Path) -> Dict[str, object]:
    if not path.exists():
        raise FileNotFoundError(f"JSON file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _as_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_context(context: str) -> str:
    c = str(context or "").strip().lower()
    if c in {"projects", "project"}:
        return "project"
    if c in {"experience", "internship", "job", "work", "employment"}:
        return "experience"
    if c in {"skills", "skill"}:
        return "skills"
    if c in {"education"}:
        return "education"
    if c in {"other"}:
        return "other"
    if c in {"general"}:
        return "general"
    return "unknown"


def _clean_contexts(payload: Dict[str, object]) -> List[str]:
    raw = payload.get("contexts")
    if not isinstance(raw, list):
        raw = payload.get("sections", [])
    if not isinstance(raw, list):
        return []
    cleaned = [_normalize_context(item) for item in raw if str(item).strip()]
    return sorted(set(cleaned))


def _dominant_context_for_frequency(contexts: Set[str]) -> str:
    # To reflect repeated project evidence (as in the example), prefer project first.
    if "project" in contexts:
        return "project"
    if "experience" in contexts:
        return "experience"
    if "skills" in contexts:
        return "skills"
    if "education" in contexts:
        return "education"
    if "general" in contexts:
        return "general"
    if "other" in contexts:
        return "other"
    return "unknown"


def _cgpa_to_10_scale(cgpa_payload: object) -> float:
    if not isinstance(cgpa_payload, dict):
        return 0.0

    raw_value = _as_float(cgpa_payload.get("value"), default=0.0)
    raw_scale = str(cgpa_payload.get("scale", "")).strip()

    if raw_value <= 0:
        return 0.0

    if raw_scale == "4":
        return min(10.0, raw_value * 2.5)
    # Default to /10 when unknown or already /10.
    return min(10.0, raw_value)


def _experience_strength(mentions: int, contexts: Iterable[str], cgpa_payload: object = None) -> Dict[str, float]:
    context_set: Set[str] = set(contexts)
    section_weight = sum(CONTEXT_WEIGHTS.get(ctx, 1.0) for ctx in context_set)

    # Requested formula: frequency_weight = min(5, log2(mentions+1)*2)
    frequency_weight = min(5.0, math.log2(max(0, mentions) + 1) * 2.0)

    context_weight = sum(CONTEXT_BONUS.get(ctx, 0.0) for ctx in context_set)

    # Apply education score from CGPA only when education context exists.
    cgpa_10 = _cgpa_to_10_scale(cgpa_payload)
    education_score = 0.0
    if "education" in context_set and cgpa_10 > 0:
        education_score = min(5.0, cgpa_10 * CGPA_TO_EDUCATION_SCORE_MULTIPLIER)

    raw_score = section_weight + frequency_weight + context_weight + education_score
    normalized_score = min(10.0, raw_score / 2.0)  # 20 -> 10/10

    return {
        "section_weight": round(section_weight, 4),
        "frequency_weight": round(frequency_weight, 4),
        "context_weight": round(context_weight, 4),
        "education_score": round(education_score, 4),
        "raw_strength_score": round(raw_score, 4),
        "normalized_strength_score": round(normalized_score, 4),
    }


def _merge_skill_payloads(keyword_data: Dict[str, object], semantic_data: Dict[str, object]) -> Dict[str, dict]:
    merged: Dict[str, dict] = {}

    def ingest(source_name: str, payload: Dict[str, object]) -> None:
        for skill, info in payload.items():
            if str(skill).startswith("__"):
                continue
            if not isinstance(info, dict):
                continue

            canonical = normalize_skill_name(str(skill))
            entry = merged.setdefault(
                canonical,
                {
                    "skill": canonical,
                    "mentions": 0,
                    "contexts": set(),
                    "source": set(),
                    "keyword_confidence": 0.0,
                    "semantic_confidence": 0.0,
                    "category": "",
                    "taxonomy_category": "",
                },
            )

            entry["mentions"] = max(entry["mentions"], _as_int(info.get("mentions", 0), default=0))
            entry["contexts"].update(_clean_contexts(info))
            entry["source"].add(source_name)
            if source_name == "keyword":
                entry["keyword_confidence"] = max(
                    entry["keyword_confidence"], _as_float(info.get("confidence", 0.0), default=0.0)
                )
            elif source_name == "semantic":
                entry["semantic_confidence"] = max(
                    entry["semantic_confidence"], _as_float(info.get("confidence", 0.0), default=0.0)
                )

            if not entry["category"] and info.get("category"):
                entry["category"] = str(info.get("category"))
            if not entry["taxonomy_category"] and info.get("taxonomy_category"):
                entry["taxonomy_category"] = str(info.get("taxonomy_category"))

    ingest("keyword", keyword_data)
    ingest("semantic", semantic_data)
    return merged


def _build_final_scores(merged: Dict[str, dict], cgpa_payload: object = None) -> Dict[str, object]:
    output: Dict[str, object] = {}
    for skill in sorted(merged.keys()):
        item = merged[skill]
        contexts = sorted(set(item["contexts"]))
        mentions = max(1, int(item["mentions"]))
        keyword_confidence = float(item["keyword_confidence"])
        semantic_confidence = float(item["semantic_confidence"])

        # Confidence fusion requested by user.
        final_confidence = (0.6 * keyword_confidence) + (0.4 * semantic_confidence)
        final_confidence = max(0.0, min(1.0, final_confidence))

        # If present in both -> boost. If not -> lower marks.
        in_both_sources = {"keyword", "semantic"}.issubset(set(item["source"]))
        source_multiplier = 1.15 if in_both_sources else 0.75

        category_raw = str(item.get("category", "") or "").strip().lower()
        skill_type_multiplier = SOFT_SKILL_MULTIPLIER if "soft" in category_raw else HARD_SKILL_MULTIPLIER

        strength = _experience_strength(mentions=mentions, contexts=contexts, cgpa_payload=cgpa_payload)
        resulting_score = (
            strength["normalized_strength_score"]
            * source_multiplier
            * skill_type_multiplier
            * (0.5 + (0.5 * final_confidence))
        )
        resulting_score = max(0.0, min(10.0, resulting_score))

        output[skill] = {
            "resulting_score": round(resulting_score, 4),
            "confidence": round(final_confidence, 4),
            "keyword_confidence": round(keyword_confidence, 4),
            "semantic_confidence": round(semantic_confidence, 4),
            "source": sorted(item["source"]),
            "mentions": mentions,
            "contexts": contexts,
            "category": item["category"] or "hard_skill",
            "taxonomy_category": item["taxonomy_category"] or "uncategorized",
            "strength_breakdown": strength,
            "verification_multiplier": source_multiplier,
            "skill_type_multiplier": skill_type_multiplier,
        }

    return output


def main() -> None:
    args = _parse_args()
    keyword_data = _load_json(args.keyword_json)
    semantic_data = _load_json(args.semantic_json)

    merged = _merge_skill_payloads(keyword_data, semantic_data)
    cgpa_payload = semantic_data.get("__cgpa__") or keyword_data.get("__cgpa__")
    combined_scores = _build_final_scores(merged, cgpa_payload=cgpa_payload)

    combined_scores["__cgpa__"] = cgpa_payload
    combined_scores["__meta__"] = {
        "keyword_json": str(args.keyword_json),
        "semantic_json": str(args.semantic_json),
        "skills_count": len([k for k in combined_scores.keys() if not k.startswith("__")]),
        "scoring_formula": {
            "confidence_fusion": "0.6*keyword_confidence + 0.4*semantic_confidence",
            "strength_engine": "SkillScore = SectionWeight + FrequencyWeight + ContextWeight",
            "education_engine": "EducationScore = min(5, CGPA_on_10_scale * 0.5) when context includes education",
            "normalized_strength": "min(10, raw_strength/2)",
            "both_sources_multiplier": 1.15,
            "single_source_multiplier": 0.75,
            "hard_skill_multiplier": HARD_SKILL_MULTIPLIER,
            "soft_skill_multiplier": SOFT_SKILL_MULTIPLIER,
            "section_weights": CONTEXT_WEIGHTS,
        },
    }

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(combined_scores, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote combined score JSON: {args.output_json}")
    print(f"Skills scored: {combined_scores['__meta__']['skills_count']}")
    if "python" in combined_scores:
        print(f"python -> {combined_scores['python']}")


if __name__ == "__main__":
    main()
