from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, Optional, Set


SEMANTIC_DIR = Path(__file__).resolve().parent
MODULE2_ROOT = SEMANTIC_DIR.parent
PROJECT_ROOT = MODULE2_ROOT.parent
DEFAULT_RESUME_PDF = PROJECT_ROOT / "module_1_Parse_extractor" / "main_Resume-2.pdf"
DEFAULT_TAXONOMY_PATH = SEMANTIC_DIR / "skill_taxonomy_500plus(2).json"
DEFAULT_OUTPUT_PATH = SEMANTIC_DIR / "layer_a_semantic_resume.json"

for path in (PROJECT_ROOT, MODULE2_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from module2_semantic.embedding_utils import get_model_device  # noqa: E402
from module2_semantic.personB_pipeline import run_semantic_pipeline  # noqa: E402
from shared.aliases import SKILL_ALIASES, normalize_skill_name  # noqa: E402
from shared.skills import SKILLS  # noqa: E402


SECTION_ALIASES = {
    "skills": "skills",
    "projects": "project",
    "project": "project",
    "experience": "experience",
    "education": "education",
    "achievements": "other",
    "leadership_roles": "other",
    "certifications": "skills",
}

SECTION_KEYWORD_BONUS = {
    "skills": 0.05,
    "project": 0.15,
    "experience": 0.20,
    "education": 0.02,
    "other": 0.03,
    "general": 0.00,
}


def _load_module1_parser():
    parser_path = PROJECT_ROOT / "module_1_Parse_extractor" / "main_extraction.py"
    if not parser_path.exists():
        raise FileNotFoundError(f"Module 1 parser not found: {parser_path}")

    spec = importlib.util.spec_from_file_location("module1_main_extraction", parser_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load parser module from {parser_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _normalize_section(section: str) -> str:
    key = re.sub(r"[^a-z_]", "", str(section or "").lower())
    return SECTION_ALIASES.get(key, "general")


def _load_skill_metadata(taxonomy_path: Path) -> Dict[str, Dict[str, str]]:
    if not taxonomy_path.exists():
        return {}
    payload = json.loads(taxonomy_path.read_text(encoding="utf-8"))
    meta: Dict[str, Dict[str, str]] = {}
    for entry in payload.get("skills", []):
        if not isinstance(entry, dict):
            continue
        canonical = normalize_skill_name(entry.get("canonical_skill", ""))
        if not canonical:
            continue
        category_label = str(entry.get("category", "") or "").strip()
        is_soft = "soft" in category_label.lower()
        meta[canonical] = {
            "category": "soft_skill" if is_soft else "hard_skill",
            "taxonomy_category": category_label or "uncategorized",
        }
    return meta


def _build_variant_map() -> Dict[str, Set[str]]:
    variants: Dict[str, Set[str]] = {normalize_skill_name(skill): {normalize_skill_name(skill)} for skill in SKILLS}
    for alias, target in SKILL_ALIASES.items():
        canonical = normalize_skill_name(target)
        alias_norm = normalize_skill_name(alias)
        if not canonical:
            continue
        variants.setdefault(canonical, {canonical})
        if alias_norm:
            variants[canonical].add(alias_norm)
    return variants


def _compile_phrase_pattern(phrase: str) -> re.Pattern:
    escaped = re.escape(phrase)
    if re.fullmatch(r"[a-z0-9]+", phrase):
        pattern = rf"\b{escaped}\b"
    else:
        pattern = rf"(?<!\w){escaped}(?!\w)"
    return re.compile(pattern, re.IGNORECASE)


def _extract_keyword_output(raw_text: str, sections: Dict[str, str], variants: Dict[str, Set[str]]) -> Dict[str, dict]:
    keyword_data: Dict[str, dict] = defaultdict(lambda: {"mentions": 0, "contexts": set()})

    search_spaces = {"general": raw_text}
    for section, text in sections.items():
        if text.strip():
            search_spaces[_normalize_section(section)] = text

    # Precompile patterns once to keep extraction fast.
    compiled_patterns: Dict[str, List[re.Pattern]] = {}
    for skill, terms in variants.items():
        patterns = []
        for term in sorted(terms):
            if len(term) < 2:
                continue
            patterns.append(_compile_phrase_pattern(term))
        if patterns:
            compiled_patterns[skill] = patterns

    for section, text in search_spaces.items():
        if not text:
            continue
        normalized_text = text.lower()
        for skill, patterns in compiled_patterns.items():
            section_hits = 0
            for pattern in patterns:
                section_hits += len(pattern.findall(normalized_text))
            if section_hits <= 0:
                continue
            keyword_data[skill]["mentions"] += section_hits
            keyword_data[skill]["contexts"].add(section)

    keyword_output: Dict[str, dict] = {}
    for skill, data in keyword_data.items():
        mentions = int(data["mentions"])
        contexts = sorted(set(data["contexts"]))
        section_bonus = max((SECTION_KEYWORD_BONUS.get(ctx, 0.0) for ctx in contexts), default=0.0)
        keyword_score = min(1.0, 0.55 + (0.10 * mentions) + section_bonus)
        keyword_output[skill] = {
            "keyword_score": round(keyword_score, 4),
            "mentions": mentions,
            "contexts": contexts,
        }
    return keyword_output


def _extract_cgpa(text: str) -> Optional[dict]:
    patterns = [
        re.compile(r"(?i)\b(?:cgpa|gpa)\s*[:\-]?\s*(\d{1,2}(?:\.\d{1,2})?)\s*/\s*(10|4(?:\.0)?)"),
        re.compile(r"(?i)\b(?:cgpa|gpa)\s*[:\-]?\s*(\d{1,2}(?:\.\d{1,2})?)"),
    ]
    for pattern in patterns:
        match = pattern.search(text or "")
        if not match:
            continue
        value = match.group(1)
        scale = match.group(2) if len(match.groups()) >= 2 else None
        out = {"value": float(value), "raw": match.group(0).strip()}
        if scale:
            out["scale"] = scale
        return out
    return None


def _flatten_sections(section_payload: dict) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for section_name, value in (section_payload or {}).items():
        if isinstance(value, list):
            merged = "\n".join(str(item).strip() for item in value if str(item).strip())
        elif isinstance(value, str):
            merged = value.strip()
        else:
            merged = ""
        if merged:
            out[section_name] = merged
    return out


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate Module 2 semantic skill JSON using the Person B pipeline."
    )
    parser.add_argument(
        "--resume-pdf",
        type=Path,
        default=None,
        help=f"Path to resume PDF. Default: {DEFAULT_RESUME_PDF}",
    )
    parser.add_argument(
        "--resume-json",
        type=Path,
        default=None,
        help="Path to resume_data JSON with keys raw_text and sections.",
    )
    parser.add_argument(
        "--text-file",
        type=Path,
        default=None,
        help="Path to plain text input. Sections will be empty.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help=f"Path for output JSON. Default: {DEFAULT_OUTPUT_PATH}",
    )
    parser.add_argument(
        "--taxonomy",
        type=Path,
        default=DEFAULT_TAXONOMY_PATH,
        help=f"Path to skills taxonomy JSON. Default: {DEFAULT_TAXONOMY_PATH}",
    )
    parser.add_argument(
        "--device",
        choices=["auto", "cpu", "cuda"],
        default="auto",
        help="Model device preference for semantic model.",
    )
    return parser.parse_args()


def _resolve_input_source(args: argparse.Namespace) -> tuple[str, Dict[str, str], str]:
    chosen_sources = [bool(args.resume_pdf), bool(args.resume_json), bool(args.text_file)]
    if sum(chosen_sources) > 1:
        raise ValueError("Use only one input source: --resume-pdf OR --resume-json OR --text-file.")

    if args.resume_json:
        if not args.resume_json.exists():
            raise FileNotFoundError(f"Resume JSON not found: {args.resume_json}")
        payload = json.loads(args.resume_json.read_text(encoding="utf-8"))
        raw_text = str(payload.get("raw_text", ""))
        sections = _flatten_sections(payload.get("sections", {}))
        return raw_text, sections, str(args.resume_json)

    if args.text_file:
        if not args.text_file.exists():
            raise FileNotFoundError(f"Text file not found: {args.text_file}")
        raw_text = args.text_file.read_text(encoding="utf-8", errors="ignore")
        return raw_text, {}, str(args.text_file)

    resume_pdf = args.resume_pdf or DEFAULT_RESUME_PDF
    if not resume_pdf.exists():
        raise FileNotFoundError(f"Resume PDF not found: {resume_pdf}")

    module1 = _load_module1_parser()
    resume_data = module1.parse_resume(str(resume_pdf))
    raw_text = str(resume_data.get("raw_text", ""))
    sections = _flatten_sections(resume_data.get("sections", {}))
    return raw_text, sections, str(resume_pdf)


def _apply_device_preference(device: str) -> None:
    if device in {"cpu", "cuda"}:
        os.environ["MODULE2_SEMANTIC_DEVICE"] = device


def main() -> None:
    args = _parse_args()
    _apply_device_preference(args.device)

    raw_text, section_texts, input_path = _resolve_input_source(args)

    skill_meta = _load_skill_metadata(args.taxonomy)
    variants = _build_variant_map()
    keyword_output = _extract_keyword_output(raw_text, section_texts, variants)
    semantic_output = run_semantic_pipeline(raw_text, keyword_output)

    final_output: Dict[str, dict] = {}
    all_skills = sorted(set(keyword_output.keys()) | set(semantic_output.keys()))
    for skill in all_skills:
        canonical = normalize_skill_name(skill)
        fused = semantic_output.get(canonical, semantic_output.get(skill, {}))
        keyword = keyword_output.get(canonical, keyword_output.get(skill, {}))
        contexts = keyword.get("contexts", [])
        mentions = int(keyword.get("mentions", 0))
        if not contexts and fused:
            contexts = ["general"]
        if mentions == 0 and fused:
            mentions = 1

        meta = skill_meta.get(canonical, {"category": "hard_skill", "taxonomy_category": "uncategorized"})
        final_output[canonical] = {
            "confidence": float(fused.get("confidence", keyword.get("keyword_score", 0.0))),
            "source": list(fused.get("source", ["keyword"] if keyword else [])),
            "mentions": mentions,
            "contexts": contexts,
            "category": meta["category"],
            "taxonomy_category": meta["taxonomy_category"],
            "sections": contexts,
        }

    final_output["__cgpa__"] = _extract_cgpa(raw_text)
    final_output["__meta__"] = {
        "input_path": input_path,
        "semantic_device": get_model_device(),
        "skills_count": len(all_skills),
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(final_output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote semantic skill JSON to: {args.output}")
    print(f"Detected skills: {len(all_skills)}")
    print(f"Semantic device: {get_model_device()}")
    print(f"CGPA: {final_output['__cgpa__']}")


if __name__ == "__main__":
    main()
