with latest as (
    select *,
        row_number() over (
            partition by ticker
            order by price_date desc
        ) as rn
    from {{ ref('mart_stock_summary') }}
),

snapshot as (
    select
        ticker,
        price_date as latest_date,
        close_price,
        daily_return_pct,
        ma_20,
        ma_50,
        trend_signal,
        volume_spike,
        avg_volume_20d,
        rsi_14,
        volatility_30d,
        bb_upper,
        bb_lower,

        -- % distance from 20d MA
        round((close_price - ma_20) / nullif(ma_20, 0) * 100, 2) as pct_from_ma20,

        -- % distance from 50d MA
        round((close_price - ma_50) / nullif(ma_50, 0) * 100, 2) as pct_from_ma50,

        -- RSI signal
        case
            when rsi_14 >= 70 then 'overbought'
            when rsi_14 <= 30 then 'oversold'
            else 'neutral'
        end as rsi_signal

    from latest
    where rn = 1
)

select * from snapshot