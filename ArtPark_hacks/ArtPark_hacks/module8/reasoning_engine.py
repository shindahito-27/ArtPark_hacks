from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional


MODULE8_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = MODULE8_DIR.parent
REPO_ROOT = PROJECT_ROOT.parents[1]

DEFAULT_GAP_JSON = REPO_ROOT / "output" / "module_4" / "gapengine_output.json"
DEFAULT_PROFESSION_JSON = REPO_ROOT / "output" / "module_5" / "profession_mapping_output.json"
DEFAULT_ROADMAP_JSON = REPO_ROOT / "output" / "module_6" / "adaptive_path_output.json"
DEFAULT_OUTPUT_JSON = REPO_ROOT / "output" / "module_8" / "reasoning_trace_output.json"
DEFAULT_TEXT_OUTPUT = REPO_ROOT / "output" / "module_8" / "reasoning_trace.txt"
DEFAULT_TOP_K = 3
LEVEL_SORT_ORDER = {
    "Critical Gap": 0,
    "Moderate Gap": 1,
    "Slight Gap": 2,
    "Good Match": 3,
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a reasoning trace report from gap, profession, and roadmap outputs."
    )
    parser.add_argument("gap_json_pos", nargs="?", type=Path, default=None)
    parser.add_argument("profession_json_pos", nargs="?", type=Path, default=None)
    parser.add_argument("roadmap_json_pos", nargs="?", type=Path, default=None)
    parser.add_argument("output_json_pos", nargs="?", type=Path, default=None)
    parser.add_argument("--gap-json", type=Path, default=None)
    parser.add_argument("--profession-json", type=Path, default=None)
    parser.add_argument("--roadmap-json", type=Path, default=None)
    parser.add_argument("--output-json", type=Path, default=None)
    parser.add_argument("--text-out", type=Path, default=DEFAULT_TEXT_OUTPUT)
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    return parser.parse_args()


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"JSON file not found: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected a top-level JSON object in {path}")
    return data


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalized_text(value: Any) -> str:
    return " ".join(str(value or "").replace("_", " ").split()).strip()


def _display_label(value: Any) -> str:
    text = _normalized_text(value)
    if not text:
        return ""

    whole_label_overrides = {
        "api": "API",
        "apis": "APIs",
        "aws": "AWS",
        "ci/cd": "CI/CD",
        "c++": "C++",
        "cv": "CV",
        "gcp": "GCP",
        "github": "GitHub",
        "javascript": "JavaScript",
        "kpis": "KPIs",
        "llm": "LLM",
        "llms": "LLMs",
        "mlops": "MLOps",
        "nlp": "NLP",
        "numpy": "NumPy",
        "power bi": "Power BI",
        "pytorch": "PyTorch",
        "rag": "RAG",
        "scikit-learn": "Scikit-learn",
        "sql": "SQL",
        "tensorflow": "TensorFlow",
    }
    lowered = text.lower()
    if lowered in whole_label_overrides:
        return whole_label_overrides[lowered]

    token_overrides = {
        "ai": "AI",
        "api": "API",
        "apis": "APIs",
        "aws": "AWS",
        "bi": "BI",
        "ci/cd": "CI/CD",
        "cv": "CV",
        "gcp": "GCP",
        "jd": "JD",
        "kpi": "KPI",
        "kpis": "KPIs",
        "llm": "LLM",
        "llms": "LLMs",
        "ml": "ML",
        "mlops": "MLOps",
        "nlp": "NLP",
        "rag": "RAG",
        "sql": "SQL",
        "ui": "UI",
        "ux": "UX",
    }

    words: List[str] = []
    for token in text.split(" "):
        lowered_token = token.lower()
        if lowered_token in token_overrides:
            words.append(token_overrides[lowered_token])
        elif "/" in token:
            words.append("/".join(part.upper() if len(part) <= 3 else part.capitalize() for part in token.split("/")))
        elif "-" in token:
            parts = []
            for part in token.split("-"):
                lowered_part = part.lower()
                if lowered_part in token_overrides:
                    parts.append(token_overrides[lowered_part])
                else:
                    parts.append(part.capitalize())
            words.append("-".join(parts))
        else:
            words.append(token.capitalize())
    return " ".join(words)


def _dedupe_preserve_order(values: List[str]) -> List[str]:
    seen = set()
    ordered: List[str] = []
    for value in values:
        cleaned = " ".join(str(value or "").split()).strip()
        if not cleaned:
            continue
        if cleaned in seen:
            continue
        seen.add(cleaned)
        ordered.append(cleaned)
    return ordered


def _append_reason(reasons: List[str], value: Optional[str]) -> None:
    if not value:
        return
    cleaned = " ".join(str(value).split()).strip()
    if cleaned and cleaned not in reasons:
        reasons.append(cleaned)


def _split_reason_string(value: Any) -> List[str]:
    if not isinstance(value, str):
        return []
    return [part.strip() for part in value.split(";") if part.strip()]


def _joined_examples(values: List[str], limit: int = 2) -> str:
    if not values:
        return ""
    labels = [_display_label(value) for value in values[:limit] if _display_label(value)]
    return ", ".join(labels)


def _natural_join(values: List[str]) -> str:
    cleaned = [value for value in values if value]
    if not cleaned:
        return ""
    if len(cleaned) == 1:
        return cleaned[0]
    if len(cleaned) == 2:
        return f"{cleaned[0]} and {cleaned[1]}"
    return ", ".join(cleaned[:-1]) + f", and {cleaned[-1]}"


def _stable_index(key: Any, size: int, salt: int = 0) -> int:
    if size <= 0:
        return 0
    token = str(key or "")
    return (sum(ord(ch) for ch in token) + salt) % size


def _pick_template(key: Any, templates: List[str], salt: int = 0) -> str:
    if not templates:
        return ""
    return templates[_stable_index(key, len(templates), salt=salt)]


def _score_text(value: Any) -> str:
    return f"{_as_float(value, default=0.0):.2f}"


class ReasoningEngine:
    def __init__(
        self,
        gap_data: Mapping[str, Any],
        profession_data: Mapping[str, Any],
        roadmap_data: Mapping[str, Any],
        top_k: int = DEFAULT_TOP_K,
    ) -> None:
        self.gap_data = gap_data
        self.profession_data = profession_data
        self.roadmap_data = roadmap_data
        self.top_k = max(int(top_k), 1)

    def _roadmap_items(self) -> List[Dict[str, Any]]:
        items = self.roadmap_data.get("roadmap_details", [])
        if not isinstance(items, list):
            return []
        return [item for item in items if isinstance(item, dict)]

    def _top_gap_items(self) -> List[Dict[str, Any]]:
        ranked: List[Dict[str, Any]] = []
        for skill, payload in self.gap_data.items():
            if str(skill).startswith("__") or not isinstance(payload, dict):
                continue
            ranked.append({"skill": skill, **payload})

        ranked.sort(
            key=lambda item: (
                -_as_float(item.get("gap_score"), default=0.0),
                -_as_float(item.get("jd_score"), default=0.0),
                str(item.get("skill") or ""),
            )
        )
        return ranked[: self.top_k]

    def _all_gap_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        for skill, payload in self.gap_data.items():
            if str(skill).startswith("__") or not isinstance(payload, dict):
                continue
            items.append({"skill": skill, **payload})
        return items

    def _build_all_gap_priority_list(self) -> List[Dict[str, Any]]:
        ranked: List[Dict[str, Any]] = []
        for item in self._all_gap_items():
            gap_score = _as_float(item.get("gap_score"), default=0.0)
            if gap_score <= 0.0:
                continue
            ranked.append(item)

        ranked.sort(
            key=lambda item: (
                LEVEL_SORT_ORDER.get(str(item.get("level") or ""), 99),
                -_as_float(item.get("gap_score"), default=0.0),
                -_as_float(item.get("jd_score"), default=0.0),
                str(item.get("skill") or ""),
            )
        )

        output: List[Dict[str, Any]] = []
        for index, item in enumerate(ranked, start=1):
            skill = str(item.get("skill") or "").strip()
            action = _normalized_text(item.get("action"))
            if not action:
                action = "review"
            output.append(
                {
                    "rank": index,
                    "skill": skill,
                    "priority_label": action,
                    "gap_level": str(item.get("level") or ""),
                    "gap_score": round(_as_float(item.get("gap_score"), default=0.0), 2),
                    "jd_score": round(_as_float(item.get("jd_score"), default=0.0), 2),
                    "resume_score": round(_as_float(item.get("resume_score"), default=0.0), 2),
                    "status": str(item.get("status") or ""),
                }
            )
        return output

    def _top_role_items(self) -> List[Dict[str, Any]]:
        items = self.profession_data.get("top_roles", [])
        if not isinstance(items, list):
            return []
        return [item for item in items if isinstance(item, dict)][: self.top_k]

    def _gap_entry_for_skill(self, skill: str) -> Mapping[str, Any]:
        for key in (skill, skill.lower(), skill.replace("-", " ").lower()):
            payload = self.gap_data.get(key)
            if isinstance(payload, Mapping):
                return payload
        return {}

    def _contrast_items(self) -> List[Dict[str, Any]]:
        candidates: List[Dict[str, Any]] = []

        primary_suppressed = self.roadmap_data.get("suppressed_direct_targets", [])
        if isinstance(primary_suppressed, list):
            for item in primary_suppressed:
                if isinstance(item, dict):
                    candidates.append({"source_track": self.roadmap_data.get("recommended_track_type"), **item})

        if candidates:
            return candidates[: self.top_k]

        profession_tracks = self.roadmap_data.get("profession_roadmaps", [])
        if isinstance(profession_tracks, list) and profession_tracks:
            first_track = profession_tracks[0]
            if isinstance(first_track, Mapping):
                suppressed = first_track.get("suppressed_direct_targets", [])
                if isinstance(suppressed, list):
                    for item in suppressed:
                        if isinstance(item, dict):
                            candidates.append({"source_track": first_track.get("track_type"), **item})

        if candidates:
            return candidates[: self.top_k]

        jd_track = self.roadmap_data.get("jd_requirement_roadmap", {})
        if isinstance(jd_track, Mapping):
            suppressed = jd_track.get("suppressed_direct_targets", [])
            if isinstance(suppressed, list):
                for item in suppressed:
                    if isinstance(item, dict):
                        candidates.append({"source_track": jd_track.get("track_type"), **item})

        candidates.sort(
            key=lambda item: (
                -(_as_float(item.get("gap"), default=0.0) * _as_float(item.get("importance"), default=0.0)),
                -_as_float(item.get("jd_score"), default=0.0),
                str(item.get("skill") or ""),
            )
        )
        return candidates[: self.top_k]

    def _build_roadmap_reasons(
        self,
        item: Mapping[str, Any],
        track_type: str,
        is_first: bool,
    ) -> List[str]:
        reasons: List[str] = []
        skill = str(item.get("skill") or "").strip().lower()
        gap_entry = self._gap_entry_for_skill(skill)
        jd_requirement_score = _as_float(gap_entry.get("jd_score"), default=0.0)
        importance = _as_float(item.get("jd_importance"), default=0.0)
        direct_gap = _as_float(item.get("direct_gap"), default=0.0)
        effective_gap = _as_float(item.get("effective_gap"), default=0.0)
        candidate_signal = _as_float(item.get("candidate_signal"), default=0.0)
        dependency_weight = _as_float(item.get("dependency_weight"), default=1.0)
        blocking_targets = [
            str(value) for value in item.get("blocking_targets", []) if _normalized_text(value)
        ]
        unlocks = [str(value) for value in item.get("unlocks", []) if _normalized_text(value)]
        if jd_requirement_score >= 5.0:
            _append_reason(
                reasons,
                _pick_template(
                    skill,
                    [
                        f"high importance in target job requirements (score: {_score_text(jd_requirement_score)})",
                        f"strong signal in the target job requirements (score: {_score_text(jd_requirement_score)})",
                        f"priority skill in the target job requirements (score: {_score_text(jd_requirement_score)})",
                    ],
                    salt=1,
                ),
            )
        elif jd_requirement_score >= 4.0:
            _append_reason(
                reasons,
                _pick_template(
                    skill,
                    [
                        f"high importance in target job requirements (score: {_score_text(jd_requirement_score)})",
                        f"strong importance in the target job requirements (score: {_score_text(jd_requirement_score)})",
                        f"clearly important in the target job requirements (score: {_score_text(jd_requirement_score)})",
                    ],
                    salt=2,
                ),
            )
        elif jd_requirement_score >= 3.5:
            _append_reason(
                reasons,
                _pick_template(
                    skill,
                    [
                        f"important in target job requirements (score: {_score_text(jd_requirement_score)})",
                        f"visible in the target job requirements (score: {_score_text(jd_requirement_score)})",
                        f"meaningfully represented in the target job requirements (score: {_score_text(jd_requirement_score)})",
                    ],
                    salt=2,
                ),
            )
        elif importance >= 3.0:
            _append_reason(
                reasons,
                _pick_template(
                    skill,
                    [
                        f"builds capability needed for the mapped role (role score: {_score_text(importance)})",
                        f"required to advance toward the mapped role expectations (role score: {_score_text(importance)})",
                        f"supports role-level capability for the mapped profession (role score: {_score_text(importance)})",
                    ],
                    salt=3,
                ),
            )
        elif importance > 0.0:
            _append_reason(
                reasons,
                _pick_template(
                    skill,
                    [
                        f"supports day-to-day capability for the mapped role (role score: {_score_text(importance)})",
                        f"helps extend the mapped role skill set (role score: {_score_text(importance)})",
                        f"adds useful coverage for the mapped profession (role score: {_score_text(importance)})",
                    ],
                    salt=4,
                ),
            )

        remaining_gap = max(effective_gap, direct_gap)
        if candidate_signal <= 0.05 and remaining_gap > 0.0:
            _append_reason(
                reasons,
                _pick_template(
                    skill,
                    [
                        f"no prior evidence of this skill appears in the candidate profile (signal: {_score_text(candidate_signal)}, gap: {_score_text(remaining_gap)})",
                        f"candidate profile shows no prior evidence for this skill (signal: {_score_text(candidate_signal)}, gap: {_score_text(remaining_gap)})",
                        f"no measurable prior exposure appears in the candidate profile (signal: {_score_text(candidate_signal)}, gap: {_score_text(remaining_gap)})",
                    ],
                    salt=5,
                ),
            )
        elif candidate_signal <= 0.2 and remaining_gap > 0.0:
            _append_reason(
                reasons,
                _pick_template(
                    skill,
                    [
                        f"only weak evidence exists in the candidate profile, so the remaining gap is still material (signal: {_score_text(candidate_signal)}, gap: {_score_text(remaining_gap)})",
                        f"candidate shows limited prior evidence, leaving a meaningful remaining gap (signal: {_score_text(candidate_signal)}, gap: {_score_text(remaining_gap)})",
                        f"prior exposure is still thin in the candidate profile (signal: {_score_text(candidate_signal)}, gap: {_score_text(remaining_gap)})",
                    ],
                    salt=6,
                ),
            )
        elif remaining_gap > 0.0:
            _append_reason(
                reasons,
                _pick_template(
                    skill,
                    [
                        f"some prior evidence exists, but it is still below target strength (signal: {_score_text(candidate_signal)}, gap: {_score_text(remaining_gap)})",
                        f"candidate has a base signal here, but the role expectation is still higher (signal: {_score_text(candidate_signal)}, gap: {_score_text(remaining_gap)})",
                    ],
                    salt=7,
                ),
            )

        critical_targets = [
            _display_label(target)
            for target in blocking_targets
            if str(self._gap_entry_for_skill(target).get("level") or "") == "Critical Gap" and _display_label(target)
        ]
        high_priority_targets = [
            _display_label(target)
            for target in blocking_targets
            if _as_float(self._gap_entry_for_skill(target).get("jd_score"), default=0.0) >= 5.0 and _display_label(target)
        ]
        if track_type == "jd_requirement":
            if str(gap_entry.get("level") or "") == "Critical Gap":
                _append_reason(
                    reasons,
                    f"directly closes a critical JD gap in {_display_label(skill)}",
                )
            elif critical_targets:
                _append_reason(
                    reasons,
                    f"selected because it directly supports critical JD gaps like {_natural_join(critical_targets[:2])}",
                )
            elif high_priority_targets:
                _append_reason(
                    reasons,
                    f"selected because it directly supports high-priority JD gaps like {_natural_join(high_priority_targets[:2])}",
                )

        blocking_labels = [_display_label(value) for value in blocking_targets[:2] if _display_label(value)]
        blocking_text = _natural_join(blocking_labels)
        if dependency_weight > 1.0 and blocking_text:
            _append_reason(
                reasons,
                _pick_template(
                    skill,
                    [
                        f"forms the foundation for {blocking_text}",
                        f"needed before you can effectively learn {blocking_text}",
                        f"has to come earlier because it supports {blocking_text}",
                    ],
                    salt=8,
                ),
            )
        elif dependency_weight > 1.0:
            _append_reason(
                reasons,
                _pick_template(
                    skill,
                    [
                        f"sits early in the dependency graph, so learning it now reduces friction later (weight: {_score_text(dependency_weight)})",
                        f"comes early in the learning path because later topics depend on it (weight: {_score_text(dependency_weight)})",
                    ],
                    salt=9,
                ),
            )

        unlock_labels = [_display_label(value) for value in unlocks[:2] if _display_label(value)]
        unlock_text = _natural_join(unlock_labels)
        if unlock_text:
            _append_reason(
                reasons,
                _pick_template(
                    skill,
                    [
                        f"unlocks downstream skills like {unlock_text}",
                        f"opens up later topics such as {unlock_text}",
                        f"creates a path to downstream skills like {unlock_text}",
                    ],
                    salt=10,
                ),
            )

        priority = _as_float(item.get("priority"), default=0.0)
        if is_first:
            _append_reason(
                reasons,
                f"ranked highest due to strongest combined priority score (priority: {_score_text(priority)})",
            )
        elif len(reasons) < 4 and priority > 0.0:
            _append_reason(
                reasons,
                _pick_template(
                    skill,
                    [
                        f"still carries a strong path priority score (priority: {_score_text(priority)})",
                        f"retains meaningful path priority in the current roadmap (priority: {_score_text(priority)})",
                    ],
                    salt=11,
                ),
            )

        if len(reasons) < 3:
            for fallback in _split_reason_string(item.get("reason")):
                if len(reasons) >= 5:
                    break
                _append_reason(reasons, fallback)

        return reasons[:5]

    def _build_role_reasons(self, item: Mapping[str, Any], is_first: bool) -> List[str]:
        reasons: List[str] = []
        role_name = str(item.get("role") or "").strip().lower()
        candidate_best_fit_role = str(self.roadmap_data.get("candidate_best_fit_role") or "").strip()
        target_jd_role = str(self.roadmap_data.get("target_jd_role") or "").strip()
        recommended_track_type = str(self.roadmap_data.get("recommended_track_type") or "").strip()
        core_skills_found = [str(value) for value in item.get("core_skills_found", []) if _normalized_text(value)]
        matched_skills = [str(value) for value in item.get("matched_skills", []) if _normalized_text(value)]
        missing_core = [str(value) for value in item.get("missing_core_skills", []) if _normalized_text(value)]
        missing_skills = [str(value) for value in item.get("missing_skills", []) if _normalized_text(value)]
        score = _as_float(item.get("score"), default=0.0)
        base_similarity = _as_float(item.get("base_similarity"), default=0.0)
        matched_labels = [_display_label(value) for value in matched_skills[:3] if _display_label(value)]
        core_labels = [_display_label(value) for value in core_skills_found[:3] if _display_label(value)]
        missing_core_labels = [_display_label(value) for value in missing_core[:2] if _display_label(value)]
        missing_labels = [_display_label(value) for value in missing_skills[:2] if _display_label(value)]

        if matched_skills:
            overlap_text = _natural_join(matched_labels)
            if len(matched_skills) >= 6:
                _append_reason(
                    reasons,
                    f"high overlap in {len(matched_skills)} matched skills including {overlap_text}",
                )
            else:
                _append_reason(
                    reasons,
                    f"meaningful overlap in {len(matched_skills)} matched skills including {overlap_text}",
                )

        if core_skills_found:
            _append_reason(
                reasons,
                f"{len(core_skills_found)} core {'skill' if len(core_skills_found) == 1 else 'skills'} already {'aligns' if len(core_skills_found) == 1 else 'align'} with this role, including {_natural_join(core_labels)}",
            )

        if missing_core:
            _append_reason(
                reasons,
                f"{len(missing_core)} core gap{'s' if len(missing_core) != 1 else ''} {'remain' if len(missing_core) != 1 else 'remains'}, mainly {_natural_join(missing_core_labels)}",
            )
        elif missing_skills:
            _append_reason(
                reasons,
                f"remaining gaps are limited to {len(missing_skills)} non-core skills, mainly {_natural_join(missing_labels)}",
            )

        if is_first and recommended_track_type == "jd_requirement":
            if target_jd_role and candidate_best_fit_role and candidate_best_fit_role.lower() != target_jd_role.lower():
                _append_reason(
                    reasons,
                    f"although {_display_label(candidate_best_fit_role)} is the closest fit from the resume, the roadmap prioritizes the target JD first",
                )
            elif candidate_best_fit_role:
                _append_reason(
                    reasons,
                    f"although {_display_label(candidate_best_fit_role)} is the closest fit from current resume evidence, the roadmap still prioritizes direct JD gaps first",
                )

        if is_first:
            _append_reason(
                reasons,
                f"selected as best-fit profession because it received the highest role score ({_score_text(score)})",
            )
        elif score > 0.0:
            _append_reason(
                reasons,
                _pick_template(
                    role_name,
                    [
                        f"role alignment score remains competitive at {_score_text(score)}",
                        f"overall role score is still strong at {_score_text(score)}",
                    ],
                    salt=12,
                ),
            )

        if len(reasons) < 4 and base_similarity > 0.0:
            _append_reason(
                reasons,
                f"base similarity with the role skill profile is {_score_text(base_similarity)}",
            )

        if len(reasons) < 3:
            for fallback in _split_reason_string(item.get("reason")):
                if len(reasons) >= 5:
                    break
                _append_reason(reasons, fallback)

        return reasons[:5]

    def _build_gap_reasons(self, item: Mapping[str, Any]) -> List[str]:
        reasons: List[str] = []
        skill = str(item.get("skill") or "").strip().lower()
        jd_phrase = str(item.get("jd_phrase") or "").strip().lower()
        jd_score = _as_float(item.get("jd_score"), default=0.0)
        gap_score = _as_float(item.get("gap_score"), default=0.0)
        resume_score = _as_float(item.get("resume_score"), default=0.0)
        status = str(item.get("status") or "").strip().lower()
        level = str(item.get("level") or "").strip()
        normalization_applied = bool(item.get("level_normalization_applied"))
        normalization_factor = _as_float(item.get("level_normalization_factor"), default=1.0)

        if jd_phrase in {"required", "mandatory", "must have"}:
            _append_reason(reasons, f"mandatory in the job description (JD score: {_score_text(jd_score)})")
        elif jd_score >= 6.0:
            _append_reason(
                reasons,
                _pick_template(
                    skill,
                    [
                        f"critical requirement in the job description (JD score: {_score_text(jd_score)})",
                        f"high-importance requirement in the job description (JD score: {_score_text(jd_score)})",
                    ],
                    salt=13,
                ),
            )
        elif jd_score >= 4.0:
            _append_reason(reasons, f"important requirement in the job description (JD score: {_score_text(jd_score)})")

        if status == "missing" or resume_score <= 0.1:
            _append_reason(
                reasons,
                _pick_template(
                    skill,
                    [
                        f"strong gap due to little or no prior experience (gap: {_score_text(gap_score)}, resume score: {_score_text(resume_score)})",
                        f"clear gap because the candidate profile shows almost no prior evidence (gap: {_score_text(gap_score)}, resume score: {_score_text(resume_score)})",
                    ],
                    salt=14,
                ),
            )
        elif status == "partial_match":
            _append_reason(
                reasons,
                f"partial evidence exists, but it remains below job expectations (gap: {_score_text(gap_score)}, resume score: {_score_text(resume_score)})",
            )
        elif gap_score > 0.0:
            _append_reason(
                reasons,
                f"role expectation still exceeds the current evidence level (gap: {_score_text(gap_score)}, resume score: {_score_text(resume_score)})",
            )

        if level == "Critical Gap":
            _append_reason(reasons, "classified as Critical Gap by the gap engine")
        elif level == "Moderate Gap":
            _append_reason(reasons, "classified as Moderate Gap by the gap engine")

        if normalization_applied and gap_score > 0.0:
            _append_reason(
                reasons,
                f"still remains a gap after seniority normalization (factor: {_score_text(normalization_factor)})",
            )

        return reasons[:5]

    def _build_contrast_reasons(self, item: Mapping[str, Any]) -> List[str]:
        reasons: List[str] = []
        skill = str(item.get("skill") or "").strip().lower()
        gap_entry = self._gap_entry_for_skill(skill)
        jd_score = _as_float(gap_entry.get("jd_score"), default=_as_float(item.get("jd_score"), default=0.0))
        candidate_signal = _as_float(item.get("candidate_signal"), default=0.0)
        suppressed_reason = str(item.get("suppressed_reason") or "").strip().lower()

        if jd_score >= 5.0:
            _append_reason(reasons, f"it still has high JD importance (score: {_score_text(jd_score)})")
        elif jd_score >= 3.5:
            _append_reason(reasons, f"it still has meaningful JD importance (score: {_score_text(jd_score)})")

        if candidate_signal <= 0.05:
            _append_reason(reasons, f"the candidate profile currently shows no prior evidence for it (signal: {_score_text(candidate_signal)})")
        elif candidate_signal <= 0.2:
            _append_reason(reasons, f"candidate evidence is still limited at this stage (signal: {_score_text(candidate_signal)})")

        if "not connected" in suppressed_reason:
            _append_reason(reasons, "not selected now because it is not strongly connected to the current learning path")
        elif suppressed_reason:
            _append_reason(reasons, _normalized_text(suppressed_reason))

        _append_reason(reasons, "better revisited after the connected core path is completed")
        return reasons[:5]

    def _build_jd_qualification_assessment(self) -> Dict[str, Any]:
        items = self._all_gap_items()
        if not items:
            return {
                "verdict": "unknown",
                "verdict_label": "Unknown",
                "summary": "Overall JD judgement could not be computed because Module 4 gap data is empty.",
                "reasoning_trace": ["Module 4 gap analysis did not return any skill entries."],
            }

        total_skills = len(items)
        critical_count = sum(1 for item in items if str(item.get("level") or "") == "Critical Gap")
        moderate_count = sum(1 for item in items if str(item.get("level") or "") == "Moderate Gap")
        missing_count = sum(1 for item in items if str(item.get("status") or "") == "missing")
        partial_count = sum(1 for item in items if str(item.get("status") or "") == "partial_match")
        matched_count = sum(1 for item in items if str(item.get("status") or "") == "matched")

        total_jd_score = sum(_as_float(item.get("jd_score"), default=0.0) for item in items)
        covered_score = sum(
            min(
                _as_float(item.get("resume_score"), default=0.0),
                _as_float(item.get("jd_score"), default=0.0),
            )
            for item in items
        )
        coverage_ratio = (covered_score / total_jd_score) if total_jd_score > 0.0 else 0.0

        if coverage_ratio >= 0.8 and critical_count == 0 and missing_count <= max(1, total_skills // 10):
            verdict = "matched"
            verdict_label = "Matched"
            reasoning = [
                f"overall JD coverage from Module 4 gap analysis is {coverage_ratio:.2%}",
                f"critical gaps are absent and only {missing_count} skill{'s' if missing_count != 1 else ''} remain fully missing",
                f"{matched_count} skills are already good matches against the JD",
                "current evidence is broadly aligned with the target JD",
            ]
        elif coverage_ratio >= 0.5 and critical_count <= 1 and missing_count <= max(3, total_skills // 3):
            verdict = "qualified"
            verdict_label = "Qualified"
            reasoning = [
                f"overall JD coverage from Module 4 gap analysis is {coverage_ratio:.2%}",
                f"{critical_count} critical gap{'s' if critical_count != 1 else ''} and {moderate_count} moderate gaps remain",
                f"{partial_count} skills show partial evidence, so the candidate has a workable base for this JD",
                "the candidate appears viable for the JD, but clear upskilling is still needed",
            ]
        else:
            verdict = "not_qualified"
            verdict_label = "Not Qualified"
            reasoning = [
                f"overall JD coverage from Module 4 gap analysis is {coverage_ratio:.2%}",
                f"{critical_count} critical gap{'s' if critical_count != 1 else ''} and {moderate_count} moderate gaps remain",
                f"{missing_count} JD skills are still fully missing, while only {matched_count} skill{'s' if matched_count != 1 else ''} are good matches",
                "current evidence is below the level expected by this JD",
            ]

        summary = (
            f"Overall JD judgement: {verdict_label}. "
            f"Coverage is {coverage_ratio:.2%} across {total_skills} evaluated JD skills."
        )
        return {
            "verdict": verdict,
            "verdict_label": verdict_label,
            "coverage_ratio": round(coverage_ratio, 4),
            "total_skills": total_skills,
            "critical_gap_count": critical_count,
            "moderate_gap_count": moderate_count,
            "missing_skill_count": missing_count,
            "partial_match_count": partial_count,
            "matched_skill_count": matched_count,
            "summary": summary,
            "reasoning_trace": reasoning,
        }

    def _build_decision_perspective(self) -> Dict[str, str]:
        candidate_best_fit_role = str(self.roadmap_data.get("candidate_best_fit_role") or "").strip() or "Unknown"
        target_jd_role = str(self.roadmap_data.get("target_jd_role") or "").strip() or "Unknown"
        selection_reason = str(
            self.roadmap_data.get("track_selection_reason")
            or self.roadmap_data.get("__meta__", {}).get("track_selection_reason")
            or ""
        ).strip()
        policy = str(self.roadmap_data.get("roadmap_selection_policy") or "").strip()
        if policy == "jd_dominant_role_supported":
            roadmap_policy = "Roadmap policy: JD alignment first, role support second."
        else:
            roadmap_policy = "Roadmap policy: current primary track selection follows the active roadmap output."

        return {
            "best_fit_role": candidate_best_fit_role,
            "target_jd_role": target_jd_role,
            "roadmap_policy": roadmap_policy,
            "selection_reason": selection_reason,
        }

    def _build_roadmap_reasoning(self) -> List[Dict[str, Any]]:
        items = self._roadmap_items()[: self.top_k]
        if not items:
            return []

        track_type = str(self.roadmap_data.get("recommended_track_type") or self.roadmap_data.get("track_type") or "")
        output: List[Dict[str, Any]] = []

        for index, item in enumerate(items):
            skill = str(item.get("skill") or "").strip()
            if not skill:
                continue

            reasons = self._build_roadmap_reasons(
                item=item,
                track_type=track_type,
                is_first=index == 0,
            )
            if index == 0:
                heading = f"{_display_label(skill)} selected first because:"
            elif item.get("phase"):
                heading = f"{_display_label(skill)} recommended in {item.get('phase')} because:"
            else:
                heading = f"{_display_label(skill)} recommended because:"

            output.append(
                {
                    "skill": skill,
                    "heading": heading,
                    "phase": item.get("phase"),
                    "track_type": track_type,
                    "reasoning_trace": reasons,
                }
            )

        return output

    def _build_profession_reasoning(self) -> List[Dict[str, Any]]:
        items = self._top_role_items()
        output: List[Dict[str, Any]] = []

        for index, item in enumerate(items):
            role_name = str(item.get("role") or "").strip()
            if not role_name:
                continue

            heading = (
                f"{_display_label(role_name)} selected as best-fit profession because:"
                if index == 0
                else f"{_display_label(role_name)} also matches because:"
            )
            output.append(
                {
                    "role": role_name,
                    "heading": heading,
                    "reasoning_trace": self._build_role_reasons(item, is_first=index == 0),
                }
            )

        return output

    def _build_gap_reasoning(self) -> List[Dict[str, Any]]:
        items = self._top_gap_items()
        output: List[Dict[str, Any]] = []

        for item in items:
            skill = str(item.get("skill") or "").strip()
            if not skill:
                continue

            level = str(item.get("level") or "").strip()
            if level == "Critical Gap":
                heading = f"{_display_label(skill)} marked as critical because:"
            else:
                heading = f"{_display_label(skill)} marked as a gap because:"

            output.append(
                {
                    "skill": skill,
                    "heading": heading,
                    "reasoning_trace": self._build_gap_reasons(item),
                }
            )

        return output

    def _build_contrast_reasoning(self) -> List[Dict[str, Any]]:
        items = self._contrast_items()
        output: List[Dict[str, Any]] = []

        for item in items:
            skill = str(item.get("skill") or "").strip()
            if not skill:
                continue

            output.append(
                {
                    "skill": skill,
                    "heading": f"{_display_label(skill)} not selected in the current roadmap because:",
                    "reasoning_trace": self._build_contrast_reasons(item),
                }
            )

        return output

    def build_payload(self) -> Dict[str, Any]:
        jd_qualification = self._build_jd_qualification_assessment()
        decision_perspective = self._build_decision_perspective()
        all_gap_priorities = self._build_all_gap_priority_list()
        roadmap_reasoning = self._build_roadmap_reasoning()
        profession_reasoning = self._build_profession_reasoning()
        gap_reasoning = self._build_gap_reasoning()
        contrast_reasoning = self._build_contrast_reasoning()
        summary_line = (
            "Every recommendation in our system is explainable - "
            "we do not just give outputs, we show the reasoning behind them."
        )

        report_text = render_reasoning_report(
            summary_line=summary_line,
            jd_qualification=jd_qualification,
            decision_perspective=decision_perspective,
            all_gap_priorities=all_gap_priorities,
            roadmap_reasoning=roadmap_reasoning,
            profession_reasoning=profession_reasoning,
            gap_reasoning=gap_reasoning,
            contrast_reasoning=contrast_reasoning,
        )

        return {
            "__meta__": {
                "recommended_track_type": self.roadmap_data.get("recommended_track_type"),
                "jd_qualification_verdict": jd_qualification.get("verdict"),
                "all_gap_priority_count": len(all_gap_priorities),
                "roadmap_reasoning_count": len(roadmap_reasoning),
                "profession_reasoning_count": len(profession_reasoning),
                "gap_reasoning_count": len(gap_reasoning),
                "contrast_reasoning_count": len(contrast_reasoning),
                "top_k": self.top_k,
            },
            "summary_line": summary_line,
            "jd_qualification_assessment": jd_qualification,
            "decision_perspective": decision_perspective,
            "all_jd_gaps_with_priority": all_gap_priorities,
            "roadmap_reasoning": roadmap_reasoning,
            "profession_reasoning": profession_reasoning,
            "gap_reasoning": gap_reasoning,
            "contrast_reasoning": contrast_reasoning,
            "report_text": report_text,
        }


def render_reasoning_report(
    summary_line: str,
    jd_qualification: Dict[str, Any],
    decision_perspective: Dict[str, str],
    all_gap_priorities: List[Dict[str, Any]],
    roadmap_reasoning: List[Dict[str, Any]],
    profession_reasoning: List[Dict[str, Any]],
    gap_reasoning: List[Dict[str, Any]],
    contrast_reasoning: List[Dict[str, Any]],
) -> str:
    lines = [
        "Reasoning Trace",
        "",
        summary_line,
        "",
        "Overall JD Judgement",
        str(jd_qualification.get("summary") or "Overall JD judgement is unavailable."),
    ]

    for reason in jd_qualification.get("reasoning_trace", [])[:5]:
        lines.append(f"- {reason}")

    lines.extend(
        [
            "",
            "Decision Perspective",
            f"- Best-fit role from resume: {decision_perspective.get('best_fit_role') or 'Unknown'}",
            f"- Target JD perspective: {decision_perspective.get('target_jd_role') or 'Unknown'}",
            f"- {decision_perspective.get('roadmap_policy') or 'Roadmap policy unavailable.'}",
        ]
    )
    if decision_perspective.get("selection_reason"):
        lines.append(f"- {decision_perspective.get('selection_reason')}")

    lines.extend(
        [
            "",
            "All JD Gaps With Priority",
        "1. Roadmap Reasoning",
        ]
    )

    lines = lines[:-1]
    lines.extend(_render_gap_priority_section(all_gap_priorities))
    lines.append("")
    lines.append("1. Roadmap Reasoning")

    lines.extend(_render_reasoning_section(roadmap_reasoning))
    lines.append("")
    lines.append("2. Profession Mapping Reasoning")
    lines.extend(_render_reasoning_section(profession_reasoning))
    lines.append("")
    lines.append("3. JD Gap Reasoning")
    lines.extend(_render_reasoning_section(gap_reasoning))
    lines.append("")
    lines.append("4. Contrast Reasoning")
    lines.extend(_render_reasoning_section(contrast_reasoning))
    return "\n".join(lines).strip() + "\n"


def _render_gap_priority_section(items: List[Dict[str, Any]]) -> List[str]:
    if not items:
        return ["No JD gaps found in Module 4 output."]

    lines: List[str] = []
    for item in items:
        lines.append(
            f"- {item.get('rank')}. {_display_label(item.get('skill'))} - "
            f"{item.get('priority_label')} | {item.get('gap_level')} | "
            f"gap score: {_score_text(item.get('gap_score'))} | "
            f"JD score: {_score_text(item.get('jd_score'))} | "
            f"status: {item.get('status')}"
        )
    return lines


def _render_reasoning_section(items: List[Dict[str, Any]]) -> List[str]:
    if not items:
        return ["No reasoning items available."]

    lines: List[str] = []
    for index, item in enumerate(items):
        if index > 0:
            lines.append("")
        lines.append(str(item.get("heading") or "Recommendation selected because:"))
        reasons = item.get("reasoning_trace", [])
        if not isinstance(reasons, list) or not reasons:
            lines.append("- recommendation derived from available pipeline signals")
            continue
        for reason in _dedupe_preserve_order([str(reason) for reason in reasons])[:5]:
            lines.append(f"- {reason}")
    return lines


def main() -> None:
    args = _parse_args()
    gap_json = args.gap_json or args.gap_json_pos or DEFAULT_GAP_JSON
    profession_json = args.profession_json or args.profession_json_pos or DEFAULT_PROFESSION_JSON
    roadmap_json = args.roadmap_json or args.roadmap_json_pos or DEFAULT_ROADMAP_JSON
    output_json = args.output_json or args.output_json_pos or DEFAULT_OUTPUT_JSON
    text_out = args.text_out or DEFAULT_TEXT_OUTPUT

    gap_data = _load_json(gap_json)
    profession_data = _load_json(profession_json)
    roadmap_data = _load_json(roadmap_json)

    engine = ReasoningEngine(
        gap_data=gap_data,
        profession_data=profession_data,
        roadmap_data=roadmap_data,
        top_k=args.top_k,
    )
    payload = engine.build_payload()

    output_json.parent.mkdir(parents=True, exist_ok=True)
    text_out.parent.mkdir(parents=True, exist_ok=True)

    output_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    text_out.write_text(str(payload.get("report_text") or ""), encoding="utf-8")

    print(f"Reasoning JSON written to: {output_json}")
    print(f"Reasoning text written to: {text_out}")


if __name__ == "__main__":
    main()
