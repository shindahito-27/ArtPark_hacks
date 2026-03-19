from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Dict, List, Optional

import pdfplumber
import pymupdf


FORM_FEED = chr(12)
URL_REGEX = re.compile(r"(?i)\b(?:https?://|www\.)[^\s<>\"\]\[(){}]+")
TARGET_SECTIONS = (
    "skills",
    "projects",
    "experience",
    "education",
    "achievements",
    "leadership_roles",
)

SECTION_PATTERNS = {
    "skills": (
        "skills",
        "technical skills",
        "core skills",
        "skill set",
    ),
    "projects": (
        "projects",
        "project experience",
        "academic projects",
    ),
    "experience": (
        "experience",
        "work experience",
        "professional experience",
        "employment",
        "internship",
        "internships",
    ),
    "education": (
        "education",
        "academic background",
        "qualifications",
    ),
    "achievements": (
        "achievements",
        "achievement",
        "accomplishments",
        "awards",
    ),
    "leadership_roles": (
        "leadership roles",
        "leadership role",
        "leadership",
        "leadership experience",
        "positions of responsibility",
        "responsibilities",
    ),
    "certifications": (
        "certifications",
        "certification",
        "certificates",
        "licenses",
    ),
}

SECTION_REGEX = re.compile(
    r"^\s*[\W_]*(skills?|projects?|experience|education|achievements?|leadership(?:\s+(?:roles?|experience))?|certifications?)\b[\W_]*$",
    flags=re.IGNORECASE,
)


def _normalize_heading(line: str) -> str:
    normalized = re.sub(r"[\s:|._-]+", " ", line.strip().lower())
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized


def _match_heading(line: str) -> Optional[str]:
    if not line or len(line.split()) > 4:
        return None

    normalized = _normalize_heading(line)
    for section, aliases in SECTION_PATTERNS.items():
        if normalized in aliases:
            return section

    if SECTION_REGEX.match(line.strip()):
        if normalized.startswith("leadership"):
            return "leadership_roles"
        token = re.sub(r"[^a-z]", "", normalized)
        for section in SECTION_PATTERNS:
            if token.startswith(section.rstrip("s")):
                return section
    return None


def _clean_line(line: str) -> str:
    line = line.strip()
    line = re.sub(r"^[\-\*\u2022\u25cf\u00b7\u25e6]+\s*", "", line)
    line = re.sub(r"\s+", " ", line)
    return line.strip()


def _extract_text_pymupdf(file_path: str) -> str:
    pages: List[str] = []
    with pymupdf.open(file_path) as doc:
        for page in doc:
            text = page.get_text("text", sort=True).strip()
            if not text:
                blocks = page.get_text("blocks")
                sorted_blocks = sorted(blocks, key=lambda b: (round(b[1], 1), round(b[0], 1)))
                text = "\n".join(
                    block[4].strip() for block in sorted_blocks if len(block) > 4 and str(block[4]).strip()
                )
            pages.append(text)
    return FORM_FEED.join(pages).strip()


def _extract_text_pdfplumber(file_path: str) -> str:
    pages: List[str] = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text(layout=True) or page.extract_text() or ""
            pages.append(text.strip())
    return FORM_FEED.join(pages).strip()


def _quality_score(text: str) -> float:
    if not text:
        return 0.0

    heading_hits = len(
        re.findall(
            r"(?im)^\s*(skills?|projects?|experience|education|achievements?|leadership(?:\s+(?:roles?|experience))?|certifications?)\s*:?\s*$",
            text,
        )
    )
    bullet_hits = len(re.findall(r"(?m)^\s*[\-\*\u2022\u25cf\u00b7]\s+", text))
    line_hits = text.count("\n")
    length_score = min(len(text), 30000) / 1200.0
    return (heading_hits * 3.0) + (bullet_hits * 0.4) + (line_hits * 0.03) + length_score


def _normalize_url(url: str) -> str:
    cleaned = url.strip().rstrip(".,;:)")
    if cleaned.lower().startswith("www."):
        cleaned = f"https://{cleaned}"
    return cleaned


def _extract_urls_from_text(text: str) -> List[str]:
    urls: List[str] = []
    seen = set()
    for match in URL_REGEX.finditer(text or ""):
        normalized = _normalize_url(match.group(0))
        key = normalized.lower()
        if normalized and key not in seen:
            seen.add(key)
            urls.append(normalized)
    return urls


def _extract_pdf_embedded_links(file_path: str) -> List[str]:
    links: List[str] = []
    seen = set()
    with pymupdf.open(file_path) as doc:
        for page in doc:
            for link in page.get_links():
                uri = str(link.get("uri") or "").strip()
                if not uri:
                    continue
                normalized = _normalize_url(uri)
                key = normalized.lower()
                if normalized and key not in seen:
                    seen.add(key)
                    links.append(normalized)
    return links


def extract_hyperlinks(file_path: str, raw_text: str) -> List[str]:
    urls = _extract_urls_from_text(raw_text)
    seen = {url.lower() for url in urls}
    if Path(file_path).suffix.lower() == ".pdf":
        try:
            for url in _extract_pdf_embedded_links(file_path):
                key = url.lower()
                if key not in seen:
                    seen.add(key)
                    urls.append(url)
        except Exception:
            pass
    return urls


def extract_raw_text(file_path: str) -> str:
    pymupdf_text = ""
    pdfplumber_text = ""

    try:
        pymupdf_text = _extract_text_pymupdf(file_path)
    except Exception:
        pymupdf_text = ""

    is_pdf = Path(file_path).suffix.lower() == ".pdf"
    if is_pdf:
        try:
            pdfplumber_text = _extract_text_pdfplumber(file_path)
        except Exception:
            pdfplumber_text = ""

    if pymupdf_text and not pdfplumber_text:
        return pymupdf_text
    if pdfplumber_text and not pymupdf_text:
        return pdfplumber_text
    if pymupdf_text and pdfplumber_text:
        pymupdf_score = _quality_score(pymupdf_text)
        pdfplumber_score = _quality_score(pdfplumber_text)
        return pdfplumber_text if pdfplumber_score > (pymupdf_score * 1.05) else pymupdf_text

    raise RuntimeError("Unable to extract text with both PyMuPDF and pdfplumber.")


def _parse_skills(lines: List[str]) -> List[str]:
    merged = "\n".join(lines)
    raw_items = re.split(r"[\n,;|/]+", merged)
    skills: List[str] = []
    seen = set()
    for item in raw_items:
        cleaned = _clean_line(item)
        if not cleaned:
            continue
        key = cleaned.lower()
        if key not in seen:
            seen.add(key)
            skills.append(cleaned)
    return skills


def _parse_generic_entries(lines: List[str]) -> List[str]:
    entries: List[str] = []
    current: List[str] = []
    for raw_line in lines:
        stripped = raw_line.strip()
        if not stripped:
            if current:
                entries.append(" ".join(current).strip())
                current = []
            continue

        cleaned = _clean_line(raw_line)
        is_bullet = bool(re.match(r"^\s*[\-\*\u2022\u25cf\u00b7]", raw_line))
        if is_bullet and current:
            entries.append(" ".join(current).strip())
            current = [cleaned]
        else:
            current.append(cleaned)

    if current:
        entries.append(" ".join(current).strip())

    deduped: List[str] = []
    seen = set()
    for entry in entries:
        key = entry.lower()
        if entry and key not in seen:
            seen.add(key)
            deduped.append(entry)
    return deduped


def split_sections(raw_text: str) -> Dict[str, List[str]]:
    section_lines: Dict[str, List[str]] = {name: [] for name in TARGET_SECTIONS}
    current_section: Optional[str] = None

    for line in raw_text.replace(FORM_FEED, "\n").splitlines():
        heading = _match_heading(line)
        if heading:
            current_section = heading
            continue
        if current_section in section_lines:
            section_lines[current_section].append(line.rstrip())

    return {
        "skills": _parse_skills(section_lines["skills"]),
        "projects": _parse_generic_entries(section_lines["projects"]),
        "experience": _parse_generic_entries(section_lines["experience"]),
        "education": _parse_generic_entries(section_lines["education"]),
        "achievements": _parse_generic_entries(section_lines["achievements"]),
        "leadership_roles": _parse_generic_entries(section_lines["leadership_roles"]),
    }


def parse_resume(file_path: str) -> Dict[str, object]:
    raw_text = extract_raw_text(file_path)
    sections = split_sections(raw_text)
    hyperlinks = extract_hyperlinks(file_path, raw_text)
    return {"raw_text": raw_text, "sections": sections, "hyperlinks": hyperlinks}


def write_text_output(file_path: str, text: str, output_path: Optional[str] = None) -> Path:
    target = Path(output_path) if output_path else Path(str(file_path) + ".txt")
    target.write_bytes(text.encode("utf-8"))
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description="Resume parser using PyMuPDF + pdfplumber fallback.")
    parser.add_argument("file", help="Path to resume document.")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print parsed resume_data JSON to stdout.",
    )
    parser.add_argument(
        "--txt-out",
        default=None,
        help="Optional output path for extracted text. Defaults to '<file>.txt'.",
    )
    args = parser.parse_args()

    resume_data = parse_resume(args.file)
    output_file = write_text_output(args.file, resume_data["raw_text"], args.txt_out)

    if args.json:
        print(json.dumps(resume_data, indent=2, ensure_ascii=False))
    else:
        print(f"Text extracted to: {output_file}")


if __name__ == "__main__":
    main()



