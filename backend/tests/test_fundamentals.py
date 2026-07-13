import unittest
from unittest.mock import patch

import pandas as pd

from fundamentals import add_fundamental_features, load_fundamentals


def _make_price_df(start="2024-01-02", periods=40):
    index = pd.date_range(start, periods=periods, freq="B")
    return pd.DataFrame({"close": range(100, 100 + periods)}, index=index)


class LoadFundamentalsTests(unittest.TestCase):
    def test_uses_pykrx_date_range_series_when_available(self):
        index = pd.date_range("2024-01-02", periods=5, freq="D")
        fake_series = pd.DataFrame(
            {
                "BPS": [37528] * 5,
                "PER": [26.2, 26.5, 25.9, 26.1, 28.0],
                "PBR": [2.21] * 5,
                "EPS": [3166] * 5,
                "DIV": [1.7] * 5,
                "DPS": [1416] * 5,
            },
            index=index,
        )
        with patch("fundamentals.stock.get_market_fundamental", return_value=fake_series):
            result = load_fundamentals("005930", "20240102", "20240106")

        self.assertGreater(result["per"].nunique(), 1)
        self.assertEqual(result.loc[index[0], "bps"], 37528)

    def test_falls_back_to_zeros_when_pykrx_raises(self):
        with patch(
            "fundamentals.stock.get_market_fundamental",
            side_effect=Exception("KRX unavailable"),
        ):
            result = load_fundamentals("005930", "20240102", "20240106")

        for col in ["bps", "per", "pbr", "eps", "div", "dps"]:
            self.assertTrue((result[col] == 0).all())


class AddFundamentalFeaturesTests(unittest.TestCase):
    def test_values_vary_across_history_not_constant(self):
        price_df = _make_price_df()
        fundamental_df = pd.DataFrame(
            {
                "bps": 37528,
                "per": [20 + i * 0.1 for i in range(len(price_df))],
                "pbr": 2.2,
                "eps": 3166,
                "div": 1.7,
                "dps": 1416,
            },
            index=price_df.index,
        )

        result = add_fundamental_features(price_df, fundamental_df)

        self.assertGreater(result["per"].nunique(), 1)

    def test_eps_growth_reflects_real_change_not_hardcoded_zero(self):
        price_df = _make_price_df(periods=45)
        eps_values = [1000] * 20 + [1200] * 25  # a real step change partway through
        fundamental_df = pd.DataFrame(
            {
                "bps": 10000,
                "per": 10,
                "pbr": 1,
                "eps": eps_values,
                "div": 1,
                "dps": 100,
            },
            index=price_df.index,
        )

        result = add_fundamental_features(price_df, fundamental_df)

        # index 25 (value 1200) vs index 5 (value 1000) straddles the step;
        # index 40 would compare two post-step values and show 0, which is
        # correct but wouldn't prove the growth calculation actually works.
        self.assertAlmostEqual(result["eps_growth_20d"].iloc[25], 0.2, places=4)

    def test_empty_input_zero_fills_without_crashing(self):
        price_df = _make_price_df()
        result = add_fundamental_features(price_df, pd.DataFrame())
        for col in ["bps", "per", "pbr", "eps", "div", "dps"]:
            self.assertTrue((result[col] == 0).all())


if __name__ == "__main__":
    unittest.main()
