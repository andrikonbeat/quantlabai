"""Technical analysis data package.

Provides spot technical indicators computed from OHLCV price history.
"""

from quantlab.data.technical.indicators import compute_indicators

__all__ = ["compute_indicators"]
