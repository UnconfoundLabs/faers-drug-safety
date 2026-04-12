"""
FAERS Drug Safety Pipeline — Step 05: Visualizations
Creates publication-quality figures for the data story.
"""

import os
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns

OUT_DIR = os.path.expanduser("~/faers-drug-safety/output/tables")
FIG_DIR = os.path.expanduser("~/faers-drug-safety/output/figures")
os.makedirs(FIG_DIR, exist_ok=True)

# ── Style ────────────────────────────────────────────────────────────────────
sns.set_style("whitegrid")
plt.rcParams.update({
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "font.size": 11,
    "axes.titlesize": 14,
    "axes.titleweight": "bold",
    "axes.labelsize": 12,
    "figure.dpi": 150,
})

COLORS = {
    "ADHD": "#4E79A7",
    "ANTIDEPRESSANT": "#E15759",
    "GLP1": "#59A14F",
}

CLASS_LABELS = {
    "ADHD": "ADHD Medications",
    "ANTIDEPRESSANT": "Antidepressants",
    "GLP1": "GLP-1 Agonists",
}

CAPTION = ("Source: FDA FAERS 2024 Q3–Q4. Spontaneous reporting data — "
           "cannot establish causation or incidence rates.")


def fig01_case_volume():
    """Bar chart: total cases per drug class."""
    df = pd.read_csv(os.path.join(OUT_DIR, "demographics_sex.csv"))
    totals = df.groupby("drug_class")["n"].sum().reset_index()
    totals["label"] = totals["drug_class"].map(CLASS_LABELS)
    totals = totals.sort_values("n", ascending=True)

    fig, ax = plt.subplots(figsize=(8, 4))
    bars = ax.barh(
        totals["label"], totals["n"],
        color=[COLORS[c] for c in totals["drug_class"]],
        height=0.5, edgecolor="white"
    )
    for bar, val in zip(bars, totals["n"]):
        ax.text(bar.get_width() + 300, bar.get_y() + bar.get_height()/2,
                f"{int(val):,}", va="center", fontsize=11, fontweight="bold")

    ax.set_xlabel("Number of Adverse Event Reports")
    ax.set_title("Adverse Event Report Volume by Drug Class")
    ax.set_xlim(0, totals["n"].max() * 1.15)
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{int(x):,}"))
    fig.text(0.5, -0.02, CAPTION, ha="center", fontsize=8, color="gray")
    plt.tight_layout()
    plt.savefig(os.path.join(FIG_DIR, "01_case_volume.png"), bbox_inches="tight")
    plt.close()
    print("  Saved 01_case_volume.png")


def fig02_sex_distribution():
    """Stacked bar: sex distribution by drug class."""
    df = pd.read_csv(os.path.join(OUT_DIR, "demographics_sex.csv"))
    # Compute percentages
    totals = df.groupby("drug_class")["n"].sum()
    df["pct"] = df.apply(lambda r: r["n"] / totals[r["drug_class"]] * 100, axis=1)
    df["label"] = df["drug_class"].map(CLASS_LABELS)

    pivot = df.pivot_table(index="label", columns="sex", values="pct", fill_value=0)
    # Reorder
    order = [CLASS_LABELS[c] for c in ["GLP1", "ANTIDEPRESSANT", "ADHD"]]
    pivot = pivot.reindex(order)

    fig, ax = plt.subplots(figsize=(9, 4))
    sex_colors = {"Female": "#E15759", "Male": "#4E79A7", "Unknown": "#BAB0AC"}
    pivot[["Female", "Male", "Unknown"]].plot.barh(
        stacked=True, ax=ax, color=[sex_colors[c] for c in ["Female", "Male", "Unknown"]],
        width=0.5, edgecolor="white"
    )
    ax.set_xlabel("Percentage of Reports (%)")
    ax.set_title("Who Reports Adverse Events? Sex Distribution by Drug Class")
    ax.legend(loc="lower right", framealpha=0.9)
    ax.set_xlim(0, 100)

    # Annotate
    for i, cls_label in enumerate(order):
        row = pivot.loc[cls_label]
        f_pct = row["Female"]
        m_pct = row["Male"]
        ax.text(f_pct/2, i, f"{f_pct:.0f}%", ha="center", va="center",
                fontsize=10, fontweight="bold", color="white")
        ax.text(f_pct + m_pct/2, i, f"{m_pct:.0f}%", ha="center", va="center",
                fontsize=10, fontweight="bold", color="white")

    fig.text(0.5, -0.02, CAPTION, ha="center", fontsize=8, color="gray")
    plt.tight_layout()
    plt.savefig(os.path.join(FIG_DIR, "02_sex_distribution.png"), bbox_inches="tight")
    plt.close()
    print("  Saved 02_sex_distribution.png")


def fig03_age_distribution():
    """Grouped bar: age distribution by drug class."""
    df = pd.read_csv(os.path.join(OUT_DIR, "demographics_age.csv"))
    df = df[df["age_group"] != "Unknown"]
    df["label"] = df["drug_class"].map(CLASS_LABELS)

    # Compute percentages within each class
    totals = df.groupby("drug_class")["n"].sum()
    df["pct"] = df.apply(lambda r: r["n"] / totals[r["drug_class"]] * 100, axis=1)

    age_order = ["<18", "18-34", "35-49", "50-64", "65+"]
    df["age_group"] = pd.Categorical(df["age_group"], categories=age_order, ordered=True)
    df = df.sort_values("age_group")

    fig, ax = plt.subplots(figsize=(10, 5))
    x = np.arange(len(age_order))
    width = 0.25

    for i, cls in enumerate(["ADHD", "ANTIDEPRESSANT", "GLP1"]):
        subset = df[df["drug_class"] == cls].set_index("age_group").reindex(age_order)
        ax.bar(x + i * width, subset["pct"], width, label=CLASS_LABELS[cls],
               color=COLORS[cls], edgecolor="white")

    ax.set_xticks(x + width)
    ax.set_xticklabels(age_order)
    ax.set_xlabel("Age Group")
    ax.set_ylabel("% of Reports (among known age)")
    ax.set_title("Age Profile of Adverse Event Reports")
    ax.legend(framealpha=0.9)
    fig.text(0.5, -0.02, CAPTION, ha="center", fontsize=8, color="gray")
    plt.tight_layout()
    plt.savefig(os.path.join(FIG_DIR, "03_age_distribution.png"), bbox_inches="tight")
    plt.close()
    print("  Saved 03_age_distribution.png")


def fig04_top_reactions():
    """Horizontal bar: top 10 reactions per drug class (small multiples)."""
    df = pd.read_csv(os.path.join(OUT_DIR, "top_reactions_by_class.csv"))

    fig, axes = plt.subplots(1, 3, figsize=(16, 6), sharey=False)

    for i, cls in enumerate(["ADHD", "ANTIDEPRESSANT", "GLP1"]):
        ax = axes[i]
        subset = df[(df["drug_class"] == cls) & (df["rank"] <= 10)].sort_values("n")

        ax.barh(subset["reaction"], subset["n"], color=COLORS[cls],
                height=0.6, edgecolor="white")
        ax.set_title(CLASS_LABELS[cls], fontsize=13, fontweight="bold",
                     color=COLORS[cls])
        ax.set_xlabel("Number of Reports")

        # Add count labels
        for _, row in subset.iterrows():
            ax.text(row["n"] + max(subset["n"]) * 0.02,
                    row["reaction"], f"{int(row['n']):,}",
                    va="center", fontsize=8)

        ax.set_xlim(0, subset["n"].max() * 1.2)

    fig.suptitle("Top 10 Most Reported Adverse Events by Drug Class",
                 fontsize=15, fontweight="bold", y=1.02)
    fig.text(0.5, -0.02, CAPTION, ha="center", fontsize=8, color="gray")
    plt.tight_layout()
    plt.savefig(os.path.join(FIG_DIR, "04_top_reactions.png"), bbox_inches="tight")
    plt.close()
    print("  Saved 04_top_reactions.png")


def fig05_signals():
    """Dot plot: top disproportionality signals per drug class."""
    df = pd.read_csv(os.path.join(OUT_DIR, "confirmed_signals.csv"))

    fig, axes = plt.subplots(1, 3, figsize=(16, 7), sharey=False)

    for i, cls in enumerate(["ADHD", "ANTIDEPRESSANT", "GLP1"]):
        ax = axes[i]
        subset = df[df["drug_class"] == cls].nlargest(12, "ror")

        # Cap extremely large ROR for display
        subset = subset.copy()
        subset["ror_display"] = subset["ror"].clip(upper=200)
        subset["ror_hi_display"] = subset["ror_hi"].clip(upper=300)
        subset["ror_lo_display"] = subset["ror_lo"]
        subset = subset.sort_values("ror_display")

        ax.errorbar(
            subset["ror_display"], subset["reaction"],
            xerr=[
                (subset["ror_display"] - subset["ror_lo_display"]).values,
                (subset["ror_hi_display"] - subset["ror_display"]).values
            ],
            fmt="o", color=COLORS[cls], capsize=3, markersize=6,
            elinewidth=1.5
        )

        ax.axvline(x=1, color="gray", linestyle="--", linewidth=0.8, alpha=0.5)
        ax.axvline(x=2, color="red", linestyle=":", linewidth=0.8, alpha=0.3)
        ax.set_xlabel("Reporting Odds Ratio (ROR)")
        ax.set_title(CLASS_LABELS[cls], fontsize=13, fontweight="bold",
                     color=COLORS[cls])

        # Add case counts
        for _, row in subset.iterrows():
            ax.text(row["ror_display"] + 5, row["reaction"],
                    f"n={int(row['a'])}", fontsize=7, va="center", color="gray")

    fig.suptitle("Strongest Safety Signals: Reporting Odds Ratio (ROR)",
                 fontsize=15, fontweight="bold", y=1.02)
    fig.text(0.5, -0.04,
             f"{CAPTION}\nSignal criteria: PRR ≥ 2, χ² ≥ 4, n ≥ 3, lower 95% CI of PRR > 1.",
             ha="center", fontsize=8, color="gray")
    plt.tight_layout()
    plt.savefig(os.path.join(FIG_DIR, "05_safety_signals.png"), bbox_inches="tight")
    plt.close()
    print("  Saved 05_safety_signals.png")


def fig06_outcomes():
    """Stacked bar: outcome severity by drug class (as % of cases)."""
    df = pd.read_csv(os.path.join(OUT_DIR, "outcomes_by_class.csv"))

    # Get total cases per class for percentages
    sex_df = pd.read_csv(os.path.join(OUT_DIR, "demographics_sex.csv"))
    case_totals = sex_df.groupby("drug_class")["n"].sum()

    df["pct"] = df.apply(
        lambda r: r["n"] / case_totals[r["drug_class"]] * 100, axis=1
    )
    df["label"] = df["drug_class"].map(CLASS_LABELS)

    # Focus on key outcomes
    key_outcomes = ["Death", "Hospitalization", "Life-threatening", "Disability"]
    df_key = df[df["outcome"].isin(key_outcomes)]

    pivot = df_key.pivot_table(index="label", columns="outcome", values="pct", fill_value=0)
    order = [CLASS_LABELS[c] for c in ["ADHD", "ANTIDEPRESSANT", "GLP1"]]
    pivot = pivot.reindex(order)[key_outcomes]

    fig, ax = plt.subplots(figsize=(10, 5))
    outcome_colors = {
        "Death": "#2d2d2d",
        "Hospitalization": "#E15759",
        "Life-threatening": "#F28E2B",
        "Disability": "#BAB0AC",
    }

    pivot.plot.barh(
        stacked=True, ax=ax,
        color=[outcome_colors[c] for c in key_outcomes],
        width=0.5, edgecolor="white"
    )

    ax.set_xlabel("% of Reports with Serious Outcome")
    ax.set_title("Serious Outcome Profile by Drug Class")
    ax.legend(loc="lower right", framealpha=0.9)
    fig.text(0.5, -0.02, CAPTION, ha="center", fontsize=8, color="gray")
    plt.tight_layout()
    plt.savefig(os.path.join(FIG_DIR, "06_outcomes.png"), bbox_inches="tight")
    plt.close()
    print("  Saved 06_outcomes.png")


def fig07_glp1_deep_dive():
    """GLP-1 specific: top drugs and their reactions."""
    import duckdb
    DB_PATH = os.path.expanduser("~/faers-drug-safety/data/db/faers.duckdb")
    con = duckdb.connect(DB_PATH, read_only=True)

    # Top GLP-1 drugs
    drug_df = con.execute("""
        SELECT
            CASE
                WHEN UPPER(drugname) LIKE '%MOUNJARO%' OR UPPER(drugname) LIKE '%TIRZEPATIDE%' THEN 'Mounjaro (tirzepatide)'
                WHEN UPPER(drugname) LIKE '%ZEPBOUND%' THEN 'Zepbound (tirzepatide)'
                WHEN UPPER(drugname) LIKE '%OZEMPIC%' THEN 'Ozempic (semaglutide)'
                WHEN UPPER(drugname) LIKE '%WEGOVY%' THEN 'Wegovy (semaglutide)'
                WHEN UPPER(drugname) LIKE '%TRULICITY%' OR UPPER(drugname) LIKE '%DULAGLUTIDE%' THEN 'Trulicity (dulaglutide)'
                WHEN UPPER(drugname) LIKE '%RYBELSUS%' THEN 'Rybelsus (semaglutide)'
                WHEN UPPER(drugname) LIKE '%SAXENDA%' OR UPPER(drugname) LIKE '%VICTOZA%' THEN 'Saxenda/Victoza (liraglutide)'
                ELSE 'Other GLP-1'
            END AS drug_label,
            COUNT(DISTINCT primaryid) AS n
        FROM cohort_glp1_drugs
        GROUP BY drug_label
        ORDER BY n DESC
    """).fetchdf()

    fig, ax = plt.subplots(figsize=(9, 5))
    drug_df_sorted = drug_df.sort_values("n")
    colors = sns.color_palette("Greens_r", len(drug_df_sorted))
    ax.barh(drug_df_sorted["drug_label"], drug_df_sorted["n"],
            color=colors, height=0.6, edgecolor="white")

    for _, row in drug_df_sorted.iterrows():
        ax.text(row["n"] + 100, row["drug_label"], f"{int(row['n']):,}",
                va="center", fontsize=10, fontweight="bold")

    ax.set_xlabel("Number of Adverse Event Reports")
    ax.set_title("GLP-1 Agonist Reports: Which Drugs Drive the Volume?")
    ax.set_xlim(0, drug_df["n"].max() * 1.15)
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{int(x):,}"))
    fig.text(0.5, -0.02, CAPTION, ha="center", fontsize=8, color="gray")
    plt.tight_layout()
    plt.savefig(os.path.join(FIG_DIR, "07_glp1_drugs.png"), bbox_inches="tight")
    plt.close()
    print("  Saved 07_glp1_drugs.png")

    con.close()


def fig08_reporter_type():
    """Who reports? Consumer vs physician by class."""
    df = pd.read_csv(os.path.join(OUT_DIR, "reporter_type.csv"))
    totals = df.groupby("drug_class")["n"].sum()
    df["pct"] = df.apply(lambda r: r["n"] / totals[r["drug_class"]] * 100, axis=1)
    df["label"] = df["drug_class"].map(CLASS_LABELS)

    # Focus on main categories
    main_reporters = ["Consumer", "Physician", "Other health professional", "Pharmacist"]
    df_main = df[df["reporter"].isin(main_reporters)]

    fig, ax = plt.subplots(figsize=(10, 5))
    pivot = df_main.pivot_table(index="label", columns="reporter", values="pct", fill_value=0)
    order = [CLASS_LABELS[c] for c in ["ADHD", "ANTIDEPRESSANT", "GLP1"]]
    pivot = pivot.reindex(order)[main_reporters]

    reporter_colors = {
        "Consumer": "#F28E2B",
        "Physician": "#4E79A7",
        "Other health professional": "#76B7B2",
        "Pharmacist": "#B07AA1",
    }

    pivot.plot.barh(
        stacked=True, ax=ax,
        color=[reporter_colors[c] for c in main_reporters],
        width=0.5, edgecolor="white"
    )

    ax.set_xlabel("% of Reports")
    ax.set_title("Who Reports Adverse Events? Reporter Type by Drug Class")
    ax.legend(loc="lower right", framealpha=0.9, fontsize=9)
    ax.set_xlim(0, 100)
    fig.text(0.5, -0.02, CAPTION, ha="center", fontsize=8, color="gray")
    plt.tight_layout()
    plt.savefig(os.path.join(FIG_DIR, "08_reporter_type.png"), bbox_inches="tight")
    plt.close()
    print("  Saved 08_reporter_type.png")


def fig09_distinguishing_reactions():
    """What makes each drug class unique? Reactions specific to each."""
    df = pd.read_csv(os.path.join(OUT_DIR, "confirmed_signals.csv"))

    # For each class, get signals with highest PRR that are clinically meaningful
    # Filter out generic/artifact terms
    noise_terms = [
        "Drug ineffective", "Off label use", "Product substitution issue",
        "Product availability issue", "Incorrect dose administered",
        "Extra dose administered", "Accidental underdose", "Toxicity to various agents",
        "Product tampering", "Adulterated product", "Product use issue",
    ]
    df_clean = df[~df["reaction"].isin(noise_terms)]

    fig, axes = plt.subplots(1, 3, figsize=(16, 6), sharey=False)

    for i, cls in enumerate(["ADHD", "ANTIDEPRESSANT", "GLP1"]):
        ax = axes[i]
        subset = df_clean[df_clean["drug_class"] == cls].nlargest(10, "a")
        subset = subset.sort_values("a")

        ax.barh(subset["reaction"], subset["a"], color=COLORS[cls],
                height=0.6, edgecolor="white")
        ax.set_title(CLASS_LABELS[cls], fontsize=13, fontweight="bold",
                     color=COLORS[cls])
        ax.set_xlabel("Number of Reports")

        for _, row in subset.iterrows():
            ax.text(row["a"] + max(subset["a"]) * 0.03, row["reaction"],
                    f"PRR={row['prr']:.1f}", fontsize=7, va="center", color="gray")

    fig.suptitle("Top Safety Signals by Report Count (Artifacts Excluded)",
                 fontsize=15, fontweight="bold", y=1.02)
    fig.text(0.5, -0.02, CAPTION, ha="center", fontsize=8, color="gray")
    plt.tight_layout()
    plt.savefig(os.path.join(FIG_DIR, "09_key_signals.png"), bbox_inches="tight")
    plt.close()
    print("  Saved 09_key_signals.png")


def main():
    print("=" * 60)
    print("FAERS Visualization — Step 05")
    print("=" * 60)

    fig01_case_volume()
    fig02_sex_distribution()
    fig03_age_distribution()
    fig04_top_reactions()
    fig05_signals()
    fig06_outcomes()
    fig07_glp1_deep_dive()
    fig08_reporter_type()
    fig09_distinguishing_reactions()

    print("\n" + "=" * 60)
    print(f"All figures saved to: {FIG_DIR}")
    for f in sorted(os.listdir(FIG_DIR)):
        size = os.path.getsize(os.path.join(FIG_DIR, f)) / 1e3
        print(f"  {f:40s} {size:>6.0f} KB")
    print("=" * 60)


if __name__ == "__main__":
    main()
