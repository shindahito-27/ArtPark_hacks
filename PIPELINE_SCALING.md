# Pipeline Scaling & Calibration Guide

This document defines how scoring is standardized across modules to ensure:
- Interpretability of outputs
- Consistent scaling across the pipeline
- Centralized tuning and calibration

---

## 1. Canonicalization Layer (Pre-Scoring)

All skills are normalized before entering the scoring pipeline.

- Shared alias map:
  `module5/profession_mapping_engine_dataset_v7.json`

Examples:
- `api` → `apis`
- `natural language processing` → `nlp`
- `node`, `nodejs` → `node.js`

**Purpose:**
Ensures consistent matching, aggregation, and scoring across modules.

---

## 2. Module 2: Candidate Skill Strength

- Primary score: `resulting_score` → **Scale: 0–10**
- Confidence signals: `confidence`, `roadmap_signal` → **Scale: 0–1**

### Scoring Components:
- Section/context weighting
- Mention frequency boosts
- Generic skill penalties
- Technical grounding thresholds

### Key Calibration Parameters:
- `candidate_strength_scale = 10.0`
- `mention_boost_per_extra = 0.04`
- `max_mention_multiplier = 1.15`
- `generic_skill_drop_threshold = 0.2`
- `grounded_technical_signal_floor = 0.32`

---

## 3. Module 3: JD Requirement Intelligence

- JD skill weight represents **requirement strength**
- Effective downstream scale: **0–10**

### Derived From:
- Importance phrases (`mandatory`, `required`, etc.)
- Frequency signals
- Experience/seniority modifiers

### Interpretation:
- Higher score → stronger employer expectation
- Serves as the **primary importance signal** in gap computation

---

## 4. Module 4: Gap Engine

### Core Formulation:

gap_score = max(0, adjusted_jd_score - resume_score)

surplus_score = max(0, resume_score - adjusted_jd_score)


### Scale:
- `gap_score`: **0+ (non-negative)**

### Key Features:
- Signed gaps are internally computed but not exposed
- Level normalization adjusts JD expectations dynamically
- Output includes `level_normalization_factor`

### Interpretation:
- `gap_score = 0` → requirement met or exceeded
- Higher `gap_score` → stronger upskilling priority

---

## 5. Module 5: Profession Mapping Engine

### Scales:
- Candidate signal → **0–1**
- Role weights → **0–1**

### Core Method:
- Cosine similarity over weighted skill vectors
- Adjusted using priors, penalties, and role constraints

### Final Scoring:

`final_score =
	(
  (similarity_weight * cosine_similarity * prior_scale)
  	+ prior_weight * prior * level_bias
  	+ core_overlap_boost
  	- missing_core_penalty
	)
	* missing_core_score_scale`

Where:

prior_scale = prior_similarity_floor + prior_similarity_gain * prior * level_bias

### Key Adjustments:
- Soft skill caps (role-dependent)
- Generic skill suppression
- Core skill penalties (additive + multiplicative)

### Important Parameters:
- `soft_skill_cap_technical = 0.15`
- `soft_skill_cap_management = 0.35`
- `zero_core_overlap_penalty = 0.08`
- `missing_core_penalty_per_skill = 0.025`
- `prior_similarity_floor = 0.7`
- `prior_similarity_gain = 0.3`

### Interpretation:
- `score` → bounded fit score (not probability)
- `roadmap_signal` → per-skill strength indicator

---

## 6. Module 6: Adaptive Path Engine

### Inputs:
- `gap_score` (Module 4)
- `roadmap_signal` (candidate signal)
- Skill dependency graph

### Core Ranking Formula:

priority = (effective_gap * effective_importance * dependency_weight) / (difficulty + 0.1)


### Adjustments:
- Prerequisite sequence boosting
- Known-skill priority discounting
- JD-aligned gap discounting

### Definitions:
- `effective_gap` → direct + propagated gap pressure
- `effective_importance` → direct + inherited importance
- `dependency_weight` → graph unlock value
- `difficulty` → role-based difficulty proxy

### Key Parameters:
- `adaptive_known_skill_threshold = 0.25`
- `adaptive_min_target_gap = 0.6`
- `adaptive_known_skill_priority_discount = 0.72`
- `adaptive_jd_known_skill_gap_discount = 0.35`
- `adaptive_jd_strong_skill_gap_discount = 0.15`
- `adaptive_prerequisite_sequence_boost_per_target = 0.08`

### Output:
- Ranked, dependency-aware learning roadmap
- Temporally structured (week-wise) execution plan

---

## 7. Module 7: Learning Resource Layer

### Design:
- Fully static (no dynamic scraping)
- Deterministic resource attachment

### Constraints:
- Minimum resources per skill: `2`
- Maximum resources per skill: `3`

### Source Priority:

module7 static JSON
→ module5 dataset
→ module6 embedded resources
→ curated fallback bucket


---

## 8. Central Calibration (Single Source of Truth)

All major tuning parameters are defined in:

module5/profession_mapping_engine_dataset_v7.json


### This includes:
- Skill alias normalization
- Generic skill penalties
- Role priors and mapping weights
- Adaptive roadmap thresholds
- Resource constraints

---

## Design Philosophy

- **Deterministic over generative** → avoids hallucinated outputs
- **Modular architecture** → strict JSON contracts between modules
- **Explainability-first** → all outputs are traceable
- **Centralized calibration** → system behavior controlled from a single source

---

## Summary

This scaling framework ensures that:

- All modules operate on **aligned score ranges**
- System behavior is **predictable and tunable**
- Outputs remain **interpretable and explainable**
- Calibration can be performed **without modifying core logic**
