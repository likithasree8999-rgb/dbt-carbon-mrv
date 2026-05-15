"""
pipeline_dag.py
───────────────
Airflow DAG: dbt_carbon_mrv_pipeline

Orchestrates the full blue carbon data pipeline:
  1. ingest_validate  — load + validate source files
  2. dbt_run          — run all dbt models
  3. dbt_test         — run all dbt tests
  4. export_analysis  — generate chart-ready CSVs for article + dashboard

Schedule: weekly (Mondays 06:00 UTC)
Owner: likitha-sree
"""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.utils.dates import days_ago

import os
import sys
import logging
import pandas as pd
from pathlib import Path

# ── Default args ──────────────────────────────────────────────────────────────

DEFAULT_ARGS = {
    "owner":            "likitha-sree",
    "depends_on_past":  False,
    "email_on_failure": True,
    "email":            ["likithasree8999@gmail.com"],
    "retries":          1,
    "retry_delay":      timedelta(minutes=5),
}

# ── DAG ───────────────────────────────────────────────────────────────────────

with DAG(
    dag_id="dbt_carbon_mrv_pipeline",
    description="Blue carbon credit analysis pipeline — Verra + Berkeley VROD",
    default_args=DEFAULT_ARGS,
    schedule_interval="0 6 * * 1",    # every Monday 06:00 UTC
    start_date=days_ago(1),
    catchup=False,
    tags=["carbon", "mrv", "blue-carbon", "verra", "dbt"],
) as dag:

    # ── Task 1: Ingest & validate ─────────────────────────────────────────────

    def run_ingest_validate():
        """Load both source files and run schema + row count validation."""
        log = logging.getLogger(__name__)

        verra_path    = Path(os.environ["VERRA_SOURCE_PATH"])
        berkeley_path = Path(os.environ["BERKELEY_SOURCE_PATH"])
        raw_dir       = Path(os.environ.get("RAW_DIR", "data/raw"))
        raw_dir.mkdir(parents=True, exist_ok=True)

        # Verra
        verra = pd.read_csv(verra_path, dtype=str)
        assert len(verra) >= 4000, f"Verra row count too low: {len(verra)}"
        assert "ID" in verra.columns, "Verra missing ID column"
        assert "Status" in verra.columns, "Verra missing Status column"
        log.info(f"Verra loaded: {len(verra):,} rows")

        # Berkeley
        berk = pd.read_excel(berkeley_path, sheet_name="PROJECTS", header=3)
        assert len(berk) >= 10000, f"Berkeley row count too low: {len(berk)}"
        assert "Voluntary Registry" in berk.columns, "Berkeley missing registry column"
        vcs_count = (berk["Voluntary Registry"] == "VCS").sum()
        assert vcs_count >= 4000, f"VCS project count too low: {vcs_count}"
        log.info(f"Berkeley loaded: {len(berk):,} rows | VCS: {vcs_count:,}")

        # Save timestamped snapshots
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        verra.to_csv(raw_dir / f"verra_projects_{ts}.csv", index=False)
        berk.to_csv(raw_dir  / f"berkeley_vrod_{ts}.csv",  index=False)
        log.info("Snapshots saved.")

    task_ingest = PythonOperator(
        task_id="ingest_validate",
        python_callable=run_ingest_validate,
    )

    # ── Task 2: dbt run ───────────────────────────────────────────────────────

    task_dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command="cd {{ var('dbt_project_dir', '/opt/airflow/dbt') }} && dbt run --profiles-dir .",
    )

    # ── Task 3: dbt test ──────────────────────────────────────────────────────

    task_dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command="cd {{ var('dbt_project_dir', '/opt/airflow/dbt') }} && dbt test --profiles-dir .",
    )

    # ── Task 4: Export analysis CSVs ──────────────────────────────────────────

    def export_analysis():
        """Generate chart-ready CSVs from the mart for the article and dashboard."""
        log = logging.getLogger(__name__)
        mart_path  = Path(os.environ.get("MART_PATH", "data/models/mart_blue_carbon.csv"))
        output_dir = Path(os.environ.get("ANALYSIS_DIR", "data/analysis"))
        output_dir.mkdir(parents=True, exist_ok=True)

        blue = pd.read_csv(mart_path)
        year_cols = [c for c in blue.columns if str(c).startswith("issued_20")]

        # 1. Annual issuance trend
        annual = {
            int(c.replace("issued_", "")): blue[c].sum()
            for c in year_cols
        }
        trend_df = pd.DataFrame(
            [{"year": y, "credits_issued": v} for y, v in sorted(annual.items())]
        )
        trend_df.to_csv(output_dir / "annual_issuance_trend.csv", index=False)
        log.info("Saved annual_issuance_trend.csv")

        # 2. Country concentration
        country_df = (
            blue.groupby("country")["credits_issued"]
            .sum()
            .reset_index()
            .sort_values("credits_issued", ascending=False)
        )
        country_df["share_pct"] = (
            country_df["credits_issued"] / country_df["credits_issued"].sum() * 100
        ).round(1)
        country_df.to_csv(output_dir / "credits_by_country.csv", index=False)
        log.info("Saved credits_by_country.csv")

        # 3. Pipeline stage summary
        pipeline_df = blue.groupby("pipeline_stage").agg(
            project_count=("project_id", "count"),
            total_credits_issued=("credits_issued", "sum"),
        ).reset_index()
        pipeline_df.to_csv(output_dir / "pipeline_stage_summary.csv", index=False)
        log.info("Saved pipeline_stage_summary.csv")

        # 4. Key metrics (single-row summary for dashboard KPIs)
        total_issued = blue["credits_issued"].sum()
        metrics = {
            "total_projects":          len(blue),
            "issuing_projects":        int(blue["has_issued_credits"].sum()),
            "pipeline_conversion_pct": round(blue["has_issued_credits"].mean() * 100, 1),
            "total_credits_issued":    int(total_issued),
            "total_credits_retired":   int(blue["credits_retired"].sum()),
            "retirement_rate_pct":     round(blue["credits_retired"].sum() / total_issued * 100, 1),
            "katingan_share_pct":      round(
                blue.loc[blue["berkeley_project_id"] == "VCS1477", "credits_issued"].sum()
                / total_issued * 100, 1
            ),
            "indonesia_share_pct":     round(
                blue[blue["country"] == "Indonesia"]["credits_issued"].sum()
                / total_issued * 100, 1
            ),
            "peak_issuance_year":      int(trend_df.loc[trend_df["credits_issued"].idxmax(), "year"]),
            "issued_2023_2025":        int(blue["issued_2023_2025"].sum()),
            "run_date":                datetime.now().strftime("%Y-%m-%d"),
        }
        pd.DataFrame([metrics]).to_csv(output_dir / "kpi_summary.csv", index=False)
        log.info("Saved kpi_summary.csv")
        log.info(f"Key metrics: {metrics}")

    task_export = PythonOperator(
        task_id="export_analysis",
        python_callable=export_analysis,
    )

    # ── DAG dependency graph ──────────────────────────────────────────────────
    #
    #   ingest_validate → dbt_run → dbt_test → export_analysis
    #

    task_ingest >> task_dbt_run >> task_dbt_test >> task_export