import unittest

import numpy as np
import pandas as pd

from regime import add_regime_features, hurst_exponent, sample_entropy


def _make_price_series(values, start="2024-01-01"):
    index = pd.date_range(start, periods=len(values), freq="B")
    return pd.DataFrame({"close": values}, index=index)


class HurstExponentTests(unittest.TestCase):
    def test_random_walk_is_close_to_half(self):
        rng = np.random.default_rng(42)
        returns = rng.normal(loc=0.0, scale=0.01, size=400)
        estimate = hurst_exponent(returns)
        self.assertFalse(np.isnan(estimate))
        self.assertAlmostEqual(estimate, 0.5, delta=0.15)

    def test_strongly_trending_series_exceeds_half(self):
        # A constant drift in returns is NOT persistence -- R/S analysis
        # demeans each chunk, so a flat drift plus i.i.d. noise reads as
        # noise (H ~ 0.5). Genuine trending/persistence needs positive
        # autocorrelation *in the returns themselves* (momentum begets
        # momentum), which is what an AR(1) with positive phi gives us.
        rng = np.random.default_rng(1)
        n = 400
        phi = 0.6
        returns = np.zeros(n)
        for i in range(1, n):
            returns[i] = phi * returns[i - 1] + rng.normal(scale=0.01)
        estimate = hurst_exponent(returns)
        self.assertGreater(estimate, 0.5)

    def test_too_short_series_returns_nan(self):
        self.assertTrue(np.isnan(hurst_exponent([1.0, 2.0, 3.0])))


class SampleEntropyTests(unittest.TestCase):
    def test_periodic_series_has_lower_entropy_than_noise(self):
        rng = np.random.default_rng(3)
        periodic = np.tile([1.0, 2.0, 3.0, 2.0], 50)
        noise = rng.normal(size=200)

        periodic_entropy = sample_entropy(periodic)
        noise_entropy = sample_entropy(noise)

        self.assertFalse(np.isnan(periodic_entropy))
        self.assertFalse(np.isnan(noise_entropy))
        self.assertLess(periodic_entropy, noise_entropy)

    def test_too_short_series_returns_nan(self):
        self.assertTrue(np.isnan(sample_entropy([1.0, 2.0])))

    def test_zero_tolerance_constant_series_returns_nan(self):
        self.assertTrue(np.isnan(sample_entropy(np.ones(50))))


class AddRegimeFeaturesTests(unittest.TestCase):
    def test_adds_expected_columns(self):
        rng = np.random.default_rng(5)
        prices = 100 * np.cumprod(1 + rng.normal(0, 0.01, size=250))
        df = _make_price_series(prices)

        result = add_regime_features(df, window=100)

        for column in (
            "hurst_100",
            "sample_entropy_100",
            "regime_label",
            "regime_gate",
        ):
            self.assertIn(column, result.columns)

    def test_warmup_period_is_unknown_and_neutral(self):
        rng = np.random.default_rng(6)
        prices = 100 * np.cumprod(1 + rng.normal(0, 0.01, size=250))
        df = _make_price_series(prices)

        result = add_regime_features(df, window=100)

        warmup = result.iloc[:50]
        self.assertTrue(warmup["hurst_100"].isna().all())
        self.assertTrue((warmup["regime_label"] == "unknown").all())
        self.assertTrue((warmup["regime_gate"] == 0).all())

    def test_trending_series_is_labeled_trending_with_positive_gate(self):
        # Positive autocorrelation in returns (momentum) is genuine
        # persistence -- unlike a flat drift, which R/S analysis demeans
        # away per chunk and reads as plain noise (H ~ 0.5, not "trending").
        rng = np.random.default_rng(7)
        n = 250
        phi = 0.6
        returns = np.zeros(n)
        for i in range(1, n):
            returns[i] = phi * returns[i - 1] + rng.normal(scale=0.01)
        prices = 100 * np.cumprod(1 + returns)
        df = _make_price_series(prices)

        result = add_regime_features(df, window=100)
        latest = result.iloc[-1]

        self.assertEqual(latest["regime_label"], "trending")
        self.assertEqual(latest["regime_gate"], 1)


if __name__ == "__main__":
    unittest.main()
