"""
dashboard/app.py
────────────────
Blue Carbon Credit Analysis Dashboard
Built by Likitha Sree Yarabarla — Climate Data Engineer

Data: Verra VCS Registry + Berkeley VROD v2026-02
Run:  streamlit run dashboard/app.py
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Blue Carbon Credit Analysis",
    page_icon="🌿",
    layout="wide",
)

# ── Load data ─────────────────────────────────────────────────────────────────

@st.cache_data
def load_data():
    mart_path = Path("data/analysis/mart_blue_carbon.csv")
    if not mart_path.exists():
        mart_path = Path("mart_blue_carbon.csv")
    df = pd.read_csv(mart_path)
    return df

@st.cache_data
def load_trend():
    path = Path("data/analysis/annual_issuance_trend.csv")
    if not path.exists():
        path = Path("annual_issuance_trend.csv")
    return pd.read_csv(path)

@st.cache_data
def load_countries():
    path = Path("data/analysis/credits_by_country.csv")
    if not path.exists():
        path = Path("credits_by_country.csv")
    return pd.read_csv(path)

try:
    blue    = load_data()
    trend   = load_trend()
    country = load_countries()
    data_loaded = True
except FileNotFoundError:
    data_loaded = False

# ── Header ────────────────────────────────────────────────────────────────────

st.markdown("# 🌿 Blue Carbon Credit Analysis")
st.markdown(
    "**Verra VCS Registry × Berkeley VROD v2026-02** · "
    "Built by [Likitha Sree Yarabarla](https://linkedin.com/in/likitha-sree) · "
    "[GitHub](https://github.com/likitha-sree/dbt-carbon-mrv)"
)
st.divider()

if not data_loaded:
    st.error(
        "Data files not found. Run the pipeline first:\n\n"
        "```bash\n"
        "python ingest_validate.py\n"
        "python clean_model.py\n"
        "```"
    )
    st.stop()

# ── KPI Row ───────────────────────────────────────────────────────────────────

total_issued    = blue["credits_issued"].sum()
total_retired   = blue["credits_retired"].sum()
total_projects  = len(blue)
issuing         = int(blue["has_issued_credits"].sum())
conversion_rate = round(issuing / total_projects * 100, 1)
retirement_rate = round(total_retired / total_issued * 100, 1)
katingan_share  = round(
    blue.loc[blue["berkeley_project_id"] == "VCS1477", "credits_issued"].sum()
    / total_issued * 100, 1
)

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Total Projects",        f"{total_projects}")
col2.metric("Ever Issued Credits",   f"{issuing} / {total_projects}",
            f"{conversion_rate}% conversion")
col3.metric("Credits Issued",        f"{total_issued/1e6:.1f}M tCO₂e")
col4.metric("Retirement Rate",       f"{retirement_rate}%")
col5.metric("Katingan Share",        f"{katingan_share}%",
            "of all blue carbon credits")

st.divider()

# ── Charts ────────────────────────────────────────────────────────────────────

col_left, col_right = st.columns(2)

# Chart 1: Annual issuance trend
with col_left:
    st.markdown("### 📉 Annual Issuance Trend (2010–2025)")
    st.caption("The collapse is real — zero credits issued in 2024 and 2025.")

    fig_trend = px.bar(
        trend,
        x="year",
        y="credits_issued",
        color_discrete_sequence=["#2E8B57"],
        labels={"credits_issued": "Credits Issued (tCO₂e)", "year": "Year"},
    )
    fig_trend.update_layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        margin=dict(t=20, b=20),
    )
    fig_trend.add_annotation(
        x=2015, y=trend[trend["year"]==2015]["credits_issued"].values[0],
        text="Peak: 14.4M (2015)",
        showarrow=True, arrowhead=2, ay=-40,
        font=dict(size=11, color="#2E8B57"),
    )
    st.plotly_chart(fig_trend, use_container_width=True)

# Chart 2: Country concentration
with col_right:
    st.markdown("### 🌍 Credits Issued by Country")
    st.caption("Two countries control 97% of all blue carbon credits ever issued.")

    top10 = country.head(10).copy()
    fig_country = px.bar(
        top10,
        x="credits_issued",
        y="country",
        orientation="h",
        color="credits_issued",
        color_continuous_scale="Greens",
        labels={"credits_issued": "Credits Issued (tCO₂e)", "country": ""},
        text=top10["share_pct"].apply(lambda x: f"{x}%"),
    )
    fig_country.update_traces(textposition="outside")
    fig_country.update_layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        coloraxis_showscale=False,
        yaxis=dict(autorange="reversed"),
        margin=dict(t=20, b=20),
    )
    st.plotly_chart(fig_country, use_container_width=True)

st.divider()

# Chart 3: Pipeline stage breakdown
col3a, col3b = st.columns(2)

with col3a:
    st.markdown("### 🔄 Pipeline Stage Breakdown")
    st.caption("91% of listed projects have never issued a single credit.")

    pipeline_summary = blue.groupby("pipeline_stage").agg(
        project_count=("project_id", "count")
    ).reset_index()

    pipeline_summary["pipeline_stage"] = pipeline_summary["pipeline_stage"].map({
        "issuing":          "✅ Issuing Credits",
        "active_pipeline":  "⏳ Active Pipeline",
        "stalled_pipeline": "❌ Stalled / Withdrawn",
        "unknown":          "❓ Unknown",
    }).fillna(pipeline_summary["pipeline_stage"])

    fig_pipe = px.pie(
        pipeline_summary,
        names="pipeline_stage",
        values="project_count",
        color_discrete_sequence=["#2E8B57", "#90EE90", "#FF6B6B", "#D3D3D3"],
        hole=0.4,
    )
    fig_pipe.update_layout(margin=dict(t=20, b=20))
    st.plotly_chart(fig_pipe, use_container_width=True)

with col3b:
    st.markdown("### 🏆 Top 10 Projects by Credits Issued")
    top_projects = blue.nlargest(10, "credits_issued")[
        ["project_name", "country", "credits_issued", "retirement_rate_pct"]
    ].copy()
    top_projects["credits_issued"] = top_projects["credits_issued"].apply(
        lambda x: f"{x/1e6:.2f}M"
    )
    top_projects["retirement_rate_pct"] = top_projects["retirement_rate_pct"].apply(
        lambda x: f"{x:.0f}%" if pd.notna(x) else "0%"
    )
    top_projects.columns = ["Project", "Country", "Credits Issued", "Retirement Rate"]
    st.dataframe(top_projects, use_container_width=True, hide_index=True)

st.divider()

# ── Promise vs Reality ────────────────────────────────────────────────────────

st.markdown("### ⚖️ Promise vs. Reality Gap")
st.caption(
    "Each project's developer-estimated annual reductions vs. total credits ever issued."
)

gap_df = blue[blue["credits_issued"] > 0].copy()
gap_df["est_annual_reductions_tco2e"] = pd.to_numeric(
    gap_df["est_annual_reductions_tco2e"], errors="coerce"
)
gap_df = gap_df.dropna(subset=["est_annual_reductions_tco2e"])

fig_gap = px.scatter(
    gap_df,
    x="est_annual_reductions_tco2e",
    y="credits_issued",
    size="credits_issued",
    color="country",
    hover_name="project_name",
    hover_data={"retirement_rate_pct": True},
    labels={
        "est_annual_reductions_tco2e": "Estimated Annual Reductions (tCO₂e)",
        "credits_issued":              "Total Credits Ever Issued (tCO₂e)",
    },
    color_discrete_sequence=px.colors.qualitative.Safe,
)
fig_gap.add_shape(
    type="line",
    x0=0, y0=0,
    x1=gap_df["est_annual_reductions_tco2e"].max(),
    y1=gap_df["est_annual_reductions_tco2e"].max(),
    line=dict(color="gray", dash="dash"),
)
fig_gap.add_annotation(
    x=gap_df["est_annual_reductions_tco2e"].max() * 0.7,
    y=gap_df["est_annual_reductions_tco2e"].max() * 0.8,
    text="Above line = issued more than 1yr of promises",
    showarrow=False,
    font=dict(size=10, color="gray"),
)
fig_gap.update_layout(
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    margin=dict(t=20, b=20),
)
st.plotly_chart(fig_gap, use_container_width=True)

st.divider()

# ── Raw data explorer ─────────────────────────────────────────────────────────

st.markdown("### 🔍 Explore the Data")
col_filter1, col_filter2 = st.columns(2)

with col_filter1:
    selected_status = st.multiselect(
        "Filter by pipeline stage",
        options=blue["pipeline_stage"].unique().tolist(),
        default=blue["pipeline_stage"].unique().tolist(),
    )

with col_filter2:
    selected_country = st.multiselect(
        "Filter by country",
        options=sorted(blue["country"].dropna().unique().tolist()),
        default=[],
    )

filtered = blue[blue["pipeline_stage"].isin(selected_status)]
if selected_country:
    filtered = filtered[filtered["country"].isin(selected_country)]

display_cols = [
    "berkeley_project_id", "project_name", "country",
    "verra_status", "credits_issued", "credits_retired",
    "retirement_rate_pct", "pipeline_stage",
]
st.dataframe(
    filtered[display_cols].rename(columns={
        "berkeley_project_id":  "Project ID",
        "project_name":         "Project Name",
        "country":              "Country",
        "verra_status":         "Verra Status",
        "credits_issued":       "Credits Issued",
        "credits_retired":      "Credits Retired",
        "retirement_rate_pct":  "Retirement Rate %",
        "pipeline_stage":       "Pipeline Stage",
    }),
    use_container_width=True,
    hide_index=True,
)

# ── Footer ────────────────────────────────────────────────────────────────────

st.divider()
st.caption(
    "Data sources: Verra VCS Registry (registry.verra.org) · "
    "Berkeley Carbon Trading Project VROD v2026-02 (CC BY 4.0) · "
    "Built with dbt + DuckDB + Streamlit · "
    "github.com/likitha-sree/dbt-carbon-mrv"
)