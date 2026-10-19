# FAERS Drug Safety Analysis

A reproducible pharmacovigilance pipeline that loads FDA adverse event reports into DuckDB and screens three drug classes (GLP-1 agonists, antidepressants, ADHD medications) for disproportionate reporting.

## Question

Across two quarters of FDA adverse event reports, which adverse events are reported disproportionately often for GLP-1 agonists, antidepressants, and ADHD medications compared with all other drugs, and which of those signals hold up once you look at how the reports were generated?

## Data source

- [FDA Adverse Event Reporting System (FAERS) Quarterly Data Extracts](https://fis.fda.gov/extensions/FPD-QDE-FAERS/FPD-QDE-FAERS.html), ASCII format, **2024 Q3 and Q4**.
- Public, de-identified spontaneous reports. Tables used: DEMO, DRUG, REAC, OUTC, RPSR, THER, INDI.
- After deduplication: **784,523 unique cases** across all drugs.

## Methods

**Pipeline (Python + SQL in DuckDB)**

```
scripts/
  01_download.py          # Download and unzip FAERS quarterly ASCII extracts from FDA
  02_load_duckdb.py       # Load $-delimited files, union quarters, deduplicate
  03_extract_cohorts.py   # Define drug-class cohorts; build case, reaction, outcome tables
  04_analysis.py          # PRR/ROR with 95% CIs, chi-square, demographic breakdowns -> CSV
  05_visualize.py         # 9 figures from the CSV tables (+ one read from DuckDB)
```

- **Deduplication:** one row per `caseid`, keeping the highest `caseversion`; all other tables are filtered to the retained `primaryid`s.
- **Cohort definition:** a case belongs to a class when a **primary suspect** (`role_cod = 'PS'`) drug matches a list of generic and brand names, using substring matching on `drugname` and `prod_ai`. The lists are in `scripts/03_extract_cohorts.py`.
- **Disproportionality:** case-level 2x2 tables for each class x MedDRA preferred term, compared against every other case in the database.
  - PRR = [a/(a+b)] / [c/(c+d)], ROR = (ad)/(bc), each with a log-scale 95% CI.
  - Chi-square with Yates continuity correction.
  - **Signal criteria:** PRR ≥ 2, χ² ≥ 4, a ≥ 3, and lower 95% CI of PRR > 1.
- **Descriptives:** age group, sex, serious outcome code, and reporter occupation by class.
- **Case-level review of top signals.** A large PRR is where review starts, not a finding on its own. For example, the ADHD cardiac valve disease signal (57 reports, PRR 80.5) traced back to literature-stimulated batch reporting. See [the ADHD data story](paper/03_adhd_data_story.md).

**Stack:** Python · DuckDB · pandas · NumPy · SciPy · matplotlib · seaborn

## How to run

The scripts use hard-coded paths under `~/faers-drug-safety/`. Clone the repo into your home directory, or edit the `*_DIR` / `DB_PATH` constants at the top of each script.

```bash
cd ~
git clone https://github.com/UnconfoundLabs/faers-drug-safety.git
cd faers-drug-safety
pip install requests tqdm duckdb pandas numpy scipy matplotlib seaborn

python scripts/01_download.py         # -> data/raw/2024Q3, data/raw/2024Q4 (zips deleted after extract)
python scripts/02_load_duckdb.py      # -> data/db/faers.duckdb (rebuilt from scratch on each run)
python scripts/03_extract_cohorts.py  # -> cohort_* tables in DuckDB
python scripts/04_analysis.py         # -> output/tables/*.csv
python scripts/05_visualize.py        # -> output/figures/*.png
```

To add quarters, edit `QUARTERS` in both `01_download.py` and `02_load_duckdb.py`. `data/` and `*.duckdb` are git-ignored; `output/` is committed.

> TODO (Hannah): add a pinned `requirements.txt` (or `pyproject.toml`) and the Python version you ran this on. The code needs Python ≥ 3.10.

## Key results

From `output/tables/` (FAERS 2024 Q3–Q4; counts are reports, not patients or incidence):

| Class | Cases | Signals meeting criteria | Example signals (MedDRA PT, n, PRR) |
|---|---:|---:|---|
| **GLP-1 agonists** | 30,271 | 214 | Impaired gastric emptying (n = 733, PRR 55.3) |
| **Antidepressants** | 10,145 | 665 | Sexual dysfunction (157, 72.6); genital anaesthesia (18, 458.0); anorgasmia (59, 75.1) |
| **ADHD medications** | 3,273 | 267 | Product substitution issue (237, 44.0); cardiac valve disease (57, 80.5; literature-stimulated, see above) |

- **Consumers file most reports:** 86% of GLP-1 reports (26,018 / 30,271) come from consumers.
- **Access problems show up as "adverse events":** the 2nd and 3rd most frequent ADHD events are product substitution and product availability issues.

Full write-ups:

- [Overview: Three Drug Classes, Three Crises](paper/00_overview.md)
- [The GLP-1 Boom and Its Side Effects](paper/01_glp1_data_story.md)
- [The Side Effects No One Talks About: Antidepressants](paper/02_antidepressant_data_story.md)
- [Can't Get the Meds: The ADHD Medication Crisis](paper/03_adhd_data_story.md)

### Figures (`output/figures/`)

| # | Figure |
|---|---|
| 01 | Report volume by drug class |
| 02 | Sex distribution |
| 03 | Age profile |
| 04 | Top 10 adverse events per class (small multiples) |
| 05 | Safety signals: ROR with 95% CI |
| 06 | Serious outcome profile |
| 07 | GLP-1 products driving report volume |
| 08 | Reporter type (consumer vs. professional) |
| 09 | Top signals by count, artifacts excluded |

## Limitations

- **Spontaneous reports measure reporting, not risk.** FAERS can't establish causation or give incidence; there is no exposure denominator.
- **Stimulated and batch reporting.** Media attention, litigation, and published studies (which trigger manufacturer literature reviews) can inflate PRRs. The ADHD cardiac valve signal is a worked example.
- **Confounding by indication.** Depression itself is associated with suicidality, fatigue, and sexual dysfunction, for example.
- **Deduplication is partial.** Only the latest `caseversion` per `caseid` is kept. FDA's published deleted-case lists are not applied, and no fuzzy matching is done across `caseid`s.
- **Name-based cohort matching.** Substring matching on free-text drug names can over-include, e.g. `AMPHETAMINE` also matches methamphetamine products. Clonidine and guanfacine are in the ADHD class even though they are often prescribed for hypertension. Only primary-suspect drugs define exposure.
- **Comparator choice.** The background is every other case in the database, which includes cases where a class drug was a secondary suspect or concomitant drug.
- **Short window.** Two quarters only, so no trend analysis.
- **Multiple testing.** Thousands of PT-level tests use frequentist thresholds with no multiplicity adjustment and no Bayesian shrinkage (e.g. EBGM/IC).

> TODO (Hannah): decide whether to note any planned extensions here (more quarters, EBGM/BCPNN, deleted-case handling), or leave them out.

## Author

Hannah Choi · [Unconfound Labs](https://github.com/UnconfoundLabs)
