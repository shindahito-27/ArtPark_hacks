from __future__ import annotations

from functools import lru_cache
from typing import List

from .aliases import _load_taxonomy, normalize_skill_name


@lru_cache(maxsize=1)
def _load_skills() -> List[str]:
    payload = _load_taxonomy()
    skills = set()
    for entry in payload.get("skills", []):
        if not isinstance(entry, dict):
            continue
        canonical = normalize_skill_name(entry.get("canonical_skill", ""))
        if canonical:
            skills.add(canonical)
    return sorted(skills)


SKILLS = _load_skills()

