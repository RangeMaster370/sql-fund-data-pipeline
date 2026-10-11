DROP TABLE IF EXISTS mart_positions; DROP TABLE IF EXISTS mart_fund_daily; DROP TABLE IF EXISTS mart_fund_performance;

-- end-of-day holdings per fund and security: cumulative signed quantity over the full price calendar
CREATE TABLE mart_positions AS
WITH cal AS (SELECT DISTINCT price_date FROM stg_prices),
pairs AS (SELECT f.fund_id, s.security_id FROM dim_fund f CROSS JOIN dim_security s),
flows AS (SELECT fund_id, security_id, trade_date AS price_date, SUM(signed_qty) AS net_qty FROM stg_trades GROUP BY 1, 2, 3),
grid AS (SELECT p.fund_id, p.security_id, c.price_date, COALESCE(f.net_qty, 0) AS net_qty
         FROM pairs p CROSS JOIN cal c LEFT JOIN flows f ON f.fund_id = p.fund_id AND f.security_id = p.security_id AND f.price_date = c.price_date)
SELECT g.fund_id, g.security_id, g.price_date, g.net_qty,
       SUM(g.net_qty) OVER (PARTITION BY g.fund_id, g.security_id ORDER BY g.price_date ROWS UNBOUNDED PRECEDING) AS quantity,
       pr.close,
       g.net_qty * pr.close AS flow_value
FROM grid g JOIN stg_prices pr ON pr.price_date = g.price_date AND pr.security_id = g.security_id;

-- fund value, time-weighted daily return (flows valued at the close), cumulative index and drawdown
CREATE TABLE mart_fund_daily AS
WITH v AS (SELECT fund_id, price_date, SUM(quantity * close) AS value, SUM(flow_value) AS flow FROM mart_positions GROUP BY 1, 2),
r AS (SELECT *, LAG(value) OVER (PARTITION BY fund_id ORDER BY price_date) AS prev_value FROM v),
t AS (SELECT *, CASE WHEN prev_value > 0 THEN (value - flow) / prev_value - 1 ELSE 0 END AS twr FROM r),
c AS (SELECT *, EXP(SUM(LN(1 + twr)) OVER (PARTITION BY fund_id ORDER BY price_date ROWS UNBOUNDED PRECEDING)) AS idx FROM t)
SELECT fund_id, price_date, value, flow, twr, idx,
       idx / MAX(idx) OVER (PARTITION BY fund_id ORDER BY price_date ROWS UNBOUNDED PRECEDING) - 1 AS drawdown
FROM c;

CREATE TABLE mart_fund_performance AS
SELECT fund_id, COUNT(*) AS days, MAX(idx) AS peak_index, MIN(drawdown) AS max_drawdown,
       (SELECT idx FROM mart_fund_daily d2 WHERE d2.fund_id = d.fund_id ORDER BY price_date DESC LIMIT 1) - 1 AS total_return
FROM mart_fund_daily d GROUP BY fund_id;
