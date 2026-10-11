DROP TABLE IF EXISTS raw_prices; DROP TABLE IF EXISTS raw_trades; DROP TABLE IF EXISTS dim_security; DROP TABLE IF EXISTS dim_fund;
DROP TABLE IF EXISTS stg_prices; DROP TABLE IF EXISTS stg_trades; DROP TABLE IF EXISTS rejects;
CREATE TABLE raw_prices (price_date TEXT, security_id TEXT, close TEXT);
CREATE TABLE raw_trades (trade_id TEXT, trade_date TEXT, fund_id TEXT, security_id TEXT, side TEXT, quantity TEXT, price TEXT);
CREATE TABLE dim_security (security_id TEXT PRIMARY KEY, name TEXT NOT NULL, currency TEXT NOT NULL);
CREATE TABLE dim_fund (fund_id TEXT PRIMARY KEY, name TEXT NOT NULL);
CREATE TABLE rejects (source TEXT, row_key TEXT, reason TEXT);
