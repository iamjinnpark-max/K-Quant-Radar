"""Options-derived signals: 25-delta risk reversal (skew) and a GEX proxy.

No live options-chain vendor is wired in yet. The calculation logic is
written against a vendor-agnostic chain schema behind an abstract
``OptionsDataSource`` interface, so a real adapter can be dropped in later
without touching the math. Until then, ``KrxIndexOptionsDataSource`` (the
intended first real target, per KOSPI200 index options) reports itself as
unavailable and the resulting feature columns are neutral (NaN, later
zero-filled by the existing pipeline) rather than raising.

Chain schema expected by the calculation functions, one row per contract:
    strike            float
    expiration         date
    option_type       "call" | "put"
    open_interest     int
    implied_vol       float (annualized, decimal e.g. 0.20)
    delta             float (calls in [0, 1], puts in [-1, 0])
    gamma             float
    underlying_price  float (same value repeated on every row)
"""
from abc import ABC, abstractmethod
from datetime import date, timedelta

import numpy as np
import pandas as pd

CHAIN_COLUMNS = [
    "strike",
    "expiration",
    "option_type",
    "open_interest",
    "implied_vol",
    "delta",
    "gamma",
    "underlying_price",
]


class OptionsDataSource(ABC):
    """Vendor-agnostic interface for fetching an options chain."""

    @abstractmethod
    def is_available(self, underlying: str, as_of: date) -> bool:
        """Whether a real chain can be fetched for this underlying/date."""

    @abstractmethod
    def get_chain(self, underlying: str, as_of: date) -> pd.DataFrame:
        """Return a chain DataFrame matching ``CHAIN_COLUMNS``.

        Only called when ``is_available`` returns True.
        """


class SyntheticOptionsDataSource(OptionsDataSource):
    """Deterministic synthetic chain generator, for tests only.

    Produces a simple equity-like volatility smile (higher IV away from the
    money, skewed so downside puts are richer than upside calls) so the
    skew/GEX calculations have something realistic-shaped to run against
    without needing a live vendor.
    """

    def __init__(self, spot: float = 100.0, seed: int = 7):
        self.spot = spot
        self._rng = np.random.default_rng(seed)

    def is_available(self, underlying: str, as_of: date) -> bool:
        return True

    def get_chain(self, underlying: str, as_of: date) -> pd.DataFrame:
        spot = self.spot
        strikes = np.arange(spot * 0.7, spot * 1.31, spot * 0.025)
        expiration = as_of + timedelta(days=30)

        rows = []
        for strike in strikes:
            moneyness = strike / spot
            base_iv = 0.20
            smile = 0.15 * (moneyness - 1) ** 2
            skew = -0.05 * (moneyness - 1)  # downside richer, typical equity skew
            iv = max(0.05, base_iv + smile + skew)

            for option_type in ("call", "put"):
                delta = self._approx_delta(option_type, moneyness, iv)
                gamma = self._approx_gamma(moneyness, iv)
                rows.append(
                    {
                        "strike": float(strike),
                        "expiration": expiration,
                        "option_type": option_type,
                        "open_interest": int(self._rng.integers(100, 5000)),
                        "implied_vol": float(iv),
                        "delta": float(delta),
                        "gamma": float(gamma),
                        "underlying_price": spot,
                    }
                )
        return pd.DataFrame(rows, columns=CHAIN_COLUMNS)

    @staticmethod
    def _approx_delta(option_type: str, moneyness: float, iv: float) -> float:
        # Logistic approximation of delta vs. moneyness -- good enough shape
        # for synthetic test data, not a real Black-Scholes delta. Delta
        # falls as moneyness (strike/spot) rises: a deep ITM call
        # (moneyness << 1) should be near 1.0, a deep OTM call
        # (moneyness >> 1) near 0.0.
        z = (moneyness - 1) / max(iv, 0.05)
        call_delta = 1 / (1 + np.exp(4 * z))
        return call_delta if option_type == "call" else call_delta - 1

    @staticmethod
    def _approx_gamma(moneyness: float, iv: float) -> float:
        return float(
            np.exp(-((moneyness - 1) ** 2) / (2 * (iv**2))) / (iv + 1e-6)
        )


class KrxIndexOptionsDataSource(OptionsDataSource):
    """Intended real adapter for KRX-listed KOSPI200 index options.

    NOT YET IMPLEMENTED. Korea has no liquid single-stock options market, so
    this is necessarily an index-level (KOSPI200) signal broadcast across
    every ticker on a given date, not a per-stock one like the rest of this
    codebase's features -- a real limitation to keep in mind once this is
    wired up for real, not just a placeholder detail.

    ``is_available`` always returns False so callers degrade to a neutral
    signal instead of crashing; ``get_chain`` raises if called anyway (it
    should never be called without checking availability first).
    """

    def is_available(self, underlying: str, as_of: date) -> bool:
        return False

    def get_chain(self, underlying: str, as_of: date) -> pd.DataFrame:
        raise NotImplementedError(
            "KRX KOSPI200 options adapter is not implemented yet; "
            "call is_available() before calling get_chain()."
        )


def _closest_by_delta(chain: pd.DataFrame, option_type: str, target_delta: float):
    subset = chain[chain["option_type"] == option_type]
    if subset.empty:
        return None
    closest_index = (subset["delta"] - target_delta).abs().idxmin()
    return subset.loc[closest_index]


def calculate_25d_risk_reversal(chain: pd.DataFrame) -> float:
    """25-delta call IV minus 25-delta put IV, per expiration's nearest match.

    Positive values mean calls are relatively richer (upside skew); negative
    values -- the equity-market norm -- mean puts are relatively richer
    (downside skew / crash protection demand).
    """
    if chain is None or chain.empty:
        return float("nan")

    call_25d = _closest_by_delta(chain, "call", 0.25)
    put_25d = _closest_by_delta(chain, "put", -0.25)
    if call_25d is None or put_25d is None:
        return float("nan")
    return float(call_25d["implied_vol"] - put_25d["implied_vol"])


def calculate_gex_proxy(chain: pd.DataFrame, contract_multiplier: int = 100) -> float:
    """Simplified dealer gamma-exposure estimate from open interest and gamma.

    Assumes the common convention that dealers are long gamma on calls and
    short gamma on puts they've sold; this is a coarse approximation, not a
    real dealer-positioning model (real GEX needs actual dealer inventory,
    which isn't observable). Scaled down (/1e9) purely so the magnitude is a
    manageable model feature rather than a raw notional dollar figure.
    """
    if chain is None or chain.empty:
        return float("nan")

    spot = float(chain["underlying_price"].iloc[0])
    sign = np.where(chain["option_type"] == "call", 1, -1)
    exposure = sign * chain["open_interest"] * chain["gamma"] * (spot**2) * contract_multiplier
    return float(np.sum(exposure) / 1e9)


def compute_options_signal(
    data_source: OptionsDataSource, underlying: str, as_of: date
) -> dict:
    """Return {"iv_skew_25d": ..., "gex_proxy": ...} for one underlying/date.

    Returns NaN for both when the data source has nothing available, rather
    than raising -- callers should never need to special-case "no vendor
    configured yet".
    """
    if not data_source.is_available(underlying, as_of):
        return {"iv_skew_25d": float("nan"), "gex_proxy": float("nan")}

    chain = data_source.get_chain(underlying, as_of)
    return {
        "iv_skew_25d": calculate_25d_risk_reversal(chain),
        "gex_proxy": calculate_gex_proxy(chain),
    }


def add_options_features(
    df: pd.DataFrame,
    data_source: OptionsDataSource,
    underlying: str = "KOSPI200",
) -> pd.DataFrame:
    """Broadcast a market-wide options signal onto a per-ticker price frame.

    Because the only available target is an index-level signal (see
    ``KrxIndexOptionsDataSource``), the same value is applied to every
    ticker on a given date rather than being stock-specific -- unlike every
    other feature in this codebase. Computes one signal per unique date in
    ``df``'s index, not per row, to avoid redundant work across a long
    per-ticker history.

    Once a real adapter is wired in, callers that run this across many
    tickers for the same date range (see ``screener.run_screener``) should
    precompute and share a single result instead of calling this per ticker,
    to avoid refetching the same index-level chain repeatedly.
    """
    df = df.copy()
    unique_dates = df.index.normalize().unique()

    signal_by_date = {
        as_of: compute_options_signal(data_source, underlying, as_of.date())
        for as_of in unique_dates
    }
    signal_df = pd.DataFrame.from_dict(signal_by_date, orient="index")

    normalized_index = df.index.normalize()
    df["iv_skew_25d"] = normalized_index.map(signal_df["iv_skew_25d"])
    df["gex_proxy"] = normalized_index.map(signal_df["gex_proxy"])
    return df
