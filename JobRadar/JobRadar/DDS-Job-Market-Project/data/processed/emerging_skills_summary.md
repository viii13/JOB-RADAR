# Hiring Momentum & Salary Premium Index Report

## Overview

This analysis evaluates skill demand momentum using cross-sectional indicators from the 2025 dataset.
**Important Methodology Note:** Because historical multi-period logs were unavailable in this dataset,
this score represents a **cross-sectional hiring urgency and wage premium proxy**, NOT longitudinal trend forecasting.

- Skills evaluated ($\ge 30$ postings): 104
- Top momentum tier: 4 skills
- Moderate momentum tier: 76 skills
- Low / Stable tier: 24 skills

## Top 20 Skills by Momentum Index

| Rank | Skill | Category | Total Jobs | Recent Jobs | Recency Share | Median Salary (INR) | Salary Ratio | Momentum Index | Tier |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | PyTorch | Data/ML | 393 | 137 | 34.9% | ₹2,250,000 | 5.29x | 78.3 | High Momentum |
| 2 | Golang | Programming Language | 325 | 107 | 32.9% | ₹2,250,000 | 5.29x | 74.1 | High Momentum |
| 3 | TensorFlow | Data/ML | 482 | 176 | 36.5% | ₹1,837,500 | 4.32x | 73.5 | High Momentum |
| 4 | NLP | Data/ML | 635 | 204 | 32.1% | ₹2,250,000 | 5.29x | 72.3 | High Momentum |
| 5 | Hibernate | Framework | 1,268 | 435 | 34.3% | ₹1,875,000 | 4.41x | 69.4 | Moderate Momentum |
| 6 | TypeScript | Programming Language | 886 | 325 | 36.7% | ₹1,600,000 | 3.76x | 69.0 | Moderate Momentum |
| 7 | Machine Learning | Data/ML | 2,127 | 736 | 34.6% | ₹1,800,000 | 4.24x | 68.5 | Moderate Momentum |
| 8 | Spring Boot | Framework | 1,924 | 642 | 33.4% | ₹1,875,000 | 4.41x | 67.4 | Moderate Momentum |
| 9 | Data Science | Data/ML | 881 | 335 | 38.0% | ₹1,250,000 | 2.94x | 64.8 | Moderate Momentum |
| 10 | Node.js | Framework | 976 | 352 | 36.1% | ₹1,450,000 | 3.41x | 64.6 | Moderate Momentum |
| 11 | Spring | Framework | 1,982 | 635 | 32.0% | ₹1,875,000 | 4.41x | 64.4 | Moderate Momentum |
| 12 | Agile | Other | 5,324 | 1,680 | 31.6% | ₹1,875,000 | 4.41x | 63.4 | Moderate Momentum |
| 13 | AWS | Cloud | 4,275 | 1,301 | 30.4% | ₹1,950,000 | 4.59x | 62.4 | Moderate Momentum |
| 14 | Docker | DevOps | 1,788 | 550 | 30.8% | ₹1,900,000 | 4.47x | 62.1 | Moderate Momentum |
| 15 | Terraform | DevOps | 797 | 245 | 30.7% | ₹1,900,000 | 4.47x | 62.1 | Moderate Momentum |
| 16 | Microservices | Web | 2,512 | 776 | 30.9% | ₹1,875,000 | 4.41x | 61.9 | Moderate Momentum |
| 17 | HR | Other | 432 | 193 | 44.7% | ₹300,000 | 0.71x | 60.0 | Moderate Momentum |
| 18 | Microsoft Azure | Cloud | 4,206 | 1,261 | 30.0% | ₹1,875,000 | 4.41x | 59.9 | Moderate Momentum |
| 19 | Flask | Framework | 324 | 102 | 31.5% | ₹1,700,000 | 4.00x | 59.6 | Moderate Momentum |
| 20 | AI | Data/ML | 2,524 | 886 | 35.1% | ₹1,300,000 | 3.06x | 59.4 | Moderate Momentum |

## Methodology & Component Weights

- **Demand Measurement:** Unique job postings (`nunique(jobId)`). No job's skill is double-counted.
- **Recency Share (60% weight):** Proportion of postings uploaded $\le 3$ days ago (*'Just Now'*, *'Today'*, *'1-3 Days Ago'*).
- **Salary Premium Ratio (40% weight):** Skill median midpoint salary relative to dataset benchmark (₹425,000 INR). Required $\ge 10$ salary samples.
- **Missing Salary Handling:** When salary data points are insufficient (< 10), index score relies 100% on recency share without inventing fake salaries.

## Limitations

- Relies on relative posting tags spanning a ~10-day scrape snapshot.
- Only ~34% of postings report structured salaries; salary ratios reflect disclosed packages only.
- A longitudinal comparison (e.g. against a 2026 dataset) will provide true year-over-year growth velocity.
