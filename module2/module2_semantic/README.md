# Module 2 Semantic Pipeline

This folder contains the Person B pipeline for semantic skill extraction. It is independent from Person A logic, accepts `keyword_output` as input, uses the shared skill inventory from `shared/skills.py`, and returns the strict final schema only.

## Files

- `embedding_utils.py`: Loads `sentence-transformers` model `all-MiniLM-L6-v2` once and exposes embedding helpers.
- `similarity.py`: Provides cosine similarity utility.
- `semantic_matcher.py`: Matches sentence embeddings against cached skill embeddings and keeps the best semantic score per skill.
- `fusion.py`: Merges keyword and semantic results into the final schema.
- `personB_pipeline.py`: Main entry point for the full semantic pipeline.

## Input Format

The pipeline expects:

```python
text: str
keyword_output: dict
```

Example:

```python
{
    "python": {
        "keyword_score": 1.0,
        "mentions": 3,
        "contexts": ["skills", "project"],
    }
}
```

## Output Format

The pipeline returns only this schema:

```python
{
    "python": {
        "confidence": 0.92,
        "source": ["keyword", "semantic"],
    }
}
```

Rules:

- All output skill keys are lowercase.
- No extra fields are returned.
- Skills not present in `shared/skills.py` are ignored.

## Matching Logic

1. Split the input text into sentences.
2. Embed sentences with `all-MiniLM-L6-v2`.
3. Load and cache shared skill embeddings once per process.
4. Compute semantic similarity for each sentence against all skills.
5. Keep only the top 3 skill matches per sentence.
6. Accept a semantic match only if similarity is greater than `0.65`.
7. Fuse semantic scores with `keyword_output`.

## Fusion Rule

If both keyword and semantic scores exist:

```python
confidence = 0.6 * keyword_score + 0.4 * semantic_score
```

If a skill exists in only one source, that score is used directly.

## Usage

```python
from module2_semantic.personB_pipeline import run_semantic_pipeline

text = "Built REST APIs with Python and FastAPI. Deployed services on AWS."
keyword_output = {
    "python": {
        "keyword_score": 1.0,
        "mentions": 2,
        "contexts": ["skills"],
    }
}

result = run_semantic_pipeline(text, keyword_output)
print(result)
```

### CLI Generator (Layer-A Style JSON)

Use this script to build a semantic JSON with `confidence`, `source`, `mentions`, `contexts`, category labels, and `__cgpa__`:

```bash
python module2_semantic/generate_resume_skill_json.py \
  --resume-pdf /home/kirat/artparl/ArtPark_hacks/module_1_Parse_extractor/main_Resume-2.pdf \
  --output /home/kirat/artparl/ArtPark_hacks/module2/module2_semantic/layer_a_semantic_resume.json
```

Other input options:

```bash
python module2_semantic/generate_resume_skill_json.py --resume-json /path/to/resume_data.json
python module2_semantic/generate_resume_skill_json.py --text-file /path/to/input.txt
```

Device control:

```bash
python module2_semantic/generate_resume_skill_json.py --device auto   # default
python module2_semantic/generate_resume_skill_json.py --device cpu
python module2_semantic/generate_resume_skill_json.py --device cuda
```

## Dependency

Install required packages before running:

```bash
pip install sentence-transformers numpy scikit-learn
```

`scikit-learn` is listed because it is commonly installed alongside `sentence-transformers`, even though this implementation computes cosine similarity with NumPy.
