import os
import duckdb
import ollama

DB_PATH = "data/finsight.duckdb"

SCHEMA = """
You have access to a DuckDB database with the following tables:

1. main_gold.mart_latest_snapshot  — one row per ticker, most recent trading day
   - ticker           VARCHAR   -- stock symbol e.g. AAPL, MSFT, EUNL.DE
   - latest_date      DATE      -- most recent trading date
   - close_price      DOUBLE    -- latest closing price
   - daily_return_pct DOUBLE    -- return vs previous day in %
   - ma_20            DOUBLE    -- 20-day moving average
   - ma_50            DOUBLE    -- 50-day moving average
   - trend_signal     VARCHAR   -- 'bullish', 'bearish', or 'neutral'
   - volume_spike     BOOLEAN   -- true if volume > 1.5x 20d average
   - avg_volume_20d   DOUBLE    -- 20-day average volume
   - pct_from_ma20    DOUBLE    -- % above/below 20d moving average
   - pct_from_ma50    DOUBLE    -- % above/below 50d moving average

2. main_gold.mart_stock_summary  — full daily history per ticker
   - price_date       DATE      -- trading date
   - ticker           VARCHAR   -- stock symbol
   - close_price      DOUBLE    -- closing price
   - volume           BIGINT    -- trading volume
   - daily_return_pct DOUBLE    -- daily return in %
   - ma_20            DOUBLE    -- 20-day moving average
   - ma_50            DOUBLE    -- 50-day moving average
   - trend_signal     VARCHAR   -- 'bullish', 'bearish', or 'neutral'
   - volume_spike     BOOLEAN   -- true if volume > 1.5x 20d average
   - daily_range      DOUBLE    -- high minus low for the day
   - avg_volume_20d   DOUBLE    -- 20-day average volume

Rules:
- Use mart_latest_snapshot for current/latest questions
- Use mart_stock_summary for historical/trend questions
- Return ONLY the raw SQL query — no explanation, no markdown, no backticks
- Do not include any text before or after the SQL
"""

def call_ollama(question: str) -> str:
    response = ollama.chat(
        model="mistral",
        messages=[
            {
                "role": "system",
                "content": SCHEMA
            },
            {
                "role": "user",
                "content": f"Question: {question}\n\nSQL:"
            }
        ]
    )
    sql = response["message"]["content"].strip()
    sql = sql.replace("```sql", "").replace("```", "").strip()
    return sql

def ask(question: str) -> None:
    print(f"\nQuestion: {question}")
    print("-" * 50)

    try:
        sql = call_ollama(question)
        print(f"Generated SQL:\n{sql}\n")

        con = duckdb.connect(DB_PATH, read_only=True)
        result = con.execute(sql).df()
        con.close()

        print("Result:")
        print(result.to_string(index=False))

    except duckdb.Error as e:
        print(f"SQL error: {e}")
        print("The model generated invalid SQL. Try rephrasing the question.")
    except Exception as e:
        print(f"Error: {e}")

    print("-" * 50)

def chat():
    print("=" * 50)
    print("  FinSight AI Agent")
    print("  Powered by Mistral (local) + DuckDB")
    print("  Free. No API key. Runs on your machine.")
    print("  Type 'exit' to quit")
    print("=" * 50)

    while True:
        try:
            question = input("\nAsk a question: ").strip()
        except KeyboardInterrupt:
            print("\nBye!")
            break

        if question.lower() in ("exit", "quit", "q"):
            print("Bye!")
            break
        if not question:
            continue

        ask(question)

if __name__ == "__main__":
    chat()