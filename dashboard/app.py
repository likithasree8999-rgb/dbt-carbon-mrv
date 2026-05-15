"""
dashboard/app.py
Blue Carbon Credit Analysis — Complete Story Dashboard
Built by Likitha Sree Yarabarla — Climate Data Engineer
Run: streamlit run dashboard/app.py
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path

st.set_page_config(
    page_title="Blue Carbon Credit Analysis",
    page_icon="🌿",
    layout="wide",
)

# ── Load ──────────────────────────────────────────────────────────────────────

@st.cache_data
def load_mart():
    for p in [
        Path("data/models/mart_blue_carbon.csv"),
        Path("data/analysis/mart_blue_carbon.csv"),
        Path("mart_blue_carbon.csv"),
    ]:
        if p.exists():
            return pd.read_csv(p, low_memory=False)
    raise FileNotFoundError("mart_blue_carbon.csv not found — run clean_model.py first")

try:
    blue = load_mart()
    data_loaded = True
except FileNotFoundError as e:
    data_loaded = False
    err = str(e)

# ── Header ────────────────────────────────────────────────────────────────────

st.markdown("# 🌿 Blue Carbon Credit Analysis")
st.markdown(
    "**Verra VCS Registry × Berkeley VROD v2026-02** · "
    "Built by [Likitha Sree Yarabarla](https://linkedin.com/in/likitha-sree) · "
    "[GitHub](https://github.com/likithasree8999-rgb/dbt-carbon-mrv)"
)
st.caption(
    "🕐 Last updated: February 2026 · "
    "91 projects analyzed · "
    "49.2M credits tracked · "
    "Data refreshes monthly · "
    "Source: Verra VCS Registry + Berkeley VROD v2026-02"

)

if not data_loaded:
    st.error(f"Data not found. Run: python clean_model.py\n\n{err}")
    st.stop()

# ── Prep ──────────────────────────────────────────────────────────────────────

for col in ["credits_issued", "credits_retired", "credits_remaining"]:
    if col in blue.columns:
        blue[col] = pd.to_numeric(blue[col], errors="coerce").fillna(0)

blue["est_annual_reductions"] = pd.to_numeric(
    blue.get("est_annual_reductions", blue.get("Estimated Annual Emission Reductions", 0)),
    errors="coerce"
)

if "retirement_rate_pct" not in blue.columns:
    blue["retirement_rate_pct"] = (
        blue["credits_retired"] / blue["credits_issued"].replace(0, float("nan")) * 100
    ).round(1)

if "pipeline_stage" not in blue.columns:
    blue["pipeline_stage"] = "stalled_pipeline"
    blue.loc[blue["credits_issued"] > 0, "pipeline_stage"] = "issuing"
    if "verra_status" in blue.columns:
        active = ["Registered", "Verification approval requested",
                  "Registration and verification approval requested"]
        mask = (blue["credits_issued"] == 0) & (blue["verra_status"].isin(active))
        blue.loc[mask, "pipeline_stage"] = "active_pipeline"

year_cols = sorted([c for c in blue.columns if str(c).isdigit() and 2010 <= int(str(c)) <= 2025])
ret_year_cols = sorted([c for c in blue.columns if str(c).endswith(".1")
                        and str(c).replace(".1","").isdigit()
                        and 2010 <= int(str(c).replace(".1","")) <= 2025])
for y in year_cols + ret_year_cols:
    blue[y] = pd.to_numeric(blue[y], errors="coerce").fillna(0)

country_col = "country_berkeley" if "country_berkeley" in blue.columns else "country"
name_col    = "project_name_berkeley" if "project_name_berkeley" in blue.columns else "project_name"
id_col      = "berkeley_project_id" if "berkeley_project_id" in blue.columns else "project_id"

# ── Core numbers ──────────────────────────────────────────────────────────────

total_issued   = blue["credits_issued"].sum()
total_retired  = blue["credits_retired"].sum()
total_projects = len(blue)
issuing        = int((blue["credits_issued"] > 0).sum())
conv_rate      = round(issuing / total_projects * 100, 1)
ret_rate       = round(total_retired / total_issued * 100, 1) if total_issued > 0 else 0
katingan_vol   = blue[blue[id_col] == "VCS1477"]["credits_issued"].sum()
kat_pct        = round(katingan_vol / total_issued * 100, 1) if total_issued > 0 else 0
total_est      = blue["est_annual_reductions"].sum()
issued_2023_25 = sum(blue[y].sum() for y in year_cols if int(y) >= 2023)

# ── Narrative ─────────────────────────────────────────────────────────────────

st.divider()
st.markdown("## The Story in 3 Sentences")
st.info(
    f"The blue carbon market lists **{total_projects} projects** on the Verra registry — "
    f"but **{total_projects - issuing} of them ({100-conv_rate:.0f}%)** have never issued a single credit. "
    f"One Indonesian project (Katingan) controls **{kat_pct}% of all {total_issued/1e6:.0f}M credits** ever issued. "
    f"Annual issuances peaked at 14.4M in 2015 and have effectively collapsed to zero since 2023."
)

# ── Key findings callout ──────────────────────────────────────────────────────

st.markdown("## 5 Key Findings")
k1, k2, k3, k4, k5 = st.columns(5)

k1.error(
    f"**{100-conv_rate:.0f}%**\n\nof projects have never issued a single credit"
)
k2.error(
    f"**{kat_pct}%**\n\nof all credits from ONE project — Katingan, Indonesia"
)
k3.warning(
    f"**{total_est/1e6:.0f}M**\n\ntonnes promised per year by the pipeline"
)
k4.error(
    f"**ZERO**\n\ncredits issued in 2024 or 2025"
)
k5.success(
    f"**{ret_rate}%**\n\nretirement rate — buyers DO use credits when available"
)

st.divider()

# ── Chart 1: Annual trend ─────────────────────────────────────────────────────

st.markdown("### 📉 Annual Issuance vs Retirement Trend (2010–2025)")
st.caption("Green = credits issued · Blue = credits retired · Red bars = collapse years")

trend_rows = []
for y in year_cols:
    yr = int(y)
    ret_col = f"{y}.1"
    retired_vol = blue[ret_col].sum() if ret_col in blue.columns else 0
    trend_rows.append({
        "year": yr,
        "Credits Issued": blue[y].sum(),
        "Credits Retired": retired_vol,
    })
trend = pd.DataFrame(trend_rows)

fig_trend = go.Figure()
fig_trend.add_trace(go.Bar(
    x=trend["year"], y=trend["Credits Issued"],
    name="Credits Issued",
    marker_color=["#FF6B6B" if y >= 2023 else "#2E8B57" for y in trend["year"]],
    hovertemplate="<b>%{x}</b><br>Issued: %{y:,.0f}<extra></extra>",
))
fig_trend.add_trace(go.Scatter(
    x=trend["year"], y=trend["Credits Retired"],
    name="Credits Retired",
    mode="lines+markers",
    line=dict(color="#1D6FA5", width=2),
    hovertemplate="<b>%{x}</b><br>Retired: %{y:,.0f}<extra></extra>",
))
fig_trend.add_annotation(
    x=2015, y=trend[trend["year"]==2015]["Credits Issued"].values[0],
    text="Peak: 14.4M (2015)",
    showarrow=True, arrowhead=2, ay=-45,
    font=dict(size=11, color="#2E8B57"),
)
fig_trend.add_annotation(
    x=2024, y=800000,
    text="ZERO issued",
    showarrow=False,
    font=dict(size=11, color="#FF6B6B"),
)
fig_trend.update_layout(
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    yaxis_title="Credits (tCO₂e)",
    xaxis_title="Year",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    margin=dict(t=40, b=20),
    height=350,
)
st.plotly_chart(fig_trend, use_container_width=True)

st.divider()

# ── Chart 2A + 2B: Country concentration ─────────────────────────────────────

st.markdown("### 🌍 Geographic Concentration")
st.caption("Left: who dominates the whole market · Right: what exists beyond Indonesia")

ctry = blue.groupby(country_col)["credits_issued"].sum().reset_index()
ctry.columns = ["country", "credits_issued"]
ctry = ctry[ctry["credits_issued"] > 0].sort_values("credits_issued", ascending=False)
ctry["share_pct"] = (ctry["credits_issued"] / ctry["credits_issued"].sum() * 100).round(1)

col_a, col_b = st.columns(2)

with col_a:
    st.markdown("**The dominance story**")
    indonesia_total = ctry[ctry["country"] == "Indonesia"]["credits_issued"].sum()
    rest_of_world   = ctry[ctry["country"] != "Indonesia"]["credits_issued"].sum()
    rest_indonesia  = indonesia_total - katingan_vol

    donut_df = pd.DataFrame({
        "label":   ["Katingan (VCS1477)", "Rest of Indonesia", "Rest of World"],
        "credits": [katingan_vol, rest_indonesia, rest_of_world],
    })
    fig_donut = go.Figure(go.Pie(
        labels=donut_df["label"],
        values=donut_df["credits"],
        hole=0.55,
        marker_colors=["#0F6E56", "#5DCAA5", "#D3D1C7"],
        textinfo="label+percent",
        hovertemplate="<b>%{label}</b><br>%{value:,.0f} credits<extra></extra>",
    ))
    fig_donut.update_layout(
        showlegend=False,
        margin=dict(t=20, b=20, l=20, r=20),
        paper_bgcolor="rgba(0,0,0,0)",
        height=300,
        annotations=[dict(
            text=f"<b>{kat_pct}%</b><br>Katingan",
            x=0.5, y=0.5, font_size=14, showarrow=False,
        )],
    )
    st.plotly_chart(fig_donut, use_container_width=True)

with col_b:
    st.markdown("**Beyond Indonesia**")
    non_indo = ctry[ctry["country"] != "Indonesia"].copy()
    fig_rest = px.bar(
        non_indo, x="credits_issued", y="country", orientation="h",
        color="credits_issued", color_continuous_scale="Greens",
        text=non_indo["share_pct"].apply(lambda x: f"{x}% global"),
        labels={"credits_issued": "Credits Issued (tCO₂e)", "country": ""},
    )
    fig_rest.update_traces(textposition="outside")
    fig_rest.update_layout(
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        coloraxis_showscale=False, yaxis=dict(autorange="reversed"),
        margin=dict(t=20, b=20), height=300,
    )
    st.plotly_chart(fig_rest, use_container_width=True)

st.divider()

# ── Chart 3: Promise vs Reality ───────────────────────────────────────────────

st.markdown("### ⚖️ Promise vs. Reality — Per Project")
st.caption(
    "X axis = developer's estimated annual reductions · "
    "Y axis = total credits ever issued · "
    "Dashed line = where issued equals one year of promises · "
    "Points BELOW the line have issued less than one year of their own projections"
)

pvr = blue[blue["credits_issued"] > 0].copy()
pvr = pvr.dropna(subset=["est_annual_reductions"])
pvr = pvr[pvr["est_annual_reductions"] > 0]

if len(pvr) > 0:
    pvr["short_name"] = pvr[name_col].str[:35]
    max_val = max(pvr["est_annual_reductions"].max(), pvr["credits_issued"].max()) * 1.1

    fig_pvr = px.scatter(
        pvr,
        x="est_annual_reductions",
        y="credits_issued",
        size="credits_issued",
        color=country_col,
        hover_name="short_name",
        hover_data={"retirement_rate_pct": True, country_col: False},
        labels={
            "est_annual_reductions": "Estimated Annual Reductions (tCO₂e)",
            "credits_issued":        "Total Credits Ever Issued (tCO₂e)",
            "retirement_rate_pct":   "Retirement Rate %",
        },
        color_discrete_sequence=px.colors.qualitative.Safe,
    )
    fig_pvr.add_shape(
        type="line", x0=0, y0=0, x1=max_val, y1=max_val,
        line=dict(color="gray", dash="dash", width=1.5),
    )
    fig_pvr.add_annotation(
        x=max_val * 0.65, y=max_val * 0.78,
        text="Above line = issued more than 1yr of promises",
        showarrow=False, font=dict(size=10, color="gray"),
    )
    fig_pvr.update_layout(
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(t=20, b=20), height=380,
    )
    st.plotly_chart(fig_pvr, use_container_width=True)
else:
    st.info("Not enough data for promise vs reality chart.")

st.divider()

# ── Chart 4: Pipeline + Top 10 ───────────────────────────────────────────────

col3, col4 = st.columns(2)

with col3:
    st.markdown("### 🔄 Pipeline Stage Breakdown")
    st.caption("91% of listed projects have never issued a single credit")
    pipe = blue.groupby("pipeline_stage").size().reset_index(name="count")
    pipe["label"] = pipe["pipeline_stage"].map({
        "issuing":          "Issuing Credits",
        "active_pipeline":  "Active Pipeline",
        "stalled_pipeline": "Stalled / Withdrawn",
    }).fillna(pipe["pipeline_stage"])
    fig3 = px.pie(pipe, names="label", values="count", hole=0.4,
                  color_discrete_sequence=["#2E8B57", "#90EE90", "#FF6B6B"])
    fig3.update_layout(margin=dict(t=10, b=10), paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig3, use_container_width=True)

with col4:
    st.markdown("### 🏆 Top 10 Projects by Credits Issued")
    st.caption("Katingan alone = 81.3% of all supply")
    top = blue.nlargest(10, "credits_issued")[
        [name_col, country_col, "credits_issued", "retirement_rate_pct"]
    ].copy()
    top["credits_issued"]      = top["credits_issued"].apply(lambda x: f"{x/1e6:.2f}M")
    top["retirement_rate_pct"] = top["retirement_rate_pct"].apply(
        lambda x: f"{x:.0f}%" if pd.notna(x) else "0%"
    )
    top.columns = ["Project", "Country", "Credits Issued", "Retirement Rate"]
    st.dataframe(top, use_container_width=True, hide_index=True)

st.divider()

# ── KPI summary row ───────────────────────────────────────────────────────────

st.markdown("### 📊 Summary Metrics")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total Projects",        f"{total_projects}")
c2.metric("Ever Issued Credits",   f"{issuing} / {total_projects}", f"{conv_rate}% conversion")
c3.metric("Total Credits Issued",  f"{total_issued/1e6:.1f}M tCO₂e")
c4.metric("Retirement Rate",       f"{ret_rate}%")
c5.metric("Katingan Share",        f"{kat_pct}%", "of all blue carbon")

st.divider()

# ── Data explorer ─────────────────────────────────────────────────────────────

st.markdown("### 🔍 Explore the Raw Data")
f1, f2 = st.columns(2)
with f1:
    stages = blue["pipeline_stage"].unique().tolist()
    sel_stage = st.multiselect("Filter by pipeline stage", stages, default=stages)
with f2:
    countries = sorted(blue[country_col].dropna().unique().tolist())
    sel_country = st.multiselect("Filter by country", countries, default=[])

filtered = blue[blue["pipeline_stage"].isin(sel_stage)]
if sel_country:
    filtered = filtered[filtered[country_col].isin(sel_country)]

show_cols = [c for c in [
    id_col, name_col, country_col, "verra_status",
    "credits_issued", "credits_retired", "retirement_rate_pct", "pipeline_stage"
] if c in filtered.columns]

st.dataframe(
    filtered[show_cols].rename(columns={
        id_col:                "Project ID",
        name_col:              "Project Name",
        country_col:           "Country",
        "verra_status":        "Verra Status",
        "credits_issued":      "Credits Issued",
        "credits_retired":     "Credits Retired",
        "retirement_rate_pct": "Retirement %",
        "pipeline_stage":      "Stage",
    }),
    use_container_width=True,
    hide_index=True,
)

st.divider()
st.caption(
    "Data: Verra VCS Registry (registry.verra.org) · "
    "Berkeley Carbon Trading Project VROD v2026-02 (CC BY 4.0, gspp.berkeley.edu) · "
    "Pipeline: dbt + DuckDB · Dashboard: Streamlit · "
    "github.com/likithasree8999-rgb/dbt-carbon-mrv"
)