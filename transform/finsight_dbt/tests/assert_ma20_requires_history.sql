-- MA20 should only be null for the first 19 rows per ticker
-- If a ticker has more than 19 rows, all MA20 values should be populated
select ticker
from {{ ref('int_prices_enriched') }}
group by ticker
having count(*) > 19
   and count(ma_20) < count(*) - 19