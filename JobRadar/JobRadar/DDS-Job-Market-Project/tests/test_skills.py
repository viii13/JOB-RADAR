"""Tests for the Milestone 3A deterministic skill extraction pipeline."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

REFERENCE_DIR = PROJECT_ROOT / "data" / "reference"
ALIASES_PATH = REFERENCE_DIR / "skill_aliases.json"
CATEGORIES_PATH = REFERENCE_DIR / "skill_categories.json"


def _load_alias_lookup() -> dict[str, str]:
    from job_market.skills import load_alias_map
    return load_alias_map(ALIASES_PATH)


def _load_category_lookup() -> dict[str, str]:
    from job_market.skills import load_category_map
    return load_category_map(CATEGORIES_PATH)


def _load_alias_map_raw() -> dict[str, list[str]]:
    return json.loads(ALIASES_PATH.read_text(encoding="utf-8"))


class NormalizationTests(unittest.TestCase):
    """Tests for normalize_skill()."""

    def setUp(self) -> None:
        self.lookup = _load_alias_lookup()

    def _normalize(self, raw: str) -> str:
        from job_market.skills import normalize_skill
        return normalize_skill(raw, self.lookup)

    def test_case_variants_normalize_to_same_canonical(self) -> None:
        """python, Python, PYTHON → Python."""
        self.assertEqual(self._normalize("python"), "Python")
        self.assertEqual(self._normalize("Python"), "Python")
        self.assertEqual(self._normalize("PYTHON"), "Python")

    def test_aliases_resolve_correctly(self) -> None:
        """ml → Machine Learning, c sharp → C#, node js → Node.js."""
        self.assertEqual(self._normalize("ml"), "Machine Learning")
        self.assertEqual(self._normalize("c sharp"), "C#")
        self.assertEqual(self._normalize("node js"), "Node.js")
        self.assertEqual(self._normalize("nodejs"), "Node.js")

    def test_jobspiq_aliases_resolve_to_existing_canonical_skills(self) -> None:
        self.assertEqual(self._normalize("REST APIs"), "REST")
        self.assertEqual(self._normalize("Google Cloud (GCP)"), "GCP")
        self.assertEqual(self._normalize("Go (Golang)"), "Golang")

    def test_preserves_special_characters(self) -> None:
        """c++ → C++, c# → C#, .net → .NET."""
        self.assertEqual(self._normalize("c++"), "C++")
        self.assertEqual(self._normalize("C++"), "C++")
        self.assertEqual(self._normalize("c#"), "C#")
        self.assertEqual(self._normalize(".net"), ".NET")

    def test_unknown_skill_is_rejected(self) -> None:
        """Unknown values must not become artificial skills."""
        self.assertEqual(self._normalize("some unusual skill"), "")
        self.assertEqual(self._normalize("Technical Sales Officer 8755671696"), "")

    def test_rest_normalizes_to_rest(self) -> None:
        """rest → REST (confirmed as REST API, not the verb)."""
        self.assertEqual(self._normalize("rest"), "REST")
        self.assertEqual(self._normalize("Rest"), "REST")
        self.assertEqual(self._normalize("REST"), "REST")

    def test_empty_or_whitespace_returns_empty(self) -> None:
        self.assertEqual(self._normalize(""), "")
        self.assertEqual(self._normalize("   "), "")


class TagExtractionTests(unittest.TestCase):
    """Tests for extract_tagged_skills()."""

    def setUp(self) -> None:
        self.lookup = _load_alias_lookup()

    def _extract(self, tags: str | None) -> list[dict[str, str]]:
        from job_market.skills import extract_tagged_skills
        return extract_tagged_skills(tags, self.lookup)

    def test_basic_tag_splitting(self) -> None:
        result = self._extract("python, sql, react")
        names = [r["skill_normalized"] for r in result]
        self.assertEqual(names, ["Python", "SQL", "React"])

    def test_filters_noise_long_tokens(self) -> None:
        """Tokens longer than 80 chars are discarded as description noise."""
        long_token = "A" * 81
        result = self._extract(f"python, {long_token}, sql")
        names = [r["skill_normalized"] for r in result]
        self.assertEqual(names, ["Python", "SQL"])

    def test_filters_empty_tokens(self) -> None:
        result = self._extract("python, , sql")
        names = [r["skill_normalized"] for r in result]
        self.assertEqual(names, ["Python", "SQL"])

    def test_deduplicates_same_skill(self) -> None:
        """Same skill appearing as different case variants → one entry."""
        result = self._extract("python, Python, PYTHON")
        names = [r["skill_normalized"] for r in result]
        self.assertEqual(names, ["Python"])

    def test_rejects_job_title_and_experience_noise(self) -> None:

        result = self._extract(
            "python, Technical Sales Officer 8755671696, B.Tech Fresher, 30-60-90 Feedback"
        )
        names = [r["skill_normalized"] for r in result]
        self.assertEqual(names, ["Python"])


    def test_none_and_nan_return_empty(self) -> None:
        self.assertEqual(self._extract(None), [])
        self.assertEqual(self._extract(float("nan")), [])
        self.assertEqual(self._extract(""), [])

    def test_preserves_raw_skill(self) -> None:
        """The original tag text is preserved in skill_raw."""
        result = self._extract("machine learning")
        self.assertEqual(result[0]["skill_raw"], "machine learning")
        self.assertEqual(result[0]["skill_normalized"], "Machine Learning")


class DescriptionExtractionTests(unittest.TestCase):
    """Tests for description-based skill detection."""

    def setUp(self) -> None:
        from job_market.skills import build_description_patterns
        self.patterns = build_description_patterns(_load_alias_map_raw())

    def _detect(self, text: str) -> set[str]:
        from job_market.skills import extract_description_skills
        results = extract_description_skills(text, self.patterns)
        return {r["skill_normalized"] for r in results}

    def test_java_does_not_match_javascript(self) -> None:
        skills = self._detect("Experience with JavaScript required")
        self.assertIn("JavaScript", skills)
        self.assertNotIn("Java", skills)

    def test_java_matches_standalone(self) -> None:
        skills = self._detect("Experience with Java and Spring Boot")
        self.assertIn("Java", skills)
        self.assertIn("Spring Boot", skills)

    def test_sql_does_not_match_mysql(self) -> None:
        skills = self._detect("Must know MySQL and PostgreSQL")
        self.assertIn("MySQL", skills)
        self.assertIn("PostgreSQL", skills)
        self.assertNotIn("SQL", skills)

    def test_sql_matches_standalone(self) -> None:
        skills = self._detect("Strong SQL and Python skills")
        self.assertIn("SQL", skills)
        self.assertIn("Python", skills)

    def test_excludes_standalone_c(self) -> None:
        """C as a standalone letter must NOT be detected."""
        skills = self._detect("knowledge of C and assembly programming")
        self.assertNotIn("C", skills)

    def test_go_only_as_golang(self) -> None:
        """Standalone 'go' must not match; 'golang' must."""
        skills_go = self._detect("We use go for backend services")
        self.assertNotIn("Golang", skills_go)

        skills_golang = self._detect("We use golang for backend services")
        self.assertIn("Golang", skills_golang)

    def test_r_only_in_context(self) -> None:
        """Standalone 'R' must not match; 'R programming' must."""
        skills_bare = self._detect("This is R and nothing else")
        self.assertNotIn("R", skills_bare)

        skills_context = self._detect("Experience with R programming required")
        self.assertIn("R", skills_context)

    def test_cplus_plus_detected(self) -> None:
        skills = self._detect("Proficient in C++ and Python")
        self.assertIn("C++", skills)
        self.assertIn("Python", skills)

    def test_dotnet_detected(self) -> None:
        skills = self._detect("Work with .NET Core and ASP.NET")
        self.assertIn(".NET Core", skills)
        self.assertIn("ASP.NET", skills)

    def test_none_and_empty_return_empty(self) -> None:
        from job_market.skills import extract_description_skills
        self.assertEqual(extract_description_skills(None, self.patterns), [])
        self.assertEqual(extract_description_skills("", self.patterns), [])

    def test_each_skill_counted_once(self) -> None:
        """Python mentioned 5 times → still only 1 detection."""
        text = "Python Python Python Python Python is great"
        results = self._detect(text)
        self.assertIn("Python", results)
        # Count occurrences in the result set.
        from job_market.skills import extract_description_skills
        full = extract_description_skills(text, self.patterns)
        python_count = sum(1 for r in full if r["skill_normalized"] == "Python")
        self.assertEqual(python_count, 1)


class SourceTrackingTests(unittest.TestCase):
    """Tests for skill_source assignment in extract_job_skills()."""

    def setUp(self) -> None:
        self.alias_lookup = _load_alias_lookup()
        self.category_lookup = _load_category_lookup()
        from job_market.skills import build_description_patterns
        self.patterns = build_description_patterns(_load_alias_map_raw())

    def _extract_for_row(
        self, tags: str | None, description: str | None, job_id: int = 1
    ) -> pd.DataFrame:
        from job_market.skills import extract_job_skills
        df = pd.DataFrame([{
            "jobId": job_id,
            "tagsAndSkills_clean": tags,
            "jobDescription_clean": description,
        }])
        return extract_job_skills(df, self.alias_lookup, self.category_lookup, self.patterns)

    def test_skill_in_both_sources(self) -> None:
        result = self._extract_for_row(
            tags="python, sql",
            description="We need Python developers with SQL experience",
        )
        python_row = result[result["skill_normalized"] == "Python"]
        self.assertEqual(len(python_row), 1)
        self.assertEqual(python_row.iloc[0]["skill_source"], "both")

    def test_skill_in_tags_only(self) -> None:
        result = self._extract_for_row(
            tags="agile, scrum",
            description="General project management role",
        )
        agile_row = result[result["skill_normalized"] == "Agile"]
        self.assertEqual(len(agile_row), 1)
        self.assertEqual(agile_row.iloc[0]["skill_source"], "tagsAndSkills")

    def test_skill_in_description_only(self) -> None:
        result = self._extract_for_row(
            tags="sales, marketing",
            description="Must know Python and Django for this role",
        )
        python_row = result[result["skill_normalized"] == "Python"]
        self.assertEqual(len(python_row), 1)
        self.assertEqual(python_row.iloc[0]["skill_source"], "jobDescription")

    def test_one_row_per_skill_per_job(self) -> None:
        """Even if Python appears in tags AND description, only 1 row."""
        result = self._extract_for_row(
            tags="python, python, Python",
            description="Python Python Python is required",
        )
        python_rows = result[result["skill_normalized"] == "Python"]
        self.assertEqual(len(python_rows), 1)


class CategoryTests(unittest.TestCase):
    """Tests for skill_category assignment."""

    def setUp(self) -> None:
        self.alias_lookup = _load_alias_lookup()
        self.category_lookup = _load_category_lookup()
        from job_market.skills import build_description_patterns
        self.patterns = build_description_patterns(_load_alias_map_raw())

    def _extract_for_row(self, tags: str) -> pd.DataFrame:
        from job_market.skills import extract_job_skills
        df = pd.DataFrame([{
            "jobId": 1,
            "tagsAndSkills_clean": tags,
            "jobDescription_clean": "",
        }])
        return extract_job_skills(df, self.alias_lookup, self.category_lookup, self.patterns)

    def test_known_categories(self) -> None:
        result = self._extract_for_row("python, react, sql, aws, docker")
        categories = dict(zip(result["skill_normalized"], result["skill_category"]))
        self.assertEqual(categories["Python"], "Programming Language")
        self.assertEqual(categories["React"], "Framework")
        self.assertEqual(categories["SQL"], "Database")
        self.assertEqual(categories["AWS"], "Cloud")
        self.assertEqual(categories["Docker"], "DevOps")

    def test_unknown_skill_is_not_extracted(self) -> None:
        result = self._extract_for_row("some unusual skill")
        self.assertEqual(len(result), 0)

    def test_new_validated_skills_are_extracted(self) -> None:

        result = self._extract_for_row(
            "project management, networking, software testing, data modeling, debugging"
        )
        names = set(result["skill_normalized"])
        self.assertEqual(
            names,
            {"Project Management", "Networking", "Software Testing", "Data Modeling", "Debugging"},
        )


    def test_ml_category(self) -> None:
        result = self._extract_for_row("machine learning, tensorflow")
        categories = dict(zip(result["skill_normalized"], result["skill_category"]))
        self.assertEqual(categories["Machine Learning"], "Data/ML")
        self.assertEqual(categories["TensorFlow"], "Data/ML")

    def test_approved_jobspiq_skills_are_extracted_with_existing_categories(self) -> None:
        result = self._extract_for_row(
            "sql server, snowflake, selenium, playwright, grafana, fastapi, prometheus, "
            "postman, next.js, graphql, cypress, computer vision, react native, jmeter, flutter, appium"
        )
        categories = dict(zip(result["skill_normalized"], result["skill_category"]))
        self.assertEqual(
            categories,
            {
                "SQL Server": "Database",
                "Snowflake": "Database",
                "Selenium": "Tools",
                "Playwright": "Tools",
                "Grafana": "DevOps",
                "FastAPI": "Framework",
                "Prometheus": "DevOps",
                "Postman": "Tools",
                "Next.js": "Framework",
                "GraphQL": "Web",
                "Cypress": "Tools",
                "Computer Vision": "Data/ML",
                "React Native": "Framework",
                "JMeter": "Tools",
                "Flutter": "Framework",
                "Appium": "Tools",
            },
        )


class MissingDataTests(unittest.TestCase):
    """Tests for rows with missing tags or descriptions."""

    def setUp(self) -> None:
        self.alias_lookup = _load_alias_lookup()
        self.category_lookup = _load_category_lookup()
        from job_market.skills import build_description_patterns
        self.patterns = build_description_patterns(_load_alias_map_raw())

    def test_missing_both_tags_and_description(self) -> None:
        from job_market.skills import extract_job_skills
        df = pd.DataFrame([{
            "jobId": 99,
            "tagsAndSkills_clean": None,
            "jobDescription_clean": None,
        }])
        result = extract_job_skills(df, self.alias_lookup, self.category_lookup, self.patterns)
        self.assertEqual(len(result), 0)

    def test_missing_tags_but_description_present(self) -> None:
        from job_market.skills import extract_job_skills
        df = pd.DataFrame([{
            "jobId": 99,
            "tagsAndSkills_clean": None,
            "jobDescription_clean": "We need Python developers",
        }])
        result = extract_job_skills(df, self.alias_lookup, self.category_lookup, self.patterns)
        self.assertTrue(len(result) > 0)
        self.assertTrue(all(result["skill_source"] == "jobDescription"))


class DescriptionOnlyRegressionTests(unittest.TestCase):
    """Regression tests for description-only skills, R, C, and empty normalized names."""

    def setUp(self) -> None:
        self.alias_lookup = _load_alias_lookup()
        self.category_lookup = _load_category_lookup()
        from job_market.skills import build_description_patterns
        self.patterns = build_description_patterns(_load_alias_map_raw())

    def _extract_for_row(
        self, tags: str | None, description: str | None, job_id: int = 1
    ) -> pd.DataFrame:
        from job_market.skills import extract_job_skills
        df = pd.DataFrame([{
            "jobId": job_id,
            "tagsAndSkills_clean": tags,
            "jobDescription_clean": description,
        }])
        return extract_job_skills(df, self.alias_lookup, self.category_lookup, self.patterns)

    def test_r_programming_in_description_extracts_canonical_r(self) -> None:
        """R programming in description must extract canonical 'R' with Programming Language category."""
        result = self._extract_for_row(
            tags=None,
            description="Experience with R programming and data science required.",
        )
        r_rows = result[result["skill_normalized"] == "R"]
        self.assertEqual(len(r_rows), 1)
        row = r_rows.iloc[0]
        self.assertEqual(row["skill_source"], "jobDescription")
        self.assertEqual(row["skill_category"], "Programming Language")

    def test_c_programming_in_description_extracts_canonical_c(self) -> None:
        """C programming in description must extract canonical 'C' with Programming Language category."""
        result = self._extract_for_row(
            tags=None,
            description="Solid understanding of C programming and algorithms.",
        )
        c_rows = result[result["skill_normalized"] == "C"]
        self.assertEqual(len(c_rows), 1)
        row = c_rows.iloc[0]
        self.assertEqual(row["skill_source"], "jobDescription")
        self.assertEqual(row["skill_category"], "Programming Language")

    def test_standalone_c_in_description_not_extracted(self) -> None:
        """Standalone C letter in description must not be falsely extracted."""
        result = self._extract_for_row(
            tags=None,
            description="We seek C level executives with leadership experience.",
        )
        c_rows = result[result["skill_normalized"] == "C"]
        self.assertEqual(len(c_rows), 0)

    def test_c_and_r_in_tags(self) -> None:
        """C and R tags must be normalized to canonical C and R."""
        result = self._extract_for_row(tags="C, R, Python", description="")
        skills = set(result["skill_normalized"])
        self.assertIn("C", skills)
        self.assertIn("R", skills)
        self.assertIn("Python", skills)

    def test_no_empty_normalized_skills_emitted(self) -> None:
        """extract_job_skills must never produce empty string or null normalized skills."""
        descriptions = [
            "Experience with R programming, C language, and Golang required",
            "General office assistant and bookkeeping duties",
            "Looking for AI engineers proficient in deep learning and Python",
        ]
        from job_market.skills import extract_job_skills
        df = pd.DataFrame([
            {"jobId": idx, "tagsAndSkills_clean": None, "jobDescription_clean": desc}
            for idx, desc in enumerate(descriptions, start=1)
        ])
        result = extract_job_skills(df, self.alias_lookup, self.category_lookup, self.patterns)
        self.assertFalse((result["skill_normalized"] == "").any())
        self.assertFalse(result["skill_normalized"].isna().any())
        self.assertTrue(all(len(s.strip()) > 0 for s in result["skill_normalized"]))

