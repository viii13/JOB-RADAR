"""Curated Verified Learning Resource Library for Technical Skills.

Stage 5.5 — Reuses verified resources from `mockLearning.js` and provides
official, verified documentation, practice platforms, and practical project specifications.
Strictly avoids fabricating course links or fictional pricing.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class LearningResource:
    """Verified course, documentation, or tutorial link."""

    title: str
    provider: str
    url: str
    type: str  # "Documentation", "Interactive Course", "Video Course", "Official Tutorial"
    badge: str
    free: bool


@dataclass(frozen=True)
class PracticePlatform:
    """Coding practice or competition platform."""

    name: str
    url: str


@dataclass(frozen=True)
class PracticalProject:
    """Concrete student-level portfolio project with measurable deliverables."""

    title: str
    difficulty: str  # "Beginner", "Intermediate", "Advanced"
    skills_applied: list[str]
    summary: str
    deliverables: list[str]


@dataclass(frozen=True)
class SkillResourcePackage:
    """Comprehensive verified learning package for a single canonical skill."""

    skill_name: str
    description: str
    resources: list[LearningResource]
    practice_platforms: list[PracticePlatform]
    projects: list[PracticalProject]
    implementation_steps: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Convert package to serializable dictionary."""
        return {
            "skill_name": self.skill_name,
            "description": self.description,
            "resources": [asdict(r) for r in self.resources],
            "practice_platforms": [asdict(p) for p in self.practice_platforms],
            "projects": [asdict(pr) for pr in self.projects],
            "implementation_steps": self.implementation_steps,
        }


# Verified Curated Resource Catalog
# Combines verified mockLearning.js resources and official documentation for top technical skills
VERIFIED_SKILL_RESOURCES: dict[str, SkillResourcePackage] = {
    # 1. From mockLearning.js: Machine Learning
    "Machine Learning": SkillResourcePackage(
        skill_name="Machine Learning",
        description="Learn mathematical intuitions, supervised/unsupervised algorithms, and scikit-learn implementations.",
        resources=[
            LearningResource(
                title="Machine Learning Specialization by Andrew Ng",
                provider="Coursera / DeepLearning.AI",
                url="https://www.coursera.org/specializations/machine-learning-introduction",
                type="Interactive Course",
                badge="Industry Gold Standard",
                free=False,
            ),
            LearningResource(
                title="Intro to Machine Learning (Micro-courses)",
                provider="Kaggle Learn",
                url="https://www.kaggle.com/learn/intro-to-machine-learning",
                type="Interactive Course",
                badge="Free Hands-on",
                free=True,
            ),
            LearningResource(
                title="Scikit-Learn Official User Guide",
                provider="scikit-learn.org",
                url="https://scikit-learn.org/stable/user_guide.html",
                type="Documentation",
                badge="Reference",
                free=True,
            ),
        ],
        practice_platforms=[
            PracticePlatform(name="Kaggle Competitions (Titanic & Housing Prices)", url="https://www.kaggle.com/competitions"),
            PracticePlatform(name="HackerRank AI Domain", url="https://www.hackerrank.com/domains/ai"),
        ],
        projects=[
            PracticalProject(
                title="Tech Salary Prediction Engine",
                difficulty="Intermediate",
                skills_applied=["Python", "Pandas", "Scikit-learn", "Regression"],
                summary="Build an end-to-end regression model predicting tech salaries based on experience, location, and skill tags with an interactive web UI.",
                deliverables=["EDA Jupyter Notebook", "Trained GradientBoosting Model", "Feature Importance Plot", "Clean GitHub Readme"],
            )
        ],
        implementation_steps=[
            "Master supervised regression and classification mechanics (Loss functions, Gradient Descent).",
            "Implement baseline linear & logistic regression using NumPy from scratch to understand math.",
            "Transition to Scikit-learn pipelines with StandardScaler, SimpleImputer, and ColumnTransformer.",
            "Evaluate rigorously with Stratified K-Fold CV, Precision/Recall, and ROC-AUC curves.",
        ],
    ),
    # 2. From mockLearning.js: Scikit-learn
    "Scikit-learn": SkillResourcePackage(
        skill_name="Scikit-learn",
        description="The premier Python machine learning library for data preprocessing, model training, and hyperparameter tuning.",
        resources=[
            LearningResource(
                title="Scikit-Learn Official Tutorials",
                provider="scikit-learn.org",
                url="https://scikit-learn.org/stable/tutorial/index.html",
                type="Documentation",
                badge="Essential",
                free=True,
            ),
            LearningResource(
                title="Machine Learning with Python & Scikit-learn",
                provider="freeCodeCamp",
                url="https://www.freecodecamp.org/news/machine-learning-with-python-and-scikit-learn/",
                type="Video Course",
                badge="Free Full Course",
                free=True,
            ),
        ],
        practice_platforms=[
            PracticePlatform(name="Kaggle Datasets & Notebooks", url="https://www.kaggle.com/datasets"),
        ],
        projects=[
            PracticalProject(
                title="Automated ML Preprocessing Pipeline",
                difficulty="Intermediate",
                skills_applied=["Python", "Scikit-learn"],
                summary="Build a reusable Scikit-learn Pipeline with custom transformers handling missing values, encoding, and scaling.",
                deliverables=["Reusable pipeline.py module", "Unit tests for custom transformers", "Cross-validation benchmark report"],
            )
        ],
        implementation_steps=[
            "Learn Pipeline and ColumnTransformer abstractions.",
            "Implement GridSearchCV and RandomizedSearchCV for hyperparameter tuning.",
            "Evaluate models with classification_report and confusion_matrix.",
        ],
    ),
    # 3. From mockLearning.js: NLP
    "NLP": SkillResourcePackage(
        skill_name="NLP",
        description="Natural Language Processing for text classification, sentiment analysis, entity extraction, and transformers.",
        resources=[
            LearningResource(
                title="Hugging Face NLP Course",
                provider="Hugging Face",
                url="https://huggingface.co/learn/nlp-course/chapter1/1",
                type="Interactive Course",
                badge="Industry Gold Standard",
                free=True,
            ),
            LearningResource(
                title="SpaCy Official Usage Documentation",
                provider="Explosion AI / spaCy",
                url="https://spacy.io/usage",
                type="Documentation",
                badge="Production NLP",
                free=True,
            ),
        ],
        practice_platforms=[
            PracticePlatform(name="Kaggle NLP Competitions (Disaster Tweets)", url="https://www.kaggle.com/c/nlp-getting-started"),
        ],
        projects=[
            PracticalProject(
                title="Job Description Skill Extractor",
                difficulty="Intermediate",
                skills_applied=["Python", "spaCy", "Regex", "NLP"],
                summary="Build an information extraction pipeline extracting technical skill entities from free-form job postings.",
                deliverables=["Custom spaCy NER pipeline", "Tokenization and evaluation script", "F1 evaluation score benchmark"],
            )
        ],
        implementation_steps=[
            "Understand tokenization, stemming, lemmatization, and TF-IDF representations.",
            "Learn pre-trained transformer pipelines (BERT, RoBERTa) with Hugging Face.",
            "Fine-tune a classification head for domain-specific text classification.",
        ],
    ),
    # 4. From mockLearning.js: AWS
    "AWS": SkillResourcePackage(
        skill_name="AWS",
        description="Amazon Web Services cloud architecture, serverless computing, storage, IAM, and container orchestration.",
        resources=[
            LearningResource(
                title="AWS Cloud Practitioner Essentials",
                provider="AWS Skill Builder",
                url="https://aws.amazon.com/training/digital/aws-cloud-practitioner-essentials/",
                type="Official Tutorial",
                badge="Official Free",
                free=True,
            ),
            LearningResource(
                title="AWS Documentation Center",
                provider="Amazon Web Services",
                url="https://docs.aws.amazon.com/",
                type="Documentation",
                badge="Reference",
                free=True,
            ),
        ],
        practice_platforms=[
            PracticePlatform(name="AWS Free Tier Hands-on Labs", url="https://aws.amazon.com/free/"),
        ],
        projects=[
            PracticalProject(
                title="Serverless Document Analysis Architecture",
                difficulty="Intermediate",
                skills_applied=["AWS S3", "AWS Lambda", "API Gateway"],
                summary="Deploy an event-driven serverless workflow that triggers a Lambda function upon S3 document upload and stores metadata.",
                deliverables=["Infrastructure as Code (Terraform or CloudFormation)", "Lambda Python handler", "Architecture diagram"],
            )
        ],
        implementation_steps=[
            "Understand IAM policies, roles, and least-privilege security.",
            "Configure VPC networking, subnets, and security groups.",
            "Deploy applications using ECS / Fargate or Lambda.",
        ],
    ),
    # 5. From mockLearning.js: Docker
    "Docker": SkillResourcePackage(
        skill_name="Docker",
        description="Containerization technology for packaging applications, managing microservices, and consistent development environments.",
        resources=[
            LearningResource(
                title="Docker Official Getting Started Guide",
                provider="Docker Docs",
                url="https://docs.docker.com/get-started/",
                type="Documentation",
                badge="Essential",
                free=True,
            ),
            LearningResource(
                title="Docker for Beginners",
                provider="freeCodeCamp",
                url="https://www.freecodecamp.org/news/the-docker-handbook/",
                type="Tutorial",
                badge="Comprehensive",
                free=True,
            ),
        ],
        practice_platforms=[
            PracticePlatform(name="Play with Docker Labs", url="https://labs.play-with-docker.com/"),
        ],
        projects=[
            PracticalProject(
                title="Multi-Service Containerized Web Stack",
                difficulty="Intermediate",
                skills_applied=["Docker", "Docker Compose", "FastAPI", "PostgreSQL"],
                summary="Build a multi-container architecture running a FastAPI backend, PostgreSQL database, and Redis cache with volume persistence.",
                deliverables=["Multi-stage Dockerfile", "docker-compose.yml file", "Healthcheck scripts"],
            )
        ],
        implementation_steps=[
            "Learn container lifecycle commands (build, run, stop, rm, ps).",
            "Write efficient multi-stage Dockerfiles minimizing image sizes.",
            "Configure docker-compose networks and persistent volumes.",
        ],
    ),
    # 6. Python
    "Python": SkillResourcePackage(
        skill_name="Python",
        description="Versatile core programming language for software engineering, data engineering, APIs, and machine learning.",
        resources=[
            LearningResource(
                title="Official Python 3 Documentation & Tutorial",
                provider="Python Software Foundation",
                url="https://docs.python.org/3/tutorial/",
                type="Documentation",
                badge="Official",
                free=True,
            ),
            LearningResource(
                title="Scientific Python Lectures",
                provider="scipy-lectures.org",
                url="https://scipy-lectures.org/",
                type="Documentation",
                badge="Data Science",
                free=True,
            ),
        ],
        practice_platforms=[
            PracticePlatform(name="LeetCode (Python Track)", url="https://leetcode.com/problemset/all/"),
            PracticePlatform(name="HackerRank Python Domain", url="https://www.hackerrank.com/domains/python"),
        ],
        projects=[
            PracticalProject(
                title="Robust REST API with Type Annotations",
                difficulty="Intermediate",
                skills_applied=["Python", "FastAPI", "Pydantic", "Pytest"],
                summary="Develop a REST API with typed request validation, error handlers, and unit test suite achieving 90%+ coverage.",
                deliverables=["FastAPI backend code", "Pytest unit test suite", "Swagger API documentation"],
            )
        ],
        implementation_steps=[
            "Master data structures, list comprehensions, generators, and OOP.",
            "Write clean modular code with typing annotations and docstrings.",
            "Implement automated testing using pytest and unittest.",
        ],
    ),
    # 7. SQL
    "SQL": SkillResourcePackage(
        skill_name="SQL",
        description="Structured Query Language for relational database querying, joins, aggregations, window functions, and analytics.",
        resources=[
            LearningResource(
                title="PostgreSQL Official Documentation",
                provider="PostgreSQL Global Development Group",
                url="https://www.postgresql.org/docs/current/tutorial.html",
                type="Documentation",
                badge="Official Standard",
                free=True,
            ),
            LearningResource(
                title="Mode Analytics SQL Tutorial",
                provider="Mode Analytics",
                url="https://mode.com/sql-tutorial/",
                type="Interactive Course",
                badge="Analytics SQL",
                free=True,
            ),
        ],
        practice_platforms=[
            PracticePlatform(name="SQLZoo Interactive Exercises", url="https://sqlzoo.net/"),
            PracticePlatform(name="LeetCode Database Problems", url="https://leetcode.com/problemset/database/"),
        ],
        projects=[
            PracticalProject(
                title="E-Commerce Analytics Database & KPI Dashboard Queries",
                difficulty="Intermediate",
                skills_applied=["SQL", "PostgreSQL", "Window Functions", "CTEs"],
                summary="Design an analytical database schema and write complex analytical queries computing monthly churn, cohort retention, and customer lifetime value.",
                deliverables=["DDL schema script", "Analytical SQL script with CTEs and window functions", "Query execution plan analysis (EXPLAIN ANALYZE)"],
            )
        ],
        implementation_steps=[
            "Master basic CRUD, filtering, GROUP BY, and aggregate functions.",
            "Master complex multi-table joins (INNER, LEFT, FULL, CROSS).",
            "Learn advanced window functions (ROW_NUMBER, RANK, LEAD, LAG) and CTEs.",
        ],
    ),
    # 8. Java
    "Java": SkillResourcePackage(
        skill_name="Java",
        description="Enterprise object-oriented programming language widely used in backend services, microservices, and big data platforms.",
        resources=[
            LearningResource(
                title="Oracle Java Documentation & Tutorials",
                provider="Oracle",
                url="https://docs.oracle.com/javase/tutorial/",
                type="Documentation",
                badge="Official",
                free=True,
            ),
            LearningResource(
                title="Spring Boot Official Quickstart",
                provider="VMware Tanzu / Spring.io",
                url="https://spring.io/quickstart",
                type="Official Tutorial",
                badge="Backend Framework",
                free=True,
            ),
        ],
        practice_platforms=[
            PracticePlatform(name="LeetCode Java Track", url="https://leetcode.com/problemset/all/"),
            PracticePlatform(name="Exercism Java Track", url="https://exercism.org/tracks/java"),
        ],
        projects=[
            PracticalProject(
                title="Spring Boot Microservice with JPA & REST",
                difficulty="Intermediate",
                skills_applied=["Java", "Spring Boot", "Spring Data JPA", "Hibernate"],
                summary="Build a scalable microservice handling CRUD operations with database migrations, repository pattern, and validation.",
                deliverables=["Spring Boot application source code", "Postman / OpenAPI collection", "JUnit integration tests"],
            )
        ],
        implementation_steps=[
            "Master core OOP principles: inheritance, polymorphism, encapsulation, abstraction.",
            "Learn collections framework (List, Map, Set) and Java Streams API.",
            "Build Spring Boot REST APIs using Spring Data JPA and Hibernate.",
        ],
    ),
    # 9. JavaScript
    "JavaScript": SkillResourcePackage(
        skill_name="JavaScript",
        description="The foundational language of the modern web for frontend interactivity, full-stack development, and Node.js backends.",
        resources=[
            LearningResource(
                title="MDN Web Docs: JavaScript Guide",
                provider="Mozilla Developer Network",
                url="https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide",
                type="Documentation",
                badge="Gold Standard",
                free=True,
            ),
            LearningResource(
                title="JavaScript.info (Modern JS Tutorial)",
                provider="javascript.info",
                url="https://javascript.info/",
                type="Interactive Course",
                badge="In-depth",
                free=True,
            ),
        ],
        practice_platforms=[
            PracticePlatform(name="LeetCode JavaScript 30-Day Challenge", url="https://leetcode.com/studyplan/30-days-of-javascript/"),
            PracticePlatform(name="Codewars JavaScript Kata", url="https://www.codewars.com/"),
        ],
        projects=[
            PracticalProject(
                title="Interactive Kanban Task Management App",
                difficulty="Intermediate",
                skills_applied=["JavaScript", "DOM API", "HTML5 Drag & Drop", "LocalStorage"],
                summary="Create a vanilla JavaScript Kanban board supporting drag-and-drop column transitions, state persistence, and filtering.",
                deliverables=["Modular ES6 JavaScript source code", "Responsive UI", "GitHub Pages deployment"],
            )
        ],
        implementation_steps=[
            "Understand variable scoping (let, const), data types, and functions.",
            "Master asynchronous JavaScript: Event Loop, Promises, and async/await.",
            "Learn DOM manipulation, event handling, and ES6 module import/export.",
        ],
    ),
    # 10. React
    "React": SkillResourcePackage(
        skill_name="React",
        description="The leading declarative component-based JavaScript library for building responsive user interfaces.",
        resources=[
            LearningResource(
                title="React Official Documentation & Interactive Quickstart",
                provider="React Core Team",
                url="https://react.dev/",
                type="Documentation",
                badge="Official Modern",
                free=True,
            ),
        ],
        practice_platforms=[
            PracticePlatform(name="React.dev Interactive Challenges", url="https://react.dev/learn"),
        ],
        projects=[
            PracticalProject(
                title="Job Radar Interactive Application Portal",
                difficulty="Intermediate",
                skills_applied=["React", "JavaScript", "Hooks", "CSS"],
                summary="Build a multi-page dashboard displaying job opportunities, filtering by experience and location, with saved bookmarks.",
                deliverables=["React functional components using useState/useEffect/useMemo", "Clean CSS styling", "Live web deployment"],
            )
        ],
        implementation_steps=[
            "Master JSX, props, and component decomposition.",
            "Master React Hooks: useState, useEffect, useRef, and custom hooks.",
            "Handle form inputs, API data fetching, loading states, and error boundaries.",
        ],
    ),
    # 11. Kubernetes
    "Kubernetes": SkillResourcePackage(
        skill_name="Kubernetes",
        description="Production-grade container orchestration system for automating deployment, scaling, and operations of application containers.",
        resources=[
            LearningResource(
                title="Kubernetes Official Documentation & Interactive Tutorials",
                provider="Cloud Native Computing Foundation (CNCF)",
                url="https://kubernetes.io/docs/tutorials/",
                type="Documentation",
                badge="Official Standard",
                free=True,
            ),
        ],
        practice_platforms=[
            PracticePlatform(name="Killercoda Interactive Kubernetes Scenarios", url="https://killercoda.com/"),
        ],
        projects=[
            PracticalProject(
                title="High-Availability Microservices Deployment on Minikube",
                difficulty="Advanced",
                skills_applied=["Kubernetes", "Docker", "YAML Manifests"],
                summary="Deploy a load-balanced web application on a local cluster with Deployments, Services, ConfigMaps, and Ingress routing.",
                deliverables=["Kubernetes YAML manifests", "Cluster deployment documentation", "Rolling update test script"],
            )
        ],
        implementation_steps=[
            "Understand cluster architecture: Control plane, Nodes, Pods, Services.",
            "Write declarative manifests for Deployments, ReplicaSets, and Services.",
            "Configure ConfigMaps, Secrets, Ingress controllers, and Horizontal Pod Autoscaling (HPA).",
        ],
    ),
    # 12. Spark
    "Spark": SkillResourcePackage(
        skill_name="Spark",
        description="Unified analytics engine for large-scale data processing, distributed SQL, streaming, and machine learning.",
        resources=[
            LearningResource(
                title="Apache Spark Official Programming Guides",
                provider="Apache Software Foundation",
                url="https://spark.apache.org/docs/latest/index.html",
                type="Documentation",
                badge="Official",
                free=True,
            ),
        ],
        practice_platforms=[
            PracticePlatform(name="Databricks Community Edition", url="https://community.cloud.databricks.com/"),
        ],
        projects=[
            PracticalProject(
                title="Distributed Log Processing & Metric Aggregation",
                difficulty="Advanced",
                skills_applied=["PySpark", "Spark SQL", "DataFrames"],
                summary="Process multi-gigabyte log datasets in distributed chunks to compute daily active users and error rates partitioned by date.",
                deliverables=["PySpark batch processing script", "Optimized DataFrame queries with partitioning", "Execution performance report"],
            )
        ],
        implementation_steps=[
            "Learn distributed computing concepts: RDDs, DataFrames, partitions, and shuffling.",
            "Write Spark SQL transformations using PySpark.",
            "Tune Spark jobs: caching, broadcast joins, and partition pruning.",
        ],
    ),
}


def get_skill_resource_package(skill_name: str) -> SkillResourcePackage | None:
    """Retrieve verified resource package for a skill, matching case-insensitively."""
    cf = skill_name.casefold()
    for s_name, pkg in VERIFIED_SKILL_RESOURCES.items():
        if s_name.casefold() == cf:
            return pkg
    return None


def generate_fallback_project(skill_name: str, priority_category: str) -> PracticalProject:
    """Generate a realistic, student-level practical project when no pre-curated package exists."""
    difficulty = "Advanced" if priority_category == "CRITICAL" else "Intermediate"
    return PracticalProject(
        title=f"Hands-on {skill_name} Technical Implementation Project",
        difficulty=difficulty,
        skills_applied=[skill_name],
        summary=f"Design, build, and document a modular application or analytical workflow demonstrating practical proficiency with {skill_name}.",
        deliverables=[
            f"Functional {skill_name} code implementation",
            "Automated test coverage or verification script",
            "Comprehensive GitHub repository with README and architecture overview",
        ],
    )
