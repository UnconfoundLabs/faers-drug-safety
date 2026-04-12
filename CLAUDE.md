# FAERS Drug Safety Analysis

## Project Overview
Full data pipeline analyzing FDA Adverse Event Reporting System (FAERS) data for three drug classes: ADHD medications, antidepressants, and GLP-1 receptor agonists.

## Stack
- **Python** — ingestion, ETL, analysis
- **SQL** — analytical queries via DuckDB
- **DuckDB** — embedded analytical database (no server)
- **Plotly/seaborn** — visualizations

## Pipeline
1. `scripts/01_download.py` — Download + unzip FAERS quarterly ASCII files
2. `scripts/02_load_duckdb.py` — Load into DuckDB, deduplicate, create clean tables
3. `scripts/03_extract_cohorts.py` — Filter to drug class cohorts (ADHD, antidepressants, GLP-1)
4. `scripts/04_analysis.py` — Disproportionality analysis (PRR, ROR), descriptive stats
5. `scripts/05_visualize.py` — Publication-quality figures

## Data
- Source: [FDA FAERS](https://fis.fda.gov/extensions/FPD-QDE-FAERS/FPD-QDE-FAERS.html)
- Format: $ delimited ASCII files, 7 tables per quarter (DEMO, DRUG, REAC, OUTC, RPSR, THER, INDI)
- Deduplication: Group by caseid, keep max caseversion
- Quarters loaded: 2024 Q3, 2024 Q4

## Drug Classes
- **ADHD**: methylphenidate, amphetamine, lisdexamfetamine, atomoxetine, guanfacine
- **Antidepressants**: sertraline, fluoxetine, escitalopram, paroxetine, citalopram, venlafaxine, duloxetine, bupropion, mirtazapine
- **GLP-1 agonists**: semaglutide, liraglutide, tirzepatide, dulaglutide, exenatide

## Key Notes
- This project lives at `~/faers-drug-safety/` (local, NOT iCloud) to avoid path issues
- Disk space is limited (~5GB) — load to DuckDB then delete raw files
- FAERS is spontaneous reporting — cannot calculate incidence rates, only disproportionality signals
- role_cod = 'PS' means primary suspect drug
