"""MetaTrader5 compatibility wrapper.

This module allows the app to run in environments where MetaTrader5 is not
available (for example Linux serverless platforms).
"""

try:
    import MetaTrader5 as mt5  # type: ignore
    MT5_AVAILABLE = True
except Exception:
    mt5 = None
    MT5_AVAILABLE = False
