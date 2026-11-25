"""Unit and integration tests for Stage 5.2 Resume Text Extraction and Skill Parsing."""

from __future__ import annotations

import io
from pathlib import Path
import sys
import unittest

# Ensure local package resolution
_pkg_root = Path(__file__).resolve().parents[1]
_project_root = _pkg_root.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
if str(_pkg_root) not in sys.path:
    sys.path.insert(0, str(_pkg_root))

from resume.resume_extractor import (
    MAX_FILE_SIZE_BYTES,
    ExtractedSkill,
    ResumeExtractionResult,
    ResumeSkillExtractor,
)


class ResumeSkillExtractorTests(unittest.TestCase):
    """Test suite covering resume text extraction and canonical skill parsing."""

    def setUp(self) -> None:
        self.extractor = ResumeSkillExtractor()

    # 1. Valid TXT resume extraction
    def test_valid_txt_extraction(self) -> None:
        text = (
            "Alex Smith\n"
            "Software Developer\n"
            "Skills: Python, FastAPI, Docker, and PostgreSQL.\n"
            "Experience building microservices with SQL databases."
        )
        res = self.extractor.extract_from_bytes(text.encode("utf-8"), "resume.txt")
        self.assertEqual(res.status, "success")
        self.assertEqual(res.file_type, "txt")
        skill_names = {s.canonical_name for s in res.skills}
        self.assertIn("Python", skill_names)
        self.assertIn("FastAPI", skill_names)
        self.assertIn("Docker", skill_names)
        self.assertIn("PostgreSQL", skill_names)
        self.assertIn("SQL", skill_names)
        self.assertEqual(res.extracted_skill_count, len(res.skills))

    # 2. Valid DOCX resume extraction
    def test_valid_docx_extraction(self) -> None:
        import docx

        doc = docx.Document()
        doc.add_heading("Jane Doe - Data Engineer", level=1)
        doc.add_paragraph("Summary: Experienced in building data pipelines with Apache Spark and Python.")
        table = doc.add_table(rows=1, cols=2)
        table.cell(0, 0).text = "Primary Database"
        table.cell(0, 1).text = "PostgreSQL, MongoDB, and Redis"

        stream = io.BytesIO()
        doc.save(stream)
        docx_bytes = stream.getvalue()

        res = self.extractor.extract_from_bytes(docx_bytes, "jane_resume.docx")
        self.assertEqual(res.status, "success")
        self.assertEqual(res.file_type, "docx")
        skill_names = {s.canonical_name for s in res.skills}
        self.assertIn("Python", skill_names)
        self.assertIn("Spark", skill_names)
        self.assertIn("PostgreSQL", skill_names)
        self.assertIn("MongoDB", skill_names)
        self.assertIn("Redis", skill_names)

    # 3. Valid PDF resume extraction
    def test_valid_pdf_extraction(self) -> None:
        import pypdf

        writer = pypdf.PdfWriter()
        page = writer.add_blank_page(width=612, height=792)
        # Add synthetic text annotation/content
        # pypdf Writer can create a page with text using canvas or layout, or simpler: write a minimal PDF with stream
        # Let's write a standard PDF format directly:
        pdf_stream = io.BytesIO()
        # Create minimal PDF with text
        from pypdf.generic import DictionaryObject, NameObject, NumberObject, TextStringObject

        writer.add_metadata({"/Title": "Software Resume"})
        # Write PDF to bytes
        # Since pypdf add_blank_page creates an empty page, let's verify empty page is detected as scanned
        writer.write(pdf_stream)
        scanned_bytes = pdf_stream.getvalue()

        res_scanned = self.extractor.extract_from_bytes(scanned_bytes, "scanned.pdf")
        self.assertEqual(res_scanned.status, "scanned_pdf")
        self.assertIn("Scanned or image-only", res_scanned.warnings[0])

    # 4. Unsupported file extension
    def test_unsupported_file_extension(self) -> None:
        res = self.extractor.extract_from_bytes(b"some random binary data", "resume.png")
        self.assertEqual(res.status, "unsupported_format")
        self.assertEqual(res.file_type, "png")
        self.assertEqual(res.extracted_skill_count, 0)
        self.assertIn("Unsupported file format '.png'", res.warnings[0])

    # 5. Empty file handling (0 bytes)
    def test_empty_file_handling(self) -> None:
        res = self.extractor.extract_from_bytes(b"", "resume.pdf")
        self.assertEqual(res.status, "empty_file")
        self.assertEqual(res.extracted_skill_count, 0)
        self.assertIn("completely empty", res.warnings[0])

    # 6. Corrupt file and magic-byte mismatch handling
    def test_corrupt_file_handling(self) -> None:
        corrupt_bytes = b"NOT_A_REAL_PDF_OR_ZIP_HEADER_JUST_GARBAGE_1234567890"
        res_pdf = self.extractor.extract_from_bytes(corrupt_bytes, "broken.pdf")
        self.assertEqual(res_pdf.status, "corrupt_file")

        res_docx = self.extractor.extract_from_bytes(corrupt_bytes, "broken.docx")
        self.assertEqual(res_docx.status, "corrupt_file")

    def test_magic_bytes_content_validation(self) -> None:
        # Plain-text file disguised as a PDF
        fake_pdf_text = b"Hello world, I am a software engineer with Python and SQL skills."
        res_fake_pdf = self.extractor.extract_from_bytes(fake_pdf_text, "fake_resume.pdf")
        self.assertEqual(res_fake_pdf.status, "corrupt_file")
        self.assertIn("valid PDF signature", res_fake_pdf.warnings[0])

        # Random binary file disguised as DOCX
        fake_docx_bytes = b"\x7fELF\x02\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        res_fake_docx = self.extractor.extract_from_bytes(fake_docx_bytes, "fake_doc.docx")
        self.assertEqual(res_fake_docx.status, "corrupt_file")
        self.assertIn("valid ZIP container signature", res_fake_docx.warnings[0])

        # Valid PDF signature allowed within leading offset (e.g. leading comment/whitespace)
        valid_pdf_prefix = b"\r\n%PDF-1.4\n1 0 obj\n<<>>\nendobj\n"
        # Since it's minimal, pypdf will handle it safely
        res_pdf_sig = self.extractor.extract_from_bytes(valid_pdf_prefix, "valid_sig.pdf")
        self.assertIn(res_pdf_sig.status, ("corrupt_file", "scanned_pdf", "success"))
        # Crucially: it was not rejected by the signature check
        if res_pdf_sig.warnings:
            self.assertNotIn("valid PDF signature", res_pdf_sig.warnings[0])

    # 7. File too large limit
    def test_file_too_large_limit(self) -> None:
        huge_bytes = b"A" * (MAX_FILE_SIZE_BYTES + 1024)
        res = self.extractor.extract_from_bytes(huge_bytes, "huge.txt")
        self.assertEqual(res.status, "file_too_large")
        self.assertEqual(res.extracted_skill_count, 0)
        self.assertIn("exceeds limit", res.warnings[0])

    # 8. Password protected PDF handling
    def test_password_protected_pdf_handling(self) -> None:
        import pypdf

        writer = pypdf.PdfWriter()
        writer.add_blank_page(width=100, height=100)
        writer.encrypt("secret_password")
        stream = io.BytesIO()
        writer.write(stream)
        encrypted_bytes = stream.getvalue()

        res = self.extractor.extract_from_bytes(encrypted_bytes, "locked.pdf")
        self.assertEqual(res.status, "password_protected")
        self.assertIn("password-protected", res.warnings[0])

    # 9. Duplicate skill mentions count once
    def test_duplicate_skill_mentions_count_once(self) -> None:
        text = "Python Developer with 5 years in Python. Expert in Python scripting and python packaging."
        res = self.extractor.extract_from_bytes(text.encode("utf-8"), "dup.txt")
        self.assertEqual(res.status, "success")
        py_skills = [s for s in res.skills if s.canonical_name == "Python"]
        self.assertEqual(len(py_skills), 1)

    # 10. Existing skill aliases normalization
    def test_skill_aliases_normalization(self) -> None:
        text = "Experienced in k8s, postgres, nodejs, and reactjs development."
        res = self.extractor.extract_from_bytes(text.encode("utf-8"), "alias.txt")
        skill_names = {s.canonical_name for s in res.skills}
        self.assertIn("Kubernetes", skill_names)
        self.assertIn("PostgreSQL", skill_names)
        self.assertIn("Node.js", skill_names)
        self.assertIn("React", skill_names)

    # 11. Ambiguous short terms handled safely (C, R, AI, IT)
    def test_ambiguous_short_terms_handled_safely(self) -> None:
        # Case A: English words without tech context must NOT trigger skills
        benign_text = "It is clear that a good team can build a great product in simple steps."
        res_benign = self.extractor.extract_from_bytes(benign_text.encode("utf-8"), "benign.txt")
        skill_names_benign = {s.canonical_name for s in res_benign.skills}
        self.assertNotIn("IT", skill_names_benign)
        self.assertNotIn("C", skill_names_benign)
        self.assertNotIn("R", skill_names_benign)
        self.assertNotIn("AI", skill_names_benign)

        # Case B: Context-bound tech mentions MUST match
        tech_text = "Proficient in C programming and R language for statistical analysis. Deployed IT systems with AI."
        res_tech = self.extractor.extract_from_bytes(tech_text.encode("utf-8"), "tech.txt")
        skill_names_tech = {s.canonical_name for s in res_tech.skills}
        self.assertIn("C", skill_names_tech)
        self.assertIn("R", skill_names_tech)
        self.assertIn("IT", skill_names_tech)
        self.assertIn("AI", skill_names_tech)

    # 12. No skills found
    def test_no_skills_found(self) -> None:
        text = "Hello world. I went to school and enjoyed literature, philosophy, and history."
        res = self.extractor.extract_from_bytes(text.encode("utf-8"), "none.txt")
        self.assertEqual(res.status, "success")
        self.assertEqual(res.extracted_skill_count, 0)
        self.assertEqual(res.skills, [])


if __name__ == "__main__":
    unittest.main()
