# Targeted Data/AI Annotation Batch Report

## Selection rules

Candidates are selected only when a transparent title, extracted-skill, or description-term rule matches. Title matches rank above skills, and skills rank above description-only matches. `candidate_target_family` and `selection_rule` are selection aids, not human-verified labels.

## Counts by target family

| Family ID | Eligible candidates after original-sample exclusions | Selected |
| --- | ---: | ---: |
| data_scientist_advanced_analytics | 1 | 1 |
| machine_learning_ai_engineer | 1 | 1 |
| data_engineer_big_data_platform | 1 | 1 |
| data_analyst_business_intelligence | 2 | 1 |

## Source distribution

- adzuna_india: 2
- historical_2025_xlsx: 2

## Duplicate and ambiguity checks

- Excluded because they were already in the original 120-record sample: 1
- Exact title/company/description-excerpt duplicates were excluded against the original sample and within this batch.
- Candidates matching more than one target rule set: 0
- Ambiguous candidates may appear in this batch once only; their human label remains blank for reviewer judgment.
- Current historical/Adzuna records with no target-rule match after original-sample exclusions: 0

## Limitations

- This is a targeted, rule-selected batch, so it is deliberately not representative of the overall job-market distribution.
- Description and skill terminology can produce false positives; annotators must rely on the guide and enter the final gold label themselves.
- Adzuna has fewer available Data/AI candidates than the historical source, so source balance is improved where available but not forced.
