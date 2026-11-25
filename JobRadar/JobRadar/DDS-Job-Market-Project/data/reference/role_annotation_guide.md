# JobRadar Role Annotation Guide

## Purpose

This guide creates **human-verified gold labels** for Phase 4, AI Job Classification. A blank `human_verified_role_label` is intentionally blank: it is not a predicted label and must not be treated as one.

Use the job title and description excerpt together. The title is a useful clue, but the stated responsibilities are stronger evidence. Assign exactly one role-family ID from `role_taxonomy.json`.

## Annotation steps

1. Read the title, company, location, and description excerpt.
2. Choose the family that describes the role's main day-to-day responsibility.
3. Enter the role-family ID in `human_verified_role_label`.
4. Add a short explanation in `annotation_notes` when the decision is uncertain, the description is too short, or two families are plausible.
5. Leave the label empty only when the record cannot be assessed from the supplied information. Explain why in `annotation_notes`.

## Decision rules by family

| Role family ID | Choose it when the main work is | Typical evidence |
| --- | --- | --- |
| `data_scientist_advanced_analytics` | Statistics, experiments, forecasting, advanced analytics | statistical modeling, A/B tests, forecasting, hypothesis testing |
| `machine_learning_ai_engineer` | Building or operating ML/AI systems | model deployment, training pipelines, NLP, CV, LLMs, generative AI, MLOps |
| `data_engineer_big_data_platform` | Moving, storing, or serving data at platform scale | ETL/ELT, Spark, Kafka, data warehouse, Airflow, pipelines |
| `data_analyst_business_intelligence` | Dashboards, reporting, SQL analysis, business metrics | Power BI, Tableau, reporting, KPI, stakeholder insights |
| `backend_core_software_engineering` | Services, APIs, business logic, databases, integrations | Python/Java backend, REST APIs, microservices, server-side development |
| `frontend_full_stack_engineering` | User-facing web/mobile interfaces or full-stack delivery | React, Angular, UI, web client, mobile app, frontend plus backend |
| `cloud_devops_sre` | Reliability, deployments, cloud infrastructure, observability | CI/CD, Kubernetes, Terraform, monitoring, SRE, cloud operations |
| `qa_automation_testing` | Testing and quality assurance | Selenium, Playwright, test plans, automation, performance testing |
| `product_technical_project_management` | Product ownership or coordinating technical delivery | roadmap, requirements, sprint planning, project/program management |
| `non_tech_corporate_operations` | A non-technical business, administrative, or operations role | recruiting, sales, HR, finance, customer support, administration |
| `other_unclassified` | The role is genuinely unclear or outside the taxonomy | insufficient description, niche role with no clear dominant responsibility |

## Ambiguous cases

- **Data Scientist vs ML/AI Engineer:** choose Data Scientist for analysis and modeling used to answer questions; choose ML/AI Engineer when the job builds, deploys, or maintains production AI systems.
- **Data Engineer vs Backend Engineer:** choose Data Engineer for pipelines, warehouses, and data platforms; choose Backend Engineer for general APIs, services, and application logic.
- **Data Analyst vs Business Intelligence:** both use `data_analyst_business_intelligence` in this first taxonomy. Record `BI-focused` or `analyst-focused` in notes if it would help a later review.
- **Full Stack vs Backend:** choose Frontend & Full Stack only if the description includes a meaningful user-interface responsibility. A backend API role remains Backend & Core Software Engineering.
- **DevOps vs Backend:** deployment or cloud tooling alone does not make a backend role DevOps. Choose DevOps/SRE when infrastructure, reliability, automation, or platform operations is the main responsibility.
- **Generative AI roles:** use `machine_learning_ai_engineer`; add `generative-AI-focused` in notes when the description clearly says LLM, RAG, prompt engineering, or generative AI.
- **Mixed roles:** select the dominant responsibility, then note the secondary responsibility. Do not apply multiple labels in this first round.

## Quality checks

- Do not infer a label from company reputation, salary, or location.
- Do not use tools/skills alone if the described work points elsewhere.
- Do not overwrite `source_code`, `job_id`, `job_version_id`, `source_job_id`, or `origin_record_key`; they provide audit traceability.
- Keep rule-generated or future model-generated labels in separate columns/files. This CSV is reserved for human verification.
