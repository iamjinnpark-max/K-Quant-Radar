import unittest

import pandas as pd

from screener import _build_price_chart


class ChartDataTests(unittest.TestCase):
    def test_chart_series_is_compact_and_json_ready(self):
        index = pd.date_range("2025-01-01", periods=140, freq="B")
        frame = pd.DataFrame(
            {
                "close": range(100, 240),
                "ma20": range(90, 230),
                "ma60": range(80, 220),
                "bb_upper": range(110, 250),
                "bb_lower": range(70, 210),
            },
            index=index,
        )

        chart = _build_price_chart(frame)

        self.assertEqual(len(chart), 126)
        self.assertEqual(chart[-1]["date"], index[-1].strftime("%Y-%m-%d"))
        self.assertIsInstance(chart[-1]["close"], float)
        self.assertEqual(
            set(chart[-1]),
            {"date", "close", "ma20", "ma60", "bb_upper", "bb_lower"},
        )


if __name__ == "__main__":
    unittest.main()
