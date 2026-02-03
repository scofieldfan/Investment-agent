import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.data_provider import get_buffett_metrics, format_stock_code
from app.database import init_db


def _parse_symbols():
    raw = os.getenv("STOCK_TEST_SYMBOLS", "600519")
    symbols = [s.strip() for s in raw.split(",") if s.strip()]
    return symbols or ["600519"]


class TestDataProvider(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def test_fetch_metrics(self):
        symbols = _parse_symbols()
        strict = os.getenv("STOCK_TEST_STRICT", "0") == "1"

        for symbol in symbols:
            with self.subTest(symbol=symbol):
                formatted = format_stock_code(symbol)
                payload = get_buffett_metrics(formatted)
                self.assertNotIn("error", payload, msg=f"{formatted} fetch error")

                metrics = payload.get("metrics", [])
                self.assertTrue(metrics, msg=f"{formatted} has no metrics")

                if strict:
                    nonzero = any(
                        (m.get("revenue", 0) or 0) != 0
                        or (m.get("net_income", 0) or 0) != 0
                        or (m.get("ocf", 0) or 0) != 0
                        or (m.get("fcf", 0) or 0) != 0
                        for m in metrics
                    )
                    self.assertTrue(
                        nonzero, msg=f"{formatted} metrics are all zero"
                    )


if __name__ == "__main__":
    unittest.main()
