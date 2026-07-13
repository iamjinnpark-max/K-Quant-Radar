import unittest
from datetime import date

import numpy as np
import pandas as pd

from options_signals import (
    CHAIN_COLUMNS,
    KrxIndexOptionsDataSource,
    SyntheticOptionsDataSource,
    add_options_features,
    calculate_25d_risk_reversal,
    calculate_gex_proxy,
    compute_options_signal,
)


class SyntheticOptionsDataSourceTests(unittest.TestCase):
    def test_chain_has_expected_schema(self):
        source = SyntheticOptionsDataSource()
        chain = source.get_chain("KOSPI200", date(2024, 1, 2))

        self.assertEqual(list(chain.columns), CHAIN_COLUMNS)
        self.assertTrue(set(chain["option_type"]) <= {"call", "put"})
        self.assertTrue((chain["open_interest"] > 0).all())

    def test_is_always_available(self):
        source = SyntheticOptionsDataSource()
        self.assertTrue(source.is_available("KOSPI200", date(2024, 1, 2)))


class RiskReversalTests(unittest.TestCase):
    def test_synthetic_downside_skew_is_negative(self):
        # The synthetic smile is built with a downside-richer skew (typical
        # equity market shape), so 25d call IV - 25d put IV should be < 0.
        chain = SyntheticOptionsDataSource().get_chain("KOSPI200", date(2024, 1, 2))
        skew = calculate_25d_risk_reversal(chain)
        self.assertFalse(np.isnan(skew))
        self.assertLess(skew, 0)

    def test_empty_chain_returns_nan(self):
        self.assertTrue(np.isnan(calculate_25d_risk_reversal(pd.DataFrame())))

    def test_missing_option_type_returns_nan(self):
        calls_only = SyntheticOptionsDataSource().get_chain(
            "KOSPI200", date(2024, 1, 2)
        )
        calls_only = calls_only[calls_only["option_type"] == "call"]
        self.assertTrue(np.isnan(calculate_25d_risk_reversal(calls_only)))


class GexProxyTests(unittest.TestCase):
    def test_returns_finite_number(self):
        chain = SyntheticOptionsDataSource().get_chain("KOSPI200", date(2024, 1, 2))
        gex = calculate_gex_proxy(chain)
        self.assertFalse(np.isnan(gex))
        self.assertTrue(np.isfinite(gex))

    def test_empty_chain_returns_nan(self):
        self.assertTrue(np.isnan(calculate_gex_proxy(pd.DataFrame())))


class KrxIndexOptionsDataSourceTests(unittest.TestCase):
    def test_reports_unavailable(self):
        source = KrxIndexOptionsDataSource()
        self.assertFalse(source.is_available("KOSPI200", date(2024, 1, 2)))

    def test_get_chain_raises_if_called_anyway(self):
        source = KrxIndexOptionsDataSource()
        with self.assertRaises(NotImplementedError):
            source.get_chain("KOSPI200", date(2024, 1, 2))

    def test_compute_options_signal_degrades_to_nan_not_a_crash(self):
        source = KrxIndexOptionsDataSource()
        signal = compute_options_signal(source, "KOSPI200", date(2024, 1, 2))
        self.assertTrue(np.isnan(signal["iv_skew_25d"]))
        self.assertTrue(np.isnan(signal["gex_proxy"]))


class AddOptionsFeaturesTests(unittest.TestCase):
    def test_broadcasts_same_signal_across_all_rows_with_synthetic_source(self):
        index = pd.date_range("2024-01-02", periods=5, freq="B")
        df = pd.DataFrame({"close": [100, 101, 99, 102, 103]}, index=index)

        result = add_options_features(df, SyntheticOptionsDataSource())

        self.assertIn("iv_skew_25d", result.columns)
        self.assertIn("gex_proxy", result.columns)
        self.assertEqual(result["iv_skew_25d"].nunique(), 1)
        self.assertFalse(result["iv_skew_25d"].isna().any())

    def test_neutral_nan_when_source_unavailable(self):
        index = pd.date_range("2024-01-02", periods=3, freq="B")
        df = pd.DataFrame({"close": [100, 101, 99]}, index=index)

        result = add_options_features(df, KrxIndexOptionsDataSource())

        self.assertTrue(result["iv_skew_25d"].isna().all())
        self.assertTrue(result["gex_proxy"].isna().all())


if __name__ == "__main__":
    unittest.main()
