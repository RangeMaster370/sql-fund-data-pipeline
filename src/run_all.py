"""Run clean and faulty loads, verify the SQL marts against an independent NumPy calculation, write results/."""
import csv, datetime, hashlib, json, os, platform, sys, time
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
from src.generate import make, to_csv_text, FUNDS, SECURITIES
from src import pipeline as pl
OUT = os.path.join(ROOT, "results")
PH, TH = ["price_date", "security_id", "close"], ["trade_id", "trade_date", "fund_id", "security_id", "side", "quantity", "price"]

def run(faults, seed=0):
    prices, trades, injected = make(seed=seed, faults=faults)
    con = pl.connect(); n_p, n_t = pl.load(con, to_csv_text(PH, prices), to_csv_text(TH, trades)); t0 = time.perf_counter(); pl.build(con)
    return con, dict(price_rows=n_p, trade_rows=n_t, injected=injected, rejected=pl.reject_counts(con), checks=pl.run_checks(con), build_s=round(time.perf_counter() - t0, 3)), prices, trades

def independent_check(con, prices, trades):
    """Recompute fund value and time-weighted return in NumPy from the clean rows; compare with the SQL marts."""
    days = sorted({p[0] for p in prices}); di = {d: i for i, d in enumerate(days)}
    sec = [s[0] for s in SECURITIES]; si = {s: i for i, s in enumerate(sec)}
    close = np.zeros((len(days), len(sec)))
    for d, s, c in prices: close[di[d], si[s]] = float(c)
    worst_v = worst_r = 0.0
    for f, _ in FUNDS:
        net = np.zeros((len(days), len(sec)))
        for tid, d, ff, s, side, q, p in trades:
            if ff == f: net[di[d], si[s]] += float(q) if side == "BUY" else -float(q)
        qty = np.cumsum(net, axis=0); v = (qty * close).sum(axis=1); flow = (net * close).sum(axis=1)
        twr = np.zeros(len(days)); twr[1:] = np.where(v[:-1] > 0, (v[1:] - flow[1:]) / np.where(v[:-1] > 0, v[:-1], 1) - 1, 0)
        rows = con.execute("SELECT value, twr FROM mart_fund_daily WHERE fund_id=? ORDER BY price_date", (f,)).fetchall()
        sv = np.array([r[0] for r in rows]); sr = np.array([r[1] for r in rows])
        worst_v = max(worst_v, float(np.max(np.abs(sv - v)))); worst_r = max(worst_r, float(np.max(np.abs(sr - twr))))
    return worst_v, worst_r

def svg(path, series):
    W, H, L, R, T, B = 900, 460, 70, 20, 40, 60
    allv = [y for _, ys in series for y in ys]; lo, hi = min(allv), max(allv); n = len(series[0][1])
    fx = lambda i: L + i / (n - 1) * (W - L - R); fy = lambda y: H - B - (y - lo) / (hi - lo) * (H - T - B)
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="Arial, sans-serif" font-size="13"><rect width="{W}" height="{H}" fill="#fff"/>',
         f'<text x="{L}" y="24" font-size="15" font-weight="bold" fill="#111827">Fund performance index from the SQL mart (synthetic data)</text>']
    for k in range(6):
        yv = lo + (hi - lo) * k / 5
        o.append(f'<line x1="{L}" y1="{fy(yv):.1f}" x2="{W-R}" y2="{fy(yv):.1f}" stroke="#e5e7eb"/><text x="{L-8}" y="{fy(yv)+4:.1f}" text-anchor="end" fill="#374151">{yv:.3f}</text>')
    o.append(f'<text x="{(L+W-R)/2}" y="{H-24}" text-anchor="middle" fill="#111827">business day</text>')
    for k, (lab, ys) in enumerate(series):
        c = ["#0f766e", "#1e3a8a", "#b45309"][k % 3]
        o.append(f'<polyline points="{" ".join(f"{fx(i):.1f},{fy(y):.1f}" for i, y in enumerate(ys))}" fill="none" stroke="{c}" stroke-width="2"/><line x1="{W-200}" y1="{T+6+k*18}" x2="{W-176}" y2="{T+6+k*18}" stroke="{c}" stroke-width="2"/><text x="{W-170}" y="{T+10+k*18}" fill="#111827">{lab}</text>')
    o.append(f'<line x1="{L}" y1="{H-B}" x2="{W-R}" y2="{H-B}" stroke="#374151"/></svg>')
    open(path, "w").write("\n".join(o))

def main():
    os.makedirs(OUT, exist_ok=True)
    con, clean, prices, trades = run(False)
    wv, wr = independent_check(con, prices, trades)
    perf = con.execute("SELECT fund_id, days, total_return, max_drawdown FROM mart_fund_performance ORDER BY fund_id").fetchall()
    svg(f"{OUT}/fund_index.svg", [(f, [r[0] for r in con.execute("SELECT idx FROM mart_fund_daily WHERE fund_id=? ORDER BY price_date", (f,))]) for f, _ in FUNDS])
    with open(f"{OUT}/fund_performance.csv", "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["fund_id", "days", "total_return", "max_drawdown"]); w.writerows(perf)
    _, faulty, _, _ = run(True)
    detected = {k: faulty["rejected"].get(k, 0) for k in faulty["injected"]}
    with open(f"{OUT}/quality_report.csv", "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["load", "check_or_reason", "count"])
        for load, d in (("clean", clean), ("faulty", faulty)):
            for k, v in d["checks"].items(): w.writerow([load, "check:" + k, v])
            for k, v in d["rejected"].items(): w.writerow([load, "reject:" + k, v])
    summary = dict(clean=clean, faulty=faulty, faults_injected=faulty["injected"], faults_detected=detected,
                   all_injected_faults_detected=all(detected[k] >= faulty["injected"][k] for k in detected),
                   sql_vs_numpy_max_abs_diff_value=wv, sql_vs_numpy_max_abs_diff_return=wr,
                   performance={r[0]: dict(days=r[1], total_return=r[2], max_drawdown=r[3]) for r in perf},
                   note="Synthetic data generated with a fixed seed; no real fund or client data.")
    json.dump(summary, open(f"{OUT}/summary.json", "w"), indent=2)
    rep = ["# Results", "", f"Clean load: {clean['price_rows']} price rows, {clean['trade_rows']} trades, rejected {sum(clean['rejected'].values())}, failed checks {sum(1 for v in clean['checks'].values() if v)}.",
           f"Faulty load: {faulty['trade_rows']} trades with {sum(faulty['injected'].values())} injected faults; rejected by reason {faulty['rejected']}; all injected faults detected: {summary['all_injected_faults_detected']}.",
           f"SQL marts against an independent NumPy calculation: max absolute difference {wv:.2e} (value), {wr:.2e} (daily return).", "", "| fund | days | total return | max drawdown |", "|---|---|---|---|"]
    rep += [f"| {r[0]} | {r[1]} | {r[2]:.4f} | {r[3]:.4f} |" for r in perf]
    open(f"{OUT}/REPORT.md", "w").write("\n".join(rep) + "\n")
    man = {"generated_utc": datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat(), "python": platform.python_version(),
           "results": {fn: hashlib.sha256(open(f"{OUT}/{fn}", "rb").read()).hexdigest() for fn in sorted(os.listdir(OUT)) if fn != "manifest.json"}}
    json.dump(man, open(f"{OUT}/manifest.json", "w"), indent=2)
    print(open(f"{OUT}/REPORT.md").read())

if __name__ == "__main__":
    main()
