# Method

## Layers
Raw tables hold every value as text exactly as loaded. Staging casts types and moves each failing row to `rejects` with the first rule it breaks, so no row disappears silently. Marts are rebuilt from staging by plain SQL and are safe to rerun.

## Calculations
Positions are the cumulative signed trade quantity per fund and security over the full price calendar. Fund value is quantity times close. The daily return is time-weighted: (value - flow) / previous value - 1, where flow is the net traded quantity valued at the close, so contributions do not count as performance. The index is exp(sum(ln(1 + return))) and drawdown is index divided by its running maximum minus one. SQLite lacks LN and EXP in some builds, so both are registered as Python functions.

## Verification
The same values are recomputed in NumPy from the clean rows and compared with the marts. Tests inject one fault per reject rule, an oversell and a corrupted mart row to prove the checks fire, and rebuild twice to show the load is repeatable.

## Limits
Synthetic prices, one currency, no cash balance, no corporate actions, no fees. Quality checks catch rule violations, not wrong but plausible values. SQLite is not a warehouse; the SQL would need dialect changes for Databricks or Azure SQL.

## Next steps
Incremental loads, a warehouse dialect, scheduled runs and a data-lineage table.
