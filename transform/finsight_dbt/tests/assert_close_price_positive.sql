-- Close price must always be positive
select *
from {{ ref('int_prices_enriched') }}
where close_price <= 0