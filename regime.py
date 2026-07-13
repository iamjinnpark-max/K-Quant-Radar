"""Rolling market-regime detection: Hurst exponent + sample entropy.

Both statistics are computed over daily log returns of a single stock's
closing price and describe the same thing from two angles: whether recent
price action looks trending (persistent), mean-reverting (anti-persistent),
or indistinguishable from a random walk.
"""
import numpy as np
import pandas as pd

DEFAULT_WINDOW = 100
TRENDING_THRESHOLD = 0.55
MEAN_REVERTING_THRESHOLD = 0.45


def hurst_exponent(series, min_chunk: int = 10) -> float:
    """Estimate the Hurst exponent via classic rescaled-range (R/S) analysis.

    H > 0.5 indicates a trending/persistent series, H < 0.5 indicates
    mean-reversion, and H == 0.5 matches a random walk. This is the simpler
    of the two methods the literature offers (the other being DFA); it is
    known to carry small-sample bias, which is why a 100-point window is the
    recommended minimum rather than something shorter.
    """
    values = np.asarray(series, dtype=float)
    values = values[~np.isnan(values)]
    n = len(values)
    if n < min_chunk * 2:
        return float("nan")

    max_chunk = n // 2
    candidate_sizes = np.unique(
        np.logspace(np.log10(min_chunk), np.log10(max_chunk), num=8).astype(int)
    )

    log_sizes = []
    log_rs = []
    for size in candidate_sizes:
        if size < min_chunk:
            continue
        n_chunks = n // size
        if n_chunks < 1:
            continue

        rs_per_chunk = []
        for chunk_index in range(n_chunks):
            chunk = values[chunk_index * size : (chunk_index + 1) * size]
            std = chunk.std()
            if std == 0:
                continue
            deviations = np.cumsum(chunk - chunk.mean())
            rescaled_range = deviations.max() - deviations.min()
            rs_per_chunk.append(rescaled_range / std)

        if rs_per_chunk:
            log_sizes.append(np.log(size))
            log_rs.append(np.log(np.mean(rs_per_chunk)))

    if len(log_sizes) < 2:
        return float("nan")

    slope, _intercept = np.polyfit(log_sizes, log_rs, 1)
    return float(np.clip(slope, 0.0, 1.0))


def sample_entropy(series, m: int = 2, r: float | None = None) -> float:
    """Estimate sample entropy (Richman & Moorman, 2000).

    Lower values mean the series repeats similar patterns (more regular /
    predictable); higher values mean less self-similarity (more random).
    ``r`` defaults to 0.2 * std(series), the conventional choice.
    """
    values = np.asarray(series, dtype=float)
    values = values[~np.isnan(values)]
    n = len(values)
    if n <= m + 1:
        return float("nan")

    tolerance = r if r is not None else 0.2 * values.std()
    if tolerance == 0:
        return float("nan")

    def _count_matches(template_len: int) -> int:
        limit = n - m
        templates = np.array(
            [values[i : i + template_len] for i in range(limit)]
        )
        count = 0
        for i in range(limit):
            distances = np.max(np.abs(templates - templates[i]), axis=1)
            count += int(np.sum(distances <= tolerance)) - 1  # exclude self
        return count

    b = _count_matches(m)
    a = _count_matches(m + 1)
    if a == 0 or b == 0:
        return float("nan")
    return float(-np.log(a / b))


def _classify_regime(hurst: float) -> str:
    if np.isnan(hurst):
        return "unknown"
    if hurst > TRENDING_THRESHOLD:
        return "trending"
    if hurst < MEAN_REVERTING_THRESHOLD:
        return "mean_reverting"
    return "random_walk"


_REGIME_GATE = {
    "trending": 1,
    "random_walk": 0,
    "mean_reverting": -1,
    "unknown": 0,
}


def add_regime_features(
    df: pd.DataFrame,
    window: int = DEFAULT_WINDOW,
    price_column: str = "close",
) -> pd.DataFrame:
    """Append rolling regime-detection columns to a price DataFrame.

    Adds, per row:
      - ``hurst_{window}``: rolling Hurst exponent, a raw model feature.
      - ``sample_entropy_{window}``: rolling sample entropy, a raw model
        feature.
      - ``regime_label``: categorical description ("trending",
        "mean_reverting", "random_walk", or "unknown" during warm-up).
      - ``regime_gate``: {-1, 0, 1} numeric encoding of ``regime_label``,
        intended as a future gating/model-switching variable rather than a
        feature fed directly into a single global model today.

    All columns are NaN for the first ``window`` rows until enough history
    accumulates; callers already fillna(0) at the end of the feature
    pipeline (see ``features.add_prediction_target``), which is the
    intended way these warm-up NaNs get resolved.
    """
    df = df.copy()
    log_returns = np.log(df[price_column]).diff()

    hurst_column = f"hurst_{window}"
    entropy_column = f"sample_entropy_{window}"

    df[hurst_column] = log_returns.rolling(window, min_periods=window).apply(
        hurst_exponent, raw=True
    )
    df[entropy_column] = log_returns.rolling(window, min_periods=window).apply(
        sample_entropy, raw=True
    )

    df["regime_label"] = df[hurst_column].map(_classify_regime)
    df["regime_gate"] = df["regime_label"].map(_REGIME_GATE)

    return df
