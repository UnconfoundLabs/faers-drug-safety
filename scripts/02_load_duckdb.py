"""
FAERS Drug Safety Pipeline — Step 02: Load into DuckDB
Reads FAERS quarterly ASCII files, loads into DuckDB, and deduplicates.
"""

import os
import glob
import duckdb

# ── Configuration ────────────────────────────────────────────────────────────
RAW_DIR = os.path.expanduser("~/faers-drug-safety/data/raw")
DB_PATH = os.path.expanduser("~/faers-drug-safety/data/db/faers.duckdb")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

QUARTERS = ["2024Q3", "2024Q4"]

# FAERS table definitions: table_prefix -> (key columns for schema hints)
TABLES = {
    "DEMO": "primaryid, caseid, caseversion, i_f_code, event_dt, mfr_dt, "
            "init_fda_dt, fda_dt, rept_cod, auth_num, mfr_num, mfr_sndr, "
            "lit_ref, age, age_cod, age_grp, sex, e_sub, wt, wt_cod, "
            "rept_dt, to_mfr, occp_cod, reporter_country, occr_country",
    "DRUG": "primaryid, caseid, drug_seq, role_cod, drugname, prod_ai, "
            "val_vbm, route, dose_vbm, cum_dose_chr, cum_dose_unit, "
            "dechal, rechal, lot_num, exp_dt, nda_num, dose_amt, "
            "dose_unit, dose_form, dose_freq",
    "REAC": "primaryid, caseid, pt, drug_rec_act",
    "OUTC": "primaryid, caseid, outc_cod",
    "RPSR": "primaryid, caseid, rpsr_cod",
    "THER": "primaryid, caseid, drug_seq, start_dt, end_dt, dur, dur_cod",
    "INDI": "primaryid, caseid, drug_seq, indi_pt",
}


def find_file(quarter: str, table: str) -> str | None:
    """Find the file for a given quarter and table."""
    q_short = quarter.replace("Q", "q")  # e.g., 2024q3
    q_dir = os.path.join(RAW_DIR, quarter)

    # Try common naming patterns
    patterns = [
        f"{table}{quarter[2:]}*",     # DEMO24Q3.txt
        f"{table.lower()}{quarter[2:]}*",
        f"{table}*",
    ]

    for pattern in patterns:
        matches = glob.glob(os.path.join(q_dir, pattern))
        txt_matches = [m for m in matches if m.endswith(".txt")]
        if txt_matches:
            return txt_matches[0]

    return None


def load_quarter(con: duckdb.DuckDBPyConnection, quarter: str):
    """Load all tables from one quarter into staging tables."""
    print(f"\n── Loading {quarter} ──")

    for table in TABLES:
        fpath = find_file(quarter, table)
        if not fpath:
            print(f"  WARNING: {table} not found for {quarter}")
            continue

        staging = f"stg_{table.lower()}_{quarter.lower().replace('q', '_q')}"
        print(f"  {table:6s} → {staging} ... ", end="", flush=True)

        try:
            con.execute(f"""
                CREATE OR REPLACE TABLE {staging} AS
                SELECT *, '{quarter}' AS source_quarter
                FROM read_csv('{fpath}',
                    delim='$',
                    header=true,
                    quote='',
                    all_varchar=true,
                    ignore_errors=true
                )
            """)
            count = con.execute(f"SELECT COUNT(*) FROM {staging}").fetchone()[0]
            print(f"{count:>10,} rows")
        except Exception as e:
            print(f"ERROR: {e}")


def union_tables(con: duckdb.DuckDBPyConnection):
    """Union all quarterly staging tables into combined raw tables."""
    print("\n── Combining quarters ──")

    for table in TABLES:
        raw_table = f"raw_{table.lower()}"

        # Find all staging tables for this type
        staging_tables = con.execute(f"""
            SELECT table_name FROM information_schema.tables
            WHERE table_name LIKE 'stg_{table.lower()}_%'
            ORDER BY table_name
        """).fetchall()

        if not staging_tables:
            print(f"  {table}: no staging tables found")
            continue

        # Get common columns across all staging tables
        col_sets = []
        for (stg,) in staging_tables:
            cols = con.execute(f"""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = '{stg}'
            """).fetchall()
            col_sets.append(set(c[0] for c in cols))

        common_cols = sorted(col_sets[0].intersection(*col_sets[1:]))
        col_list = ", ".join(f'"{c}"' for c in common_cols)

        union_parts = [
            f"SELECT {col_list} FROM {stg}" for (stg,) in staging_tables
        ]
        union_sql = " UNION ALL ".join(union_parts)

        con.execute(f"CREATE OR REPLACE TABLE {raw_table} AS {union_sql}")
        count = con.execute(f"SELECT COUNT(*) FROM {raw_table}").fetchone()[0]
        print(f"  {raw_table:20s} {count:>12,} rows")

        # Drop staging tables
        for (stg,) in staging_tables:
            con.execute(f"DROP TABLE {stg}")


def deduplicate(con: duckdb.DuckDBPyConnection):
    """
    Deduplicate: keep only the latest version of each case.
    In DEMO, group by caseid, keep max caseversion.
    Then filter all other tables to only those primaryids.
    """
    print("\n── Deduplicating ──")

    # Step 1: Find the latest version of each case
    con.execute("""
        CREATE OR REPLACE TABLE demo AS
        WITH ranked AS (
            SELECT *,
                ROW_NUMBER() OVER (
                    PARTITION BY caseid
                    ORDER BY CAST(caseversion AS INTEGER) DESC
                ) AS rn
            FROM raw_demo
        )
        SELECT * EXCLUDE (rn)
        FROM ranked
        WHERE rn = 1
    """)

    raw_count = con.execute("SELECT COUNT(*) FROM raw_demo").fetchone()[0]
    dedup_count = con.execute("SELECT COUNT(*) FROM demo").fetchone()[0]
    removed = raw_count - dedup_count
    print(f"  DEMO: {raw_count:,} → {dedup_count:,} ({removed:,} duplicates removed)")

    # Step 2: Filter other tables to valid primaryids
    for table in ["drug", "reac", "outc", "rpsr", "ther", "indi"]:
        raw_table = f"raw_{table}"
        if con.execute(f"""
            SELECT COUNT(*) FROM information_schema.tables
            WHERE table_name = '{raw_table}'
        """).fetchone()[0] == 0:
            continue

        con.execute(f"""
            CREATE OR REPLACE TABLE {table} AS
            SELECT r.*
            FROM {raw_table} r
            INNER JOIN demo d ON r.primaryid = d.primaryid
        """)
        raw_ct = con.execute(f"SELECT COUNT(*) FROM {raw_table}").fetchone()[0]
        new_ct = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table.upper():6s}: {raw_ct:>10,} → {new_ct:>10,}")

        # Drop raw table
        con.execute(f"DROP TABLE {raw_table}")

    # Drop raw_demo
    con.execute("DROP TABLE IF EXISTS raw_demo")


def print_summary(con: duckdb.DuckDBPyConnection):
    """Print summary of final tables."""
    print("\n" + "=" * 60)
    print("FINAL DATABASE SUMMARY")
    print("=" * 60)

    tables = con.execute("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'main'
          AND table_name NOT LIKE 'stg_%'
          AND table_name NOT LIKE 'raw_%'
        ORDER BY table_name
    """).fetchall()

    for (table,) in tables:
        count = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table:20s} {count:>12,} rows")

    # Quick stats
    print("\n── Quick Stats ──")

    # Date range
    date_range = con.execute("""
        SELECT MIN(fda_dt), MAX(fda_dt) FROM demo
        WHERE fda_dt IS NOT NULL AND LENGTH(fda_dt) = 8
    """).fetchone()
    print(f"  FDA date range: {date_range[0]} – {date_range[1]}")

    # Sex distribution
    print("  Sex distribution:")
    sex_dist = con.execute("""
        SELECT sex, COUNT(*) AS n,
               ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 1) AS pct
        FROM demo
        GROUP BY sex
        ORDER BY n DESC
    """).fetchall()
    for sex, n, pct in sex_dist:
        print(f"    {sex or 'NULL':10s} {n:>10,}  ({pct}%)")

    # Top 10 drugs
    print("  Top 10 reported drugs (primary suspect):")
    top_drugs = con.execute("""
        SELECT UPPER(drugname) AS drug, COUNT(DISTINCT primaryid) AS n
        FROM drug
        WHERE role_cod = 'PS'
        GROUP BY UPPER(drugname)
        ORDER BY n DESC
        LIMIT 10
    """).fetchall()
    for drug, n in top_drugs:
        print(f"    {drug:40s} {n:>8,}")


def main():
    print("=" * 60)
    print("FAERS DuckDB Loader — Step 02")
    print("=" * 60)

    # Remove existing DB to start fresh
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    con = duckdb.connect(DB_PATH)

    # Load each quarter
    for quarter in QUARTERS:
        load_quarter(con, quarter)

    # Combine
    union_tables(con)

    # Deduplicate
    deduplicate(con)

    # Summary
    print_summary(con)

    con.close()

    # Print DB size
    db_size_mb = os.path.getsize(DB_PATH) / 1e6
    print(f"\n  Database size: {db_size_mb:.1f} MB")
    print(f"  Path: {DB_PATH}")

    print("\n" + "=" * 60)
    print("DuckDB load complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
