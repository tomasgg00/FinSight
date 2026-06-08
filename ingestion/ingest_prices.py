import ssl
import os
import urllib3

ssl._create_default_https_context = ssl._create_unverified_context
os.environ["PYTHONHTTPSVERIFY"] = "0"
os.environ["CURL_CA_BUNDLE"] = ""
os.environ["REQUESTS_CA_BUNDLE"] = ""
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

import yfinance as yf
import duckdb
import pandas as pd
from datetime import datetime
import time

TICKERS = [
    # Original stocks
    "AAPL", "MSFT", "GOOGL", "AMZN", "JPM", "GS", "BAC",
    # Your ETF portfolio
    "EUNL.DE", "QDVA.DE", "IS0E.DE", "DAVV.DE",
    "WTAI", "EXUS", "XNAS.DE", "DBPG.DE", "4GLD", "DAPP"
]
DB_PATH = "data/finsight.duckdb"

def ingest_prices():
    print(f"[{datetime.now()}] Starting price ingestion...")

    all_data = []

    for ticker in TICKERS:
        print(f"  Fetching {ticker}...")
        try:
            df = yf.download(
                ticker,
                period="2y",
                auto_adjust=True,
                progress=False
            )
            if df.empty:
                print(f"    WARNING: No data returned for {ticker}, skipping.")
                continue

            df = df.reset_index()
            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
            df.columns = [c.lower().replace(" ", "_") for c in df.columns]
            df["ticker"] = ticker
            df["ingested_at"] = datetime.now()
            all_data.append(df)
            print(f"    Got {len(df)} rows")
            time.sleep(2)

        except Exception as e:
            print(f"    WARNING: Failed to fetch {ticker} — {e}")
            time.sleep(5)
            continue

    if not all_data:
        print("ERROR: No data fetched.")
        return

    df_all = pd.concat(all_data, ignore_index=True)

    expected = ["date", "open", "high", "low", "close", "volume", "ticker", "ingested_at"]
    df_all = df_all[[c for c in expected if c in df_all.columns]]

    con = duckdb.connect(DB_PATH)
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

    row_count = con.execute("SELECT COUNT(*) FROM raw_prices").fetchone()[0]
    print(f"\n  Loaded {row_count} rows into raw_prices")

    preview = con.execute("""
        SELECT ticker, COUNT(*) as days,
               MIN(date)::DATE as from_date,
               MAX(date)::DATE as to_date
        FROM raw_prices
        GROUP BY ticker
        ORDER BY ticker
    """).df()
    print("\n  Summary:")
    print(preview.to_string(index=False))

    con.close()
    print(f"\n[{datetime.now()}] Done. Database at: {DB_PATH}")

if __name__ == "__main__":
    ingest_prices()