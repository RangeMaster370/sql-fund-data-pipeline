"""Synthetic fund data: prices and trades as CSV text, with optional injected faults."""
import csv, io
import numpy as np

SECURITIES = [("SEC1", "Alpha Equity", "EUR"), ("SEC2", "Beta Equity", "EUR"), ("SEC3", "Gamma Bond", "EUR"),
              ("SEC4", "Delta Equity", "EUR"), ("SEC5", "Epsilon Bond", "EUR"), ("SEC6", "Zeta Equity", "EUR")]
FUNDS = [("F1", "Growth Fund"), ("F2", "Balanced Fund"), ("F3", "Income Fund")]

def business_days(n, start="2025-01-01"):
    d = np.datetime64(start); out = []
    while len(out) < n:
        if np.is_busday(d): out.append(str(d))
        d += np.timedelta64(1, "D")
    return out

def make(seed=0, n_days=250, n_trades=900, faults=False):
    rng = np.random.default_rng(seed)
    days = business_days(n_days)
    prices = {}
    for i, (sid, _, _) in enumerate(SECURITIES):
        vol = 0.012 if "Equity" in SECURITIES[i][1] else 0.003
        r = rng.normal(0.0002, vol, n_days)
        prices[sid] = np.round(100 * np.exp(np.cumsum(r)), 4)
    price_rows = [[days[t], sid, f"{prices[sid][t]:.4f}"] for sid in prices for t in range(n_days)]
    hold = {(f, s): 0.0 for f, _ in FUNDS for s, _, _ in SECURITIES}
    trades = []
    ts = sorted(rng.choice(n_days, n_trades, replace=True))
    for k, t in enumerate(ts):
        f = FUNDS[rng.integers(len(FUNDS))][0]; s = SECURITIES[rng.integers(len(SECURITIES))][0]
        h = hold[(f, s)]
        if h > 50 and rng.random() < 0.4:
            side, q = "SELL", float(rng.integers(10, int(h * 0.6) + 11) // 1)
            q = min(q, h)
        else:
            side, q = "BUY", float(rng.integers(10, 200))
        hold[(f, s)] += q if side == "BUY" else -q
        trades.append([f"T{k:05d}", days[t], f, s, side, f"{q:.0f}", f"{prices[s][t] * (1 + rng.normal(0, 0.001)):.4f}"])
    injected = {}
    if faults:
        # one example of each fault kind, applied to copies so the clean rows stay valid
        trades.append(list(trades[5]))                                  # duplicate trade id
        injected["duplicate_id"] = 1
        bad = list(trades[10]); bad[0] = "TX001"; bad[5] = "-40"; trades.append(bad); injected["non_positive_quantity"] = 1
        bad = list(trades[11]); bad[0] = "TX002"; bad[3] = "SEC99"; trades.append(bad); injected["unknown_security"] = 1
        bad = list(trades[12]); bad[0] = "TX003"; bad[2] = ""; trades.append(bad); injected["missing_value"] = 1
        bad = list(trades[13]); bad[0] = "TX004"; bad[6] = f"{float(bad[6]) * 1.5:.4f}"; trades.append(bad); injected["price_outside_band"] = 1
        bad = list(trades[14]); bad[0] = "TX005"; bad[1] = "2025-03-01"; trades.append(bad); injected["not_a_business_day"] = 1
        bad = list(trades[15]); bad[0] = "TX006"; bad[4] = "HOLD"; trades.append(bad); injected["invalid_side"] = 1
    return price_rows, trades, injected

def to_csv_text(header, rows):
    b = io.StringIO(); w = csv.writer(b); w.writerow(header); w.writerows(rows); return b.getvalue()
