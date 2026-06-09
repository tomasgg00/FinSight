with silver as (
    select * from {{ ref('int_prices_enriched') }}
),

summary as (
    select
        price_date,
        ticker,
        close_price,
        volume,
        daily_return_pct,
        ma_20,
        ma_50,
        bb_upper,
        bb_lower,
        rsi_14,
        volatility_30d,

        case
            when close_price > ma_20 and close_price > ma_50 then 'bullish'
            when close_price < ma_20 and close_price < ma_50 then 'bearish'
            else 'neutral'
        end as trend_signal,

        case
            when volume > avg_volume_20d * 1.5 then true
            else false
        end as volume_spike,

        daily_range,
        avg_volume_20d

    from silver
)

select * from summary