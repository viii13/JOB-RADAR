# Skill Extraction Audit Report (Milestone 3A — Deterministic Baseline)

## Dataset

- Total rows processed: 97,682
- Rows with tagsAndSkills: 97,111
- Rows without tagsAndSkills: 571
- Rows with jobDescription: 97,662
- Rows without jobDescription: 20

## Extraction results

- Total (jobId, skill) pairs: 210,043
- Unique normalized skills: 104
- Jobs with at least one skill: 68,004

## Skill source breakdown

- jobDescription: 85,294
- tagsAndSkills: 83,076
- both: 41,673

## Category breakdown

- Other: 56,587
- Tools: 28,175
- Programming Language: 26,978
- DevOps: 18,535
- Framework: 16,019
- Data/ML: 15,301
- Web: 15,163
- Database: 14,882
- Cloud: 12,054
- BI/Visualization: 6,349
- _Categorized rows_: 153,456
- _Uncategorized (Other) rows_: 56,587

## Top 20 skills by demand (unique job postings)

  1. Communication Skills: 10,709
  2. Python: 7,520
  3. Customer Service: 7,445
  4. SAP: 7,213
  5. SQL: 6,654
  6. Project Management: 6,350
  7. Marketing: 6,329
  8. Java: 5,608
  9. Agile: 5,324
 10. CSS: 4,901
 11. IT: 4,637
 12. JavaScript: 4,517
 13. REST: 4,310
 14. AWS: 4,275
 15. Excel: 4,221
 16. Microsoft Azure: 4,206
 17. Troubleshooting: 4,193
 18. Accounting: 3,901
 19. C#: 3,457
 20. Oracle: 3,275

## Methodology

- **Source A (tagsAndSkills):** comma-separated tags split, filtered (≤80 chars), normalized.
- **Source B (jobDescription):** curated dictionary matched with word-boundary regex.
- **Normalization:** alias map → acronym preservation → title-case fallback.
- **Ambiguous skills:** C excluded from description search; R/Go restricted to contextual phrases; IT/AI case-sensitive.
- **Deduplication:** one row per (jobId, skill_normalized); source='both' when found in both.

## Limitations

- This is a **deterministic, rule-based baseline** (Milestone 3A).
- Skills not in the curated dictionary are missed in description-only detection.
- Ambiguous short tokens (C, R, Go) may have residual false positives from tags.
- jobUploaded provides only ~10 days of relative posting age — no historical calendar dates.
- A pretrained transformer-based semantic matcher (Milestone 3B) can later complement this baseline.
