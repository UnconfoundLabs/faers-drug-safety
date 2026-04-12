"""
FAERS Drug Safety Pipeline — Step 03: Extract Drug Class Cohorts
Identifies ADHD meds, antidepressants, and GLP-1 agonists in the FAERS data
and creates cohort tables for analysis.
"""

import os
import duckdb

DB_PATH = os.path.expanduser("~/faers-drug-safety/data/db/faers.duckdb")

# ── Drug class definitions ───────────────────────────────────────────────────
# Using both brand and generic names (FAERS drugname field is inconsistent)

DRUG_CLASSES = {
    "ADHD": {
        "generic": [
            "METHYLPHENIDATE", "AMPHETAMINE", "DEXTROAMPHETAMINE",
            "LISDEXAMFETAMINE", "ATOMOXETINE", "GUANFACINE",
            "CLONIDINE",  # also used for ADHD
        ],
        "brand": [
            "RITALIN", "CONCERTA", "FOCALIN", "DAYTRANA", "QUILLIVANT",
            "ADDERALL", "VYVANSE", "DEXEDRINE",
            "STRATTERA", "QELBREE",  # viloxazine
            "INTUNIV", "KAPVAY", "TENEX",
            "JORNAY", "APTENSIO", "COTEMPLA", "AZSTARYS",
        ],
    },
    "ANTIDEPRESSANT": {
        "generic": [
            # SSRIs
            "SERTRALINE", "FLUOXETINE", "ESCITALOPRAM", "CITALOPRAM",
            "PAROXETINE", "FLUVOXAMINE",
            # SNRIs
            "VENLAFAXINE", "DULOXETINE", "DESVENLAFAXINE", "LEVOMILNACIPRAN",
            # Others
            "BUPROPION", "MIRTAZAPINE", "TRAZODONE", "NEFAZODONE",
            "VILAZODONE", "VORTIOXETINE",
            # TCAs (common ones)
            "AMITRIPTYLINE", "NORTRIPTYLINE", "IMIPRAMINE", "DESIPRAMINE",
            "CLOMIPRAMINE", "DOXEPIN",
        ],
        "brand": [
            "ZOLOFT", "PROZAC", "LEXAPRO", "CELEXA", "PAXIL", "LUVOX",
            "EFFEXOR", "CYMBALTA", "PRISTIQ", "FETZIMA",
            "WELLBUTRIN", "ZYBAN", "REMERON", "DESYREL", "OLEPTRO",
            "VIIBRYD", "TRINTELLIX", "BRINTELLIX",
            "ELAVIL", "PAMELOR", "TOFRANIL", "ANAFRANIL",
        ],
    },
    "GLP1": {
        "generic": [
            "SEMAGLUTIDE", "LIRAGLUTIDE", "TIRZEPATIDE", "DULAGLUTIDE",
            "EXENATIDE", "LIXISENATIDE",
        ],
        "brand": [
            "OZEMPIC", "WEGOVY", "RYBELSUS",
            "VICTOZA", "SAXENDA",
            "MOUNJARO", "ZEPBOUND",
            "TRULICITY",
            "BYETTA", "BYDUREON",
            "ADLYXIN", "SOLIQUA",
        ],
    },
}


def build_match_clause(drug_class: dict) -> str:
    """Build a SQL LIKE/IN clause for matching drug names."""
    conditions = []

    # Exact matches for generic names (with wildcards for salt forms)
    for name in drug_class["generic"]:
        conditions.append(f"UPPER(drugname) LIKE '%{name}%'")

    # Exact matches for brand names
    for name in drug_class["brand"]:
        conditions.append(f"UPPER(drugname) LIKE '%{name}%'")

    # Also check prod_ai (active ingredient field — cleaner)
    for name in drug_class["generic"]:
        conditions.append(f"UPPER(COALESCE(prod_ai, '')) LIKE '%{name}%'")

    return " OR ".join(conditions)


def main():
    print("=" * 60)
    print("FAERS Cohort Extraction — Step 03")
    print("=" * 60)

    con = duckdb.connect(DB_PATH)

    for class_name, drug_dict in DRUG_CLASSES.items():
        print(f"\n── {class_name} ──")

        match_clause = build_match_clause(drug_dict)

        # Step 1: Find all drug records matching this class (primary suspect only)
        con.execute(f"""
            CREATE OR REPLACE TABLE cohort_{class_name.lower()}_drugs AS
            SELECT
                d.primaryid,
                d.caseid,
                d.drug_seq,
                d.drugname,
                d.prod_ai,
                d.role_cod,
                d.route,
                d.dose_amt,
                d.dose_unit,
                '{class_name}' AS drug_class
            FROM drug d
            WHERE d.role_cod = 'PS'
              AND ({match_clause})
        """)

        drug_count = con.execute(
            f"SELECT COUNT(*) FROM cohort_{class_name.lower()}_drugs"
        ).fetchone()[0]
        case_count = con.execute(
            f"SELECT COUNT(DISTINCT primaryid) FROM cohort_{class_name.lower()}_drugs"
        ).fetchone()[0]
        print(f"  Drug records: {drug_count:,}  |  Unique cases: {case_count:,}")

        # Show top drugs in this class
        print(f"  Top drugs matched:")
        top = con.execute(f"""
            SELECT UPPER(drugname) AS drug, COUNT(DISTINCT primaryid) AS n
            FROM cohort_{class_name.lower()}_drugs
            GROUP BY UPPER(drugname)
            ORDER BY n DESC
            LIMIT 10
        """).fetchall()
        for drug, n in top:
            print(f"    {drug:40s} {n:>6,}")

    # Step 2: Create unified cohort with demographics and reactions
    print("\n── Building unified cohort table ──")

    con.execute("""
        CREATE OR REPLACE TABLE cohort_all AS
        WITH drug_cases AS (
            SELECT primaryid, drug_class, drugname, prod_ai, route
            FROM cohort_adhd_drugs
            UNION ALL
            SELECT primaryid, drug_class, drugname, prod_ai, route
            FROM cohort_antidepressant_drugs
            UNION ALL
            SELECT primaryid, drug_class, drugname, prod_ai, route
            FROM cohort_glp1_drugs
        )
        SELECT
            dc.primaryid,
            dc.drug_class,
            dc.drugname,
            dc.prod_ai,
            dc.route,
            de.age,
            de.age_cod,
            de.sex,
            de.wt,
            de.wt_cod,
            de.reporter_country,
            de.occr_country,
            de.event_dt,
            de.fda_dt,
            de.occp_cod,
            de.i_f_code,
            de.source_quarter
        FROM drug_cases dc
        INNER JOIN demo de ON dc.primaryid = de.primaryid
    """)

    total = con.execute("SELECT COUNT(*) FROM cohort_all").fetchone()[0]
    print(f"  Total cohort records: {total:,}")

    # Step 3: Create cohort reactions table
    con.execute("""
        CREATE OR REPLACE TABLE cohort_reactions AS
        SELECT
            ca.primaryid,
            ca.drug_class,
            ca.drugname,
            r.pt AS reaction,
            ca.sex,
            ca.age,
            ca.age_cod
        FROM cohort_all ca
        INNER JOIN reac r ON ca.primaryid = r.primaryid
    """)

    rxn_count = con.execute("SELECT COUNT(*) FROM cohort_reactions").fetchone()[0]
    print(f"  Total cohort reactions: {rxn_count:,}")

    # Step 4: Create cohort outcomes table
    con.execute("""
        CREATE OR REPLACE TABLE cohort_outcomes AS
        SELECT
            ca.primaryid,
            ca.drug_class,
            ca.drugname,
            o.outc_cod,
            ca.sex,
            ca.age,
            ca.age_cod
        FROM cohort_all ca
        INNER JOIN outc o ON ca.primaryid = o.primaryid
    """)

    out_count = con.execute("SELECT COUNT(*) FROM cohort_outcomes").fetchone()[0]
    print(f"  Total cohort outcomes: {out_count:,}")

    # ── Summary by class ──
    print("\n" + "=" * 60)
    print("COHORT SUMMARY")
    print("=" * 60)

    summary = con.execute("""
        SELECT
            drug_class,
            COUNT(DISTINCT primaryid) AS cases,
            COUNT(*) AS records
        FROM cohort_all
        GROUP BY drug_class
        ORDER BY cases DESC
    """).fetchall()

    for cls, cases, records in summary:
        print(f"  {cls:20s}  {cases:>8,} cases  ({records:>8,} records)")

    # Top reactions per class
    for cls in ["ADHD", "ANTIDEPRESSANT", "GLP1"]:
        print(f"\n  Top 10 adverse reactions — {cls}:")
        top_rxn = con.execute(f"""
            SELECT reaction, COUNT(DISTINCT primaryid) AS n
            FROM cohort_reactions
            WHERE drug_class = '{cls}'
            GROUP BY reaction
            ORDER BY n DESC
            LIMIT 10
        """).fetchall()
        for rxn, n in top_rxn:
            print(f"    {rxn:45s} {n:>6,}")

    # Outcome severity
    print("\n  Serious outcomes by class:")
    print(f"  {'Class':20s} {'Death':>8s} {'Hosp':>8s} {'Life-thr':>8s} {'Disabl':>8s}")
    for cls in ["ADHD", "ANTIDEPRESSANT", "GLP1"]:
        outcomes = con.execute(f"""
            SELECT
                SUM(CASE WHEN outc_cod = 'DE' THEN 1 ELSE 0 END) AS death,
                SUM(CASE WHEN outc_cod = 'HO' THEN 1 ELSE 0 END) AS hosp,
                SUM(CASE WHEN outc_cod = 'LT' THEN 1 ELSE 0 END) AS life_thr,
                SUM(CASE WHEN outc_cod = 'DS' THEN 1 ELSE 0 END) AS disabl
            FROM cohort_outcomes
            WHERE drug_class = '{cls}'
        """).fetchone()
        print(f"  {cls:20s} {outcomes[0]:>8,} {outcomes[1]:>8,} "
              f"{outcomes[2]:>8,} {outcomes[3]:>8,}")

    con.close()
    print("\n" + "=" * 60)
    print("Cohort extraction complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
