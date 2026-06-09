with source as (
    select * from raw_prices
),

renamed as (
    select
        date::date          as price_date,
        ticker,
        open::double        as open_price,
        high::double        as high_price,
        low::double         as low_price,
        close::double       as close_price,
        volume::bigint      as volume,
        ingested_at
    from source
)

select * from renamed