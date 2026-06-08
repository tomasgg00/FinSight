import ssl
import os
import urllib3

ssl._create_default_https_context = ssl._create_unverified_context
os.environ["PYTHONHTTPSVERIFY"] = "0"
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

import streamlit as st
import duckdb
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import ollama

DB_PATH = "data/finsight.duckdb"

st.set_page_config(
    page_title="FinSight",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .metric-card {
        background: #1A1D27;
        border: 1px solid #2A2D3A;
        border-radius: 12px;
        padding: 1.2rem 1.5rem;
        margin-bottom: 0.5rem;
    }
    .metric-label {
        font-size: 12px;
        color: #888;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin-bottom: 4px;
    }
    .metric-value {
        font-size: 28px;
        font-weight: 600;
        color: #E8E8E8;
        line-height: 1.1;
    }
    .metric-sub { font-size: 13px; margin-top: 4px; }
    .positive { color: #1D9E75; }
    .negative { color: #E24B4A; }
    .neutral  { color: #EF9F27; }
    .signal-bullish {
        background: #0F3D2E; color: #1D9E75;
        padding: 3px 10px; border-radius: 20px;
        font-size: 12px; font-weight: 500;
    }
    .signal-bearish {
        background: #3D1515; color: #E24B4A;
        padding: 3px 10px; border-radius: 20px;
        font-size: 12px; font-weight: 500;
    }
    .signal-neutral {
        background: #3D2E0F; color: #EF9F27;
        padding: 3px 10px; border-radius: 20px;
        font-size: 12px; font-weight: 500;
    }
    .section-header {
        font-size: 13px; font-weight: 500; color: #888;
        text-transform: uppercase; letter-spacing: 0.08em;
        margin: 1.5rem 0 1rem; padding-bottom: 8px;
        border-bottom: 1px solid #2A2D3A;
    }
</style>
""", unsafe_allow_html=True)

SCHEMA = """
You have access to a DuckDB database with the following tables:

1. main_gold.mart_latest_snapshot  — one row per ticker, most recent trading day
   - ticker           VARCHAR
   - latest_date      DATE
   - close_price      DOUBLE
   - daily_return_pct DOUBLE
   - ma_20            DOUBLE
   - ma_50            DOUBLE
   - trend_signal     VARCHAR   -- 'bullish', 'bearish', or 'neutral'
   - volume_spike     BOOLEAN
   - avg_volume_20d   DOUBLE
   - pct_from_ma20    DOUBLE
   - pct_from_ma50    DOUBLE
   - rsi_14           DOUBLE
   - rsi_signal       VARCHAR   -- 'overbought', 'oversold', 'neutral'
   - volatility_30d   DOUBLE
   - bb_upper         DOUBLE
   - bb_lower         DOUBLE

2. main_gold.mart_stock_summary  — full daily history per ticker
   - price_date       DATE
   - ticker           VARCHAR
   - close_price      DOUBLE
   - volume           BIGINT
   - daily_return_pct DOUBLE
   - ma_20            DOUBLE
   - ma_50            DOUBLE
   - trend_signal     VARCHAR
   - volume_spike     BOOLEAN
   - daily_range      DOUBLE
   - avg_volume_20d   DOUBLE
   - rsi_14           DOUBLE
   - volatility_30d   DOUBLE
   - bb_upper         DOUBLE
   - bb_lower         DOUBLE

Rules:
- Use mart_latest_snapshot for current/latest questions
- Use mart_stock_summary for historical questions
- Return ONLY the raw SQL — no markdown, no backticks, no explanation
"""

@st.cache_data(ttl=3600)
def get_snapshot():
    con = duckdb.connect(DB_PATH, read_only=True)
    df = con.execute("SELECT * FROM main_gold.mart_latest_snapshot ORDER BY ticker").df()
    con.close()
    return df

@st.cache_data(ttl=3600)
def get_history(ticker):
    con = duckdb.connect(DB_PATH, read_only=True)
    df = con.execute("""
        SELECT s.price_date, s.close_price, s.ma_20, s.ma_50,
               s.volume, s.daily_return_pct, s.daily_range,
               s.bb_upper, s.bb_lower, s.rsi_14, s.volatility_30d,
               r.open_price, r.high_price, r.low_price
        FROM main_gold.mart_stock_summary s
        LEFT JOIN main_bronze.stg_prices r
               ON s.ticker = r.ticker AND s.price_date = r.price_date
        WHERE s.ticker = ?
        ORDER BY s.price_date
    """, [ticker]).df()
    con.close()
    return df

@st.cache_data(ttl=3600)
def get_correlation():
    con = duckdb.connect(DB_PATH, read_only=True)
    df = con.execute("""
        SELECT price_date, ticker, daily_return_pct
        FROM main_gold.mart_stock_summary
        WHERE price_date >= current_date - interval '1 year'
    """).df()
    con.close()
    pivot = df.pivot(index="price_date", columns="ticker", values="daily_return_pct")
    return pivot.corr().round(2)

def call_ollama(question):
    response = ollama.chat(
        model="mistral",
        messages=[
            {"role": "system", "content": SCHEMA},
            {"role": "user",   "content": f"Question: {question}\n\nSQL:"}
        ]
    )
    sql = response["message"]["content"].strip()
    return sql.replace("```sql", "").replace("```", "").strip()

def candlestick_chart(history, ticker):
    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.6, 0.2, 0.2],
        subplot_titles=("", "Daily return %", "RSI (14)")
    )

    if "open_price" in history.columns and history["open_price"].notna().sum() > 10:
        fig.add_trace(go.Candlestick(
            x=history["price_date"],
            open=history["open_price"],
            high=history["high_price"],
            low=history["low_price"],
            close=history["close_price"],
            name="Price",
            increasing_line_color="#1D9E75",
            decreasing_line_color="#E24B4A",
            increasing_fillcolor="#1D9E75",
            decreasing_fillcolor="#E24B4A",
        ), row=1, col=1)
    else:
        fig.add_trace(go.Scatter(
            x=history["price_date"], y=history["close_price"],
            name="Price", line=dict(color="#1D9E75", width=2)
        ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=history["price_date"], y=history["ma_20"],
        name="MA20", line=dict(color="#EF9F27", width=1.5, dash="dot")
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=history["price_date"], y=history["ma_50"],
        name="MA50", line=dict(color="#7F77DD", width=1.5, dash="dot")
    ), row=1, col=1)

    if "bb_upper" in history.columns and history["bb_upper"].notna().sum() > 10:
        fig.add_trace(go.Scatter(
            x=history["price_date"], y=history["bb_upper"],
            name="BB Upper", line=dict(color="#534AB7", width=1, dash="dash"),
            opacity=0.6
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=history["price_date"], y=history["bb_lower"],
            name="BB Lower", line=dict(color="#534AB7", width=1, dash="dash"),
            fill="tonexty", fillcolor="rgba(83,74,183,0.05)",
            opacity=0.6
        ), row=1, col=1)

    colors = ["#1D9E75" if v >= 0 else "#E24B4A"
              for v in history["daily_return_pct"].fillna(0)]
    fig.add_trace(go.Bar(
        x=history["price_date"], y=history["daily_return_pct"],
        name="Return %", marker_color=colors, showlegend=False
    ), row=2, col=1)

    if "rsi_14" in history.columns and history["rsi_14"].notna().sum() > 10:
        fig.add_trace(go.Scatter(
            x=history["price_date"], y=history["rsi_14"],
            name="RSI", line=dict(color="#1D9E75", width=1.5),
            showlegend=False
        ), row=3, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color="#E24B4A",
                      opacity=0.6, row=3, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="#1D9E75",
                      opacity=0.6, row=3, col=1)

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0F1117",
        plot_bgcolor="#0F1117",
        height=680,
        margin=dict(l=0, r=0, t=30, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=1.02,
                    xanchor="right", x=1),
        xaxis_rangeslider_visible=False,
        font=dict(family="sans-serif", size=12, color="#888"),
        title=dict(text=ticker, font=dict(size=16, color="#E8E8E8")),
    )
    fig.update_xaxes(gridcolor="#1A1D27", showgrid=True)
    fig.update_yaxes(gridcolor="#1A1D27", showgrid=True)
    fig.update_yaxes(title_text="RSI", row=3, col=1, range=[0, 100])
    return fig

def heatmap_chart(snapshot):
    metrics = ["pct_from_ma20", "pct_from_ma50", "daily_return_pct"]
    labels  = ["% from MA20", "% from MA50", "Daily return %"]
    matrix  = snapshot.set_index("ticker")[metrics].astype(float)

    fig = go.Figure(go.Heatmap(
        z=matrix.values,
        x=labels,
        y=matrix.index.tolist(),
        colorscale=[[0, "#E24B4A"], [0.5, "#1A1D27"], [1, "#1D9E75"]],
        zmid=0,
        text=matrix.values.round(2),
        texttemplate="%{text}%",
        showscale=True,
        colorbar=dict(tickfont=dict(color="#888"))
    ))
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0F1117",
        plot_bgcolor="#0F1117",
        height=420,
        margin=dict(l=0, r=0, t=10, b=0),
        font=dict(color="#888")
    )
    return fig

def correlation_chart(corr):
    fig = go.Figure(go.Heatmap(
        z=corr.values,
        x=corr.columns.tolist(),
        y=corr.index.tolist(),
        colorscale=[[0, "#E24B4A"], [0.5, "#1A1D27"], [1, "#1D9E75"]],
        zmid=0,
        zmin=-1, zmax=1,
        text=corr.values,
        texttemplate="%{text}",
        showscale=True,
        colorbar=dict(tickfont=dict(color="#888"))
    ))
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0F1117",
        plot_bgcolor="#0F1117",
        height=520,
        margin=dict(l=0, r=0, t=10, b=0),
        font=dict(color="#888", size=11)
    )
    return fig

# ── Sidebar ───────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📈 FinSight")
    st.caption("AI-powered market intelligence")
    st.divider()
    page = st.radio(
        "Navigate",
        ["Market overview", "Ticker deep dive", "AI agent"],
        label_visibility="collapsed"
    )
    st.divider()
    snapshot = get_snapshot()
    st.caption(f"Last updated: {snapshot['latest_date'].max()}")
    st.caption(f"{len(snapshot)} tickers tracked")

# ── Page 1: Market Overview ───────────────────────────────
if page == "Market overview":
    st.markdown("# Market overview")

    bullish = len(snapshot[snapshot["trend_signal"] == "bullish"])
    bearish = len(snapshot[snapshot["trend_signal"] == "bearish"])
    neutral = len(snapshot[snapshot["trend_signal"] == "neutral"])
    spikes  = len(snapshot[snapshot["volume_spike"] == True])
    avg_ret = snapshot["daily_return_pct"].mean()

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.markdown(f"""<div class="metric-card">
            <div class="metric-label">Bullish</div>
            <div class="metric-value positive">{bullish}</div>
        </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""<div class="metric-card">
            <div class="metric-label">Bearish</div>
            <div class="metric-value negative">{bearish}</div>
        </div>""", unsafe_allow_html=True)
    with c3:
        st.markdown(f"""<div class="metric-card">
            <div class="metric-label">Neutral</div>
            <div class="metric-value neutral">{neutral}</div>
        </div>""", unsafe_allow_html=True)
    with c4:
        st.markdown(f"""<div class="metric-card">
            <div class="metric-label">Volume spikes</div>
            <div class="metric-value">{spikes}</div>
        </div>""", unsafe_allow_html=True)
    with c5:
        color = "positive" if avg_ret >= 0 else "negative"
        sign  = "+" if avg_ret >= 0 else ""
        st.markdown(f"""<div class="metric-card">
            <div class="metric-label">Avg daily return</div>
            <div class="metric-value {color}">{sign}{avg_ret:.2f}%</div>
        </div>""", unsafe_allow_html=True)

    st.markdown('<p class="section-header">Signal heatmap</p>',
                unsafe_allow_html=True)
    st.plotly_chart(heatmap_chart(snapshot), use_container_width=True)

    st.markdown('<p class="section-header">All tickers</p>',
                unsafe_allow_html=True)
    for _, row in snapshot.iterrows():
        sig   = row["trend_signal"]
        ret   = row["daily_return_pct"]
        sign  = "+" if ret >= 0 else ""
        color = "positive" if ret >= 0 else "negative"
        rsi   = row.get("rsi_14", None)
        rsi_str = f"RSI: {rsi:.0f}" if rsi is not None and not pd.isna(rsi) else ""

        c1, c2, c3, c4, c5 = st.columns([1.5, 1.5, 1.5, 1.5, 2.5])
        c1.markdown(f"**{row['ticker']}**")
        c2.markdown(f"${row['close_price']:.2f}")
        c3.markdown(f"<span class='{color}'>{sign}{ret:.2f}%</span>",
                    unsafe_allow_html=True)
        c4.markdown(f"<span class='signal-{sig}'>{sig}</span>",
                    unsafe_allow_html=True)
        c5.markdown(
            f"MA20: {row['pct_from_ma20']:.1f}% &nbsp; "
            f"MA50: {row['pct_from_ma50']:.1f}% &nbsp; {rsi_str}",
            unsafe_allow_html=True
        )
        st.divider()

# ── Page 2: Ticker Deep Dive ──────────────────────────────
elif page == "Ticker deep dive":
    tickers = snapshot["ticker"].tolist()
    ticker  = st.selectbox("Select ticker", tickers)
    row     = snapshot[snapshot["ticker"] == ticker].iloc[0]
    history = get_history(ticker)

    sig   = row["trend_signal"]
    ret   = row["daily_return_pct"]
    sign  = "+" if ret >= 0 else ""
    color = "positive" if ret >= 0 else "negative"
    rsi   = row.get("rsi_14", None)
    rsi_sig = row.get("rsi_signal", "neutral")
    vol   = row.get("volatility_30d", 0)

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1:
        st.markdown(f"""<div class="metric-card">
            <div class="metric-label">Price</div>
            <div class="metric-value">${row['close_price']:.2f}</div>
        </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""<div class="metric-card">
            <div class="metric-label">Daily return</div>
            <div class="metric-value {color}">{sign}{ret:.2f}%</div>
        </div>""", unsafe_allow_html=True)
    with c3:
        st.markdown(f"""<div class="metric-card">
            <div class="metric-label">Signal</div>
            <div class="metric-value">
                <span class="signal-{sig}">{sig.upper()}</span>
            </div>
        </div>""", unsafe_allow_html=True)
    with c4:
        pct = row["pct_from_ma20"]
        col = "positive" if pct >= 0 else "negative"
        st.markdown(f"""<div class="metric-card">
            <div class="metric-label">% from MA20</div>
            <div class="metric-value {col}">{pct:+.2f}%</div>
        </div>""", unsafe_allow_html=True)
    with c5:
        rsi_col = ("negative" if rsi_sig == "overbought"
                   else "positive" if rsi_sig == "oversold"
                   else "neutral")
        rsi_val = f"{rsi:.1f}" if rsi is not None and not pd.isna(rsi) else "—"
        st.markdown(f"""<div class="metric-card">
            <div class="metric-label">RSI (14)</div>
            <div class="metric-value {rsi_col}">{rsi_val}</div>
            <div class="metric-sub {rsi_col}">{rsi_sig}</div>
        </div>""", unsafe_allow_html=True)
    with c6:
        vol_val = f"{vol:.2f}%" if vol is not None and not pd.isna(vol) else "—"
        st.markdown(f"""<div class="metric-card">
            <div class="metric-label">Volatility 30d</div>
            <div class="metric-value">{vol_val}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown('<p class="section-header">Price chart</p>',
                unsafe_allow_html=True)
    st.plotly_chart(candlestick_chart(history, ticker),
                    use_container_width=True)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown('<p class="section-header">Moving averages</p>',
                    unsafe_allow_html=True)
        fig = px.line(history, x="price_date", y=["ma_20", "ma_50"],
                      template="plotly_dark",
                      color_discrete_map={"ma_20": "#EF9F27",
                                          "ma_50": "#7F77DD"})
        fig.update_layout(paper_bgcolor="#0F1117", plot_bgcolor="#0F1117",
                          height=250, margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        st.markdown('<p class="section-header">Volume</p>',
                    unsafe_allow_html=True)
        fig = px.bar(history, x="price_date", y="volume",
                     template="plotly_dark",
                     color_discrete_sequence=["#534AB7"])
        fig.update_layout(paper_bgcolor="#0F1117", plot_bgcolor="#0F1117",
                          height=250, margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig, use_container_width=True)

    st.markdown('<p class="section-header">Correlation matrix — all tickers (1 year)</p>',
                unsafe_allow_html=True)
    st.caption("Shows how closely each pair of assets moves together. 1.0 = perfect correlation, -1.0 = inverse.")
    corr = get_correlation()
    st.plotly_chart(correlation_chart(corr), use_container_width=True)

# ── Page 3: AI Agent ──────────────────────────────────────
elif page == "AI agent":
    st.markdown("# AI agent")
    st.caption("Ask anything about the market in plain English")

    suggestions = [
        "Which tickers are bullish?",
        "Best performing stock last month?",
        "Which ticker has highest RSI?",
        "Most volatile ticker this year?",
        "Lowest daily return today?",
    ]

    st.markdown('<p class="section-header">Suggested questions</p>',
                unsafe_allow_html=True)
    cols = st.columns(len(suggestions))
    for i, s in enumerate(suggestions):
        if cols[i].button(s, use_container_width=True):
            st.session_state.setdefault("messages", [])
            st.session_state["pending_question"] = s

    st.divider()

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            if msg["role"] == "assistant" and "df" in msg:
                if msg.get("sql"):
                    st.caption(f"SQL: `{msg['sql']}`")
                st.dataframe(msg["df"], use_container_width=True,
                             hide_index=True)
            else:
                st.markdown(msg["content"])

    question = st.chat_input("Ask a question about the market...")
    if not question and "pending_question" in st.session_state:
        question = st.session_state.pop("pending_question")

    if question:
        st.session_state.messages.append({"role": "user",
                                           "content": question})
        with st.chat_message("user"):
            st.markdown(question)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    sql = call_ollama(question)
                    con = duckdb.connect(DB_PATH, read_only=True)
                    result = con.execute(sql).df()
                    con.close()
                    st.caption(f"SQL: `{sql}`")
                    st.dataframe(result, use_container_width=True,
                                 hide_index=True)
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": question,
                        "sql": sql,
                        "df": result
                    })
                except Exception as e:
                    err = f"Could not generate a result: {e}"
                    st.error(err)
                    st.session_state.messages.append({
                        "role": "assistant", "content": err
                    })