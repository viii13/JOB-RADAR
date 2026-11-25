"""Resume Text Extraction and Canonical Skill Parsing.

Stage 5.2 — Supports PDF (via pypdf), DOCX (via python-docx), and TXT.
Reuses JobRadar's canonical skill taxonomy, alias map, and categorization
from `job_market.skills`.
"""

from __future__ import annotations

import io
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
import re
import sys
from typing import Any, BinaryIO

# Ensure backend source is on sys.path to reuse skills.py
_current_dir = Path(__file__).resolve().parent
_phase5_root = _current_dir.parent
_project_root = _phase5_root.parent.parent
_backend_src = _project_root / "DDS-Job-Market-Project" / "src"
_ref_dir = _project_root / "DDS-Job-Market-Project" / "data" / "reference"

if str(_backend_src) not in sys.path:
    sys.path.insert(0, str(_backend_src))

from job_market.skills import (
    _SPECIAL_DESCRIPTION_PATTERNS,
    build_description_patterns,
    load_alias_map,
    load_category_map,
)

# Limits
MAX_FILE_SIZE_BYTES: int = 5 * 1024 * 1024  # 5 MB
MAX_PAGE_COUNT: int = 10
MIN_TEXT_LENGTH_NON_SCANNED: int = 20
SUPPORTED_EXTENSIONS: set[str] = {".pdf", ".docx", ".txt"}


@dataclass(frozen=True)
class ExtractedSkill:
    """Canonical skill extracted from resume with context evidence."""

    canonical_name: str
    category: str
    evidence: str


@dataclass(frozen=True)
class ResumeExtractionResult:
    """Result of resume text extraction and skill parsing."""

    status: str  # "success", "unsupported_format", "empty_file", "file_too_large", "corrupt_file", "scanned_pdf", "password_protected"
    file_type: str
    extracted_skill_count: int
    skills: list[ExtractedSkill]
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Convert result container to serializable dictionary."""
        return {
            "status": self.status,
            "file_type": self.file_type,
            "extracted_skill_count": self.extracted_skill_count,
            "skills": [asdict(s) for s in self.skills],
            "warnings": self.warnings,
        }


class ResumeSkillExtractor:
    """Extracts text from PDF/DOCX/TXT resumes and parses canonical skills."""

    def __init__(
        self,
        alias_path: str | Path | None = None,
        category_path: str | Path | None = None,
    ) -> None:
        """Initialize extractor with canonical skill aliases and categories."""
        alias_file = Path(alias_path) if alias_path else _ref_dir / "skill_aliases.json"
        cat_file = Path(category_path) if category_path else _ref_dir / "skill_categories.json"

        if not alias_file.is_file():
            raise FileNotFoundError(f"Skill aliases reference file not found at: {alias_file}")
        if not cat_file.is_file():
            raise FileNotFoundError(f"Skill categories reference file not found at: {cat_file}")

        self.alias_lookup = load_alias_map(alias_file)
        self.category_lookup = load_category_map(cat_file)

        raw_aliases: dict[str, list[str]] = json.loads(alias_file.read_text(encoding="utf-8"))
        self.description_patterns = build_description_patterns(raw_aliases)

    def extract_from_file(self, file_path: str | Path) -> ResumeExtractionResult:
        """Extract text and skills from a file path."""
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"Resume file not found at: {path}")

        file_size = path.stat().st_size
        if file_size == 0:
            return ResumeExtractionResult(
                status="empty_file",
                file_type=path.suffix.lower().lstrip("."),
                extracted_skill_count=0,
                skills=[],
                warnings=["The provided resume file is completely empty (0 bytes)."],
            )

        if file_size > MAX_FILE_SIZE_BYTES:
            return ResumeExtractionResult(
                status="file_too_large",
                file_type=path.suffix.lower().lstrip("."),
                extracted_skill_count=0,
                skills=[],
                warnings=[
                    f"File size ({file_size / (1024 * 1024):.2f} MB) exceeds maximum allowed limit of {MAX_FILE_SIZE_BYTES / (1024 * 1024):.1f} MB."
                ],
            )

        ext = path.suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            return ResumeExtractionResult(
                status="unsupported_format",
                file_type=ext.lstrip("."),
                extracted_skill_count=0,
                skills=[],
                warnings=[
                    f"Unsupported file format '{ext}'. Supported formats are: {', '.join(sorted(SUPPORTED_EXTENSIONS))}."
                ],
            )

        with open(path, "rb") as f:
            file_bytes = f.read()

        return self.extract_from_bytes(file_bytes=file_bytes, file_name=path.name)

    def extract_from_bytes(self, file_bytes: bytes, file_name: str) -> ResumeExtractionResult:
        """Extract text and skills from in-memory bytes."""
        if not file_bytes or len(file_bytes) == 0:
            ext = Path(file_name).suffix.lower().lstrip(".")
            return ResumeExtractionResult(
                status="empty_file",
                file_type=ext,
                extracted_skill_count=0,
                skills=[],
                warnings=["The provided resume content is completely empty (0 bytes)."],
            )

        if len(file_bytes) > MAX_FILE_SIZE_BYTES:
            ext = Path(file_name).suffix.lower().lstrip(".")
            return ResumeExtractionResult(
                status="file_too_large",
                file_type=ext,
                extracted_skill_count=0,
                skills=[],
                warnings=[
                    f"File size ({len(file_bytes) / (1024 * 1024):.2f} MB) exceeds limit of {MAX_FILE_SIZE_BYTES / (1024 * 1024):.1f} MB."
                ],
            )

        ext = Path(file_name).suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            return ResumeExtractionResult(
                status="unsupported_format",
                file_type=ext.lstrip("."),
                extracted_skill_count=0,
                skills=[],
                warnings=[
                    f"Unsupported file format '{ext}'. Supported formats are: {', '.join(sorted(SUPPORTED_EXTENSIONS))}."
                ],
            )

        # Content-based signature (magic bytes) validation before parser dispatch
        if ext == ".pdf":
            # PDF specification allows the %PDF- header to appear anywhere in the first 1024 bytes
            if b"%PDF-" not in file_bytes[:1024]:
                return ResumeExtractionResult(
                    status="corrupt_file",
                    file_type="pdf",
                    extracted_skill_count=0,
                    skills=[],
                    warnings=["Declared PDF file does not contain a valid PDF signature (%PDF-)."],
                )
            return self._extract_pdf(file_bytes)
        elif ext == ".docx":
            # DOCX is an OpenXML ZIP package starting with the PK signature (PK\x03\x04 or PK\x05\x06)
            if not file_bytes.startswith(b"PK"):
                return ResumeExtractionResult(
                    status="corrupt_file",
                    file_type="docx",
                    extracted_skill_count=0,
                    skills=[],
                    warnings=["Declared DOCX file does not contain a valid ZIP container signature (PK)."],
                )
            return self._extract_docx(file_bytes)
        else:  # .txt
            return self._extract_txt(file_bytes)

    def _extract_pdf(self, file_bytes: bytes) -> ResumeExtractionResult:
        """Extract text from PDF using pypdf."""
        import pypdf
        from pypdf.errors import PdfReadError

        warnings: list[str] = []
        try:
            stream = io.BytesIO(file_bytes)
            reader = pypdf.PdfReader(stream)

            # Check password protection
            if reader.is_encrypted:
                return ResumeExtractionResult(
                    status="password_protected",
                    file_type="pdf",
                    extracted_skill_count=0,
                    skills=[],
                    warnings=["PDF is password-protected or encrypted. Please provide an unencrypted resume."],
                )

            total_pages = len(reader.pages)
            if total_pages == 0:
                return ResumeExtractionResult(
                    status="corrupt_file",
                    file_type="pdf",
                    extracted_skill_count=0,
                    skills=[],
                    warnings=["PDF document contains 0 pages."],
                )

            if total_pages > MAX_PAGE_COUNT:
                warnings.append(
                    f"PDF has {total_pages} pages, which exceeds the recommended limit of {MAX_PAGE_COUNT} pages. Only the first {MAX_PAGE_COUNT} pages were analyzed."
                )
                pages_to_read = reader.pages[:MAX_PAGE_COUNT]
            else:
                pages_to_read = reader.pages

            extracted_text_chunks: list[str] = []
            for page in pages_to_read:
                text = page.extract_text() or ""
                extracted_text_chunks.append(text)

            full_text = "\n".join(extracted_text_chunks).strip()

            # Check for scanned or image-only PDF
            non_space_chars = len(re.sub(r"\s+", "", full_text))
            if non_space_chars < MIN_TEXT_LENGTH_NON_SCANNED:
                return ResumeExtractionResult(
                    status="scanned_pdf",
                    file_type="pdf",
                    extracted_skill_count=0,
                    skills=[],
                    warnings=[
                        "PDF contains no extractable text. Scanned or image-only PDFs require a text-based resume (OCR is not supported)."
                    ],
                )

            skills = self._parse_skills_from_text(full_text)
            return ResumeExtractionResult(
                status="success",
                file_type="pdf",
                extracted_skill_count=len(skills),
                skills=skills,
                warnings=warnings,
            )

        except (PdfReadError, Exception) as exc:
            return ResumeExtractionResult(
                status="corrupt_file",
                file_type="pdf",
                extracted_skill_count=0,
                skills=[],
                warnings=[f"Failed to read PDF document: {type(exc).__name__} - {str(exc)}"],
            )

    def _extract_docx(self, file_bytes: bytes) -> ResumeExtractionResult:
        """Extract text from DOCX using python-docx."""
        try:
            import docx

            stream = io.BytesIO(file_bytes)
            doc = docx.Document(stream)

            text_chunks: list[str] = []
            for p in doc.paragraphs:
                if p.text and p.text.strip():
                    text_chunks.append(p.text.strip())

            # Also check table contents (many resumes use tables for layouts)
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        if cell.text and cell.text.strip():
                            text_chunks.append(cell.text.strip())

            full_text = "\n".join(text_chunks).strip()
            if not full_text:
                return ResumeExtractionResult(
                    status="empty_file",
                    file_type="docx",
                    extracted_skill_count=0,
                    skills=[],
                    warnings=["DOCX file contains no text paragraphs or table entries."],
                )

            skills = self._parse_skills_from_text(full_text)
            return ResumeExtractionResult(
                status="success",
                file_type="docx",
                extracted_skill_count=len(skills),
                skills=skills,
                warnings=[],
            )
        except Exception as exc:
            return ResumeExtractionResult(
                status="corrupt_file",
                file_type="docx",
                extracted_skill_count=0,
                skills=[],
                warnings=[f"Failed to read DOCX document: {type(exc).__name__} - {str(exc)}"],
            )

    def _extract_txt(self, file_bytes: bytes) -> ResumeExtractionResult:
        """Extract text from TXT with encoding fallback."""
        try:
            try:
                full_text = file_bytes.decode("utf-8")
            except UnicodeDecodeError:
                full_text = file_bytes.decode("latin-1")

            full_text = full_text.strip()
            if not full_text:
                return ResumeExtractionResult(
                    status="empty_file",
                    file_type="txt",
                    extracted_skill_count=0,
                    skills=[],
                    warnings=["TXT file is empty."],
                )

            skills = self._parse_skills_from_text(full_text)
            return ResumeExtractionResult(
                status="success",
                file_type="txt",
                extracted_skill_count=len(skills),
                skills=skills,
                warnings=[],
            )
        except Exception as exc:
            return ResumeExtractionResult(
                status="corrupt_file",
                file_type="txt",
                extracted_skill_count=0,
                skills=[],
                warnings=[f"Failed to decode TXT file: {type(exc).__name__} - {str(exc)}"],
            )

    def _parse_skills_from_text(self, text: str) -> list[ExtractedSkill]:
        """Extract canonical skills and surrounding evidence snippets from text."""
        if not text or not text.strip():
            return []

        # Standardize linebreaks while preserving technical characters
        normalized_text = re.sub(r"\r\n", "\n", text)

        extracted: list[ExtractedSkill] = []
        seen_canonical: set[str] = set()

        # Iterate over all compiled description patterns (which include special patterns for C, R, IT, AI)
        for canonical, pattern in self.description_patterns:
            matches = list(pattern.finditer(normalized_text))
            if not matches:
                continue

            if canonical in seen_canonical:
                continue

            # Pick the first match to generate an evidence snippet
            first_match = matches[0]
            start_pos = max(0, first_match.start() - 40)
            end_pos = min(len(normalized_text), first_match.end() + 40)

            raw_snippet = normalized_text[start_pos:end_pos].replace("\n", " ").strip()
            # Collapse multiple spaces
            evidence_snippet = re.sub(r"\s+", " ", raw_snippet)
            if start_pos > 0:
                evidence_snippet = "..." + evidence_snippet
            if end_pos < len(normalized_text):
                evidence_snippet = evidence_snippet + "..."

            category = self.category_lookup.get(canonical, "Technical Skill")
            seen_canonical.add(canonical)
            extracted.append(
                ExtractedSkill(
                    canonical_name=canonical,
                    category=category,
                    evidence=evidence_snippet,
                )
            )

        # Sort alphabetically by canonical name for deterministic output
        extracted.sort(key=lambda s: s.canonical_name.casefold())
        return extracted
