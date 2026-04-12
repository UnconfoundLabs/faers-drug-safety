"""
FAERS Drug Safety Pipeline — Step 04: Disproportionality Analysis
Computes PRR (Proportional Reporting Ratio) and ROR (Reporting Odds Ratio)
for drug-adverse event pairs, plus demographic breakdowns.
"""

import os
import duckdb
import pandas as pd
import numpy as np
from scipy import stats

DB_PATH = os.path.expanduser("~/faers-drug-safety/data/db/faers.duckdb")
OUT_DIR = os.path.expanduser("~/faers-drug-safety/output/tables")
os.makedirs(OUT_DIR, exist_ok=True)


def compute_disproportionality(con: duckdb.DuckDBPyConnection):
    """
    Compute PRR and ROR for each drug_class × adverse_event pair.

    2x2 table:
                    Event+    Event-
    Drug+           a         b
    Drug-           c         d

    PRR = (a / (a+b)) / (c / (c+d))
    ROR = (a*d) / (b*c)
    """
    print("── Computing disproportionality signals ──")

    # Total unique cases in the full database (all drugs, not just cohort)
    total_cases = con.execute(
        "SELECT COUNT(DISTINCT primaryid) FROM demo"
    ).fetchone()[0]
    print(f"  Total cases in database: {total_cases:,}")

    # For each drug class, compute 2x2 table for each reaction
    for drug_class in ["ADHD", "ANTIDEPRESSANT", "GLP1"]:
        print(f"\n  Processing {drug_class}...")

        # Cases with this drug class (primary suspect)
        con.execute(f"""
            CREATE OR REPLACE TEMP TABLE _drug_cases AS
            SELECT DISTINCT primaryid
            FROM cohort_{drug_class.lower()}_drugs
        """)

        drug_n = con.execute("SELECT COUNT(*) FROM _drug_cases").fetchone()[0]

        # All reactions for this drug class
        con.execute(f"""
            CREATE OR REPLACE TEMP TABLE _drug_reactions AS
            SELECT DISTINCT primaryid, pt AS reaction
            FROM reac
            WHERE primaryid IN (SELECT primaryid FROM _drug_cases)
        """)

        # Count each reaction
        # a = cases with drug AND reaction
        # b = cases with drug but NOT reaction
        # c = cases without drug but WITH reaction
        # d = cases without drug and without reaction
        con.execute(f"""
            CREATE OR REPLACE TABLE signal_{drug_class.lower()} AS
            WITH reaction_counts AS (
                SELECT
                    reaction,
                    COUNT(DISTINCT primaryid) AS a
                FROM _drug_reactions
                GROUP BY reaction
                HAVING COUNT(DISTINCT primaryid) >= 3  -- minimum count filter
            ),
            background AS (
                SELECT
                    r.pt AS reaction,
                    COUNT(DISTINCT r.primaryid) AS total_with_event
                FROM reac r
                WHERE r.primaryid NOT IN (SELECT primaryid FROM _drug_cases)
                GROUP BY r.pt
            )
            SELECT
                '{drug_class}' AS drug_class,
                rc.reaction,
                rc.a,
                ({drug_n} - rc.a) AS b,
                COALESCE(bg.total_with_event, 0) AS c,
                ({total_cases} - {drug_n} - COALESCE(bg.total_with_event, 0)) AS d,
                {drug_n} AS drug_total,
                {total_cases} AS db_total
            FROM reaction_counts rc
            LEFT JOIN background bg ON rc.reaction = bg.reaction
            WHERE COALESCE(bg.total_with_event, 0) > 0
            ORDER BY rc.a DESC
        """)

        sig_count = con.execute(
            f"SELECT COUNT(*) FROM signal_{drug_class.lower()}"
        ).fetchone()[0]
        print(f"    {sig_count:,} reaction terms evaluated")

    # Now compute PRR and ROR in Python for proper CI calculation
    print("\n── Computing PRR, ROR, and confidence intervals ──")

    all_signals = []

    for drug_class in ["ADHD", "ANTIDEPRESSANT", "GLP1"]:
        df = con.execute(
            f"SELECT * FROM signal_{drug_class.lower()}"
        ).fetchdf()

        a = df["a"].values.astype(float)
        b = df["b"].values.astype(float)
        c = df["c"].values.astype(float)
        d = df["d"].values.astype(float)

        # PRR = (a/(a+b)) / (c/(c+d))
        prr = (a / (a + b)) / (c / (c + d))

        # ROR = (a*d) / (b*c)
        ror = (a * d) / (b * c)

        # 95% CI for log(ROR) — Gart's method
        log_ror = np.log(ror)
        se_log_ror = np.sqrt(1/a + 1/b + 1/c + 1/d)
        ror_lo = np.exp(log_ror - 1.96 * se_log_ror)
        ror_hi = np.exp(log_ror + 1.96 * se_log_ror)

        # 95% CI for log(PRR)
        log_prr = np.log(prr)
        se_log_prr = np.sqrt(1/a - 1/(a+b) + 1/c - 1/(c+d))
        prr_lo = np.exp(log_prr - 1.96 * se_log_prr)
        prr_hi = np.exp(log_prr + 1.96 * se_log_prr)

        # Chi-square test
        chi2_vals = []
        p_vals = []
        for i in range(len(df)):
            table = np.array([[a[i], b[i]], [c[i], d[i]]])
            try:
                chi2, p, _, _ = stats.chi2_contingency(table, correction=True)
                chi2_vals.append(chi2)
                p_vals.append(p)
            except:
                chi2_vals.append(np.nan)
                p_vals.append(np.nan)

        df["prr"] = prr
        df["prr_lo"] = prr_lo
        df["prr_hi"] = prr_hi
        df["ror"] = ror
        df["ror_lo"] = ror_lo
        df["ror_hi"] = ror_hi
        df["chi2"] = chi2_vals
        df["p_value"] = p_vals

        # Signal criteria: PRR >= 2, chi2 >= 4, a >= 3, PRR_lo > 1
        df["is_signal"] = (
            (df["prr"] >= 2) &
            (df["chi2"] >= 4) &
            (df["a"] >= 3) &
            (df["prr_lo"] > 1)
        )

        all_signals.append(df)

        # Print top signals
        signals = df[df["is_signal"]].sort_values("prr", ascending=False)
        print(f"\n  {drug_class} — {len(signals)} signals detected (PRR≥2, χ²≥4, n≥3, PRR_lo>1)")
        print(f"  Top 15 signals:")
        print(f"  {'Reaction':<45s} {'N':>6s} {'PRR':>7s} {'ROR':>7s} {'p-value':>10s}")
        print(f"  {'-'*45} {'-'*6} {'-'*7} {'-'*7} {'-'*10}")
        for _, row in signals.head(15).iterrows():
            print(f"  {row['reaction']:<45s} {int(row['a']):>6d} "
                  f"{row['prr']:>7.1f} {row['ror']:>7.1f} "
                  f"{row['p_value']:>10.2e}")

    # Combine and save
    all_df = pd.concat(all_signals, ignore_index=True)
    all_df.to_csv(os.path.join(OUT_DIR, "disproportionality_signals.csv"), index=False)
    print(f"\n  Saved all signals: disproportionality_signals.csv ({len(all_df):,} rows)")

    # Save signals only
    signals_only = all_df[all_df["is_signal"]].sort_values(
        ["drug_class", "prr"], ascending=[True, False]
    )
    signals_only.to_csv(os.path.join(OUT_DIR, "confirmed_signals.csv"), index=False)
    print(f"  Saved confirmed signals: confirmed_signals.csv ({len(signals_only):,} rows)")

    return all_df


def demographic_analysis(con: duckdb.DuckDBPyConnection):
    """Analyze adverse events by demographics within each drug class."""
    print("\n\n── Demographic Analysis ──")

    # Age distribution
    print("\n  Age distribution by drug class:")
    age_df = con.execute("""
        SELECT
            drug_class,
            CASE
                WHEN age_cod IN ('YR', 'YEAR') AND CAST(age AS FLOAT) < 18 THEN '<18'
                WHEN age_cod IN ('YR', 'YEAR') AND CAST(age AS FLOAT) BETWEEN 18 AND 34 THEN '18-34'
                WHEN age_cod IN ('YR', 'YEAR') AND CAST(age AS FLOAT) BETWEEN 35 AND 49 THEN '35-49'
                WHEN age_cod IN ('YR', 'YEAR') AND CAST(age AS FLOAT) BETWEEN 50 AND 64 THEN '50-64'
                WHEN age_cod IN ('YR', 'YEAR') AND CAST(age AS FLOAT) >= 65 THEN '65+'
                ELSE 'Unknown'
            END AS age_group,
            COUNT(DISTINCT primaryid) AS n
        FROM cohort_all
        WHERE TRY_CAST(age AS FLOAT) IS NOT NULL OR age IS NULL
        GROUP BY drug_class, age_group
        ORDER BY drug_class, age_group
    """).fetchdf()

    age_df.to_csv(os.path.join(OUT_DIR, "demographics_age.csv"), index=False)

    # Pivot for display
    age_pivot = age_df.pivot_table(
        index="age_group", columns="drug_class", values="n", fill_value=0
    )
    print(age_pivot.to_string())

    # Sex distribution
    print("\n  Sex distribution by drug class:")
    sex_df = con.execute("""
        SELECT
            drug_class,
            CASE
                WHEN sex = 'F' THEN 'Female'
                WHEN sex = 'M' THEN 'Male'
                ELSE 'Unknown'
            END AS sex,
            COUNT(DISTINCT primaryid) AS n
        FROM cohort_all
        GROUP BY drug_class, sex
        ORDER BY drug_class, sex
    """).fetchdf()

    sex_df.to_csv(os.path.join(OUT_DIR, "demographics_sex.csv"), index=False)

    sex_pivot = sex_df.pivot_table(
        index="sex", columns="drug_class", values="n", fill_value=0
    )
    print(sex_pivot.to_string())

    # Top reactions by sex within each class
    print("\n  Sex differences in top reactions:")
    for drug_class in ["ADHD", "ANTIDEPRESSANT", "GLP1"]:
        sex_rxn = con.execute(f"""
            SELECT
                sex,
                reaction,
                COUNT(DISTINCT primaryid) AS n
            FROM cohort_reactions
            WHERE drug_class = '{drug_class}'
              AND sex IN ('M', 'F')
            GROUP BY sex, reaction
            HAVING COUNT(DISTINCT primaryid) >= 5
            ORDER BY sex, n DESC
        """).fetchdf()

        sex_rxn.to_csv(
            os.path.join(OUT_DIR, f"reactions_by_sex_{drug_class.lower()}.csv"),
            index=False
        )

    # Outcome severity by drug class
    print("\n  Outcome distribution:")
    outcome_df = con.execute("""
        SELECT
            drug_class,
            CASE outc_cod
                WHEN 'DE' THEN 'Death'
                WHEN 'HO' THEN 'Hospitalization'
                WHEN 'LT' THEN 'Life-threatening'
                WHEN 'DS' THEN 'Disability'
                WHEN 'CA' THEN 'Congenital anomaly'
                WHEN 'RI' THEN 'Required intervention'
                WHEN 'OT' THEN 'Other serious'
                ELSE outc_cod
            END AS outcome,
            COUNT(DISTINCT primaryid) AS n
        FROM cohort_outcomes
        GROUP BY drug_class, outcome
        ORDER BY drug_class, n DESC
    """).fetchdf()

    outcome_df.to_csv(os.path.join(OUT_DIR, "outcomes_by_class.csv"), index=False)
    outcome_pivot = outcome_df.pivot_table(
        index="outcome", columns="drug_class", values="n", fill_value=0
    )
    print(outcome_pivot.to_string())

    # Reporter type
    print("\n  Reporter type:")
    reporter_df = con.execute("""
        SELECT
            drug_class,
            CASE occp_cod
                WHEN 'MD' THEN 'Physician'
                WHEN 'PH' THEN 'Pharmacist'
                WHEN 'HP' THEN 'Other health professional'
                WHEN 'CN' THEN 'Consumer'
                WHEN 'LW' THEN 'Lawyer'
                WHEN 'OT' THEN 'Other'
                ELSE COALESCE(occp_cod, 'Unknown')
            END AS reporter,
            COUNT(DISTINCT primaryid) AS n
        FROM cohort_all
        GROUP BY drug_class, reporter
        ORDER BY drug_class, n DESC
    """).fetchdf()

    reporter_df.to_csv(os.path.join(OUT_DIR, "reporter_type.csv"), index=False)
    reporter_pivot = reporter_df.pivot_table(
        index="reporter", columns="drug_class", values="n", fill_value=0
    )
    print(reporter_pivot.to_string())

    return age_df, sex_df, outcome_df


def top_reactions_comparison(con: duckdb.DuckDBPyConnection):
    """Compare top reactions across the three drug classes."""
    print("\n\n── Cross-class Reaction Comparison ──")

    comparison = con.execute("""
        WITH ranked AS (
            SELECT
                drug_class,
                reaction,
                COUNT(DISTINCT primaryid) AS n,
                ROUND(COUNT(DISTINCT primaryid) * 100.0 /
                    SUM(COUNT(DISTINCT primaryid)) OVER (PARTITION BY drug_class), 2
                ) AS pct,
                ROW_NUMBER() OVER (
                    PARTITION BY drug_class ORDER BY COUNT(DISTINCT primaryid) DESC
                ) AS rank
            FROM cohort_reactions
            GROUP BY drug_class, reaction
        )
        SELECT drug_class, reaction, n, pct, rank
        FROM ranked
        WHERE rank <= 20
        ORDER BY drug_class, rank
    """).fetchdf()

    comparison.to_csv(os.path.join(OUT_DIR, "top_reactions_by_class.csv"), index=False)
    print(f"  Saved top_reactions_by_class.csv")

    # Reactions unique to each class (in top 20 of one but not top 50 of others)
    print("\n  Distinguishing reactions per class:")
    for cls in ["ADHD", "ANTIDEPRESSANT", "GLP1"]:
        top_this = set(comparison[comparison["drug_class"] == cls]["reaction"])
        top_50_others = set()
        for other in ["ADHD", "ANTIDEPRESSANT", "GLP1"]:
            if other == cls:
                continue
            other_top = con.execute(f"""
                SELECT reaction FROM (
                    SELECT reaction, COUNT(DISTINCT primaryid) AS n
                    FROM cohort_reactions
                    WHERE drug_class = '{other}'
                    GROUP BY reaction
                    ORDER BY n DESC
                    LIMIT 50
                )
            """).fetchdf()
            top_50_others.update(other_top["reaction"].tolist())

        unique = top_this - top_50_others
        if unique:
            print(f"    {cls}: {', '.join(sorted(unique))}")

    return comparison


def main():
    print("=" * 60)
    print("FAERS Analysis — Step 04")
    print("=" * 60)

    con = duckdb.connect(DB_PATH, read_only=False)

    # Disproportionality analysis
    signals_df = compute_disproportionality(con)

    # Demographics
    age_df, sex_df, outcome_df = demographic_analysis(con)

    # Cross-class comparison
    comparison = top_reactions_comparison(con)

    con.close()

    # File summary
    print("\n" + "=" * 60)
    print("OUTPUT FILES")
    print("=" * 60)
    for f in sorted(os.listdir(OUT_DIR)):
        if f.endswith(".csv"):
            size = os.path.getsize(os.path.join(OUT_DIR, f))
            rows = len(pd.read_csv(os.path.join(OUT_DIR, f)))
            print(f"  {f:50s} {rows:>6,} rows  ({size/1e3:.1f} KB)")

    print("\n" + "=" * 60)
    print("Analysis complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
