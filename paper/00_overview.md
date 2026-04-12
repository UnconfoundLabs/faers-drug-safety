# Three Drug Classes, Three Crises: What FDA Adverse Event Data Reveals About GLP-1 Agonists, Antidepressants, and ADHD Medications

*A comparative analysis using the FDA Adverse Event Reporting System (FAERS), Q3–Q4 2024*

---

## Overview

We analyzed 784,523 deduplicated adverse event reports submitted to the FDA in Q3–Q4 2024, focusing on three drug classes with distinct patient populations, safety profiles, and systemic challenges:

| Drug Class | Reports | Top Signal | Key Theme |
|---|---|---|---|
| **GLP-1 Agonists** | 30,271 | Gastroparesis (PRR = 55) | Rapid adoption outpacing safety monitoring |
| **Antidepressants** | 10,145 | Sexual dysfunction (PRR = 458) | Undertreated side effects in a widely prescribed class |
| **ADHD Medications** | 3,273 | Supply/access issues (PRR = 44) | A system crisis masquerading as pharmacovigilance data |

Each class tells a different story — but together, they reveal common patterns in how drug safety monitoring works and where it fails.

---

## Common Findings

**Consumer reporting dominates.** Across all three classes, patients — not physicians — are the primary reporters. For GLP-1 agonists, 86% of reports come from consumers. Even for antidepressants, where physician involvement is highest, consumers still account for 49%. The FDA's safety surveillance system is increasingly a patient-driven enterprise.

**Women report more.** Female patients account for 62% of GLP-1 reports, 50% of antidepressant reports, and 34% of ADHD reports. This partly reflects prescribing patterns but also suggests differential exposure to side effects or differential willingness to report.

**Disproportionality signals cluster by mechanism.** GLP-1 signals are gastrointestinal (gastroparesis, nausea, obstruction). Antidepressant signals are neuropsychiatric (suicidality, sexual dysfunction, discontinuation). ADHD signals split between psychiatric effects (anxiety, aggression) and system failures (supply, affordability). The FAERS data correctly fingerprints each drug class's mechanism of action.

---

## The Data Stories

This analysis is organized as three standalone data stories:

1. **[The GLP-1 Boom and Its Side Effects](01_glp1_data_story.md)** — 30,000 reports, dosing errors, gastroparesis, and a consumer-driven safety signal
2. **[The Side Effects No One Talks About](02_antidepressant_data_story.md)** — Sexual dysfunction with PRR values of 458, discontinuation syndrome, and the highest serious outcome rate
3. **[Can't Get the Meds, Can't Afford the Meds](03_adhd_data_story.md)** — When 20% of adverse events aren't about the drug — they're about the system

---

## Pipeline

This analysis was built as a reproducible end-to-end data pipeline:

```
01_download.py      → Download FAERS quarterly ASCII files from FDA
02_load_duckdb.py   → Load into DuckDB, deduplicate by caseid/caseversion
03_extract_cohorts.py → Filter to drug class cohorts by generic/brand name
04_analysis.py      → PRR/ROR disproportionality analysis, demographics, chi-square tests
05_visualize.py     → Publication-quality figures (matplotlib/seaborn)
```

**Stack:** Python, SQL, DuckDB, pandas, scipy, matplotlib, seaborn.

**Data:** [FDA FAERS Quarterly Data Extracts](https://fis.fda.gov/extensions/FPD-QDE-FAERS/FPD-QDE-FAERS.html), Q3–Q4 2024.

---

*Author: Hannah Choi*
