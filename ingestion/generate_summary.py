import os
import ssl
import urllib3

ssl._create_default_https_context = ssl._create_unverified_context
os.environ["PYTHONHTTPSVERIFY"] = "0"
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

import duckdb
import ollama
import pandas as pd
from datetime import datetime

DB_PATH = "data/finsight.duckdb"

def generate_daily_summary():
    print(f"[{datetime.now()}] Generating daily market summary...")

    con = duckdb.connect(DB_PATH)

    con.execute("""
        CREATE TABLE IF NOT EXISTS market_summaries (
            summary_date  DATE,
            generated_at  TIMESTAMP,
            summary       VARCHAR,
            model         VARCHAR
        )
    """)

    snapshot = con.execute("""
        SELECT ticker, close_price, daily_return_pct,
               trend_signal, rsi_14, rsi_signal,
               pct_from_ma20, pct_from_ma50, volume_spike
        FROM main_gold.mart_latest_snapshot
        ORDER BY daily_return_pct DESC
    """).df()

    today = datetime.now().date()
    existing = con.execute("""
        SELECT COUNT(*) FROM market_summaries
        WHERE summary_date = ?
    """, [today]).fetchone()[0]

    if existing > 0:
        print("  Summary already exists for today — skipping.")
        con.close()
        return

    bullish  = snapshot[snapshot["trend_signal"] == "bullish"]["ticker"].tolist()
    bearish  = snapshot[snapshot["trend_signal"] == "bearish"]["ticker"].tolist()
    neutral  = snapshot[snapshot["trend_signal"] == "neutral"]["ticker"].tolist()
    spikes   = snapshot[snapshot["volume_spike"] == True]["ticker"].tolist()
    overbought = snapshot[snapshot["rsi_signal"] == "overbought"]["ticker"].tolist()
    oversold   = snapshot[snapshot["rsi_signal"] == "oversold"]["ticker"].tolist()
    top_gainer = snapshot.iloc[0]
    top_loser  = snapshot.iloc[-1]

    prompt = f"""You are a professional market analyst writing a daily briefing.
Today is {today}. Here is the market data:

BULLISH tickers ({len(bullish)}): {', '.join(bullish) if bullish else 'none'}
BEARISH tickers ({len(bearish)}): {', '.join(bearish) if bearish else 'none'}
NEUTRAL tickers ({len(neutral)}): {', '.join(neutral) if neutral else 'none'}

Top gainer: {top_gainer['ticker']} at {top_gainer['daily_return_pct']:+.2f}%
Top loser:  {top_loser['ticker']} at {top_loser['daily_return_pct']:+.2f}%

Volume spikes (unusual activity): {', '.join(spikes) if spikes else 'none'}
Overbought (RSI >= 70): {', '.join(overbought) if overbought else 'none'}
Oversold (RSI <= 30): {', '.join(oversold) if oversold else 'none'}

Write a concise 3-4 sentence market brief in the style of a Bloomberg morning note.
Be specific — name tickers and numbers. Highlight the most important signals.
Do not use bullet points. Write in flowing prose. Do not mention RSI or MA by name — 
translate them into plain English (e.g. "momentum is fading", "trading at elevated levels").
"""

    response = ollama.chat(
        model="mistral",
        messages=[{"role": "user", "content": prompt}]
    )
    summary = response["message"]["content"].strip()
    print(f"\n  Summary:\n{summary}\n")

    summary_df = pd.DataFrame([{
        "summary_date": today,
        "generated_at": datetime.now(),
        "summary":      summary,
        "model":        "mistral"
    }])
    con.execute("INSERT INTO market_summaries SELECT * FROM summary_df")
    con.close()
    print(f"[{datetime.now()}] Summary saved.")

if __name__ == "__main__":
    generate_daily_summary()