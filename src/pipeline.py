"""Load CSV text into SQLite, stage with rejects, build marts, run quality checks."""
import csv, io, math, os, sqlite3
SQL = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sql")
from .generate import SECURITIES, FUNDS

def _script(name):
    return open(os.path.join(SQL, name)).read()

def connect(path=":memory:"):
    con = sqlite3.connect(path)
    con.create_function("LN", 1, lambda x: math.log(x) if x and x > 0 else None)   # math functions are not in every SQLite build
    con.create_function("EXP", 1, lambda x: math.exp(x) if x is not None else None)
    return con

def load(con, price_csv, trade_csv):
    con.executescript(_script("01_schema.sql"))
    con.executemany("INSERT INTO dim_security VALUES (?,?,?)", SECURITIES)
    con.executemany("INSERT INTO dim_fund VALUES (?,?)", FUNDS)
    pr = list(csv.reader(io.StringIO(price_csv)))[1:]; tr = list(csv.reader(io.StringIO(trade_csv)))[1:]
    con.executemany("INSERT INTO raw_prices VALUES (?,?,?)", pr)
    con.executemany("INSERT INTO raw_trades VALUES (?,?,?,?,?,?,?)", tr)
    return len(pr), len(tr)

def build(con):
    con.executescript(_script("02_staging.sql"))
    con.executescript(_script("03_marts.sql"))

CHECKS = {   # name -> SQL returning the number of violating rows (0 = pass)
    "negative_positions": "SELECT COUNT(*) FROM mart_positions WHERE quantity < -1e-9",
    "duplicate_trade_ids_in_staging": "SELECT COUNT(*) FROM (SELECT trade_id FROM stg_trades GROUP BY trade_id HAVING COUNT(*) > 1)",
    "prices_missing_for_calendar": "SELECT COUNT(*) FROM (SELECT d.security_id, c.price_date FROM dim_security d CROSS JOIN (SELECT DISTINCT price_date FROM stg_prices) c LEFT JOIN stg_prices p ON p.security_id = d.security_id AND p.price_date = c.price_date WHERE p.close IS NULL)",
    "orphan_trades": "SELECT COUNT(*) FROM stg_trades WHERE security_id NOT IN (SELECT security_id FROM dim_security) OR fund_id NOT IN (SELECT fund_id FROM dim_fund)",
    "trades_not_all_accounted": "SELECT ABS((SELECT COUNT(*) FROM raw_trades) - (SELECT COUNT(*) FROM stg_trades) - (SELECT COUNT(*) FROM rejects WHERE source='trades'))",
    "drawdown_positive": "SELECT COUNT(*) FROM mart_fund_daily WHERE drawdown > 1e-12",
}

def run_checks(con):
    return {k: con.execute(q).fetchone()[0] for k, q in CHECKS.items()}

def reject_counts(con):
    return dict(con.execute("SELECT reason, COUNT(*) FROM rejects GROUP BY reason ORDER BY reason").fetchall())
