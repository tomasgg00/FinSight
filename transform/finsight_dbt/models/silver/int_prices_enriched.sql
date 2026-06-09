{{
    config(
        materialized='incremental',
        unique_key=['ticker', 'price_date']
    )
}}

with base as (
    select * from {{ ref('stg_prices') }}
),

-- Step 1: basic metrics and moving averages
step1 as (
    select
        price_date,
        ticker,
        open_price,
        high_price,
        low_price,
        close_price,
        volume,

        round(avg(close_price) over (
            partition by ticker order by price_date
            rows between 19 preceding and current row
        ), 4) as ma_20,

        round(avg(close_price) over (
            partition by ticker order by price_date
            rows between 49 preceding and current row
        ), 4) as ma_50,

        round(avg(close_price) over (
            partition by ticker order by price_date
            rows between 19 preceding and current row
        ) + 2 * stddev(close_price) over (
            partition by ticker order by price_date
            rows between 19 preceding and current row
        ), 4) as bb_upper,

        round(avg(close_price) over (
            partition by ticker order by price_date
            rows between 19 preceding and current row
        ) - 2 * stddev(close_price) over (
            partition by ticker order by price_date
            rows between 19 preceding and current row
        ), 4) as bb_lower,

        round(high_price - low_price, 4) as daily_range,

        round(avg(volume) over (
            partition by ticker order by price_date
            rows between 19 preceding and current row
        ), 0) as avg_volume_20d,

        ingested_at

    from base
),

-- Step 2: daily return and price change
step2 as (
    select
        *,
        round(
            (close_price - lag(close_price) over (
                partition by ticker order by price_date
            )) / nullif(lag(close_price) over (
                partition by ticker order by price_date
            ), 0) * 100,
        4) as daily_return_pct,

        close_price - lag(close_price) over (
            partition by ticker order by price_date
        ) as price_change

    from step1
),

-- Step 3: RSI gains and losses
step3 as (
    select
        *,
        round(avg(case when price_change > 0 then price_change else 0 end) over (
            partition by ticker order by price_date
            rows between 13 preceding and current row
        ), 6) as avg_gain,

        round(avg(case when price_change < 0 then abs(price_change) else 0 end) over (
            partition by ticker order by price_date
            rows between 13 preceding and current row
        ), 6) as avg_loss

    from step2
),

-- Step 4: RSI and volatility
step4 as (
    select
        *,
        round(case
            when avg_loss = 0 then 100
            else 100 - (100 / (1 + (avg_gain / nullif(avg_loss, 0))))
        end, 2) as rsi_14,

        round(stddev(daily_return_pct) over (
            partition by ticker order by price_date
            rows between 29 preceding and current row
        ), 4) as volatility_30d

    from step3
)

select
    price_date,
    ticker,
    open_price,
    high_price,
    low_price,
    close_price,
    volume,
    daily_return_pct,
    ma_20,
    ma_50,
    bb_upper,
    bb_lower,
    daily_range,
    avg_volume_20d,
    volatility_30d,
    rsi_14,
    ingested_at

from step4

{% if is_incremental() %}
    where price_date > (select max(price_date) from {{ this }})
{% endif %}