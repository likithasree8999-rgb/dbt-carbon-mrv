# dbt-carbon-mrv

**An end-to-end data pipeline for blue carbon credit analysis using the Verra VCS Registry and Berkeley Voluntary Registry Offsets Database.**

Built by [Likitha Sree Yarabarla](https://linkedin.com/in/likitha-sree) · Climate Data Engineer  
Stack: Python · dbt · DuckDB · Airflow · Streamlit · GitHub Actions

---

## What This Pipeline Does

Ingests, validates, models, and analyzes every blue carbon (Wetland Restoration & Conservation) credit ever issued on the Verra VCS registry. Produces a publication-ready analytical dataset and live Streamlit dashboard.

**Key findings surfaced by this pipeline:**
- 91% of blue carbon projects listed on Verra have never issued a single credit
- One project (Katingan, Indonesia) accounts for 81.3% of all blue carbon credits ever issued
- The pipeline promises ~47M tonnes CO₂e per year — the market has issued 49M tonnes in its entire history
- Annual issuances collapsed from 14.4M (2015) to zero in 2024–2025
- Two countries (Indonesia + Pakistan) control 97% of all credits ever issued

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     Data Sources                        │
│  Verra Registry (registry.verra.org)                    │
│  Berkeley VROD  (gspp.berkeley.edu)                     │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│              Ingestion & Validation                     │
│  ingestion/ingest_validate.py                           │
│  · Schema checks · Row count assertions · MD5 checksums │
│  · Saves timestamped snapshots to data/raw/             │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│               dbt Transformations                       │
│  staging/stg_verra.sql       — clean Verra source       │
│  staging/stg_berkeley.sql    — clean Berkeley source    │
│  marts/mart_blue_carbon.sql  — merged analytical mart   │
│  · Runs on DuckDB (local) or Snowflake (production)     │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│                    Analysis                             │
│  orchestration/pipeline_dag.py — Airflow DAG            │
│  · 5 key findings · Chart-ready exports                 │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│                   Dashboard                             │
│  dashboard/app.py — Streamlit                           │
│  · Live KPIs · Interactive charts · Methodology notes  │
└─────────────────────────────────────────────────────────┘
```

---

## Repo Structure

```
dbt-carbon-mrv/
├── ingestion/
│   └── ingest_validate.py        # Stage 1: load, validate, snapshot
├── dbt/
│   ├── dbt_project.yml           # dbt project config
│   ├── profiles.yml              # DuckDB connection
│   ├── models/
│   │   ├── staging/
│   │   │   ├── stg_verra.sql         # clean Verra source
│   │   │   ├── stg_berkeley.sql      # clean Berkeley source
│   │   │   └── schema.yml            # column docs + tests
│   │   └── marts/
│   │       ├── mart_blue_carbon.sql  # final analytical mart
│   │       └── schema.yml            # mart docs + tests
│   ├── tests/
│   │   └── assert_blue_carbon_not_empty.sql
│   └── macros/
│       └── safe_divide.sql
├── orchestration/
│   └── pipeline_dag.py           # Airflow DAG
├── dashboard/
│   └── app.py                    # Streamlit dashboard
├── data/
│   ├── sources/                  # raw downloaded files (gitignored)
│   └── raw/                      # validated snapshots (gitignored)
├── .github/
│   └── workflows/
│       └── ci.yml                # GitHub Actions: lint + dbt test
├── .env.example                  # environment variable template
├── .gitignore
├── requirements.txt
└── README.md
```

---

## Quickstart

### 1. Clone and set up environment

```bash
git clone https://github.com/likitha-sree/dbt-carbon-mrv.git
cd dbt-carbon-mrv
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your file paths
```

### 3. Drop source files into data/sources/

```
data/sources/allprojects.csv
data/sources/Voluntary-Registry-Offsets-Database--v2026-02.xlsx
```

### 4. Run ingestion and validation

```bash
python ingestion/ingest_validate.py
```

### 5. Run dbt transformations

```bash
cd dbt
dbt deps
dbt run
dbt test
```

### 6. Launch Streamlit dashboard

```bash
streamlit run dashboard/app.py
```

---

## Data Sources

| Source | Provider | License | URL |
|--------|----------|---------|-----|
| VCS Project Registry | Verra | Public | registry.verra.org |
| Voluntary Registry Offsets Database v2026-02 | Berkeley Carbon Trading Project | CC BY 4.0 | gspp.berkeley.edu |

**Citation for Berkeley data:**  
Haya, B.K., Quartson, P., Bernard, T., Abayo, A., Rong, X., So, I.S. (2026). *Voluntary Registry Offsets Database v2026-02*, Berkeley Carbon Trading Project, University of California, Berkeley.

---

## Methodology Notes

- **Blue carbon definition:** Projects classified as `Type = "Wetland Restoration"` in the Berkeley VROD, corresponding to `AFOLU Activities` containing `WRC` (Wetland Restoration & Conservation) in the Verra registry.
- **Merge key:** Berkeley Project IDs use the format `VCS{numeric_id}`. The numeric portion is extracted and joined to Verra's integer project ID.
- **Credit volumes:** Sourced from Berkeley VROD which aggregates issuance and retirement records from the Verra registry. All figures are in tonnes CO₂e (1 VCU = 1 tonne CO₂e).
- **Annual issuance:** Reflects the vintage year of emission reductions, not the date of registry issuance.
- **Pipeline projects:** Projects with status `Under Development`, `Under Validation`, or `Registration Requested` are classified as pipeline (not yet issuing credits).

---

## Author

**Likitha Sree Yarabarla** — Climate Data Engineer  
4+ years building data pipelines for environmental impact measurement.  
Currently: BI Analyst at Worldview Development USA, tracking 21.5M tonnes CO₂e across 6 Verra-verified mangrove restoration projects.

[LinkedIn](https://linkedin.com/in/likitha-sree) · [GitHub](https://github.com/likitha-sree) · likithasree8999@gmail.com

---

## License

Code: MIT License  
Data: subject to original source licenses (Verra public use; Berkeley CC BY 4.0)