# 📈 FinSight — AI-Powered Market Intelligence Platform

> A production-grade data engineering project built end-to-end: from raw market data ingestion to an AI agent that answers questions in plain English.

---

## What is FinSight?

FinSight is a personal market intelligence platform that tracks stocks and ETFs through a full modern data stack — ingestion, transformation, semantic layer, and an AI-powered query agent. It was built to demonstrate production data engineering patterns, not just isolated scripts.

---

## Architecture

```
Yahoo Finance API
      │
      ▼
┌─────────────────┐
│   Ingestion     │  Python + yfinance → DuckDB
│   (Bronze)      │  Raw OHLCV prices, 16 tickers
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Transformation │  dbt Core — Medallion architecture
│  Bronze → Gold  │  Types, tests, documentation
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
 Silver      Gold
 ──────      ────
 Returns     Trend signals
 MA20/50     RSI (14)
 RSI         Bollinger Bands
 Bollinger   Volatility 30d
 Volatility  Correlation
         │
         ▼
┌─────────────────┐
│   AI Agent      │  Local LLM (Mistral via Ollama)
│  Text-to-SQL    │  Natural language → SQL → Results
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Dashboard     │  Streamlit + Plotly
│   (3 pages)     │  Dark theme, candlesticks, heatmaps
└─────────────────┘
```

---

## Stack

| Layer | Technology |
|---|---|
| Ingestion | Python, yfinance, DuckDB |
| Transformation | dbt Core, DuckDB adapter |
| Warehouse | DuckDB (local, zero-cost) |
| Orchestration | Manual / extensible to Dagster |
| AI Agent | Mistral (local via Ollama) |
| Dashboard | Streamlit, Plotly |
| Version control | Git, GitHub |

**Cost: €0.** Everything runs locally. No cloud, no subscriptions.

---

## Features

### Market Overview
- Live signal heatmap across all tickers (bullish / bearish / neutral)
- Colour-coded ticker table with MA20, MA50 and daily return
- Market-wide summary metrics

### Ticker Deep Dive
- Candlestick chart with Bollinger Bands, MA20, MA50 overlays
- RSI (14) panel with overbought/oversold zones
- Daily return bar chart
- 30-day volatility metric
- Full correlation matrix across all tracked assets (1 year)

### AI Agent
- Ask questions in plain English — the agent writes SQL and queries your Gold tables
- Powered by Mistral running fully locally via Ollama
- Suggested questions for visitors
- Shows the generated SQL for transparency

---

## Data Pipeline

The pipeline follows a **medallion architecture**:

**Bronze** — raw data landed from Yahoo Finance, typed and renamed. No business logic.

**Silver** — enriched models: daily returns, 20/50-day moving averages, Bollinger Bands (±2σ), RSI (14-period), 30-day rolling volatility.

**Gold** — business-ready marts: `mart_stock_summary` (full history) and `mart_latest_snapshot` (one row per ticker, current state with trend signals).

dbt runs **12 data quality tests** on every pipeline run — null checks, uniqueness, accepted value ranges.

---

## Tickers Tracked

### Stocks
`AAPL` `MSFT` `GOOGL` `AMZN` `JPM` `GS` `BAC`

### ETFs
`EUNL.DE` `QDVA.DE` `IS0E.DE` `DAVV.DE` `WTAI` `EXUS` `XNAS.DE` `DBPG.DE` `DAPP`

---

## Running Locally

### Prerequisites
- Python 3.10+
- [Ollama](https://ollama.com) with Mistral installed (`ollama pull mistral`)
- Git

### Setup

```bash
git clone https://github.com/tomasgg00/FinSight.git
cd FinSight

python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux

pip install yfinance duckdb pandas requests dagster \
            dagster-webserver dbt-duckdb streamlit \
            plotly ollama python-dotenv httpx
```

### Configure dbt

Create `~/.dbt/profiles.yml`:

```yaml
finsight_dbt:
  target: dev
  outputs:
    dev:
      type: duckdb
      path: /absolute/path/to/FinSight/data/finsight.duckdb
      threads: 4
```

### Run the pipeline

```bash
# 1. Ingest data
python ingestion/ingest_prices.py

# 2. Transform with dbt
cd transform/finsight_dbt
dbt run
dbt test
cd ../..

# 3. Launch dashboard
streamlit run dashboard/app.py
```

### Run the AI agent (CLI)

```bash
python ai_agent/agent.py
```

---

## Project Structure

```
FinSight/
├── ingestion/
│   └── ingest_prices.py       # Yahoo Finance → DuckDB
├── transform/
│   └── finsight_dbt/
│       └── models/
│           ├── bronze/        # stg_prices
│           ├── silver/        # int_prices_enriched
│           └── gold/          # mart_stock_summary, mart_latest_snapshot
├── ai_agent/
│   └── agent.py               # Mistral text-to-SQL agent
├── dashboard/
│   └── app.py                 # Streamlit dashboard
├── data/                      # DuckDB file (gitignored)
├── .streamlit/
│   └── config.toml            # Dark theme config
└── .gitignore
```

---

## What I Learned Building This

- End-to-end data pipeline design using the medallion architecture
- dbt modelling: staging, intermediate, and mart layers with full test coverage
- Window functions in SQL: moving averages, RSI, Bollinger Bands, rolling volatility
- Local LLM integration for text-to-SQL using Ollama + Mistral
- Corporate network SSL bypass patterns for Python HTTP libraries
- Building production-grade Streamlit dashboards with Plotly

---

## Roadmap

- [ ] Phase 3 — Smarter AI: plain English summaries + chart generation from questions
- [ ] Phase 4 — Portfolio tracker: P&L on personal ETF holdings, benchmark comparison
- [ ] Deployment to Streamlit Community Cloud with Neon Postgres backend
- [ ] Dagster orchestration for scheduled daily pipeline runs
- [ ] News sentiment ingestion via RSS feeds

---

## Links
- 📊 **dbt docs**: https://tomasgg00.github.io/FinSight
- 🚀 **Live app**: coming soon

---

*Built by [Tomás Gonçalves](https://github.com/tomasgg00)*