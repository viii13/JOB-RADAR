import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
JOBRADAR_ROOT = PROJECT_ROOT.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
if str(JOBRADAR_ROOT) not in sys.path:
    sys.path.insert(0, str(JOBRADAR_ROOT))
aiml_dir = JOBRADAR_ROOT / "AI_ML"
if str(aiml_dir) not in sys.path:
    sys.path.insert(0, str(aiml_dir))

from job_market.cleaning import (
    REQUIRED_COLUMNS,
    clean_job_data,
    clean_location,
    clean_skills,
    clean_text,
    parse_experience,
)
from job_market.skills import (
    load_alias_map,
    load_category_map,
    normalize_skill,
    extract_tagged_skills,
    build_description_patterns,
    extract_description_skills,
)
from job_market.emerging import (
    compute_hiring_momentum_index,
    parse_relative_upload_days,
)
from job_market.adzuna_client import (
    AdzunaClient,
    sanitize_url,
)
from job_market.classification import (
    classify_job_by_rules,
    load_role_classifier,
    load_role_taxonomy,
    predict_job_role,
    prepare_classification_text,
)
from job_market.career_recommendations_api import (
    get_career_recommendations,
    get_skill_gap_analysis,
    generate_learning_roadmap,
    extract_resume_skills,
    load_role_skill_benchmarks,
)
from job_market.salary_prediction_api import _get_engine, get_salary_model_metadata

print("ALL IMPORTS SUCCEEDED!")
