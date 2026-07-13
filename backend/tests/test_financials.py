import sys
import unittest
from unittest.mock import MagicMock, patch

import pandas as pd

from financials import add_financial_features, load_financials


def _mock_opendartreader(mock_dart):
    # financials.py does `import OpenDartReader; dart = OpenDartReader(key)`
    # *inside* the function (an intentional lazy/optional-dependency import),
    # so there's no module-level `financials.OpenDartReader` attribute to
    # patch directly. Injecting a fake module into sys.modules is what the
    # local `import OpenDartReader` statement actually resolves against.
    fake_module = MagicMock(return_value=mock_dart)
    return patch.dict(sys.modules, {"OpenDartReader": fake_module})


def _make_price_df(start="2023-01-02", periods=750):
    index = pd.date_range(start, periods=periods, freq="B")
    return pd.DataFrame({"close": range(100, 100 + periods)}, index=index)


def _fake_finstate(year, revenue):
    return pd.DataFrame(
        [
            {"account_nm": "매출액", "thstrm_amount": str(revenue)},
            {"account_nm": "영업이익", "thstrm_amount": "1000"},
            {"account_nm": "당기순이익", "thstrm_amount": "800"},
            {"account_nm": "부채총계", "thstrm_amount": "5000"},
            {"account_nm": "자본총계", "thstrm_amount": "10000"},
            {"account_nm": "영업활동현금흐름", "thstrm_amount": "900"},
            {"account_nm": "유형자산의 취득", "thstrm_amount": "100"},
        ]
    )


class LoadFinancialsTests(unittest.TestCase):
    @patch("financials.get_dart_api_key", return_value="fake-key")
    def test_different_years_are_effective_at_different_dates_not_constant(
        self, _mock_key
    ):
        mock_dart = MagicMock()

        def finstate_all(ticker, year, reprt_code):
            return _fake_finstate(year, revenue=1000 + year)

        mock_dart.finstate_all.side_effect = finstate_all

        with _mock_opendartreader(mock_dart):
            result = load_financials("005930", "20220101", "20260101")

        self.assertGreater(result["revenue"].dropna().nunique(), 1)

    @patch("financials.get_dart_api_key", return_value="fake-key")
    def test_report_never_applied_before_its_effective_date(self, _mock_key):
        mock_dart = MagicMock()

        def finstate_all(ticker, year, reprt_code):
            if year == 2025:
                return _fake_finstate(year, revenue=99999)
            return pd.DataFrame()

        mock_dart.finstate_all.side_effect = finstate_all

        with _mock_opendartreader(mock_dart):
            result = load_financials("005930", "20230101", "20260101")

        # FY2025's report is only effective from 2026-04-01 -- must not leak
        # backward onto 2025 dates.
        self.assertTrue(result.loc["2025-12-31":"2025-12-31", "revenue"].isna().all())

    @patch("financials.get_dart_api_key", return_value=None)
    def test_missing_api_key_returns_empty_dataframe(self, _mock_key):
        result = load_financials("005930", "20230101", "20260101")
        self.assertTrue(result.empty)


class AddFinancialFeaturesTests(unittest.TestCase):
    def test_values_vary_across_a_multi_year_window(self):
        price_df = _make_price_df()
        financial_df = pd.DataFrame(
            {
                "revenue": [100.0] * 300 + [200.0] * 450,
                "ebitda": 10.0,
                "net_income": 8.0,
                "operating_margin": 0.1,
                "net_margin": 0.08,
                "roe": 0.1,
                "debt_ratio": 0.5,
                "free_cash_flow": 5.0,
            },
            index=price_df.index,
        )

        result = add_financial_features(price_df, financial_df)

        self.assertGreater(result["revenue"].nunique(), 1)

    def test_empty_input_zero_fills_without_crashing(self):
        price_df = _make_price_df(periods=10)
        result = add_financial_features(price_df, pd.DataFrame())
        for col in ["revenue", "ebitda", "net_income", "roe", "debt_ratio"]:
            self.assertTrue((result[col] == 0).all())


if __name__ == "__main__":
    unittest.main()
