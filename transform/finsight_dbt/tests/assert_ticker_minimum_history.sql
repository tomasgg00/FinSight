-- Every ticker should have at least 100 days of price history
-- Fewer than 100 days suggests a data ingestion problem
select ticker, count(*) as days
from {{ ref('mart_stock_summary') }}
group by ticker
having count(*) < 100