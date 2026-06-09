{% snapshot snap_market_signals %}

{{
    config(
        target_schema='snapshots',
        unique_key='ticker',
        strategy='check',
        check_cols=[
            'trend_signal',
            'rsi_signal',
            'volume_spike',
            'close_price'
        ]
    )
}}

select
    ticker,
    latest_date,
    close_price,
    daily_return_pct,
    ma_20,
    ma_50,
    trend_signal,
    rsi_14,
    rsi_signal,
    volatility_30d,
    volume_spike,
    pct_from_ma20,
    pct_from_ma50
from {{ ref('mart_latest_snapshot') }}

{% endsnapshot %}