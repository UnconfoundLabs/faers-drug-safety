# FAERS Drug Safety Analysis

Comparative pharmacovigilance analysis of three drug classes using FDA Adverse Event Reporting System (FAERS) data from Q3–Q4 2024.

## Drug Classes

| Class | Cases | Key Finding |
|---|---|---|
| **GLP-1 Agonists** | 30,271 | Gastroparesis signal (PRR=55), dosing errors as #1 event |
| **Antidepressants** | 10,145 | Sexual dysfunction (PRR=458), highest serious outcome rate |
| **ADHD Medications** | 3,273 | Supply/affordability crisis visible in safety data |

## Data Stories

- [Overview: Three Drug Classes, Three Crises](paper/00_overview.md)
- [The GLP-1 Boom and Its Side Effects](paper/01_glp1_data_story.md)
- [The Side Effects No One Talks About: Antidepressants](paper/02_antidepressant_data_story.md)
- [Can't Get the Meds: The ADHD Medication Crisis](paper/03_adhd_data_story.md)

## Pipeline

End-to-end reproducible pipeline: download → DuckDB → cohort extraction → disproportionality analysis → visualization.

```
scripts/
  01_download.py          # Download FAERS quarterly ASCII files
  02_load_duckdb.py       # Load into DuckDB, deduplicate
  03_extract_cohorts.py   # Filter to drug class cohorts
  04_analysis.py          # PRR/ROR, demographics, chi-square
  05_visualize.py         # 9 publication-quality figures
```

## Key Figures

| Figure | Description |
|---|---|
| 01 | Adverse event report volume by drug class |
| 02 | Sex distribution of reporters |
| 03 | Age profile of reports |
| 04 | Top 10 adverse events per class (small multiples) |
| 05 | Safety signals: Reporting Odds Ratio with 95% CI |
| 06 | Serious outcome profile |
| 07 | GLP-1 drugs: which products drive volume |
| 08 | Reporter type (consumer vs. physician) |
| 09 | Top signals by count, artifacts excluded |

## Methods

- **Disproportionality analysis:** PRR and ROR from 2×2 contingency tables
- **Signal criteria:** PRR ≥ 2, χ² ≥ 4, n ≥ 3, lower 95% CI of PRR > 1
- **Deduplication:** Latest case version retained per caseid
- **Database:** 784,523 unique cases across all drugs

## Stack

Python 3.14 · DuckDB · pandas · scipy · matplotlib · seaborn

## Data Source

[FDA FAERS Quarterly Data Extracts](https://fis.fda.gov/extensions/FPD-QDE-FAERS/FPD-QDE-FAERS.html)

## Author

Hannah Choi
