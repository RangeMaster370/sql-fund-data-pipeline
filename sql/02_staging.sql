-- prices: typed, one row per security and day
CREATE TABLE stg_prices AS
SELECT price_date, security_id, CAST(close AS REAL) AS close
FROM raw_prices WHERE close GLOB '[0-9]*' AND CAST(close AS REAL) > 0
GROUP BY price_date, security_id;

-- reject reasons, first failing rule per raw row (rows are numbered so duplicates can be told apart)
DROP TABLE IF EXISTS numbered;
CREATE TEMP TABLE numbered AS
SELECT rowid AS rn, *, ROW_NUMBER() OVER (PARTITION BY trade_id ORDER BY rowid) AS id_occurrence FROM raw_trades;

INSERT INTO rejects (source, row_key, reason)
SELECT 'trades', trade_id || '#' || rn, reason FROM (
  SELECT rn, trade_id,
    CASE
      WHEN trade_id IS NULL OR trade_id = '' OR trade_date = '' OR fund_id = '' OR security_id = '' OR side = '' OR quantity = '' OR price = '' THEN 'missing_value'
      WHEN id_occurrence > 1 THEN 'duplicate_id'
      WHEN side NOT IN ('BUY','SELL') THEN 'invalid_side'
      WHEN NOT (quantity GLOB '[0-9]*') OR CAST(quantity AS REAL) <= 0 THEN 'non_positive_quantity'
      WHEN NOT (price GLOB '[0-9]*') OR CAST(price AS REAL) <= 0 THEN 'non_positive_price'
      WHEN security_id NOT IN (SELECT security_id FROM dim_security) OR fund_id NOT IN (SELECT fund_id FROM dim_fund) THEN 'unknown_security'
      WHEN trade_date NOT IN (SELECT DISTINCT price_date FROM stg_prices) THEN 'not_a_business_day'
      WHEN ABS(CAST(price AS REAL) / (SELECT close FROM stg_prices p WHERE p.price_date = n.trade_date AND p.security_id = n.security_id) - 1) > 0.05 THEN 'price_outside_band'
    END AS reason
  FROM numbered n
) WHERE reason IS NOT NULL;

CREATE TABLE stg_trades AS
SELECT trade_id, trade_date, fund_id, security_id, side, CAST(quantity AS REAL) AS quantity, CAST(price AS REAL) AS price,
       CASE side WHEN 'BUY' THEN 1.0 ELSE -1.0 END * CAST(quantity AS REAL) AS signed_qty
FROM numbered WHERE trade_id || '#' || rn NOT IN (SELECT row_key FROM rejects WHERE source = 'trades');
