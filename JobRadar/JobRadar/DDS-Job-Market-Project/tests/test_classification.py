"""Focused unit tests for AI job classification foundation, rule baseline, and grouped splitting."""

from __future__ import annotations

from pathlib import Path
import shutil
import sys
import tempfile
import unittest

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from job_market.classification import (
    FALLBACK_ROLE_ID,
    FALLBACK_ROLE_NAME,
    PROVISIONAL_SILVER_LABEL_SOURCE,
    TAXONOMY_ROLE_NAMES,
    ErrorAnalysisReport,
    JobTextFeatures,
    MLClassificationResult,
    ModelEvaluationReport,
    RoleClassifierBundle,
    RoleClassifierMetadata,
    RuleClassificationResult,
    SplitVerificationResult,
    analyze_classification_errors,
    classify_job_by_rules,
    clean_text_snippet,
    contains_term,
    evaluate_role_classifier,
    fit_role_classifier,
    generate_provisional_silver_labels,
    get_model_summary,
    load_role_classifier,
    load_role_taxonomy,
    make_grouped_train_val_test_split,
    predict_job_role,
    predict_role,
    predict_role_probabilities,
    prepare_classification_text,
    prepare_labeled_dataset,
    save_role_classifier,
    verify_split_leakage,
)


class ClassificationFoundationTests(unittest.TestCase):
    """Test text preparation, taxonomy loader, and keyword matching."""

    def test_load_role_taxonomy_default(self) -> None:
        taxonomy = load_role_taxonomy()
        self.assertIn("role_families", taxonomy)
        families = {f["id"]: f["name"] for f in taxonomy["role_families"]}
        self.assertEqual(len(families), 11)
        self.assertIn("data_scientist_advanced_analytics", families)
        self.assertIn("machine_learning_ai_engineer", families)
        self.assertIn("other_unclassified", families)

    def test_clean_text_snippet(self) -> None:
        raw = "  Senior   Software   \n\n Engineer   with Python   "
        self.assertEqual(clean_text_snippet(raw), "Senior Software Engineer with Python")
        truncated = clean_text_snippet(raw, max_chars=15)
        self.assertEqual(truncated, "Senior Software")
        self.assertEqual(clean_text_snippet(None), "")

    def test_contains_term_word_boundaries(self) -> None:
        # Whole words match
        self.assertTrue(contains_term("qa", "Senior QA Engineer"))
        self.assertTrue(contains_term("sdet", "Lead SDET Position"))
        self.assertTrue(contains_term("c++", "C++ Systems Developer"))
        self.assertTrue(contains_term("c#", "C# / .NET Developer"))
        self.assertTrue(contains_term(".net", "Core .NET Developer"))

        # Substrings inside words do NOT match
        self.assertFalse(contains_term("qa", "qualify for the role"))
        self.assertFalse(contains_term("r", "software engineer"))

    def test_prepare_classification_text_boosting_and_truncation(self) -> None:
        title = "Staff Machine Learning Engineer"
        skills = ["PyTorch", "Transformers", "Python"]
        tags = ["it-jobs", "ai-engineer"]
        long_desc = "Building cutting-edge models for semantic search and recommendation systems. " * 20

        features = prepare_classification_text(
            title=title,
            skills=skills,
            tags=tags,
            description=long_desc,
            max_desc_chars=200,
            title_boost=3,
            skill_boost=2,
        )

        self.assertIsInstance(features, JobTextFeatures)
        self.assertEqual(features.title, title)
        self.assertEqual(features.canonical_skills, ("PyTorch", "Transformers", "Python"))
        self.assertEqual(features.source_tags, ("it-jobs", "ai-engineer"))
        self.assertLessEqual(len(features.description_excerpt), 200)

        # Title appears boosted 3 times in combined text
        self.assertEqual(features.combined_text.count(title), 3)
        # Skills appear boosted 2 times
        self.assertEqual(features.combined_text.count("PyTorch, Transformers, Python"), 2)


class RuleClassificationBaselineTests(unittest.TestCase):
    """Test explainable multi-signal rule-based classification."""

    def test_classify_all_canonical_role_families(self) -> None:
        test_cases = [
            (
                "Senior Data Scientist",
                ["data science", "statistics", "statistical modeling"],
                "Statistical modeling, hypothesis testing, and causal inference.",
                "data_scientist_advanced_analytics",
            ),
            (
                "Lead Machine Learning Engineer",
                ["machine learning", "pytorch", "deep learning"],
                "Train and deploy large language models and neural networks.",
                "machine_learning_ai_engineer",
            ),
            (
                "Big Data Engineer",
                ["spark", "kafka", "hadoop", "snowflake"],
                "Building robust data pipelines, ETL workflows, and data lake infrastructure.",
                "data_engineer_big_data_platform",
            ),
            (
                "Senior Business Intelligence Analyst",
                ["power bi", "tableau", "excel", "sql"],
                "Build executive dashboards, KPI reports, and business intelligence models.",
                "data_analyst_business_intelligence",
            ),
            (
                "Principal Backend Software Engineer",
                ["python", "fastapi", "postgresql", "rest api"],
                "Design and maintain scalable microservices and backend database architectures.",
                "backend_core_software_engineering",
            ),
            (
                "Frontend React Developer",
                ["react", "typescript", "tailwind", "html"],
                "Create responsive user interfaces and modern web applications.",
                "frontend_full_stack_engineering",
            ),
            (
                "DevOps / SRE Platform Engineer",
                ["aws", "kubernetes", "terraform", "docker"],
                "Manage cloud infrastructure, CI/CD pipelines, and cluster observability.",
                "cloud_devops_sre",
            ),
            (
                "Automation Test Engineer / SDET",
                ["selenium", "cypress", "pytest", "test automation"],
                "Author test plans, automate regression test cases, and verify software quality.",
                "qa_automation_testing",
            ),
            (
                "Technical Product Manager",
                ["jira", "agile", "scrum", "product strategy"],
                "Define product roadmaps, lead sprint planning, and manage stakeholder backlogs.",
                "product_technical_project_management",
            ),
            (
                "Senior HR Talent Acquisition Specialist",
                ["recruiting", "talent sourcing"],
                "Manage end-to-end talent acquisition and candidate interviews.",
                "non_tech_corporate_operations",
            ),
        ]

        for title, skills, desc, expected_role in test_cases:
            with self.subTest(title=title, expected_role=expected_role):
                result = classify_job_by_rules(
                    title=title,
                    skills=skills,
                    description=desc,
                )
                self.assertEqual(result.role_id, expected_role)
                self.assertEqual(result.role_name, TAXONOMY_ROLE_NAMES[expected_role])
                self.assertTrue(result.is_classified)
                self.assertGreaterEqual(result.confidence, 0.70)
                self.assertGreaterEqual(result.score, 100.0)
                self.assertGreater(len(result.matched_rules), 0)

    def test_fallback_to_other_unclassified(self) -> None:
        result = classify_job_by_rules(
            title="General Consultant",
            skills=[],
            description="Client meetings, travel, general office communication.",
        )
        self.assertEqual(result.role_id, FALLBACK_ROLE_ID)
        self.assertEqual(result.role_name, FALLBACK_ROLE_NAME)
        self.assertFalse(result.is_classified)
        self.assertEqual(result.confidence, 0.0)
        self.assertEqual(result.score, 0.0)
        self.assertIsNone(result.runner_up_role_id)

    def test_ambiguous_role_tracking(self) -> None:
        # A title mentioning both Data Science and Generative AI
        result = classify_job_by_rules(
            title="Senior Data Scientist - GenAI Applications",
            skills=["machine learning", "statistics", "pytorch"],
            description="Apply generative ai and statistical experimentation to enterprise applications.",
        )
        self.assertTrue(result.is_classified)
        # Winner must be one of the two related families
        self.assertIn(
            result.role_id,
            ("data_scientist_advanced_analytics", "machine_learning_ai_engineer"),
        )
        # Runner-up must be the other family with a recorded score
        self.assertIn(
            result.runner_up_role_id,
            ("data_scientist_advanced_analytics", "machine_learning_ai_engineer"),
        )
        self.assertGreater(result.runner_up_score, 0.0)

    def test_specific_title_overrides_generic_software_engineer(self) -> None:
        # "Frontend Software Engineer" has both specific "frontend" and general "software engineer"
        result = classify_job_by_rules(
            title="Frontend Software Engineer",
            skills=["react", "typescript"],
        )
        self.assertEqual(result.role_id, "frontend_full_stack_engineering")
        # Runner-up should be backend_core_software_engineering from the general term
        self.assertEqual(result.runner_up_role_id, "backend_core_software_engineering")

        # "QA Software Engineer" has specific "qa" and general "software engineer"
        qa_result = classify_job_by_rules(
            title="QA Software Engineer",
            skills=["selenium"],
        )
        self.assertEqual(qa_result.role_id, "qa_automation_testing")


class GroupedSplitLeakageTests(unittest.TestCase):
    """Test grouped train/val/test splitting and leakage verification."""

    def test_grouped_split_zero_leakage(self) -> None:
        # Synthetic dataset with duplicates and shared fingerprints
        data = [
            # Group 1: Company A, Data Scientist
            {"job_id": 1, "company_name": "Company A", "title": "Data Scientist", "content_fingerprint": "fp_001"},
            {"job_id": 2, "company_name": "Company A", "title": "Data Scientist", "content_fingerprint": "fp_001"},
            {"job_id": 3, "company_name": "Company A", "title": "Data Scientist", "content_fingerprint": "fp_002"},

            # Group 2: Company A, Backend Engineer (different title)
            {"job_id": 4, "company_name": "Company A", "title": "Backend Engineer", "content_fingerprint": "fp_003"},
            {"job_id": 5, "company_name": "Company A", "title": "Backend Engineer", "content_fingerprint": "fp_003"},

            # Group 3: Company B, ML Engineer
            {"job_id": 6, "company_name": "Company B", "title": "ML Engineer", "content_fingerprint": "fp_004"},
            {"job_id": 7, "company_name": "Company B", "title": "ML Engineer", "content_fingerprint": "fp_005"},

            # Group 4: Company C, Devops Engineer
            {"job_id": 8, "company_name": "Company C", "title": "DevOps Engineer", "content_fingerprint": "fp_006"},

            # Group 5: Company D, QA Engineer
            {"job_id": 9, "company_name": "Company D", "title": "QA Engineer", "content_fingerprint": "fp_007"},

            # Group 6: Company E, BI Analyst
            {"job_id": 10, "company_name": "Company E", "title": "BI Analyst", "content_fingerprint": "fp_008"},

            # Group 7: Company F, Product Manager
            {"job_id": 11, "company_name": "Company F", "title": "Product Manager", "content_fingerprint": "fp_009"},

            # Group 8: Company G, Data Engineer
            {"job_id": 12, "company_name": "Company G", "title": "Data Engineer", "content_fingerprint": "fp_010"},
        ]
        df = pd.DataFrame(data)

        split_df, verification = make_grouped_train_val_test_split(
            df,
            train_ratio=0.70,
            val_ratio=0.15,
            test_ratio=0.15,
            seed=20261111,
        )

        self.assertTrue(verification.is_valid)
        self.assertEqual(len(verification.leakage_details), 0)
        self.assertEqual(verification.total_records, 12)
        self.assertEqual(
            verification.train_count + verification.val_count + verification.test_count,
            12,
        )

        # Check that records 1, 2, and 3 are all in the SAME split (they share (Company A, Data Scientist))
        splits_g1 = split_df[split_df["job_id"].isin([1, 2, 3])]["split"].unique()
        self.assertEqual(len(splits_g1), 1)

        # Check zero overlaps across all split pairs
        for pair, count in verification.company_title_overlaps.items():
            self.assertEqual(count, 0, f"Leaked company/title in {pair}")
        for pair, count in verification.fingerprint_overlaps.items():
            self.assertEqual(count, 0, f"Leaked fingerprint in {pair}")

    def test_transitive_fingerprint_union(self) -> None:
        # Job 1 shares company/title with Job 2
        # Job 2 shares fingerprint with Job 3 (different company/title)
        # All three must be kept in the same split!
        data = [
            {"job_id": 1, "company_name": "Alpha Corp", "title": "Engineer", "content_fingerprint": "fp_A"},
            {"job_id": 2, "company_name": "Alpha Corp", "title": "Engineer", "content_fingerprint": "fp_B"},
            {"job_id": 3, "company_name": "Beta Corp", "title": "Lead Engineer", "content_fingerprint": "fp_B"},
            {"job_id": 4, "company_name": "Gamma Corp", "title": "Analyst", "content_fingerprint": "fp_C"},
            {"job_id": 5, "company_name": "Delta Corp", "title": "Specialist", "content_fingerprint": "fp_D"},
        ]
        df = pd.DataFrame(data)

        split_df, verification = make_grouped_train_val_test_split(
            df,
            train_ratio=0.60,
            val_ratio=0.20,
            test_ratio=0.20,
            seed=42,
        )

        self.assertTrue(verification.is_valid)
        # Jobs 1, 2, 3 must have identical split
        transitive_splits = split_df[split_df["job_id"].isin([1, 2, 3])]["split"].unique()
        self.assertEqual(len(transitive_splits), 1)

    def test_deterministic_split_reproducibility(self) -> None:
        data = [
            {"job_id": i, "company_name": f"Company {i % 4}", "title": f"Role {i % 3}", "content_fingerprint": f"fp_{i % 5}"}
            for i in range(50)
        ]
        df = pd.DataFrame(data)

        df1, _ = make_grouped_train_val_test_split(df, seed=9999)
        df2, _ = make_grouped_train_val_test_split(df, seed=9999)

        pd.testing.assert_series_equal(df1["split"], df2["split"])
        pd.testing.assert_series_equal(df1["group_key"], df2["group_key"])

    def test_leakage_verifier_detects_contamination(self) -> None:
        # Intentionally create contaminated splits
        contaminated_data = [
            {"company_name": "Acme", "title": "Data Scientist", "content_fingerprint": "fp_x", "split": "train"},
            {"company_name": "Acme", "title": "Data Scientist", "content_fingerprint": "fp_y", "split": "test"},  # Shared (Acme, Data Scientist)
            {"company_name": "Beta", "title": "Engineer", "content_fingerprint": "fp_z", "split": "train"},
            {"company_name": "Gamma", "title": "Architect", "content_fingerprint": "fp_z", "split": "val"},  # Shared fp_z
        ]
        df = pd.DataFrame(contaminated_data)
        verification = verify_split_leakage(df)

        self.assertFalse(verification.is_valid)
        self.assertGreater(verification.company_title_overlaps["train_test"], 0)
        self.assertGreater(verification.fingerprint_overlaps["train_val"], 0)
        self.assertGreater(len(verification.leakage_details), 0)


class RoleClassifierMLTests(unittest.TestCase):
    """Test TF-IDF + Logistic Regression ML pipeline, evaluation, and provenance safety."""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="test_ml_clf_"))
        # Synthetic training records covering multiple role families
        self.raw_training_data = [
            # Data Scientist
            {"title": "Senior Data Scientist", "skills": "data science, statistics, r", "source_tags_text": "it-jobs", "job_description": "Statistical modeling and hypothesis testing.", "label": "data_scientist_advanced_analytics"},
            {"title": "Staff Data Scientist", "skills": "predictive modeling, python, statistics", "source_tags_text": "ai", "job_description": "Causal inference and forecasting models.", "label": "data_scientist_advanced_analytics"},
            {"title": "Quantitative Researcher", "skills": "statistics, econometrics", "source_tags_text": "analytics", "job_description": "Experimentation and algorithmic research.", "label": "data_scientist_advanced_analytics"},

            # ML Engineer
            {"title": "Machine Learning Engineer", "skills": "pytorch, deep learning, nlp", "source_tags_text": "ai", "job_description": "Deploying large language models and neural networks.", "label": "machine_learning_ai_engineer"},
            {"title": "AI / GenAI Engineer", "skills": "transformers, python, hugging face", "source_tags_text": "ai", "job_description": "Fine-tuning transformer models for vector search.", "label": "machine_learning_ai_engineer"},
            {"title": "Deep Learning Specialist", "skills": "computer vision, opencv, pytorch", "source_tags_text": "it-jobs", "job_description": "Object detection and deep neural architectures.", "label": "machine_learning_ai_engineer"},

            # Backend Engineer
            {"title": "Backend Python Developer", "skills": "python, fastapi, postgresql", "source_tags_text": "backend", "job_description": "Building scalable REST APIs and database queries.", "label": "backend_core_software_engineering"},
            {"title": "Senior Java Software Engineer", "skills": "java, spring boot, microservices", "source_tags_text": "it-jobs", "job_description": "Core backend services and high throughput systems.", "label": "backend_core_software_engineering"},
            {"title": "Golang Server Developer", "skills": "go, redis, postgresql", "source_tags_text": "developer", "job_description": "High performance server architecture.", "label": "backend_core_software_engineering"},

            # Cloud / DevOps
            {"title": "DevOps Cloud Engineer", "skills": "aws, terraform, docker, kubernetes", "source_tags_text": "cloud", "job_description": "CI/CD pipelines, container orchestration, and reliability.", "label": "cloud_devops_sre"},
            {"title": "Site Reliability Engineer (SRE)", "skills": "linux, kubernetes, prometheus", "source_tags_text": "devops", "job_description": "Cluster observability and cloud infrastructure automation.", "label": "cloud_devops_sre"},
            {"title": "Cloud Architect", "skills": "azure, terraform, ci/cd", "source_tags_text": "cloud", "job_description": "Enterprise cloud security and infrastructure design.", "label": "cloud_devops_sre"},

            # QA Automation
            {"title": "QA Automation Engineer", "skills": "selenium, cypress, test automation", "source_tags_text": "qa", "job_description": "Writing test plans and automating regression suites.", "label": "qa_automation_testing"},
            {"title": "SDET - Software Quality", "skills": "pytest, junit, postman", "source_tags_text": "qa", "job_description": "Authoring automated test harnesses and bug verification.", "label": "qa_automation_testing"},
            {"title": "Lead Test Engineer", "skills": "playwright, automation testing", "source_tags_text": "tester", "job_description": "Quality assurance and end-to-end framework delivery.", "label": "qa_automation_testing"},
        ]
        self.df_train = pd.DataFrame(self.raw_training_data)
        self.texts_train, self.labels_train, _ = prepare_labeled_dataset(
            self.df_train, label_col="label"
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_tfidf_feature_generation(self) -> None:
        bundle = fit_role_classifier(
            self.texts_train,
            self.labels_train,
            ngram_range=(1, 2),
            min_df=1,
        )
        self.assertIsInstance(bundle, RoleClassifierBundle)
        vectorizer = bundle.pipeline.named_steps["tfidf"]
        vocab = vectorizer.vocabulary_
        self.assertGreater(len(vocab), 10)

        # Bigrams are generated
        has_bigram = any(" " in term for term in vocab.keys())
        self.assertTrue(has_bigram, "Expected word bigrams in TF-IDF vocabulary")

        # Feature count recorded in metadata matches vocabulary size
        self.assertEqual(bundle.metadata.num_features, len(vocab))

    def test_training_and_prediction(self) -> None:
        bundle = fit_role_classifier(
            self.texts_train,
            self.labels_train,
            min_df=1,
            random_state=42,
        )
        self.assertEqual(len(bundle.metadata.classes_), 5)

        # Predict on new unseen postings
        pred_backend = predict_role(
            bundle, ["Lead Python FastAPI Microservices Engineer with PostgreSQL"]
        )
        self.assertEqual(pred_backend[0], "backend_core_software_engineering")

        pred_devops = predict_role(
            bundle, ["Senior AWS Kubernetes Terraform Cloud Specialist"]
        )
        self.assertEqual(pred_devops[0], "cloud_devops_sre")

        # Single-job prediction helper
        res = predict_job_role(
            bundle,
            title="Senior Deep Learning & LLM Engineer",
            skills=["pytorch", "transformers"],
        )
        self.assertIsInstance(res, MLClassificationResult)
        self.assertEqual(res.predicted_role, "machine_learning_ai_engineer")
        self.assertGreaterEqual(res.confidence, 0.25)
        self.assertTrue(res.is_provisional)

    def test_probability_output_properties(self) -> None:
        bundle = fit_role_classifier(
            self.texts_train, self.labels_train, min_df=1, random_state=42
        )
        test_text = "Automation QA Tester with Cypress and Selenium"
        probs_list = predict_role_probabilities(bundle, [test_text])

        self.assertEqual(len(probs_list), 1)
        probs = probs_list[0]

        # All classes represented
        self.assertEqual(set(probs.keys()), set(bundle.metadata.classes_))

        # Probabilities sum to 1.0 within floating point tolerance
        total_prob = sum(probs.values())
        self.assertAlmostEqual(total_prob, 1.0, places=2)

        # Probabilities are sorted descending
        prob_vals = list(probs.values())
        self.assertEqual(prob_vals, sorted(prob_vals, reverse=True))

        # Expected top class is QA
        self.assertEqual(list(probs.keys())[0], "qa_automation_testing")

    def test_unseen_vocabulary_handling(self) -> None:
        bundle = fit_role_classifier(
            self.texts_train, self.labels_train, min_df=1, random_state=42
        )
        # Completely out-of-vocabulary gibberish text
        oov_text = "Zorblaxian fribulator qwertyuiop987654321 asdfghjkl"
        pred = predict_role(bundle, [oov_text])
        self.assertIn(pred[0], bundle.metadata.classes_)

        probs = predict_role_probabilities(bundle, [oov_text])[0]
        self.assertAlmostEqual(sum(probs.values()), 1.0, places=2)

    def test_missing_and_invalid_labels(self) -> None:
        dirty_data = [
            {"title": "Job 1", "label": "data_scientist_advanced_analytics"},
            {"title": "Job 2", "label": None},
            {"title": "Job 3", "label": ""},
            {"title": "Job 4", "label": "nan"},
            {"title": "Job 5", "label": "invalid_unknown_role"},
            {"title": "Job 6", "label": "backend_core_software_engineering"},
        ]
        df_dirty = pd.DataFrame(dirty_data)

        # Only valid roles preserved
        valid_roles = ["data_scientist_advanced_analytics", "backend_core_software_engineering"]
        texts, labels, cleaned_df = prepare_labeled_dataset(
            df_dirty, label_col="label", valid_roles=valid_roles
        )
        self.assertEqual(len(labels), 2)
        self.assertEqual(labels, ["data_scientist_advanced_analytics", "backend_core_software_engineering"])
        self.assertEqual(len(cleaned_df), 2)

        # Accidental training on unannotated gold labels is blocked
        df_unannotated_gold = pd.DataFrame([
            {"title": "Job 1", "human_verified_role_label": None},
            {"title": "Job 2", "human_verified_role_label": ""},
        ])
        with self.assertRaises(ValueError):
            prepare_labeled_dataset(df_unannotated_gold, label_col="human_verified_role_label")

        # Single-class dataset cannot be trained
        single_class_texts = ["Text 1", "Text 2"]
        single_class_labels = ["role_a", "role_a"]
        with self.assertRaises(ValueError):
            fit_role_classifier(single_class_texts, single_class_labels)

        # Empty dataset cannot be trained
        with self.assertRaises(ValueError):
            fit_role_classifier([], [])

    def test_deterministic_reproducibility(self) -> None:
        bundle1 = fit_role_classifier(
            self.texts_train, self.labels_train, min_df=1, random_state=20261111
        )
        bundle2 = fit_role_classifier(
            self.texts_train, self.labels_train, min_df=1, random_state=20261111
        )

        clf1 = bundle1.pipeline.named_steps["clf"]
        clf2 = bundle2.pipeline.named_steps["clf"]
        np.testing.assert_allclose(clf1.coef_, clf2.coef_)
        np.testing.assert_allclose(clf1.intercept_, clf2.intercept_)

        eval_texts = ["FastAPI Backend Developer", "Kubernetes DevOps SRE"]
        probs1 = predict_role_probabilities(bundle1, eval_texts)
        probs2 = predict_role_probabilities(bundle2, eval_texts)
        self.assertEqual(probs1, probs2)

    def test_group_leakage_with_training_pipeline(self) -> None:
        # Grouped dataset with duplicate companies/titles and fingerprints
        grouped_records = [
            # Group 1 (3 records)
            {"company_name": "Acme", "title": "Data Scientist", "content_fingerprint": "fp1", "skills": "python", "job_description": "ds"},
            {"company_name": "Acme", "title": "Data Scientist", "content_fingerprint": "fp1", "skills": "python", "job_description": "ds"},
            {"company_name": "Acme", "title": "Data Scientist", "content_fingerprint": "fp2", "skills": "python", "job_description": "ds"},

            # Group 2 (2 records)
            {"company_name": "Beta", "title": "DevOps Lead", "content_fingerprint": "fp3", "skills": "aws", "job_description": "cloud"},
            {"company_name": "Beta", "title": "DevOps Lead", "content_fingerprint": "fp3", "skills": "aws", "job_description": "cloud"},

            # Group 3 (2 records)
            {"company_name": "Gamma", "title": "Backend Dev", "content_fingerprint": "fp4", "skills": "django", "job_description": "backend"},
            {"company_name": "Gamma", "title": "Backend Dev", "content_fingerprint": "fp5", "skills": "django", "job_description": "backend"},

            # Group 4 (1 record)
            {"company_name": "Delta", "title": "QA Tester", "content_fingerprint": "fp6", "skills": "selenium", "job_description": "test"},

            # Group 5 (1 record)
            {"company_name": "Epsilon", "title": "ML Engineer", "content_fingerprint": "fp7", "skills": "pytorch", "job_description": "ml"},
        ]
        df = pd.DataFrame(grouped_records)
        df_silver = generate_provisional_silver_labels(df)

        split_df, verification = make_grouped_train_val_test_split(
            df_silver,
            train_ratio=0.60,
            val_ratio=0.20,
            test_ratio=0.20,
            seed=20261111,
        )
        self.assertTrue(verification.is_valid)
        self.assertEqual(verification.company_title_overlaps["train_val"], 0)
        self.assertEqual(verification.company_title_overlaps["train_test"], 0)
        self.assertEqual(verification.fingerprint_overlaps["train_val"], 0)
        self.assertEqual(verification.fingerprint_overlaps["train_test"], 0)

        # Train on train split only
        train_split = split_df[split_df["split"] == "train"]
        val_split = split_df[split_df["split"] == "val"]

        X_train, y_train, _ = prepare_labeled_dataset(
            train_split, label_col="provisional_silver_label"
        )
        X_val, y_val, _ = prepare_labeled_dataset(
            val_split, label_col="provisional_silver_label"
        )
        self.assertGreater(len(X_train), 0)
        self.assertGreater(len(X_val), 0)

    def test_model_save_and_load(self) -> None:
        bundle = fit_role_classifier(
            self.texts_train, self.labels_train, min_df=1, random_state=42
        )
        save_path = self.temp_dir / "test_model_bundle.joblib"
        saved_path = save_role_classifier(bundle, save_path)
        self.assertTrue(saved_path.is_file())

        loaded_bundle = load_role_classifier(saved_path)
        self.assertIsInstance(loaded_bundle, RoleClassifierBundle)
        self.assertEqual(loaded_bundle.metadata.model_name, bundle.metadata.model_name)
        self.assertEqual(loaded_bundle.metadata.classes_, bundle.metadata.classes_)
        self.assertEqual(loaded_bundle.metadata.num_features, bundle.metadata.num_features)

        # Loaded model produces identical predictions
        test_texts = ["Senior Java Developer", "Cloud Kubernetes SRE"]
        original_preds = predict_role(bundle, test_texts)
        loaded_preds = predict_role(loaded_bundle, test_texts)
        self.assertEqual(original_preds, loaded_preds)

    def test_evaluation_report(self) -> None:
        bundle = fit_role_classifier(
            self.texts_train, self.labels_train, min_df=1, random_state=42
        )
        # Evaluate on validation samples
        val_data = [
            {"title": "Lead Data Scientist", "skills": "statistics, r", "source_tags_text": "it-jobs", "job_description": "Statistical inference.", "label": "data_scientist_advanced_analytics"},
            {"title": "Core Backend Java Developer", "skills": "java, spring boot", "source_tags_text": "backend", "job_description": "Scalable APIs.", "label": "backend_core_software_engineering"},
            {"title": "Cloud SRE Platform Lead", "skills": "aws, docker, kubernetes", "source_tags_text": "cloud", "job_description": "Infrastructure.", "label": "cloud_devops_sre"},
        ]
        df_val = pd.DataFrame(val_data)
        X_val, y_val, _ = prepare_labeled_dataset(df_val, label_col="label")

        rule_preds = [
            classify_job_by_rules(row["title"], skills=row["skills"].split(", ")).role_id
            for _, row in df_val.iterrows()
        ]

        report = evaluate_role_classifier(
            bundle=bundle,
            X_eval=X_val,
            y_eval=y_val,
            X_train=self.texts_train,
            y_train=self.labels_train,
            split_name="val",
            rule_baseline_preds=rule_preds,
        )

        self.assertIsInstance(report, ModelEvaluationReport)
        self.assertEqual(report.split_name, "val")
        self.assertTrue(report.is_provisional)
        self.assertGreaterEqual(report.model_accuracy, 0.60)
        self.assertGreaterEqual(report.model_macro_f1, 0.50)
        self.assertIsNotNone(report.rule_baseline_accuracy)
        self.assertGreater(len(report.confusion_matrix), 0)
        self.assertTrue(any("PROVISIONAL DIAGNOSTIC ONLY" in n for n in report.evaluation_notes))


class ErrorAnalysisAndConfidenceTests(unittest.TestCase):
    """Test Stage 2.4 confusion-matrix error analysis, confidence tiering, and fallbacks."""

    def setUp(self) -> None:
        self.train_texts = [
            "Senior Data Scientist Python Statistics",
            "Staff Data Scientist R Modeling",
            "Machine Learning Engineer PyTorch Deep Learning",
            "Python Backend Developer FastAPI PostgreSQL",
            "Java Software Engineer Spring Boot Microservices",
            "DevOps Cloud Engineer AWS Kubernetes",
        ]
        self.train_labels = [
            "data_scientist_advanced_analytics",
            "data_scientist_advanced_analytics",
            "machine_learning_ai_engineer",
            "backend_core_software_engineering",
            "backend_core_software_engineering",
            "cloud_devops_sre",
        ]
        self.bundle = fit_role_classifier(
            self.train_texts,
            self.train_labels,
            label_source="provisional_silver_rule_v1",
            min_df=1,
            random_state=42,
        )

    def test_confidence_tier_assignment(self) -> None:
        res = predict_job_role(
            self.bundle,
            title="Senior Python Backend Developer with FastAPI",
        )
        self.assertIn(res.confidence_tier, ("HIGH", "MEDIUM", "LOW", "UNCERTAIN"))
        self.assertGreater(res.confidence, 0.0)
        self.assertFalse(res.is_fallback)

    def test_fallback_on_min_confidence_threshold(self) -> None:
        # Require an impossibly high confidence (0.9999) to force fallback
        res = predict_job_role(
            self.bundle,
            title="Senior Python Developer",
            min_confidence_threshold=0.9999,
        )
        self.assertEqual(res.predicted_role, FALLBACK_ROLE_ID)
        self.assertEqual(res.predicted_role_name, FALLBACK_ROLE_NAME)
        self.assertTrue(res.is_fallback)
        # Original probabilities are still preserved
        self.assertGreater(len(res.class_probabilities), 0)

    def test_fallback_on_narrow_margin(self) -> None:
        # Require a wide margin over runner-up (0.99) to force fallback
        res = predict_job_role(
            self.bundle,
            title="Senior Python Developer",
            confidence_margin_threshold=0.99,
        )
        self.assertEqual(res.predicted_role, FALLBACK_ROLE_ID)
        self.assertTrue(res.is_fallback)

    def test_analyze_classification_errors_metrics(self) -> None:
        y_true = [
            "data_scientist_advanced_analytics",
            "backend_core_software_engineering",
            "backend_core_software_engineering",
            "cloud_devops_sre",
        ]
        y_pred = [
            "data_scientist_advanced_analytics",
            "backend_core_software_engineering",
            "frontend_full_stack_engineering",  # Error: Backend predicted as Frontend
            "cloud_devops_sre",
        ]
        probs = [
            {"data_scientist_advanced_analytics": 0.85, "backend_core_software_engineering": 0.15},
            {"backend_core_software_engineering": 0.65, "frontend_full_stack_engineering": 0.35},
            {"frontend_full_stack_engineering": 0.52, "backend_core_software_engineering": 0.48},
            {"cloud_devops_sre": 0.25, "backend_core_software_engineering": 0.75},  # Low confidence
        ]

        report = analyze_classification_errors(y_true, y_pred, probabilities=probs)
        self.assertIsInstance(report, ErrorAnalysisReport)
        self.assertEqual(report.total_samples, 4)
        self.assertEqual(report.total_errors, 1)
        self.assertEqual(report.overall_error_rate, 0.25)
        self.assertEqual(len(report.top_confusions), 1)
        self.assertEqual(report.top_confusions[0]["true_role"], "backend_core_software_engineering")
        self.assertEqual(report.top_confusions[0]["pred_role"], "frontend_full_stack_engineering")

        # Per-class summary check
        self.assertIn("backend_core_software_engineering", report.per_class_error_summary)
        backend_stats = report.per_class_error_summary["backend_core_software_engineering"]
        self.assertEqual(backend_stats["support"], 2)
        self.assertEqual(backend_stats["errors"], 1)

        # Stratification & Brier score check
        self.assertIn("HIGH", report.confidence_stratification)
        self.assertIsNotNone(report.brier_score)
        self.assertGreater(report.brier_score, 0.0)


if __name__ == "__main__":
    unittest.main()


