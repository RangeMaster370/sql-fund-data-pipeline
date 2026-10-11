import os, sys
import pytest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src import pipeline as pl
from src.generate import make, to_csv_text
from src.run_all import run, independent_check, PH, TH

def test_clean_load_has_no_rejects_and_all_checks_pass():
    con, r, _, _ = run(False)
    assert r["rejected"] == {} and all(v == 0 for v in r["checks"].values())
    assert r["trade_rows"] == 900

@pytest.mark.parametrize("reason", ["duplicate_id", "non_positive_quantity", "unknown_security", "missing_value",
                                    "price_outside_band", "not_a_business_day", "invalid_side"])
def test_each_injected_fault_is_rejected_with_its_own_reason(reason):
    _, r, _, _ = run(True)
    assert r["injected"][reason] == 1 and r["rejected"].get(reason) == 1

def test_every_raw_trade_is_accounted_for():
    _, r, _, _ = run(True)
    assert r["checks"]["trades_not_all_accounted"] == 0

def test_rejected_rows_do_not_reach_the_marts():
    con, _, _, _ = run(True)
    assert con.execute("SELECT COUNT(*) FROM stg_trades WHERE trade_id LIKE 'TX%'").fetchone()[0] == 0

def test_sql_marts_match_independent_numpy_calculation():
    con, _, prices, trades = run(False)
    wv, wr = independent_check(con, prices, trades)
    assert wv < 1e-6 and wr < 1e-12

def test_rebuild_is_idempotent():
    prices, trades, _ = make(seed=1)
    con = pl.connect()
    out = []
    for _ in range(2):
        pl.load(con, to_csv_text(PH, prices), to_csv_text(TH, trades)); pl.build(con)
        out.append(con.execute("SELECT fund_id, ROUND(SUM(value), 6) FROM mart_fund_daily GROUP BY 1 ORDER BY 1").fetchall())
    assert out[0] == out[1]

def test_negative_position_check_catches_an_oversell():
    prices, trades, _ = make(seed=2)
    trades.append(["TZ001", trades[0][1], trades[0][2], trades[0][3], "SELL", "999999", trades[0][6]])
    con = pl.connect(); pl.load(con, to_csv_text(PH, prices), to_csv_text(TH, trades)); pl.build(con)
    assert pl.run_checks(con)["negative_positions"] > 0

def test_drawdown_check_catches_a_corrupted_mart():
    con, _, _, _ = run(False)
    con.execute("UPDATE mart_fund_daily SET drawdown = 0.5 WHERE rowid = 1")
    assert pl.run_checks(con)["drawdown_positive"] == 1

def test_max_drawdown_is_never_positive():
    con, _, _, _ = run(False)
    assert con.execute("SELECT MAX(max_drawdown) FROM mart_fund_performance").fetchone()[0] <= 0
