"""
dbt-carbon-mrv | Stage 1: Ingest & Validate
============================================
Sources:
  - Verra Registry allprojects.csv       (registry.verra.org)
  - Berkeley VROD .xlsx                  (gspp.berkeley.edu)

What this script does:
  1. Loads both raw sources
  2. Validates schema — required columns present
  3. Validates data quality — row counts, nulls, numeric ranges
  4. Logs a clear pass/fail report
  5. Saves clean raw copies to /data/raw/ for Stage 2

Run:
  python ingest_validate.py

Author: Likitha Sree Yarabarla
"""

import os
import sys
import hashlib
import logging
from datetime import datetime
from pathlib import Path

import pandas as pd

# ── Config ────────────────────────────────────────────────────────────────────

RAW_DIR = Path("data/raw")
RAW_DIR.mkdir(parents=True, exist_ok=True)

VERRA_PATH   = Path("data/sources/allprojects.csv")
BERKELEY_PATH = Path("data/sources/Voluntary-Registry-Offsets-Database--v2026-02.xlsx")

# Minimum row counts — fail loudly if source has shrunk unexpectedly
MIN_ROWS = {
    "verra":    4_000,
    "berkeley": 10_000,
}

# Required columns — fail if any are missing
REQUIRED_COLS = {
    "verra": [
        "ID", "Name", "Proponent", "Project Type",
        "AFOLU Activities", "Methodology", "Status",
        "Country/Area", "Estimated Annual Emission Reductions",
        "Region", "Project Registration Date",
        "Crediting Period Start Date", "Crediting Period End Date",
    ],
    "berkeley": [
        "Project ID", "Project Name", "Voluntary Registry",
        "Voluntary Status", "Scope", "Type", "Country",
        "Total Credits \nIssued", "Total Credits \nRetired",
        "Total Credits Remaining",
    ],
}

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(RAW_DIR / "ingest.log"),
    ],
)
log = logging.getLogger(__name__)

# ── Helpers ───────────────────────────────────────────────────────────────────

def file_checksum(path: Path) -> str:
    """MD5 checksum — detect if source file has changed between runs."""
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_schema(df: pd.DataFrame, source: str) -> list[str]:
    """Return list of missing required columns."""
    missing = [c for c in REQUIRED_COLS[source] if c not in df.columns]
    return missing


def validate_row_count(df: pd.DataFrame, source: str) -> bool:
    """Return True if row count meets minimum threshold."""
    return len(df) >= MIN_ROWS[source]


def null_report(df: pd.DataFrame, key_cols: list[str]) -> dict:
    """Return null % for key columns."""
    return {
        col: round(df[col].isna().mean() * 100, 1)
        for col in key_cols
        if col in df.columns
    }


def log_separator(title: str):
    log.info("─" * 60)
    log.info(f"  {title}")
    log.info("─" * 60)

# ── Loaders ───────────────────────────────────────────────────────────────────

def load_verra(path: Path) -> pd.DataFrame:
    log_separator("VERRA REGISTRY — allprojects.csv")
    log.info(f"Source : {path}")
    log.info(f"MD5    : {file_checksum(path)}")

    df = pd.read_csv(path, dtype=str)  # load as str first — validate before coercing
    log.info(f"Rows   : {len(df):,}  |  Cols: {len(df.columns)}")

    # Schema check
    missing = validate_schema(df, "verra")
    if missing:
        log.error(f"SCHEMA FAIL — missing columns: {missing}")
        sys.exit(1)
    log.info("Schema : PASS — all required columns present")

    # Row count check
    if not validate_row_count(df, "verra"):
        log.error(f"ROW COUNT FAIL — got {len(df):,}, expected >= {MIN_ROWS['verra']:,}")
        sys.exit(1)
    log.info(f"Rows   : PASS — {len(df):,} >= {MIN_ROWS['verra']:,}")

    # Null report on key fields
    key_cols = ["ID", "Name", "Status", "Country/Area", "AFOLU Activities"]
    nulls = null_report(df, key_cols)
    for col, pct in nulls.items():
        level = log.warning if pct > 20 else log.info
        level(f"Nulls  : {col:<40} {pct:>5}%")

    # Status distribution — sanity check
    log.info("Status distribution:")
    for status, count in df["Status"].value_counts().items():
        log.info(f"         {status:<55} {count:>5}")

    return df


def load_berkeley(path: Path) -> pd.DataFrame:
    log_separator("BERKELEY VROD — Voluntary-Registry-Offsets-Database")
    log.info(f"Source : {path}")
    log.info(f"MD5    : {file_checksum(path)}")

    # Header is on row 4 (0-indexed row 3)
    df = pd.read_excel(path, sheet_name="PROJECTS", header=3, dtype=str)
    log.info(f"Rows   : {len(df):,}  |  Cols: {len(df.columns)}")

    # Schema check
    missing = validate_schema(df, "berkeley")
    if missing:
        log.error(f"SCHEMA FAIL — missing columns: {missing}")
        sys.exit(1)
    log.info("Schema : PASS — all required columns present")

    # Row count check
    if not validate_row_count(df, "berkeley"):
        log.error(f"ROW COUNT FAIL — got {len(df):,}, expected >= {MIN_ROWS['berkeley']:,}")
        sys.exit(1)
    log.info(f"Rows   : PASS — {len(df):,} >= {MIN_ROWS['berkeley']:,}")

    # Registry distribution — confirm VCS is present
    log.info("Registry distribution:")
    for reg, count in df["Voluntary Registry"].value_counts().items():
        log.info(f"         {reg:<20} {count:>6}")

    # VCS-specific checks
    vcs = df[df["Voluntary Registry"] == "VCS"]
    log.info(f"VCS projects : {len(vcs):,}")

    wetland = vcs[vcs["Type"] == "Wetland Restoration"]
    log.info(f"WRC / Wetland Restoration : {len(wetland):,}")
    if len(wetland) < 50:
        log.warning("Low wetland project count — check 'Type' column values haven't changed")

    # Null report on credit columns
    credit_cols = [
        "Total Credits \nIssued",
        "Total Credits \nRetired",
        "Total Credits Remaining",
    ]
    nulls = null_report(df, credit_cols)
    for col, pct in nulls.items():
        log.info(f"Nulls  : {col.strip():<35} {pct:>5}%")

    return df

# ── Save raw snapshots ────────────────────────────────────────────────────────

def save_raw(df: pd.DataFrame, name: str):
    """Save timestamped snapshot to data/raw/ so every run is reproducible."""
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    out_path = RAW_DIR / f"{name}_{ts}.csv"
    df.to_csv(out_path, index=False)
    log.info(f"Saved  : {out_path}  ({len(df):,} rows)")
    return out_path

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    log.info("=" * 60)
    log.info("  dbt-carbon-mrv  |  Stage 1: Ingest & Validate")
    log.info(f"  Run at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log.info("=" * 60)

    errors = []

    try:
        df_verra = load_verra(VERRA_PATH)
        save_raw(df_verra, "verra_projects")
    except SystemExit:
        errors.append("verra")

    try:
        df_berkeley = load_berkeley(BERKELEY_PATH)
        save_raw(df_berkeley, "berkeley_vrod")
    except SystemExit:
        errors.append("berkeley")

    log_separator("SUMMARY")
    if errors:
        log.error(f"FAILED sources: {errors}")
        log.error("Fix errors above before running Stage 2.")
        sys.exit(1)
    else:
        log.info("ALL CHECKS PASSED — ready for Stage 2 (clean & model)")
        log.info(f"Outputs saved to: {RAW_DIR.resolve()}")


if __name__ == "__main__":
    main()