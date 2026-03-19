from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Dict, List


BASE_ALIASES = {
    "js": "javascript",
    "tf": "tensorflow",
    "cv": "computer vision",
    "postgres": "postgresql",
    "node": "nodejs",
    "node.js": "nodejs",
}


def _norm(value: str) -> str:
    cleaned = str(value or "").strip().lower()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned


@lru_cache(maxsize=1)
def _load_taxonomy() -> Dict[str, object]:
    root = Path(__file__).resolve().parents[1]
    env_path = os.getenv("SKILL_TAXONOMY_PATH", "").strip()
    candidates: List[Path] = []
    if env_path:
        candidates.append(Path(env_path))
    candidates.extend(
        [
            root / "module2" / "module2_semantic" / "skill_taxonomy_500plus(2).json",
            root / "module2_semantic" / "skill_taxonomy_500plus(2).json",
            root / "module2" / "skill_taxonomy_500plus(1).json",
        ]
    )
    for taxonomy_path in candidates:
        if not taxonomy_path.exists():
            continue
        return json.loads(taxonomy_path.read_text(encoding="utf-8"))
    return {"aliases": {}, "skills": []}


@lru_cache(maxsize=1)
def _build_aliases() -> Dict[str, str]:
    payload = _load_taxonomy()
    alias_map: Dict[str, str] = {}

    root_aliases = payload.get("aliases", {})
    if isinstance(root_aliases, dict):
        for alias, canonical in root_aliases.items():
            alias_norm = _norm(alias)
            canonical_norm = _norm(canonical)
            if alias_norm and canonical_norm:
                alias_map[alias_norm] = canonical_norm

    for entry in payload.get("skills", []):
        if not isinstance(entry, dict):
            continue
        canonical = _norm(entry.get("canonical_skill", ""))
        if not canonical:
            continue
        for alias in entry.get("aliases", []) or []:
            alias_norm = _norm(alias)
            if alias_norm:
                alias_map[alias_norm] = canonical

    for alias, canonical in BASE_ALIASES.items():
        alias_map[_norm(alias)] = _norm(canonical)

    return alias_map


SKILL_ALIASES = _build_aliases()


def normalize_skill_name(skill: str) -> str:
    normalized = _norm(skill)
    return SKILL_ALIASES.get(normalized, normalized)
