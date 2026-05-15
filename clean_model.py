"""
dbt-carbon-mrv | Stage 2: Clean & Model
========================================
Reads from:   data/raw/verra_projects_*.csv
              data/raw/berkeley_vrod_*.csv

Produces:     data/models/stg_all_vcs.csv         -- all VCS projects cleaned
              data/models/stg_blue_carbon.csv      -- blue carbon (WRC) only
              data/models/mart_blue_carbon.csv     -- analysis-ready master table

What this script does:
  1. Loads the latest raw snapshots from Stage 1
  2. Cleans each source (types, nulls, column names)
  3. Merges Berkeley credit volumes onto Verra project detail
  4. Filters to blue carbon (Wetland Restoration / WRC)
  5. Engineers key metrics: retirement rate, pipeline flag, credit gap
  6. Saves three output tables to data/models/

Run:
  python clean_model.py

Author: Likitha Sree Yarabarla
"""

import sys
import logging
from pathlib import Path
from datetime import datetime

import pandas as pd

# ── Config ────────────────────────────────────────────────────────────────────

RAW_DIR    = Path("data/raw")
MODELS_DIR = Path("data/models")
MODELS_DIR.mkdir(parents=True, exist_ok=True)

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(MODELS_DIR / "clean_model.log"),
    ],
)
log = logging.getLogger(__name__)

# ── Helpers ───────────────────────────────────────────────────────────────────

def latest_file(folder: Path, prefix: str) -> Path:
    """Pick the most recently created file matching a prefix."""
    matches = sorted(folder.glob(f"{prefix}*.csv"), reverse=True)
    if not matches:
        log.error(f"No file found in {folder} matching '{prefix}*'")
        sys.exit(1)
    log.info(f"Using : {matches[0].name}")
    return matches[0]


def log_separator(title: str):
    log.info("─" * 60)
    log.info(f"  {title}")
    log.info("─" * 60)


def save_model(df: pd.DataFrame, name: str) -> Path:
    out = MODELS_DIR / f"{name}.csv"
    df.to_csv(out, index=False)
    log.info(f"Saved  : {out}  ({len(df):,} rows  ×  {len(df.columns)} cols)")
    return out

# ── Stage 2a: Clean Verra ─────────────────────────────────────────────────────

def clean_verra(path: Path) -> pd.DataFrame:
    log_separator("CLEAN — Verra projects")
    df = pd.read_csv(path, dtype=str)
    log.info(f"Loaded : {len(df):,} rows")

    # Rename for clarity
    df = df.rename(columns={
        "ID":                                  "verra_id",
        "Name":                                "project_name_verra",
        "Proponent":                           "proponent",
        "Project Type":                        "project_type",
        "AFOLU Activities":                    "afolu_activities",
        "Methodology":                         "verra_methodology",
        "Status":                              "verra_status",
        "Country/Area":                        "country_verra",
        "Estimated Annual Emission Reductions": "est_annual_reductions",
        "Region":                              "region_verra",
        "Project Registration Date":           "registration_date",
        "Crediting Period Start Date":         "crediting_start",
        "Crediting Period End Date":           "crediting_end",
    })

    # Types
    df["verra_id"]             = pd.to_numeric(df["verra_id"], errors="coerce")
    df["est_annual_reductions"] = (
        df["est_annual_reductions"]
        .str.replace(",", "", regex=False)
        .pipe(pd.to_numeric, errors="coerce")
    )
    df["registration_date"] = pd.to_datetime(df["registration_date"], errors="coerce")
    df["crediting_start"]   = pd.to_datetime(df["crediting_start"],   errors="coerce")
    df["crediting_end"]     = pd.to_datetime(df["crediting_end"],     errors="coerce")

    # Flag blue carbon (WRC = Wetland Restoration & Conservation)
    df["is_blue_carbon"] = df["afolu_activities"].fillna("").str.contains(
        "WRC", case=False
    )

    # Pipeline health flag
    active_statuses = {
        "Registered",
        "Verification approval requested",
        "Registration and verification approval requested",
        "Crediting Period Renewal Requested",
        "Crediting Period Renewal and Verification Approval Requested",
    }
    df["is_active"] = df["verra_status"].isin(active_statuses)

    log.info(f"Blue carbon (WRC) projects : {df['is_blue_carbon'].sum()}")
    log.info(f"Active projects            : {df['is_active'].sum()}")
    log.info(f"Nulls in verra_id          : {df['verra_id'].isna().sum()}")

    return df


# ── Stage 2b: Clean Berkeley ──────────────────────────────────────────────────

def clean_berkeley(path: Path) -> pd.DataFrame:
    log_separator("CLEAN — Berkeley VROD")
    df = pd.read_csv(path, dtype=str)
    log.info(f"Loaded : {len(df):,} rows")

    # Filter to VCS only
    df = df[df["Voluntary Registry"] == "VCS"].copy()
    log.info(f"VCS only : {len(df):,} rows")

    # Strip 'VCS' prefix from Project ID to get numeric key for merge
    df["verra_id"] = (
        df["Project ID"]
        .str.replace("VCS", "", regex=False)
        .str.strip()
        .pipe(pd.to_numeric, errors="coerce")
    )

    # Rename credit columns (they have newlines in names)
    df = df.rename(columns={
        "Project ID":               "berkeley_project_id",
        "Project Name":             "project_name_berkeley",
        "Voluntary Status":         "berkeley_status",
        "Scope":                    "scope",
        "Type":                     "project_type_berkeley",
        "Country":                  "country_berkeley",
        "Total Credits \nIssued":   "credits_issued",
        "Total Credits \nRetired":  "credits_retired",
        "Total Credits Remaining":  "credits_remaining",
        "Total Buffer \nPool Deposits": "buffer_pool_deposits",
        "First Year of Project (Vintage)": "first_vintage_year",
    })

    # Numeric types
    for col in ["credits_issued", "credits_retired", "credits_remaining", "buffer_pool_deposits"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # Year columns (annual issuance by vintage) — keep as numeric
    year_cols = [c for c in df.columns if isinstance(c, int) and 1995 <= c <= 2026]
    for y in year_cols:
        df[y] = pd.to_numeric(df[y], errors="coerce").fillna(0)

    log.info(f"Nulls in verra_id : {df['verra_id'].isna().sum()}")
    log.info(f"Credits issued total : {df['credits_issued'].sum():,.0f}")

    return df


# ── Stage 2c: Merge ───────────────────────────────────────────────────────────

def merge_sources(verra: pd.DataFrame, berkeley: pd.DataFrame) -> pd.DataFrame:
    log_separator("MERGE — Verra + Berkeley on verra_id")

    merged = berkeley.merge(verra, on="verra_id", how="inner")
    log.info(f"Merged rows : {len(merged):,}")
    log.info(f"Lost from Berkeley : {len(berkeley) - len(merged):,} (projects not in Verra export)")
    log.info(f"Lost from Verra    : {len(verra) - len(merged):,} (non-VCS projects)")

    return merged


# ── Stage 2d: Engineer features ───────────────────────────────────────────────

def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    log_separator("FEATURE ENGINEERING")

    # Retirement rate (0-100%)
    df["retirement_rate_pct"] = (
        df["credits_retired"] / df["credits_issued"].replace(0, float("nan")) * 100
    ).round(1)

    # Has ever issued any credits
    df["has_issued_credits"] = df["credits_issued"] > 0

    # Credit gap vs annual estimate
    df["est_annual_reductions"] = pd.to_numeric(df["est_annual_reductions"], errors="coerce")
    df["credit_gap"] = df["est_annual_reductions"] - df["credits_issued"]

    # Crediting period length in years
    df["crediting_years"] = (
        (df["crediting_end"] - df["crediting_start"])
        .dt.days / 365.25
    ).round(1)

    # Annual issuance trend columns — names may be int or str depending on load path
    year_cols = [
        c for c in df.columns
        if str(c).isdigit() and 2010 <= int(str(c)) <= 2025
    ]
    for y in year_cols:
        df[y] = pd.to_numeric(df[y], errors="coerce").fillna(0)

    if year_cols:
        df["peak_issuance_year"]       = df[year_cols].idxmax(axis=1)
        df["peak_issuance_volume"]     = df[year_cols].max(axis=1)
        recent = [c for c in year_cols if int(str(c)) >= 2023]
        df["recent_issuance_2023_2025"] = df[recent].sum(axis=1) if recent else 0
    else:
        df["peak_issuance_year"]        = None
        df["peak_issuance_volume"]      = 0
        df["recent_issuance_2023_2025"] = 0

    log.info(f"Projects with credits issued   : {df['has_issued_credits'].sum()}")
    log.info(f"Projects with zero credits     : {(~df['has_issued_credits']).sum()}")
    log.info(f"Avg retirement rate            : {df['retirement_rate_pct'].mean():.1f}%")
    log.info(f"Projects with 2023-25 issuance : {(df['recent_issuance_2023_2025'] > 0).sum()}")

    return df


# ── Stage 2e: Blue carbon subset ─────────────────────────────────────────────

def filter_blue_carbon(df: pd.DataFrame) -> pd.DataFrame:
    log_separator("FILTER — Blue carbon (Wetland Restoration)")

    blue = df[df["project_type_berkeley"] == "Wetland Restoration"].copy()
    log.info(f"Blue carbon projects : {len(blue)}")
    log.info(f"Credits issued       : {blue['credits_issued'].sum():,.0f}")
    log.info(f"Credits retired      : {blue['credits_retired'].sum():,.0f}")
    log.info(f"Retirement rate      : {blue['credits_retired'].sum() / blue['credits_issued'].sum() * 100:.1f}%")

    # Country concentration
    log.info("Top 5 countries by credits issued:")
    top = blue.groupby("country_berkeley")["credits_issued"].sum().nlargest(5)
    for country, vol in top.items():
        pct = vol / blue["credits_issued"].sum() * 100
        log.info(f"  {country:<20} {vol:>12,.0f}  ({pct:.1f}%)")

    return blue


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    log.info("=" * 60)
    log.info("  dbt-carbon-mrv  |  Stage 2: Clean & Model")
    log.info(f"  Run at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log.info("=" * 60)

    # Load latest raw snapshots from Stage 1
    verra_path    = latest_file(RAW_DIR, "verra_projects")
    berkeley_path = latest_file(RAW_DIR, "berkeley_vrod")

    # Clean each source
    verra    = clean_verra(verra_path)
    berkeley = clean_berkeley(berkeley_path)

    # Merge
    merged = merge_sources(verra, berkeley)

    # Save staging model — all VCS projects
    save_model(merged, "stg_all_vcs")

    # Engineer features
    merged = engineer_features(merged)

    # Blue carbon subset
    blue = filter_blue_carbon(merged)

    # Save models
    save_model(merged, "stg_all_vcs_featured")
    save_model(blue,   "mart_blue_carbon")

    log_separator("SUMMARY")
    log.info("ALL MODELS BUILT — ready for Stage 3 (analyze)")
    log.info(f"Outputs in : {MODELS_DIR.resolve()}")
    log.info("")
    log.info("  stg_all_vcs_featured.csv  — all VCS projects with features")
    log.info("  mart_blue_carbon.csv      — blue carbon mart (your article data)")


if __name__ == "__main__":
    main()