# Cleaning Audit Report

## Row counts

- Rows before cleaning: 97,929
- Rows after cleaning: 97,682
- Verified exact duplicate rows removed: 247

## Duplicate jobId conflicts retained

- Conflicting jobId groups: 3
- Rows retained for review: 6

## Missing values after cleaning

- jobDescription_missing: 14
- tagsAndSkills_missing: 571
- experience_source_missing: 2,102

## Salary status counts

- not_disclosed: 63,920
- valid: 33,138
- missing_bounds: 571
- zero_unknown: 45
- incomplete_range: 8

## Experience status counts

- valid_numeric: 97,111
- missing_or_unparseable: 571

## Columns added

- duplicate_jobid_conflict
- title_clean
- jobDescription_clean
- jobDescription_missing
- tagsAndSkills_clean
- tagsAndSkills_missing
- location_clean
- companyName_clean
- salary_status
- salary_range_invalid
- minimumSalary_clean
- maximumSalary_clean
- experience_status
- experience_range_invalid
- minimumExperience_clean
- maximumExperience_clean

## Important decisions

- All original source columns are preserved in the cleaned dataset.
- Only exact full-row duplicates are removed; conflicting jobId records are retained and flagged.
- Salary 0-0 and 'Not disclosed' are unavailable values, not zero salary.
- jobUploaded is preserved exactly; no historical dates are created from relative labels.
