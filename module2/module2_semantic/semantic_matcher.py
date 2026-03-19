"""Production-ready semantic matching for Person B skill extraction."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Dict, Iterable, List, Sequence

import numpy as np

from shared.aliases import SKILL_ALIASES, normalize_skill_name

from .embedding_utils import embed_sentences


TOP_SKILLS_PER_UNIT = 3
DEFAULT_THRESHOLD = 0.65
CONTEXT_WEIGHTS = {
    "projects": 1.0,
    "experience": 0.9,
    "skills": 0.7,
    "unknown": 1.0,
    "other": 0.5,
}
TECH_KEYWORDS = {
    "api",
    "apis",
    "backend",
    "classification",
    "cloud",
    "container",
    "containers",
    "database",
    "data",
    "deployment",
    "docker",
    "etl",
    "infrastructure",
    "model",
    "models",
    "pipeline",
    "pipelines",
    "query",
    "resume",
    "service",
    "services",
    "system",
    "systems",
}
ACTION_VERBS = {
    "architected",
    "automated",
    "built",
    "created",
    "deployed",
    "designed",
    "developed",
    "implemented",
    "improved",
    "led",
    "managed",
    "mentored",
    "optimized",
    "trained",
    "used",
    "working",
    "worked",
}
PROGRAMMING_DATA_SKILLS = {
    "c",
    "c++",
    "css",
    "data analysis",
    "data engineering",
    "data science",
    "django",
    "fastapi",
    "flask",
    "golang",
    "html",
    "java",
    "javascript",
    "mongodb",
    "mysql",
    "node.js",
    "numpy",
    "pandas",
    "postgresql",
    "python",
    "react",
    "rest api",
    "scikit-learn",
    "sql",
    "typescript",
}
ML_AI_SKILLS = {
    "computer vision",
    "deep learning",
    "machine learning",
    "nlp",
    "pytorch",
    "tensorflow",
}
CUSTOM_EXPANSIONS: Dict[str, List[str]] = {
    "aws": [
        "aws cloud computing deployment infrastructure ec2 s3 lambda",
        "amazon web services cloud deployment scalable backend systems",
        "aws infrastructure devops cloud platform operations",
    ],
    "azure": [
        "azure cloud computing infrastructure deployment app services storage",
        "microsoft azure cloud platform deployment devops operations",
        "azure infrastructure containers virtual machines networking",
    ],
    "computer vision": [
        "computer vision image processing visual recognition detection models",
        "image classification object detection visual intelligence pipelines",
        "vision models image data feature extraction inference",
    ],
    "communication": [
        "communication stakeholder collaboration presentation coordination teamwork",
        "cross-functional communication documentation meetings collaboration delivery",
        "clear communication teamwork stakeholder management professional interaction",
    ],
    "data analysis": [
        "data analysis reporting metrics dashboards business insights excel",
        "analyzing datasets statistics reporting visualization business intelligence",
        "data exploration insights reporting dashboard creation analytics",
    ],
    "data engineering": [
        "data engineering pipelines etl batch processing warehousing orchestration",
        "building data pipelines ingestion transformation scalable data systems",
        "etl workflows pipeline orchestration storage processing data platforms",
    ],
    "data science": [
        "data science predictive analytics experimentation statistical modeling",
        "data science machine learning insights models analytics workflows",
        "statistical analysis predictive modeling experimentation data products",
    ],
    "deep learning": [
        "deep learning neural networks model training inference pytorch tensorflow",
        "neural network architectures representation learning training pipelines",
        "deep learning models embeddings sequence models computer vision",
    ],
    "docker": [
        "docker containerization devops deployment kubernetes containers microservices",
        "docker images container orchestration deployment environments",
        "containerized applications docker devops backend deployment workflows",
    ],
    "excel": [
        "excel spreadsheets reporting analysis formulas dashboards business data",
        "microsoft excel data reporting analytics spreadsheet modeling",
        "spreadsheet analysis reporting metrics excel business workflows",
    ],
    "fastapi": [
        "fastapi python backend api development async web services",
        "fastapi rest api microservices python backend engineering",
        "python fastapi services backend endpoints web application development",
    ],
    "flask": [
        "flask python web application backend api development",
        "flask backend services python microframework rest endpoints",
        "python flask web services backend engineering deployment",
    ],
    "git": [
        "git version control collaboration branching code management",
        "source control git repositories versioning collaboration workflows",
        "git commits branches pull requests release engineering",
    ],
    "kubernetes": [
        "kubernetes container orchestration deployment scaling cluster management",
        "kubernetes devops containers cloud-native deployment operations",
        "cluster orchestration kubernetes deployments services scaling infrastructure",
    ],
    "leadership": [
        "leadership mentoring ownership decision making team delivery management",
        "technical leadership mentoring planning execution stakeholder alignment",
        "leading teams delivery ownership mentoring collaboration management",
    ],
    "linux": [
        "linux operating systems shell servers infrastructure deployment",
        "linux environments command line systems administration backend operations",
        "unix linux production systems deployment automation environments",
    ],
    "machine learning": [
        "machine learning model training prediction classification regression",
        "ml algorithms feature engineering evaluation inference pipelines",
        "predictive modeling supervised learning model development analytics",
    ],
    "mongodb": [
        "mongodb nosql database document store backend persistence",
        "document database mongodb backend storage querying applications",
        "mongodb collections nosql storage application data models",
    ],
    "mysql": [
        "mysql relational database sql querying schema design",
        "mysql database management relational storage queries transactions",
        "sql mysql backend database operations reporting analytics",
    ],
    "nlp": [
        "natural language processing text classification information extraction embeddings",
        "nlp text analytics language models entity extraction resume parsing",
        "document understanding text mining language processing pipelines",
    ],
    "node.js": [
        "node.js javascript backend server development apis services",
        "node js backend runtime web services api development",
        "javascript server-side engineering node.js applications microservices",
    ],
    "numpy": [
        "numpy numerical computing arrays vectorized python data processing",
        "scientific computing arrays matrix operations numpy python",
        "numpy data manipulation numerical analysis backend ml preprocessing",
    ],
    "pandas": [
        "pandas data analysis dataframe transformation cleaning python",
        "data wrangling pandas analytics reporting tabular processing",
        "python pandas dataframes preprocessing analysis pipelines",
    ],
    "postgresql": [
        "postgresql relational database sql querying schema indexing",
        "postgres database backend storage reporting analytics transactions",
        "postgresql data persistence relational modeling application queries",
    ],
    "power bi": [
        "power bi dashboards reporting business intelligence analytics visualization",
        "business reporting dashboards metrics visualization power bi insights",
        "power bi data reporting dashboard design business analytics",
    ],
    "project management": [
        "project management planning coordination delivery stakeholder communication",
        "roadmap planning execution delivery tracking team coordination",
        "managing timelines scope resources delivery cross-functional projects",
    ],
    "python": [
        "python programming backend scripting fastapi flask pandas numpy",
        "backend development python services automation api engineering",
        "python data processing scripting machine learning applications",
    ],
    "pytorch": [
        "pytorch deep learning neural network training modeling",
        "pytorch model training tensors inference deep learning pipelines",
        "neural network development pytorch experiments model optimization",
    ],
    "react": [
        "react frontend javascript component development web interfaces",
        "react ui development frontend applications state management",
        "react web apps frontend engineering javascript components",
    ],
    "rest api": [
        "rest api backend service endpoints http integration development",
        "api design backend endpoints web services restful architecture",
        "restful services backend integration application interfaces",
    ],
    "scikit-learn": [
        "scikit-learn machine learning model training evaluation preprocessing",
        "sklearn classification regression feature engineering ml workflows",
        "scikit-learn predictive modeling analytics experimentation pipelines",
    ],
    "sql": [
        "sql database querying relational database postgresql mysql",
        "structured query language analytics joins schema reporting",
        "sql queries relational data analysis backend persistence",
    ],
    "tableau": [
        "tableau dashboards reporting data visualization business intelligence",
        "tableau analytics dashboards metrics insights reporting workflows",
        "data visualization tableau dashboard creation reporting analytics",
    ],
    "tensorflow": [
        "tensorflow deep learning neural network model training",
        "tensorflow machine learning pipelines inference training experiments",
        "neural models tensorflow deep learning production workflows",
    ],
}
_SKILL_STORE: "SkillStore | None" = None
_SKILL_STORE_LOCK = Lock()


@dataclass(frozen=True)
class TextUnit:
    """Semantic text unit extracted from resume text."""

    text: str
    context: str = "other"
    origin: str = "sentence"


@dataclass(frozen=True)
class SkillStore:
    """Cached multi-vector representation of all allowed skills."""

    skills: tuple[str, ...]
    thresholds: np.ndarray
    variant_matrix: np.ndarray
    variant_skill_indices: np.ndarray
    expansions: Dict[str, str]
    variants: Dict[str, List[str]]


def _dedupe_preserve_order(values: Iterable[str]) -> List[str]:
    seen = set()
    ordered: List[str] = []
    for value in values:
        normalized = " ".join(value.strip().split())
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return ordered


def get_skill_category(skill: str) -> str:
    """Return the semantic threshold category for a skill."""
    canonical_skill = normalize_skill_name(skill)
    if canonical_skill in ML_AI_SKILLS:
        return "ml_ai"
    if canonical_skill in PROGRAMMING_DATA_SKILLS:
        return "programming_data"
    return "tools_general"


def get_dynamic_threshold(skill: str) -> float:
    """Return per-skill threshold by category."""
    category = get_skill_category(skill)
    if category == "programming_data":
        return 0.6
    if category == "ml_ai":
        return 0.55
    return DEFAULT_THRESHOLD


def expand_skill(skill: str) -> str:
    """
    Build a reusable semantic expansion string for a skill.

    Every skill is expanded beyond a single token to support richer embedding.
    """
    canonical_skill = normalize_skill_name(skill)
    if canonical_skill in CUSTOM_EXPANSIONS:
        return CUSTOM_EXPANSIONS[canonical_skill][0]

    category = get_skill_category(canonical_skill)
    tokens = canonical_skill.replace(".", " ").replace("-", " ").split()
    alias_terms = [
        alias.replace(".", " ").replace("-", " ")
        for alias, target in SKILL_ALIASES.items()
        if normalize_skill_name(target) == canonical_skill
    ]

    if category == "programming_data":
        descriptors = ["development", "implementation", "backend", "data workflows", "engineering"]
    elif category == "ml_ai":
        descriptors = ["modeling", "training", "inference", "analytics", "machine intelligence"]
    else:
        descriptors = ["tooling", "deployment", "operations", "production workflows", "engineering"]

    expansion_parts = [canonical_skill]
    expansion_parts.extend(tokens)
    expansion_parts.extend(alias_terms)
    expansion_parts.extend(descriptors)
    return " ".join(_dedupe_preserve_order(expansion_parts))


def build_skill_variants(skill: str) -> List[str]:
    """Create multiple semantic variants for a skill."""
    canonical_skill = normalize_skill_name(skill)
    if canonical_skill in CUSTOM_EXPANSIONS:
        return _dedupe_preserve_order(CUSTOM_EXPANSIONS[canonical_skill])

    expansion = expand_skill(canonical_skill)
    category = get_skill_category(canonical_skill)

    if category == "programming_data":
        variants = [
            expansion,
            f"{canonical_skill} programming development backend engineering data processing",
            f"{canonical_skill} implementation application services projects production usage",
        ]
    elif category == "ml_ai":
        variants = [
            expansion,
            f"{canonical_skill} models training inference experimentation analytics",
            f"{canonical_skill} machine learning pipelines research production deployment",
        ]
    else:
        variants = [
            expansion,
            f"{canonical_skill} tooling deployment operations platform engineering",
            f"{canonical_skill} practical experience projects implementation delivery",
        ]
    return _dedupe_preserve_order(variants)


def build_skill_store(skills: Sequence[str]) -> SkillStore:
    """Build cached multi-vector embeddings for all allowed skills."""
    canonical_skills = tuple(_dedupe_preserve_order(normalize_skill_name(skill) for skill in skills))
    variant_texts: List[str] = []
    variant_skill_indices: List[int] = []
    expansions: Dict[str, str] = {}
    variants_by_skill: Dict[str, List[str]] = {}

    for skill_index, skill in enumerate(canonical_skills):
        expansions[skill] = expand_skill(skill)
        skill_variants = build_skill_variants(skill)
        variants_by_skill[skill] = skill_variants
        for variant in skill_variants:
            variant_texts.append(variant)
            variant_skill_indices.append(skill_index)

    variant_vectors = embed_sentences(variant_texts)
    variant_matrix = (
        np.vstack(variant_vectors).astype(np.float32)
        if variant_vectors
        else np.zeros((0, 0), dtype=np.float32)
    )
    thresholds = np.asarray([get_dynamic_threshold(skill) for skill in canonical_skills], dtype=np.float32)

    return SkillStore(
        skills=canonical_skills,
        thresholds=thresholds,
        variant_matrix=variant_matrix,
        variant_skill_indices=np.asarray(variant_skill_indices, dtype=np.int32),
        expansions=expansions,
        variants=variants_by_skill,
    )


def get_skill_store(skills: Sequence[str]) -> SkillStore:
    """Return the global cached multi-vector skill store."""
    global _SKILL_STORE
    if _SKILL_STORE is None:
        with _SKILL_STORE_LOCK:
            if _SKILL_STORE is None:
                _SKILL_STORE = build_skill_store(skills)
    return _SKILL_STORE


def is_informative_text(text: str) -> bool:
    """Filter out short and non-informative noisy fragments."""
    tokens = [token.strip(".,:;()[]{}").lower() for token in text.split()]
    tokens = [token for token in tokens if token]
    if len(tokens) < 3:
        return False
    if any(token in ACTION_VERBS for token in tokens):
        return True
    return any(token in TECH_KEYWORDS for token in tokens)


def _context_weight(context: str) -> float:
    return float(CONTEXT_WEIGHTS.get(context, 1.0))


def match_semantic_skills(
    text_units: Sequence[TextUnit],
    skill_store: SkillStore,
) -> Dict[str, Dict[str, float]]:
    """
    Match normalized text units against multi-vector skill embeddings.

    Returns a compact semantic payload per skill:
    {
        "python": {"semantic_score": 0.81, "match_count": 2}
    }
    """
    if not text_units or skill_store.variant_matrix.size == 0:
        return {}

    unique_units: List[TextUnit] = []
    seen_units = set()
    for unit in text_units:
        normalized_text = " ".join(unit.text.strip().split()).lower()
        if not normalized_text or normalized_text in seen_units:
            continue
        seen_units.add(normalized_text)
        unique_units.append(TextUnit(text=normalized_text, context=unit.context, origin=unit.origin))

    if not unique_units:
        return {}

    unit_vectors = embed_sentences(unit.text for unit in unique_units)
    if not unit_vectors:
        return {}

    unit_matrix = np.vstack(unit_vectors).astype(np.float32)
    similarity_matrix = unit_matrix @ skill_store.variant_matrix.T

    unit_skill_scores = np.full((len(unique_units), len(skill_store.skills)), -1.0, dtype=np.float32)
    for variant_index, skill_index in enumerate(skill_store.variant_skill_indices):
        np.maximum(
            unit_skill_scores[:, skill_index],
            similarity_matrix[:, variant_index],
            out=unit_skill_scores[:, skill_index],
        )

    context_weights = np.asarray([_context_weight(unit.context) for unit in unique_units], dtype=np.float32)
    weighted_scores = unit_skill_scores * context_weights[:, None]

    best_scores = np.zeros(len(skill_store.skills), dtype=np.float32)
    match_counts = np.zeros(len(skill_store.skills), dtype=np.int32)

    for unit_index in range(weighted_scores.shape[0]):
        row = weighted_scores[unit_index]
        if row.size == 0:
            continue

        top_k = min(TOP_SKILLS_PER_UNIT, row.size)
        candidate_indices = np.argpartition(row, -top_k)[-top_k:]
        ranked_indices = candidate_indices[np.argsort(row[candidate_indices])[::-1]]

        for skill_index in ranked_indices:
            score = float(row[skill_index])
            if score < float(skill_store.thresholds[skill_index]):
                continue
            best_scores[skill_index] = max(best_scores[skill_index], score)
            match_counts[skill_index] += 1

    semantic_output: Dict[str, Dict[str, float]] = {}
    for skill_index, skill in enumerate(skill_store.skills):
        if best_scores[skill_index] <= 0.0:
            continue
        semantic_output[skill] = {
            "semantic_score": round(float(best_scores[skill_index]), 4),
            "match_count": int(match_counts[skill_index]),
        }
    return semantic_output
