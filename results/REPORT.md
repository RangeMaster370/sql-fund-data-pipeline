# Results

Clean load: 1500 price rows, 900 trades, rejected 0, failed checks 0.
Faulty load: 907 trades with 7 injected faults; rejected by reason {'duplicate_id': 1, 'invalid_side': 1, 'missing_value': 1, 'non_positive_quantity': 1, 'not_a_business_day': 1, 'price_outside_band': 1, 'unknown_security': 1}; all injected faults detected: True.
SQL marts against an independent NumPy calculation: max absolute difference 1.16e-10 (value), 4.44e-16 (daily return).

| fund | days | total return | max drawdown |
|---|---|---|---|
| F1 | 250 | -0.0467 | -0.0688 |
| F2 | 250 | -0.0162 | -0.0854 |
| F3 | 250 | 0.0045 | -0.0632 |
