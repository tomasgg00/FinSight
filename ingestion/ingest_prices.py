import ssl
import os
import urllib3
import time

ssl._create_default_https_context = ssl._create_unverified_context
os.environ["PYTHONHTTPSVERIFY"] = "0"
os.environ["CURL_CA_BUNDLE"] = ""
os.environ["REQUESTS_CA_BUNDLE"] = ""
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

import yfinance as yf
import duckdb
import pandas as pd
import requests
from datetime import datetime
from schemas import PriceRecord

TICKERS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "JPM", "GS", "BAC",
    "EUNL.DE", "QDVA.DE", "IS0E.DE", "DAVV.DE",
    "WTAI", "EXUS", "XNAS.DE", "DBPG.DE", "DAPP"
]
DB_PATH = "data/finsight.duckdb"

def get_session():
    session = requests.Session()
    session.verify = False
    return session

def init_observability(con):
    con.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_runs (
            run_id          VARCHAR,
            run_at          TIMESTAMP,
            status          VARCHAR,
            total_rows      INTEGER,
            tickers_success INTEGER,
            tickers_failed  INTEGER,
            duration_secs   DOUBLE,
            error_message   VARCHAR
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_run_details (
            run_id      VARCHAR,
            ticker      VARCHAR,
            rows_loaded INTEGER,
            status      VARCHAR,
            error       VARCHAR,
            loaded_at   TIMESTAMP
        )
    """)

def validate_dataframe(df, ticker):
    validation_errors = 0
    for _, row in df.iterrows():
        try:
            PriceRecord(
                date=row["date"],
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=int(row["volume"]),
                ticker=ticker,
                ingested_at=row["ingested_at"]
            )
        except Exception as e:
            validation_errors += 1
    return validation_errors

def ingest_prices():
    run_id    = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_start = datetime.now()
    print(f"[{run_start}] Starting ingestion — run_id: {run_id}")

    session     = get_session()
    all_data    = []
    run_details = []
    failed      = []

    for ticker in TICKERS:
        print(f"  Fetching {ticker}...")
        try:
            df = yf.download(
                ticker, period="2y",
                auto_adjust=True, progress=False
            )
            if df.empty:
                raise ValueError("No data returned")

            df = df.reset_index()
            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
            df.columns = [c.lower().replace(" ", "_") for c in df.columns]
            df["ticker"]      = ticker
            df["ingested_at"] = datetime.now()

            # Pydantic schema validation
            validation_errors = validate_dataframe(df, ticker)
            if validation_errors > 0:
                print(f"    WARNING: {validation_errors} rows failed schema validation")
            else:
                print(f"    All {len(df)} rows passed schema validation")

            all_data.append(df)

            run_details.append({
                "run_id": run_id, "ticker": ticker,
                "rows_loaded": len(df), "status": "success",
                "error": None, "loaded_at": datetime.now()
            })
            print(f"    Got {len(df)} rows")
            time.sleep(2)

        except Exception as e:
            print(f"    WARNING: Failed {ticker} — {e}")
            failed.append(ticker)
            run_details.append({
                "run_id": run_id, "ticker": ticker,
                "rows_loaded": 0, "status": "failed",
                "error": str(e), "loaded_at": datetime.now()
            })
            time.sleep(5)

    con = duckdb.connect(DB_PATH)
    init_observability(con)

    total_rows = 0
    status     = "success"
    error_msg  = None

    if all_data:
        df_all = pd.concat(all_data, ignore_index=True)
        expected = ["date", "open", "high", "low", "close",
                    "volume", "ticker", "ingested_at"]
        df_all = df_all[[c for c in expected if c in df_all.columns]]

        con.execute("""
            CREATE TABLE IF NOT EXISTS raw_prices (
                date        TIMESTAMP,
                open        DOUBLE,
                high        DOUBLE,
                low         DOUBLE,
                close       DOUBLE,
                volume      BIGINT,
                ticker      VARCHAR,
                ingested_at TIMESTAMP
            )
        """)
        con.execute("DELETE FROM raw_prices")
        con.execute("INSERT INTO raw_prices SELECT * FROM df_all")
        total_rows = con.execute("SELECT COUNT(*) FROM raw_prices").fetchone()[0]
        print(f"\n  Loaded {total_rows} rows into raw_prices")
    else:
        status    = "failed"
        error_msg = "No data fetched for any ticker"
        print("ERROR: No data fetched.")

    details_df = pd.DataFrame(run_details)
    con.execute("INSERT INTO pipeline_run_details SELECT * FROM details_df")

    duration = (datetime.now() - run_start).total_seconds()
    run_log  = pd.DataFrame([{
        "run_id":          run_id,
        "run_at":          run_start,
        "status":          status,
        "total_rows":      total_rows,
        "tickers_success": len(TICKERS) - len(failed),
        "tickers_failed":  len(failed),
        "duration_secs":   round(duration, 2),
        "error_message":   error_msg
    }])
    con.execute("INSERT INTO pipeline_runs SELECT * FROM run_log")

    print(f"\n  Run summary:")
    print(con.execute("SELECT * FROM pipeline_runs ORDER BY run_at DESC LIMIT 3").df().to_string(index=False))

    con.close()
    print(f"\n[{datetime.now()}] Done in {duration:.1f}s")

if __name__ == "__main__":
    ingest_prices()