# SQL fund data pipeline

A small SQL data pipeline in SQLite and Python: raw CSV text, staging with typed rows and a reject table, marts built with SQL window functions, and automated data-quality checks. Built October 2026 as a practice project on **synthetic** fund prices and trades (fixed seed). It uses no real fund, client or employer data.

## What it does
- `sql/01_schema.sql` raw tables and dimensions, `sql/02_staging.sql` typing, rule-by-rule rejects and staged trades, `sql/03_marts.sql` end-of-day positions, fund value, time-weighted daily return, cumulative index and drawdown (window functions: `SUM OVER`, `LAG`, running `MAX`).
- Seven reject rules (duplicate id, missing value, invalid side, non-positive quantity or price, unknown security or fund, not a business day, price more than 5 % from the close). Every raw trade ends up either staged or in `rejects`.
- Six SQL quality checks on the marts (negative positions, duplicates, missing prices, orphans, row accounting, drawdown sign).

## Results (from `results/summary.json`)
- Clean load: 1500 price rows and 900 trades, 0 rejected, 0 failed checks.
- Faulty load: 7 injected faults, one per rule, all 7 rejected with the right reason.
- The SQL marts match an independent NumPy calculation: max absolute difference 1.2e-10 in fund value and 4.4e-16 in daily return.
- Three funds over 250 business days: total return -4.67%, -1.62%, 0.45%; these are properties of random synthetic prices, not findings.

## Not done
No cloud database, no Databricks or Azure, no scheduler, no incremental loads, no real market data, no cash or currency handling (holdings value only, one currency).

## Run
```
pip install -r requirements.txt
python3 -m pytest -q tests
python3 src/run_all.py
```
