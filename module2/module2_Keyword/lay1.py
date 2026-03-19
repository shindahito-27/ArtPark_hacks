from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Any, Set, Tuple


# -----------------------------
# CONFIG
# -----------------------------
SOFT_SKILLS = {
    "leadership", "communication", "teamwork", "strategy",
    "branding", "management", "logistics", "collaboration"
}


# -----------------------------
# HELPERS
# -----------------------------
def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


# -----------------------------
# SECTION DETECTION
# -----------------------------
def detect_section(text: str, start_char: int) -> str:
    text_lower = text.lower()

    section_keywords = {
        "project": ["project", "projects"],
        "experience": ["experience", "internship", "work"],
        "education": ["education", "university", "college"],
        "skills": ["skills", "technical skills"]
    }

    window = text_lower[max(0, start_char - 300):start_char]

    for section, keywords in section_keywords.items():
        for kw in keywords:
            if kw in window:
                return section

    return "general"


# -----------------------------
# CGPA EXTRACTION
# -----------------------------
def extract_cgpa(text: str):
    patterns = [
        r'(cgpa|gpa)[^\d]{0,10}(\d\.\d+)',
        r'(\d\.\d+)\s*/\s*10',
        r'(\d\.\d+)\s*/\s*4'
    ]

    for pattern in patterns:
        match = re.search(pattern, text.lower())
        if match:
            value = float(match.group(2) if len(match.groups()) > 1 else match.group(1))
            return {
                "value": value,
                "raw": match.group(0),
                "scale": "10" if "/10" in match.group(0) else "4"
            }

    return None


# -----------------------------
# TAXONOMY LOADER
# -----------------------------
def load_taxonomy(path: str):
    data = json.loads(Path(path).read_text())

    skill_to_category = {}
    all_terms = set()
    term_to_canonical = {}

    # Root-level aliases (e.g., nlp -> natural language processing)
    for alias, canonical in data.get("aliases", {}).items():
        alias_n = normalize_text(alias)
        canonical_n = normalize_text(canonical)
        if alias_n and canonical_n:
            term_to_canonical[alias_n] = canonical_n
            all_terms.add(alias_n)

    for entry in data["skills"]:
        skill = normalize_text(entry["canonical_skill"])
        category = entry["category"]

        skill_to_category[skill] = category
        all_terms.add(skill)
        term_to_canonical[skill] = skill

        for alias in entry.get("aliases", []):
            alias_n = normalize_text(alias)
            all_terms.add(alias_n)
            term_to_canonical[alias_n] = skill

    return all_terms, skill_to_category, term_to_canonical


# -----------------------------
# MATCHER
# -----------------------------
def extract_matches(text: str, skills: Set[str], term_to_canonical: Dict[str, str]):
    """
    Fast matcher: token n-gram search against taxonomy terms.
    Avoids O(num_skills * text_len) regex scans.
    """
    matches = []
    seen = set()

    token_spans = [(m.group(0), m.start(), m.end()) for m in re.finditer(r"\b[\w\-\+\.]+\b", text)]
    if not token_spans:
        return matches

    # Max words in a taxonomy term controls n-gram size.
    max_len = max((len(term.split()) for term in skills), default=1)
    max_len = min(max_len, 8)

    norm_tokens = [normalize_text(tok) for tok, _, _ in token_spans]

    for i in range(len(token_spans)):
        for n in range(max_len, 0, -1):
            j = i + n
            if j > len(token_spans):
                continue
            phrase = " ".join(norm_tokens[i:j]).strip()
            if phrase not in skills:
                continue

            canonical = term_to_canonical.get(phrase, phrase)
            start = token_spans[i][1]
            end = token_spans[j - 1][2]
            dedupe_key = (canonical, start, end)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)

            matches.append(
                {
                    "skill": canonical,
                    "matched_text": text[start:end],
                    "start": start,
                    "end": end,
                }
            )

    return matches


# -----------------------------
# MAIN BUILDER (IMPORTANT)
# -----------------------------
def build_output(text: str, matches: List[Dict], skill_to_category: Dict):
    skill_data = {}

    for m in matches:
        skill = m["skill"]
        section = detect_section(text, m["start"])
        category = skill_to_category.get(skill, "General")

        if skill not in skill_data:
            skill_data[skill] = {
                "confidence": 1.0,
                "source": ["keyword"],
                "mentions": 0,
                "contexts": set(),
                "category": "soft_skill" if skill in SOFT_SKILLS else "hard_skill",
                "taxonomy_category": category,
                "sections": set()
            }

        skill_data[skill]["mentions"] += 1
        skill_data[skill]["contexts"].add(section)
        skill_data[skill]["sections"].add(section)

    # Convert sets → lists
    for skill in skill_data:
        skill_data[skill]["contexts"] = list(skill_data[skill]["contexts"])
        skill_data[skill]["sections"] = list(skill_data[skill]["sections"])

    # CGPA
    cgpa = extract_cgpa(text)
    if cgpa:
        skill_data["__cgpa__"] = cgpa

    # META
    skill_data["__meta__"] = {
        "skills_count": len(skill_data) - (1 if "__cgpa__" in skill_data else 0),
        "semantic_device": "cpu"
    }

    return skill_data


# -----------------------------
# PIPELINE CLASS
# -----------------------------
class LayerAExtractor:
    def __init__(self, taxonomy_path: str):
        self.skills, self.skill_to_category, self.term_to_canonical = load_taxonomy(taxonomy_path)

    def run(self, text: str):
        matches = extract_matches(text, self.skills, self.term_to_canonical)
        return build_output(text, matches, self.skill_to_category)


# -----------------------------
# CLI
# -----------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--taxonomy", required=True)
    parser.add_argument("--output", default=None)

    args = parser.parse_args()

    text = Path(args.input).read_text()

    extractor = LayerAExtractor(args.taxonomy)
    result = extractor.run(text)

    output_json = json.dumps(result, indent=2)

    if args.output:
        Path(args.output).write_text(output_json)

    print(output_json)