-- RSI must always be between 0 and 100
select *
from {{ ref('int_prices_enriched') }}
where rsi_14 is not null
  and (rsi_14 < 0 or rsi_14 > 100)