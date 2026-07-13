# Regime and options-derived signals

Two additional feature modules feed `model.FEATURE_COLUMNS` alongside the
existing technical, investor-flow, fundamental, financial, and news
features: `regime.py` (Hurst exponent + sample entropy) and
`options_signals.py` (25-delta risk reversal + a GEX proxy). Both are
research/backtesting feature generators, not a trading or execution path —
see [Limitations and disclaimer](#limitations-and-disclaimer).

## Module 1: Regime detection (`regime.py`)

Computed per stock, from that stock's own daily closing prices — no
external data source required.

- **Hurst exponent** (`hurst_{window}`, default window 100 trading days):
  estimated via classic rescaled-range (R/S) analysis on daily log returns.
  H > 0.5 reads as trending/persistent price action, H < 0.5 reads as
  mean-reverting, and H ≈ 0.5 is indistinguishable from a random walk.
- **Sample entropy** (`sample_entropy_{window}`): a secondary measure of how
  self-similar/regular recent price action is. Lower values mean more
  repeating structure; higher values mean more randomness.
- **`regime_label`**: `"trending"` / `"mean_reverting"` / `"random_walk"` /
  `"unknown"` (during the warm-up period before `window` days of history
  exist), derived from the Hurst exponent via fixed thresholds (> 0.55
  trending, < 0.45 mean-reverting).
- **`regime_gate`**: a `{-1, 0, 1}` numeric encoding of `regime_label`,
  intended as a future gating/model-switching variable. It is *not* fed into
  today's single global RandomForest model — there is currently only one
  forecasting model in this codebase, so there is nothing to switch between
  yet. Only `hurst_{window}` and `sample_entropy_{window}` are wired into
  `FEATURE_COLUMNS` as raw features.

### Limitations

- R/S analysis is the simpler of the two standard Hurst estimators (the
  other being DFA) and is known to carry small-sample bias — this is why a
  100-day window is the recommended minimum rather than something shorter.
- Fixed 0.45/0.55 thresholds are a reasonable default, not a calibrated
  cutoff for any particular stock or market regime.
- The first `window` rows of any stock's history are `"unknown"`/NaN until
  enough data accumulates; the existing feature pipeline
  (`features.add_prediction_target`) zero-fills these at the end, same as
  it already does for other rolling-window technical indicators.

## Module 2: Options-derived signals (`options_signals.py`)

- **25-delta risk reversal / skew** (`iv_skew_25d`): the implied volatility
  of the ~25-delta call minus the ~25-delta put, from the nearest-expiration
  chain. Negative values (calls cheaper than puts) are the typical equity
  market shape; positive values indicate unusual upside demand.
- **GEX proxy** (`gex_proxy`): a simplified dealer gamma-exposure estimate
  from each contract's open interest and gamma, assuming the common
  convention that dealers are long gamma on calls and short gamma on puts.

### No live vendor is wired in yet

Korea has no liquid single-stock options market, so the only realistic
first target is KRX-listed **KOSPI200 index options** — meaning this is
necessarily a market-wide signal broadcast identically to every ticker on a
given date, not a per-stock signal like the rest of this codebase's
features. `KrxIndexOptionsDataSource` is a stub: `is_available()` always
returns `False`, so `iv_skew_25d` and `gex_proxy` currently resolve to NaN →
zero for every row, contributing no real information to the model today.
The calculation logic (`calculate_25d_risk_reversal`, `calculate_gex_proxy`)
is fully implemented and tested against `SyntheticOptionsDataSource`'s
synthetic chain, so wiring in a real KRX derivatives feed later is a matter
of implementing `KrxIndexOptionsDataSource.get_chain`, not touching the math.

Because it's index-level, a real implementation should compute the signal
once per date and share it across every ticker in a screener run — calling
it once per ticker per date, as `screener.analyze_one_stock` does today,
becomes wasteful the moment a real (rate-limited or paid) vendor is behind it.

### Limitations

- This is a simplified GEX estimate, not a real dealer-positioning model —
  actual dealer inventory isn't observable from public open-interest data.
- The interface and synthetic test data assume a standard listed-options
  chain shape (strike/expiration/OI/greeks); a real KRX adapter may need to
  derive greeks itself if KRX doesn't publish them directly.
- Being index-level rather than per-stock, this signal cannot distinguish
  between individual tickers — every stock in a given day's scan currently
  gets the identical `iv_skew_25d`/`gex_proxy` value.

## Limitations and disclaimer

Both modules are research/backtesting feature generators for the existing
forecasting model. Neither is wired into any live trading or order
execution path, and neither should be. Their outputs — like every other
feature and the resulting Alpha Score in this codebase — are ranked
research signals, not investment advice, a forecast, or a guarantee of
future performance.
