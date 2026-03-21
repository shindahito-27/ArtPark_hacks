# Pipeline Scaling Guide

This note explains how scores are scaled across modules so the outputs stay interpretable and the tuning knobs stay in one place.

## Canonicalization First

- Skills are canonicalized before scoring.
- The shared alias map lives in [`ArtPark_hacks/ArtPark_hacks/module5/profession_mapping_engine_dataset_v7.json`](/home/kirat/artpark/ArtPark_hacks/ArtPark_hacks/module5/profession_mapping_engine_dataset_v7.json).
- Examples:
  - `api` -> `apis`
  - `natural language processing` -> `nlp`
  - `node`, `nodejs` -> `node.js`

## Module 2: Candidate Skill Strength

- Main strength field: `resulting_score`
- Scale: `0-10`
- Confidence-style fields such as `confidence` / `roadmap_signal`
- Scale: `0-1`
- Candidate role-mapping signal uses:
  - section/context multipliers
  - mention boosts
  - generic-skill caps and penalties

Important knobs in `mapping_policy`:

- `candidate_strength_scale = 10.0`
- `mention_boost_per_extra = 0.04`
- `max_mention_multiplier = 1.15`
- `generic_skill_drop_threshold = 0.2`
- `grounded_technical_signal_floor = 0.32`

## Module 3: JD Skill Importance

- JD skill weights are treated as requirement strength.
- Effective scale in downstream modules: approximately `0-10`
- Weight is built from:
  - importance phrase strength
  - frequency bonus
  - experience/seniority modifiers

Interpretation:

- higher JD score = stronger employer expectation
- this is the main `importance` input to the gap engine

## Module 4: Gap Engine

- Public deficit field: `gap_score`
- Scale: `0+`
- Formula:

```text
gap_score = max(0, adjusted_jd_score - resume_score)
surplus_score = max(0, resume_score - adjusted_jd_score)
```

- Negative signed gaps are not exposed to the roadmap anymore.
- Level normalization is applied before the final public gap:
  - candidate level vs JD level adjusts the JD pressure
  - output includes `level_normalization_factor`

Interpretation:

- `gap_score = 0` means the candidate already meets or exceeds the requirement
- larger positive `gap_score` means stronger learning need

## Module 5: Profession Mapping

- Candidate technical signal for role mapping
- Scale: `0-1`
- Role weights in the dataset
- Scale: `0-1`
- Similarity uses cosine similarity over weighted vectors.

Current final score shape:

```text
final_score =
(
  (similarity_weight * cosine_similarity * prior_scale)
  + prior_weight * prior * level_bias
  + core_overlap_boost
  - missing_core_penalty
)
* missing_core_score_scale
```

Where:

- `prior_scale = prior_similarity_floor + prior_similarity_gain * prior * level_bias`
- technical roles cap soft skills heavily in cosine similarity
- generic skills are capped or dropped before they can dominate
- missing core skills reduce score both additively and multiplicatively

Important knobs:

- `soft_skill_cap_technical = 0.15`
- `soft_skill_cap_management = 0.35`
- `zero_core_overlap_penalty = 0.08`
- `missing_core_penalty_per_skill = 0.025`
- `missing_core_penalty_ratio_weight = 0.03`
- `missing_core_score_scale_per_skill = 0.05`
- `missing_core_score_scale_ratio_weight = 0.1`
- `missing_core_score_scale_floor = 0.8`
- `prior_similarity_floor = 0.7`
- `prior_similarity_gain = 0.3`

Useful interpretation:

- `score` is a bounded fit score, not a probability
- `signal` / `roadmap_signal` is a per-skill presence strength

## Module 6: Adaptive Path Engine

- Inputs:
  - positive `gap_score` from module 4
  - `roadmap_signal` / candidate signal from module 5
  - dependency graph from the dataset
- Output priority scale: open-ended positive score used only for ranking

Core ranking formula:

```text
priority =
  (effective_gap * effective_importance * dependency_weight)
  / (difficulty + 0.1)
```

Then adjusted by:

- prerequisite sequence boost
- known-skill priority discount
- JD known-skill gap discount

Definitions:

- `effective_gap`: direct gap or propagated prerequisite pressure
- `effective_importance`: direct importance or inherited downstream importance
- `dependency_weight`: graph unlock/foundational value
- `difficulty`: role-frequency/role-weight derived difficulty proxy

Important knobs:

- `adaptive_known_skill_threshold = 0.25`
- `adaptive_min_target_gap = 0.6`
- `adaptive_known_skill_priority_discount = 0.72`
- `adaptive_jd_known_skill_gap_discount = 0.35`
- `adaptive_jd_strong_skill_gap_discount = 0.15`
- `adaptive_prerequisite_sequence_boost_per_target = 0.08`

Track separation:

- `candidate_best_fit_role` = best mapped profession
- `target_jd_role` = JD target view
- `profession_roadmaps` and `jd_requirement_roadmap` are intentionally separate

## Module 7: Learning Resources

- No dynamic scraping
- Static curated resources are attached to roadmap items
- Each emitted skill should have at least `2` named resources
- Max shown per skill: `3`

Source priority:

```text
module7 static JSON
-> module5 dataset resources
-> module6 embedded resources
-> curated fallback bucket
```

Important knobs:

- `minimum_named_resources_per_skill = 2`
- `maximum_named_resources_per_skill = 3`

## Single Source Of Truth

Most shared tuning values live in:

- [`ArtPark_hacks/ArtPark_hacks/module5/profession_mapping_engine_dataset_v7.json`](/home/kirat/artpark/ArtPark_hacks/ArtPark_hacks/module5/profession_mapping_engine_dataset_v7.json)

Use that file as the main calibration surface for:

- alias normalization
- generic-skill penalties
- profession-mapping priors and penalties
- adaptive roadmap thresholds
- resource limits
