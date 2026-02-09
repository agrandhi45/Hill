import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import re

# App configuration
st.set_page_config(
    page_title="SignalDeck Multi-State",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Paths for CSVs (deployment-safe)
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BASE_PATH = ROOT / "Outputs"

STATE_FOLDERS = {
    "CA": BASE_PATH / "CA",
    "NY": BASE_PATH / "NY",
    "MA": BASE_PATH / "MA",
    "TX": BASE_PATH / "TX",
}

CSV_NAME = "SEC_FORMD_2025_VC_INVESTOR_INTENT_FINAL.csv

# Load CSV for selected state
@st.cache_data
def load_state_csv(state):
    path = STATE_FOLDERS[state] / CSV_NAME
    df = pd.read_csv(path, parse_dates=["filing_date"])
    df = df.rename(columns={
        "issuer_name": "Fund Name",
        "issuer_state": "State",
        "fund_vertical": "Sector",
        "intent_bucket": "Intent Bucket",
        "actively_deploying": "Actively Deploying",
        "offering_amount_total": "Total Fund Size",
        "total_amount_sold": "Lifetime Capital Deployed",
        "decayed_amount_sold": "Recent Capital Deployed",
        "sale_velocity": "Capital Velocity",
        "sale_acceleration": "Capital Acceleration",
        "fund_momentum": "Fund Momentum",
        "investor_intent_score": "Investor Intent Score",
        "related_person_name": "GP Name",
        "number_of_investors": "Investor Count",
        "why_investor": "Why This Investor",
        "days_since_filing": "Days Since Filing"
    })
    return df

# Sidebar for state, tier, filters
st.sidebar.header("Settings")
state = st.sidebar.selectbox("Select State", list(STATE_FOLDERS.keys()))
view = st.sidebar.radio(
    "View Mode",
    ["Founder View", "Institutional View", "Advanced Market Analytics"],
    index=0
)

df = load_state_csv(state)

sector_filter = st.sidebar.multiselect(
    "Sector",
    sorted(df["Sector"].dropna().unique())
)
intent_filter = st.sidebar.multiselect(
    "Intent Bucket",
    ["🔥 Hot", "🟡 Warm", "❄️ Cold"],
    default=["🔥 Hot", "🟡 Warm"]
)
min_score = st.sidebar.slider(
    "Minimum Investor Intent Score",
    0.0, 1.0, 0.45, 0.05
)

# Apply filters
filtered = df.copy()
if sector_filter:
    filtered = filtered[filtered["Sector"].isin(sector_filter)]
if intent_filter:
    filtered = filtered[filtered["Intent Bucket"].isin(intent_filter)]
filtered = filtered[filtered["Investor Intent Score"] >= min_score]
if filtered.empty:
    st.warning("No investors matched to the selected filters.")
    st.stop()

# Normalize GP Names
filtered["GP Name"] = (
    filtered["GP Name"]
    .astype(str)           # Ensure all values are strings
    .str.replace(r"([a-z])([A-Z])", r"\1 \2") # Camel Case
    .str.replace("_", " ") # Replace underscores with spaces
    .str.title()           # Capitalize each word
    .str.strip())          # Remove leading/trailing spaces        

# Top metrics
c1, c2, c3, c4 = st.columns(4)
c1.metric("Active Funds", int(filtered["Actively Deploying"].sum()))
c2.metric("Recent Capital", f"${filtered['Recent Capital Deployed'].sum():,.0f}")
c3.metric("Median Intent Score", f"{filtered['Investor Intent Score'].median():.2f}")
c4.metric("Unique Funds", filtered["Fund Name"].nunique())

# Founder view
if view == "Founder View":
    st.subheader("Ask SignalDeck")
    query = st.text_input("Try: 'email these 5 funds this week' or 'who is moving fastest in fintech'")
    temp = filtered.copy()
    if query:
        q = query.lower()
        sector_match = re.search(r"(fintech|saas|ai|crypto|health|climate)", q)
        if sector_match:
            temp = temp[temp["Sector"].str.lower().str.contains(sector_match.group(1), na=False)]
        if "fast" in q or "quick" in q:
            temp = temp.sort_values("Capital Velocity", ascending=False)
        if "email" in q or "this week" in q:
            temp = temp.sort_values(["Investor Intent Score","Capital Velocity"], ascending=False).head(5)
        st.success(f"SignalDeck suggests prioritizing {len(temp)} funds.")
        st.dataframe(
            temp[["Fund Name","Sector","Investor Intent Score","Recent Capital Deployed","Why This Investor"]],
            use_container_width=True
        )

    fig_deploy = px.scatter(
        temp.head(50),
        x="Capital Velocity",
        y="Recent Capital Deployed",
        size="Investor Count",
        color="Intent Bucket",
        hover_name="Fund Name",
        title="Active Funds Deployment",
        color_discrete_map={"🔥 Hot":"#ff6b6b","🟡 Warm":"#feca57","❄️ Cold":"#8395a7"},
        template="plotly_white"
    )
    st.plotly_chart(fig_deploy, use_container_width=True)

# Institutional view
elif view == "Institutional View":
    st.subheader("Market Structure & Capital Flow")
    fig_deploy = px.scatter(
        filtered,
        x="Capital Velocity",
        y="Recent Capital Deployed",
        size="Investor Count",
        color="Intent Bucket",
        hover_name="Fund Name",
        title="Capital Deployment Map",
        color_discrete_map={"🔥 Hot":"#e74c3c","🟡 Warm":"#f1c40f","❄️ Cold":"#95a5a6"},
        template="plotly_white"
    )
    st.plotly_chart(fig_deploy, use_container_width=True)

    sorted_cap = filtered.sort_values("Recent Capital Deployed", ascending=False)["Recent Capital Deployed"]
    cum_cap = sorted_cap.cumsum()/sorted_cap.sum()
    top10_share = cum_cap.iloc[int(len(cum_cap)*0.1)-1]
    fig_gini = go.Figure()
    fig_gini.add_trace(go.Scatter(y=cum_cap, fill="tozeroy", name="Capital Share"))
    fig_gini.add_trace(go.Scatter(y=np.linspace(0,1,len(cum_cap)), line=dict(dash="dash"), name="Equality Line"))
    fig_gini.update_layout(title="Capital Concentration Curve", xaxis_title="Ranked Funds", yaxis_title="Cumulative Capital Share", template="plotly_white")
    st.plotly_chart(fig_gini, use_container_width=True)
    st.info(f"Top 10% of funds account for **{top10_share:.0%}** of recent capital deployment.")
    
    
    gp_df = filtered.groupby("GP Name", as_index=False).agg(
        capital=("Recent Capital Deployed","sum"),
        intent=("Investor Intent Score","mean"),
        velocity=("Capital Velocity","mean")
    )
    fig_gp = px.scatter(
        gp_df,
        x="velocity",
        y="intent",
        size="capital",
        hover_name="GP Name",
        title="GP Influence & Capital Concentration",
        template="plotly_white",
        color_discrete_sequence=px.colors.qualitative.Dark24
    )
    st.plotly_chart(fig_gp, use_container_width=True)

# Advanced Market Analytics view
else:
    st.subheader("Advanced Market Analytics")
    st.caption("Deep diagnostics on timing, momentum, and capital behavior with insights")

    x_med = filtered["Days Since Filing"].median()
    y_med = filtered["Fund Momentum"].median()
    fig_quad = px.scatter(
        filtered,
        x="Days Since Filing",
        y="Fund Momentum",
        color="Actively Deploying",
        hover_name="Fund Name",
        title="Momentum vs Recency",
        template="plotly_white",
        color_discrete_sequence=["#1f77b4","#ff7f0e"]
    )
    fig_quad.add_vline(x=x_med, line_dash="dash")
    fig_quad.add_hline(y=y_med, line_dash="dash")
    st.plotly_chart(fig_quad, use_container_width=True)

    intent_time = filtered.groupby(pd.Grouper(key="filing_date", freq="M"))["Recent Capital Deployed"].sum().reset_index()
    intent_time["rolling_mean"] = intent_time["Recent Capital Deployed"].rolling(3).mean()
    fig_time = go.Figure()
    fig_time.add_bar(x=intent_time["filing_date"], y=intent_time["Recent Capital Deployed"], marker_color="#1abc9c")
    fig_time.add_scatter(x=intent_time["filing_date"], y=intent_time["rolling_mean"], mode="lines", name="3M Rolling Mean", line=dict(color="#34495e"))
    fig_time.update_layout(title="Investor Intent Over Time", template="plotly_white")
    st.plotly_chart(fig_time, use_container_width=True)

    fig_momentum = px.scatter(
        filtered,
        x="Total Fund Size",
        y="Fund Momentum",
        size="Investor Count",
        color="Capital Velocity",
        log_x=True,
        hover_name="Fund Name",
        title="Fund Momentum vs Fund Size",
        template="plotly_white",
        color_continuous_scale=px.colors.sequential.Plasma
    )
    st.plotly_chart(fig_momentum, use_container_width=True)

    top_funds = filtered.sort_values("Investor Intent Score", ascending=False).head(20)
    fig_vel_time = px.scatter(
        top_funds,
        x="filing_date",
        y="Capital Velocity",
        size="Total Fund Size",
        color="Investor Intent Score",
        hover_name="Fund Name",
        title="Capital Velocity vs Time (Top 20 Funds)",
        template="plotly_white",
        color_continuous_scale=px.colors.sequential.Viridis
    )
    st.plotly_chart(fig_vel_time, use_container_width=True)

    top_10_pct = int(0.1 * len(filtered))
    capital_top_10 = filtered.sort_values("Recent Capital Deployed", ascending=False).head(top_10_pct)["Recent Capital Deployed"].sum()
    capital_share = capital_top_10 / filtered["Recent Capital Deployed"].sum()
    st.metric("Top 10% Funds Deploy", f"{capital_share:.0%}")
    fast_count = (filtered["Capital Velocity"] >= filtered["Capital Velocity"].quantile(0.9)).sum()
    st.metric("Top 10% Fast-Moving Funds", f"{fast_count} funds")
    anomaly_count = ((filtered["Investor Intent Score"] > 0.75) & (filtered["Recent Capital Deployed"] < filtered["Recent Capital Deployed"].median())).sum()
    st.metric("High Intent, Low Recent Deployment", f"{anomaly_count} funds")
