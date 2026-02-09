import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import re

# Page configuration
st.set_page_config(
    page_title="SignalDeck Multi-State",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Styling
st.markdown("""
<style>
h1, h2, h3 { font-family: Inter, sans-serif; }

.caption-text {
    font-size: 15px;
    color: #ffffff;
    font-style: italic;
    opacity: 0.85;
    margin-top: 6px;
}
</style>
""", unsafe_allow_html=True)

ROOT = Path(__file__).resolve().parent
BASE_PATH = ROOT / "Outputs"

STATE_FOLDERS = {
    "CA": BASE_PATH / "CA",
    "NY": BASE_PATH / "NY",
    "MA": BASE_PATH / "MA",
    "TX": BASE_PATH / "TX",
}

CSV_NAME = "SEC_FORMD_2025_VC_INVESTOR_INTENT_FINAL.csv"

@st.cache_data(show_spinner=False)
def load_state_csv(state: str) -> pd.DataFrame:
    path = STATE_FOLDERS[state] / CSV_NAME
    if not path.exists():
        st.error(f"Missing data file for {state}")
        st.stop()

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
        "days_since_filing": "Days Since Filing",
        "filing_date": "Filing Date"
    })
    return df

# Sidebar
st.sidebar.header("Settings")
state = st.sidebar.selectbox("Select State", list(STATE_FOLDERS.keys()))
view = st.sidebar.radio(
    "View Mode",
    ["Founder View", "Institutional View", "Advanced Market Analytics"],
    index=0
)

df = load_state_csv(state)

# GP name normalization
df["GP Name"] = (
    df["GP Name"]
    .astype(str)
    .str.replace(r"([a-z])([A-Z])", r"\1 \2", regex=True)
    .str.replace("_", " ")
    .str.title()
    .str.strip()
)

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

filtered = df.copy()
if sector_filter:
    filtered = filtered[filtered["Sector"].isin(sector_filter)]
if intent_filter:
    filtered = filtered[filtered["Intent Bucket"].isin(intent_filter)]
filtered = filtered[filtered["Investor Intent Score"] >= min_score]

if filtered.empty:
    st.warning("No investors matched to the selected filters.")
    st.stop()

# Metrics
c1, c2, c3, c4 = st.columns(4)
c1.metric("Active Funds", int(filtered["Actively Deploying"].sum()))
c2.metric("Recent Capital", f"${filtered['Recent Capital Deployed'].sum():,.0f}")
c3.metric("Median Intent Score", f"{filtered['Investor Intent Score'].median():.2f}")
c4.metric("Unique Funds", filtered["Fund Name"].nunique())

# ---------------- Founder View ----------------
if view == "Founder View":

    st.subheader("Ask SignalDeck")
    st.caption("SignalDeck prioritizes investors by deployment size, speed, and real-time intent.")

    query = st.text_input(
        "Try: 'largest fast checks in AI', 'who should I email this week', 'cold fintech funds'"
    )

    temp = filtered.copy()

    if query:
        q = query.lower()

        sector_match = re.search(r"(fintech|saas|ai|crypto|health|climate)", q)
        if sector_match:
            sector = sector_match.group(1)
            temp = temp[temp["Sector"].str.lower().str.contains(sector, na=False)]

        if "largest" in q or "big" in q:
            temp = temp.sort_values("Recent Capital Deployed", ascending=False)

        if "fast" in q or "quick" in q or "moving" in q:
            temp = temp.sort_values("Capital Velocity", ascending=False)

        if ("largest" in q) and ("fast" in q or "quick" in q):
            temp["signal_rank"] = (
                temp["Recent Capital Deployed"].rank(pct=True) * 0.45 +
                temp["Capital Velocity"].rank(pct=True) * 0.35 +
                temp["Investor Intent Score"].rank(pct=True) * 0.20
            )
            temp = temp.sort_values("signal_rank", ascending=False)

        if "hot" in q:
            temp = temp[temp["Intent Bucket"] == "🔥 Hot"]
        if "warm" in q:
            temp = temp[temp["Intent Bucket"] == "🟡 Warm"]
        if "cold" in q:
            temp = temp[temp["Intent Bucket"] == "❄️ Cold"]

        if "email" in q or "this week" in q or "reach out" in q:
            temp = temp.head(5)

        st.success(f"SignalDeck suggests prioritizing {len(temp)} funds.")

        st.dataframe(
            temp[[
                "Fund Name",
                "Sector",
                "Investor Intent Score",
                "Recent Capital Deployed",
                "Why This Investor"
            ]],
            use_container_width=True
        )

        # Founder Insight
        if not temp.empty:
            top_fund = temp.iloc[0]

            st.markdown(
                f"""
                <div class="caption-text">
                🔍 <b>Founder Insight:</b><br>
                <b>{top_fund['Fund Name']}</b> stands out due to strong recent deployment 
                (${top_fund['Recent Capital Deployed']:,.0f}) and high momentum.
                <br><br>
                💡 Prioritize outreach now — funds showing rapid capital movement typically 
                respond faster and maintain active deal pipelines.
                </div>
                """,
                unsafe_allow_html=True
            )

    fig = px.scatter(
        temp.head(50),
        x="Capital Velocity",
        y="Recent Capital Deployed",
        size="Investor Count",
        color="Intent Bucket",
        hover_name="Fund Name",
        title="Active Funds Deployment",
        template="plotly_white"
    )

    st.plotly_chart(fig, use_container_width=True)

    st.markdown(
        "<div class='caption-text'>Velocity shows how quickly capital is moving relative to peer funds.</div>",
        unsafe_allow_html=True
    )

# ---------------- Institutional View ----------------
elif view == "Institutional View":

    st.subheader("Market Structure & Capital Flow")

    fig = px.scatter(
        filtered,
        x="Capital Velocity",
        y="Recent Capital Deployed",
        size="Investor Count",
        color="Intent Bucket",
        hover_name="Fund Name",
        title="Capital Deployment Map",
        template="plotly_white"
    )

    st.plotly_chart(fig, use_container_width=True)

    # Institutional Insight
    top_20_pct = int(0.2 * len(filtered))
    capital_top_20 = (
        filtered.sort_values("Recent Capital Deployed", ascending=False)
        .head(top_20_pct)["Recent Capital Deployed"].sum()
    )
    capital_share_20 = capital_top_20 / filtered["Recent Capital Deployed"].sum()

    st.markdown(
        f"""
        <div class="caption-text">
        📊 <b>Market Insight:</b><br>
        Top 20% of funds deploy <b>{capital_share_20:.0%}</b> of recent capital.
        Capital concentration indicates momentum clustering among leading managers.
        </div>
        """,
        unsafe_allow_html=True
    )

    # GP Analysis
    gp_df = filtered.groupby("GP Name", as_index=False).agg(
        capital=("Recent Capital Deployed", "sum"),
        intent=("Investor Intent Score", "mean"),
        velocity=("Capital Velocity", "mean")
    )

    fig_gp = px.scatter(
        gp_df,
        x="velocity",
        y="intent",
        size="capital",
        hover_name="GP Name",
        title="GP Influence & Deployment Power",
        template="plotly_white"
    )

    st.plotly_chart(fig_gp, use_container_width=True)

    if not gp_df.empty:
        top_gp = gp_df.sort_values("capital", ascending=False).iloc[0]

        st.markdown(
            f"""
            <div class="caption-text">
            🧠 <b>GP Signal:</b><br>
            <b>{top_gp['GP Name']}</b> currently drives the highest deployment volume
            while maintaining strong intent and velocity.
            </div>
            """,
            unsafe_allow_html=True
        )

# ---------------- Advanced Analytics ----------------
else:

    st.subheader("Advanced Market Analytics")
    st.caption("Deep diagnostics on timing, momentum, and investor behavior.")

    fig = px.scatter(
        filtered,
        x="Days Since Filing",
        y="Fund Momentum",
        color="Intent Bucket",
        hover_name="Fund Name",
        title="Momentum vs Recency",
        template="plotly_white"
    )

    st.plotly_chart(fig, use_container_width=True)

    st.markdown(
        "<div class='caption-text'>Cold funds cluster where both recency and momentum are weak.</div>",
        unsafe_allow_html=True
    )

    intent_time = (
        filtered
        .groupby(pd.Grouper(key="Filing Date", freq="MS"))["Recent Capital Deployed"]
        .sum()
        .reset_index()
    )

    fig_time = go.Figure()
    fig_time.add_bar(
        x=intent_time["Filing Date"],
        y=intent_time["Recent Capital Deployed"]
    )

    st.plotly_chart(fig_time, use_container_width=True)

    st.markdown(
        "<div class='caption-text'>Tracks deployment cycles across the entire investor market.</div>",
        unsafe_allow_html=True
    )

    top_10_pct = int(0.1 * len(filtered))
    capital_top_10 = (
        filtered.sort_values("Recent Capital Deployed", ascending=False)
        .head(top_10_pct)["Recent Capital Deployed"].sum()
    )

    total_cap = filtered["Recent Capital Deployed"].sum()
    capital_share = capital_top_10 / total_cap if total_cap > 0 else 0

    st.metric("Top 10% Funds Deploy", f"{capital_share:.0%}")
