"""Comprehensive tests for JobRadar Phase 5.6 Career Recommendation API endpoints.

Covers:
1. Valid PDF resume upload
2. Valid DOCX resume upload
3. Valid TXT resume upload
4. Unsupported file format rejection (HTTP 400)
5. Empty resume upload rejection (HTTP 400)
6. Oversized resume upload rejection (HTTP 413)
7. Scanned PDF handling with appropriate status and warnings
8. Resume with no recognized skills handling
9. Manual student skills without a resume
10. Valid career recommendation request
11. Empty student profile recommendation request
12. Invalid target career rejection (HTTP 400)
13. Valid skill-gap analysis request
14. Missing / invalid role benchmark handling (HTTP 400)
15. Valid learning roadmap generation request
16. No skill gap (all skills acquired) handling
17. Invalid request schema rejection
18. Consistent HTTP error responses
19. Full End-to-End API workflow (Resume -> Skills -> Recommendations -> Gap -> Roadmap)
20. Full Manual Skills workflow without resume upload
"""

from __future__ import annotations

import asyncio
import io
from pathlib import Path
import sys
import unittest

from fastapi import HTTPException, UploadFile, status

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
JOBRADAR_ROOT = PROJECT_ROOT.parent
if str(JOBRADAR_ROOT) not in sys.path:
    sys.path.insert(0, str(JOBRADAR_ROOT))

from job_market.api import create_app
from job_market.career_recommendations_api import (
    CareerRecommendationRequest,
    MAX_RESUME_SIZE_BYTES,
    RoadmapRequest,
    SkillGapRequest,
    extract_resume_skills,
    generate_learning_roadmap,
    get_career_recommendations,
    get_skill_gap_analysis,
    get_skills_by_role,
    get_supported_roles,
    resolve_target_role_id,
)


def _build_minimal_valid_pdf_bytes(text: str = "Skills: Python, SQL, Docker, and Machine Learning.") -> bytes:
    """Build a synthetic, valid single-page PDF containing extractable text."""
    import pypdf
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)

    # Encode text inside standard PDF text operators
    clean_text = text.replace("(", "").replace(")", "")
    stream_bytes = f"BT /F1 12 Tf 72 712 Td ({clean_text}) Tj ET".encode("latin1")
    stream = DecodedStreamObject()
    stream.set_data(stream_bytes)

    font = DictionaryObject()
    font[NameObject("/Type")] = NameObject("/Font")
    font[NameObject("/Subtype")] = NameObject("/Type1")
    font[NameObject("/BaseFont")] = NameObject("/Helvetica")

    fonts = DictionaryObject()
    fonts[NameObject("/F1")] = font

    resources = DictionaryObject()
    resources[NameObject("/Font")] = fonts

    page[NameObject("/Resources")] = resources
    page[NameObject("/Contents")] = stream

    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _build_minimal_valid_docx_bytes(text: str = "Skilled in Java, Spring Boot, SQL, and Git.") -> bytes:
    """Build a synthetic, valid single-page DOCX containing the given text."""
    import docx
    doc = docx.Document()
    doc.add_heading("Candidate Resume", level=1)
    doc.add_paragraph(text)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


class CareerRecommendationsApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = create_app()

    # 1. Valid PDF resume upload
    def test_01_valid_pdf_resume_upload(self) -> None:
        pdf_bytes = _build_minimal_valid_pdf_bytes("Proficient in Python, SQL, Docker, and Machine Learning.")
        f = io.BytesIO(pdf_bytes)
        upload = UploadFile(file=f, filename="resume.pdf", size=len(pdf_bytes))
        
        response = asyncio.run(extract_resume_skills(file=upload))
        self.assertEqual(response.file_type.lower(), "pdf")
        self.assertIn(response.status, ["success", "no_skills_found"])
        self.assertGreater(response.file_size_bytes, 0)
        self.assertIsInstance(response.skills, list)
        self.assertIsInstance(response.skill_names, list)

    # 2. Valid DOCX resume upload
    def test_02_valid_docx_resume_upload(self) -> None:
        docx_bytes = _build_minimal_valid_docx_bytes("Core competencies: Java, Spring Boot, SQL, Git, and Docker.")
        f = io.BytesIO(docx_bytes)
        upload = UploadFile(file=f, filename="student_resume.docx", size=len(docx_bytes))
        
        response = asyncio.run(extract_resume_skills(file=upload))
        self.assertEqual(response.file_type.lower(), "docx")
        self.assertEqual(response.status, "success")
        self.assertGreater(response.extracted_skill_count, 0)
        self.assertIn("Java", response.skill_names)
        self.assertIn("SQL", response.skill_names)

    # 3. Valid TXT resume upload
    def test_03_valid_txt_resume_upload(self) -> None:
        txt_content = (
            "Software Engineer Resume\n"
            "Skills: JavaScript, React, HTML, CSS, TypeScript, Node.js, and MongoDB.\n"
        ).encode("utf-8")
        f = io.BytesIO(txt_content)
        upload = UploadFile(file=f, filename="portfolio.txt", size=len(txt_content))
        
        response = asyncio.run(extract_resume_skills(file=upload))
        self.assertEqual(response.file_type.lower(), "txt")
        self.assertEqual(response.status, "success")
        self.assertIn("JavaScript", response.skill_names)
        self.assertIn("React", response.skill_names)

    # 4. Unsupported file format rejection
    def test_04_unsupported_file_format_rejected(self) -> None:
        f = io.BytesIO(b"some random binary or image data")
        upload = UploadFile(file=f, filename="candidate_photo.png", size=len(f.getvalue()))
        
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(extract_resume_skills(file=upload))
        self.assertEqual(ctx.exception.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Unsupported file format", ctx.exception.detail)

    # 5. Empty resume upload rejection
    def test_05_empty_resume_rejected(self) -> None:
        f = io.BytesIO(b"")
        upload = UploadFile(file=f, filename="empty_resume.txt", size=0)
        
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(extract_resume_skills(file=upload))
        self.assertEqual(ctx.exception.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("empty", ctx.exception.detail.lower())

    # 6. Oversized resume upload rejection
    def test_06_oversized_resume_rejected(self) -> None:
        large_bytes = b"X" * (MAX_RESUME_SIZE_BYTES + 1024)
        f = io.BytesIO(large_bytes)
        upload = UploadFile(file=f, filename="giant_resume.txt", size=len(large_bytes))
        
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(extract_resume_skills(file=upload))
        self.assertEqual(ctx.exception.status_code, status.HTTP_413_CONTENT_TOO_LARGE)
        self.assertIn("exceeds maximum allowed size", ctx.exception.detail)

    # 7. Scanned PDF handling
    def test_07_scanned_pdf_handled_with_warning(self) -> None:
        from pypdf import PdfWriter
        writer = PdfWriter()
        writer.add_blank_page(width=612, height=792)
        buf = io.BytesIO()
        writer.write(buf)
        scanned_bytes = buf.getvalue()
        
        f = io.BytesIO(scanned_bytes)
        upload = UploadFile(file=f, filename="scanned_resume.pdf", size=len(scanned_bytes))
        
        response = asyncio.run(extract_resume_skills(file=upload))
        self.assertEqual(response.status, "scanned_pdf")
        self.assertEqual(response.extracted_skill_count, 0)
        self.assertTrue(any("scanned" in w.lower() for w in response.warnings))

    # 8. Resume with no recognized skills
    def test_08_resume_with_no_recognized_skills(self) -> None:
        text = b"Hello, I am a business executive who managed office logistics and operations."
        f = io.BytesIO(text)
        upload = UploadFile(file=f, filename="non_tech.txt", size=len(text))
        
        response = asyncio.run(extract_resume_skills(file=upload))
        self.assertEqual(response.extracted_skill_count, 0)
        self.assertTrue(any("no recognizable" in w.lower() for w in response.warnings))

    # 9. Manual student skills without a resume
    def test_09_manual_skills_recommendation_request(self) -> None:
        req = CareerRecommendationRequest(
            skills=["Python", "SQL", "Pandas", "Scikit-learn"],
            preferred_role="Data Scientist",
        )
        response = get_career_recommendations(req)
        self.assertEqual(response.status, "success")
        self.assertEqual(len(response.recommendations), 8)
        self.assertIn("Python", response.normalized_skills)
        # Top recommendation should have high match score
        top_rec = response.recommendations[0]
        self.assertGreater(top_rec.match_score, 0.0)

    # 10. Valid career recommendation request
    def test_10_valid_career_recommendation_ranking(self) -> None:
        req = CareerRecommendationRequest(
            skills=["Java", "Spring Boot", "SQL", "Docker", "REST API", "Microservices"],
            preferred_role="Backend Developer",
        )
        response = get_career_recommendations(req)
        self.assertEqual(len(response.recommendations), 8)
        # Check backend engineering is top ranked
        top = response.recommendations[0]
        self.assertEqual(top.role_id, "backend_core_software_engineering")
        self.assertTrue(top.is_preferred)
        matching_names = [s.skill_name for s in top.matching_skills]
        self.assertIn("Java", matching_names)

    # 11. Empty student profile recommendation request
    def test_11_empty_student_profile(self) -> None:
        req = CareerRecommendationRequest(skills=[])
        response = get_career_recommendations(req)
        self.assertEqual(response.status, "incomplete_profile")
        self.assertEqual(len(response.recommendations), 8)
        # All scores should be 0.0
        self.assertTrue(all(r.match_score == 0.0 for r in response.recommendations))

    # 12. Invalid target career rejection
    def test_12_invalid_target_career_rejected(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            resolve_target_role_id("Astronaut Chef Specialization")
        self.assertEqual(ctx.exception.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("not a supported technical role", ctx.exception.detail)

    # 13. Valid skill-gap analysis request
    def test_13_valid_skill_gap_analysis(self) -> None:
        req = SkillGapRequest(
            skills=["Python", "SQL"],
            target_role="Data Scientist",
        )
        response = get_skill_gap_analysis(req)
        self.assertEqual(response.role_id, "data_scientist_advanced_analytics")
        self.assertGreaterEqual(response.readiness_score, 0.0)
        self.assertLessEqual(response.readiness_score, 100.0)
        acquired_names = [s.skill_name for s in response.acquired_skills]
        self.assertIn("Python", acquired_names)
        self.assertIn("SQL", acquired_names)
        self.assertEqual(response.support_tier, "LOW")

    # 14. Missing / invalid role benchmark handling
    def test_14_missing_benchmark_data_handling(self) -> None:
        req = SkillGapRequest(
            skills=["Python"],
            target_role="invalid_unknown_role_xyz",
        )
        with self.assertRaises(HTTPException) as ctx:
            get_skill_gap_analysis(req)
        self.assertEqual(ctx.exception.status_code, status.HTTP_400_BAD_REQUEST)

    # 15. Valid learning roadmap generation request
    def test_15_valid_learning_roadmap_request(self) -> None:
        req = RoadmapRequest(
            skills=["Python", "SQL"],
            target_role="data_scientist_advanced_analytics",
        )
        response = generate_learning_roadmap(req)
        self.assertEqual(response.role_id, "data_scientist_advanced_analytics")
        self.assertGreater(len(response.milestones), 0)
        # Check first milestone structure
        m1 = response.milestones[0]
        self.assertTrue(m1.title)
        self.assertGreater(m1.estimated_weeks, 0)
        self.assertIsInstance(m1.learning_objectives, list)
        self.assertIsInstance(m1.resources, list)
        self.assertIsInstance(m1.practice_platforms, list)

    # 16. No skill gap (all skills acquired) handling
    def test_16_no_skill_gap_advanced_mastery(self) -> None:
        all_front_skills = [
            "JavaScript", "TypeScript", "React", "HTML", "CSS", "Node.js", "Git",
            "Next.js", "Tailwind CSS", "Redux", "REST API", "GraphQL", "Jest",
            "Webpack", "Docker", "AWS", "Python", "SQL", "MongoDB", "PostgreSQL",
        ]
        req = RoadmapRequest(
            skills=all_front_skills,
            target_role="frontend_full_stack_engineering",
        )
        response = generate_learning_roadmap(req)
        self.assertGreater(len(response.milestones), 0)
        self.assertIn("frontend_full_stack_engineering", response.role_id)

    # 17. Invalid request schema rejection
    def test_17_invalid_request_schema(self) -> None:
        with self.assertRaises(Exception):
            SkillGapRequest(skills=["Python"])  # missing target_role

    # 18. Consistent HTTP error responses
    def test_18_consistent_http_error_responses(self) -> None:
        req = RoadmapRequest(skills=["Python"], target_role="")
        with self.assertRaises(HTTPException) as ctx:
            generate_learning_roadmap(req)
        self.assertEqual(ctx.exception.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("cannot be empty", ctx.exception.detail)

    # 19. Full End-to-End API workflow
    def test_19_full_end_to_end_resume_workflow(self) -> None:
        """Test: Resume Upload -> Extracted Skills -> Career Recs -> Target Career -> Skill Gap -> Roadmap."""
        # Step A: Resume Upload (DOCX)
        docx_bytes = _build_minimal_valid_docx_bytes(
            "Skills: Python, SQL, Pandas, NumPy, Scikit-learn, Git, Statistics."
        )
        f = io.BytesIO(docx_bytes)
        upload = UploadFile(file=f, filename="e2e_student_resume.docx", size=len(docx_bytes))
        extraction_res = asyncio.run(extract_resume_skills(file=upload))
        self.assertEqual(extraction_res.status, "success")
        extracted_skills = extraction_res.skill_names
        self.assertIn("Python", extracted_skills)
        self.assertIn("SQL", extracted_skills)

        # Step B: Career Recommendations
        rec_req = CareerRecommendationRequest(
            skills=extracted_skills,
            preferred_role="Data Scientist",
        )
        rec_res = get_career_recommendations(rec_req)
        self.assertEqual(len(rec_res.recommendations), 8)
        top_role = rec_res.recommendations[0]
        self.assertIn(top_role.role_id, ["data_scientist_advanced_analytics", "data_engineer_big_data_platform"])

        # Step C: Select Target Career & Skill-Gap Analysis
        gap_req = SkillGapRequest(
            skills=extracted_skills,
            target_role=top_role.role_id,
        )
        gap_res = get_skill_gap_analysis(gap_req)
        self.assertEqual(gap_res.role_id, top_role.role_id)
        self.assertGreater(gap_res.readiness_score, 0.0)

        # Step D: Personalized Learning Roadmap
        road_req = RoadmapRequest(
            skills=extracted_skills,
            target_role=top_role.role_id,
        )
        road_res = generate_learning_roadmap(road_req)
        self.assertGreater(len(road_res.milestones), 0)
        self.assertGreater(road_res.total_estimated_weeks, 0)

    # 20. Full Manual Skills workflow without resume upload
    def test_20_full_manual_skills_workflow(self) -> None:
        """Test student entering skills directly without uploading any resume."""
        manual_skills = ["Java", "Spring Boot", "SQL", "Git"]
        
        # Step A: Career Recommendations directly from manual skills
        rec_req = CareerRecommendationRequest(
            skills=manual_skills,
            preferred_role="Backend Developer",
        )
        rec_res = get_career_recommendations(rec_req)
        self.assertEqual(len(rec_res.recommendations), 8)
        self.assertEqual(rec_res.recommendations[0].role_id, "backend_core_software_engineering")

        # Step B: Skill-Gap Analysis
        gap_req = SkillGapRequest(
            skills=manual_skills,
            target_role="backend_core_software_engineering",
        )
        gap_res = get_skill_gap_analysis(gap_req)
        acquired_names = [s.skill_name for s in gap_res.acquired_skills]
        self.assertIn("Java", acquired_names)
        self.assertIn("SQL", acquired_names)

        # Step C: Roadmap
        road_req = RoadmapRequest(
            skills=manual_skills,
            target_role="backend_core_software_engineering",
        )
        road_res = generate_learning_roadmap(road_req)
        self.assertGreater(len(road_res.milestones), 0)

    # Supported roles endpoint test
    def test_21_supported_roles_catalog(self) -> None:
        roles = get_supported_roles()
        self.assertEqual(len(roles), 8)
        role_ids = [r["role_id"] for r in roles]
        self.assertIn("data_scientist_advanced_analytics", role_ids)
        self.assertIn("backend_core_software_engineering", role_ids)

    def test_22_skills_by_role_endpoint(self) -> None:
        res = get_skills_by_role(role="Data Scientist")
        self.assertTrue(res["success"])
        self.assertEqual(res["role_id"], "data_scientist_advanced_analytics")
        self.assertGreater(len(res["skills"]), 0)
        skill_names = [s["skill"] for s in res["skills"]]
        self.assertIn("Python", skill_names)



if __name__ == "__main__":
    unittest.main()
