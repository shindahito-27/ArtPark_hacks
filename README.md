# Resume Extraction (PDF)

A Python-based resume parser that extracts:
- Full raw text from a resume PDF
- Structured sections (`skills`, `projects`, `experience`, `education`, `achievements`, `leadership_roles`)
- Hyperlinks (visible links and embedded/clickable PDF links)

## What This Project Does

The parser reads a resume PDF using two extraction engines:
- `PyMuPDF` (primary)
- `pdfplumber` (fallback/comparison)

It scores extraction quality and chooses the better text result, then:
- Detects section headings
- Splits section content into clean entries
- Extracts hyperlinks from both text and PDF annotations

## Project Files

- `main_extraction.py`: Standalone parser script
- `requirements.txt`: Pinned Python dependencies
- `main_Resume-2.pdf`: Sample input resume
- `main_Resume-2.pdf.txt`: Extracted plain text output

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

Run with JSON output:

```bash
python main_extraction.py main_Resume-2.pdf --json
```

Run and only write extracted text file:

```bash
python main_extraction.py main_Resume-2.pdf
```

Optional custom text output path:

```bash
python main_extraction.py main_Resume-2.pdf --txt-out extracted_resume.txt
```

## Output Format

JSON output contains:
- `raw_text`: Full extracted text
- `sections`: Parsed sections
- `hyperlinks`: URL/email/phone links found in text or embedded in the PDF

Example top-level structure:

```json
{
  "raw_text": "...",
  "sections": {
    "skills": [],
    "projects": [],
    "experience": [],
    "education": [],
    "achievements": [],
    "leadership_roles": []
  },
  "hyperlinks": []
}
```

## Notes

- Heading matching supports common variants like `Technical Skills`, `Achievements`, and `Leadership Experience`.
- Best results are with text-based PDFs (not fully scanned image PDFs).
