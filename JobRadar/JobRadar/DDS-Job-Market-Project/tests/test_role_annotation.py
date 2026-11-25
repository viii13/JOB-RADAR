"""Tests for deterministic, source-traceable role annotation sampling."""

from __future__ import annotations

import csv
import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from job_market.database import create_session_factory, initialize_database
from job_market.models import Job, JobVersion, Source
from job_market.role_annotation import (
    ANNOTATION_COLUMNS,
    create_blinded_annotation_batch,
    generate_annotation_sample,
    generate_targeted_annotation_sample,
)
from job_market.run_targeted_role_annotation import (
    file_has_human_labels,
    validate_safe_to_overwrite,
    main as run_targeted_main,
)



class RoleAnnotationSampleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = initialize_database("sqlite:///:memory:")
        self.Session = create_session_factory(self.engine)

    def tearDown(self) -> None:
        self.engine.dispose()

    def _add_version(self, session, source: Source, source_id: str, title: str, description: str) -> None:
        observed = datetime(2026, 11, 11, tzinfo=UTC)
        job = Job(
            source=source,
            source_job_id=source_id,
            identity_key=f"{source.code}:{source_id}",
            identity_status="provider_id",
            first_seen_at=observed,
            last_seen_at=observed,
        )
        session.add(JobVersion(
            job=job,
            version_number=1,
            is_current=True,
            origin_record_key=f"{source.code}:record:{source_id}",
            mapping_status="exact",
            title=title,
            company_name="Example Co",
            location="Bengaluru",
            job_description=description,
            salary_status="not_disclosed",
            salary_period="unknown",
            observed_at=observed,
            ingested_at=observed,
            transform_version="test",
        ))

    def test_sample_is_deterministic_balanced_and_leaves_labels_blank(self) -> None:
        with self.Session.begin() as session:
            historical = Source(code="historical_2025_xlsx", name="Historical", source_type="historical_file")
            adzuna = Source(code="adzuna_india", name="Adzuna", source_type="api")
            session.add_all((historical, adzuna))
            self._add_version(session, historical, "h-1", "Data Analyst", "Uses SQL and dashboards.")
            self._add_version(session, historical, "h-2", "Data Analyst", "Uses SQL and dashboards.")
            self._add_version(session, historical, "h-3", "Backend Engineer", "Builds Python services.")
            self._add_version(session, adzuna, "a-1", "ML Engineer", "Deploys machine learning models.")
            self._add_version(session, adzuna, "a-2", "QA Engineer", "Automates browser tests.")

        output_directory = PROJECT_ROOT / "tests" / "_role_annotation_output"
        first_path = output_directory / "first.csv"
        second_path = output_directory / "second.csv"
        with self.Session() as session:
            first = generate_annotation_sample(session, first_path, per_source=2, seed=42)
            second = generate_annotation_sample(session, second_path, per_source=2, seed=42)

        self.assertEqual(first.records_written, 4)
        self.assertEqual(first.records_written, second.records_written)
        self.assertEqual(first_path.read_text(encoding="utf-8"), second_path.read_text(encoding="utf-8"))
        with first_path.open(encoding="utf-8", newline="") as sample_file:
            rows = list(csv.DictReader(sample_file))
        self.assertEqual({row["source_code"] for row in rows}, {"historical_2025_xlsx", "adzuna_india"})
        self.assertEqual(sum(row["source_code"] == "historical_2025_xlsx" for row in rows), 2)
        self.assertEqual(sum(row["source_code"] == "adzuna_india" for row in rows), 2)
        self.assertTrue(all(row["human_verified_role_label"] == "" for row in rows))
        self.assertTrue(all(row["annotation_notes"] == "" for row in rows))
        self.assertEqual(len({(row["title"], row["company"], row["description_excerpt"]) for row in rows}), 4)

    def test_targeted_sample_excludes_original_records_and_keeps_gold_labels_blank(self) -> None:
        with self.Session.begin() as session:
            historical = Source(code="historical_2025_xlsx", name="Historical", source_type="historical_file")
            adzuna = Source(code="adzuna_india", name="Adzuna", source_type="api")
            session.add_all((historical, adzuna))
            self._add_version(session, historical, "h-ds", "Data Scientist", "Builds statistical forecasting models.")
            self._add_version(session, adzuna, "a-ds", "Research Scientist", "Runs advanced statistical experiments.")
            self._add_version(session, historical, "h-ml", "Machine Learning Engineer", "Deploys model training pipelines.")
            self._add_version(session, historical, "h-de", "Data Engineer", "Builds ETL data pipelines with Spark.")
            self._add_version(session, historical, "h-da", "Data Analyst", "Creates Power BI dashboards and reports.")
            self._add_version(session, adzuna, "a-da", "Business Intelligence Analyst", "Creates Tableau KPI reporting.")

        output_directory = PROJECT_ROOT / "tests" / "_role_annotation_output"
        original_path = output_directory / "original.csv"
        targeted_path = output_directory / "targeted.csv"
        report_path = output_directory / "targeted_report.md"
        original_path.parent.mkdir(parents=True, exist_ok=True)
        with original_path.open("w", encoding="utf-8", newline="") as original_file:
            writer = csv.DictWriter(original_file, fieldnames=["job_version_id", "title", "company", "description_excerpt"])
            writer.writeheader()
            writer.writerow({
                "job_version_id": "1", "title": "Data Scientist", "company": "Example Co",
                "description_excerpt": "Builds statistical forecasting models.",
            })

        with self.Session() as session:
            result = generate_targeted_annotation_sample(
                session, targeted_path, original_sample_path=original_path, report_path=report_path,
                per_family=1, seed=42,
            )

        self.assertEqual(result.records_written, 4)
        self.assertEqual(result.selected_by_family["data_scientist_advanced_analytics"], 1)
        with targeted_path.open(encoding="utf-8", newline="") as targeted_file:
            rows = list(csv.DictReader(targeted_file))
        self.assertNotIn("1", {row["job_version_id"] for row in rows})
        self.assertEqual({row["candidate_target_family"] for row in rows}, set(result.selected_by_family))
        self.assertTrue(all(row["human_verified_role_label"] == "" for row in rows))
        self.assertTrue(all(row["annotation_notes"] == "" for row in rows))
        self.assertTrue(all(row["selection_rule"] for row in rows))
        self.assertGreaterEqual(result.unmatched_candidate_records, 0)
        self.assertIn("Selection rules", report_path.read_text(encoding="utf-8"))

    def test_blinded_batch_removes_selection_metadata_without_changing_records(self) -> None:
        output_directory = PROJECT_ROOT / "tests" / "_role_annotation_output"
        targeted_path = output_directory / "targeted.csv"
        blinded_path = output_directory / "targeted_blind.csv"
        output_directory.mkdir(parents=True, exist_ok=True)
        columns = list(ANNOTATION_COLUMNS) + ["candidate_target_family", "selection_rule"]
        source_rows = [
            {
                "annotation_record_id": "first", "source_code": "historical_2025_xlsx", "job_id": "1",
                "job_version_id": "11", "source_job_id": "h-1", "origin_record_key": "historical:1",
                "title": "Data Scientist", "company": "Example", "location": "Pune",
                "description_excerpt": "Builds forecasting models.", "human_verified_role_label": "",
                "annotation_notes": "", "candidate_target_family": "data_scientist_advanced_analytics",
                "selection_rule": "title=data scientist",
            },
            {
                "annotation_record_id": "second", "source_code": "adzuna_india", "job_id": "2",
                "job_version_id": "12", "source_job_id": "a-2", "origin_record_key": "adzuna:2",
                "title": "Data Engineer", "company": "Example", "location": "Delhi",
                "description_excerpt": "Builds ETL pipelines.", "human_verified_role_label": "",
                "annotation_notes": "", "candidate_target_family": "data_engineer_big_data_platform",
                "selection_rule": "title=data engineer",
            },
        ]
        with targeted_path.open("w", encoding="utf-8", newline="") as targeted_file:
            writer = csv.DictWriter(targeted_file, fieldnames=columns)
            writer.writeheader()
            writer.writerows(source_rows)
        source_before = targeted_path.read_text(encoding="utf-8")

        result = create_blinded_annotation_batch(targeted_path, blinded_path)

        self.assertEqual(result.records_written, 2)
        self.assertEqual(targeted_path.read_text(encoding="utf-8"), source_before)
        with blinded_path.open(encoding="utf-8", newline="") as blinded_file:
            reader = csv.DictReader(blinded_file)
            blinded_rows = list(reader)
        self.assertEqual(reader.fieldnames, list(ANNOTATION_COLUMNS))
        self.assertEqual([row["annotation_record_id"] for row in blinded_rows], ["first", "second"])
        self.assertEqual([row["job_version_id"] for row in blinded_rows], ["11", "12"])
        self.assertTrue(all(not row["human_verified_role_label"] and not row["annotation_notes"] for row in blinded_rows))

    def test_committed_blinded_annotation_batch_matches_targeted_batch(self) -> None:
        annotations_dir = PROJECT_ROOT / "data" / "annotations"
        targeted_path = annotations_dir / "targeted_data_ai_role_annotation_batch.csv"
        blinded_path = annotations_dir / "targeted_data_ai_role_annotation_batch_blind.csv"

        self.assertTrue(targeted_path.exists(), f"Targeted batch file must exist at {targeted_path}")
        self.assertTrue(blinded_path.exists(), f"Blinded batch file must exist at {blinded_path}")

        with targeted_path.open(encoding="utf-8", newline="") as f_target:
            target_reader = csv.DictReader(f_target)
            target_rows = list(target_reader)

        with blinded_path.open(encoding="utf-8", newline="") as f_blind:
            blind_reader = csv.DictReader(f_blind)
            blind_rows = list(blind_reader)

        self.assertEqual(len(blind_rows), 72)
        self.assertEqual(len(blind_rows), len(target_rows))
        self.assertEqual(blind_reader.fieldnames, list(ANNOTATION_COLUMNS))
        self.assertNotIn("candidate_target_family", blind_reader.fieldnames)
        self.assertNotIn("selection_rule", blind_reader.fieldnames)

        for target_row, blind_row in zip(target_rows, blind_rows):
            for col in ANNOTATION_COLUMNS:
                self.assertEqual(blind_row[col], target_row[col])
            self.assertEqual(blind_row["human_verified_role_label"], "")
            self.assertEqual(blind_row["annotation_notes"], "")

    def test_validate_safe_to_overwrite_blocks_by_default(self) -> None:
        output_dir = PROJECT_ROOT / "tests" / "_role_annotation_output"
        output_dir.mkdir(parents=True, exist_ok=True)
        test_file = output_dir / "unannotated_test.csv"
        test_file.write_text("header\nvalue\n", encoding="utf-8")

        with self.assertRaises(FileExistsError):
            validate_safe_to_overwrite([test_file], force=False)

        validate_safe_to_overwrite([test_file], force=True)

    def test_validate_safe_to_overwrite_protects_human_labels(self) -> None:
        output_dir = PROJECT_ROOT / "tests" / "_role_annotation_output"
        output_dir.mkdir(parents=True, exist_ok=True)
        annotated_file = output_dir / "annotated_test.csv"
        with annotated_file.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["id", "human_verified_role_label", "annotation_notes"])
            writer.writeheader()
            writer.writerow({
                "id": "1",
                "human_verified_role_label": "data_scientist_advanced_analytics",
                "annotation_notes": "Verified by human",
            })

        self.assertTrue(file_has_human_labels(annotated_file))

        with self.assertRaises(PermissionError):
            validate_safe_to_overwrite([annotated_file], force=True, confirm_annotated=False)

        validate_safe_to_overwrite([annotated_file], force=True, confirm_annotated=True)

    def test_run_targeted_main_cli_respects_overwrite_protection(self) -> None:
        output_dir = PROJECT_ROOT / "tests" / "_role_annotation_output"
        output_dir.mkdir(parents=True, exist_ok=True)
        dummy_out = output_dir / "cli_test_out.csv"
        dummy_blind = output_dir / "cli_test_blind.csv"
        dummy_out.write_text("existing", encoding="utf-8")

        with self.assertRaises(FileExistsError):
            run_targeted_main(["--output", str(dummy_out), "--blinded-output", str(dummy_blind)])




if __name__ == "__main__":
    unittest.main()
