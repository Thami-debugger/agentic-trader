import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
BINANCE_SECRET = os.getenv("BINANCE_SECRET")

NEWS_API_KEY = os.getenv("NEWS_API_KEY")
OPENAI_NEWS_MODEL = os.getenv("OPENAI_NEWS_MODEL", "gpt-4o-mini")
OPENAI_NEWS_MAX_ARTICLES = int(os.getenv("OPENAI_NEWS_MAX_ARTICLES", "8"))

MT5_LOGIN = int(os.getenv("MT5_LOGIN", 0))
MT5_PASSWORD = os.getenv("MT5_PASSWORD")
MT5_SERVER = os.getenv("MT5_SERVER")
MT5_TERMINAL_PATH = os.getenv("MT5_TERMINAL_PATH")

DEFAULT_SYMBOL = os.getenv("DEFAULT_SYMBOL", "XAUUSD")
LOT_SIZE = float(os.getenv("LOT_SIZE", "0.01"))
AUTO_TRADE = os.getenv("AUTO_TRADE", "false").lower() == "true"
STOP_LOSS_POINTS = int(os.getenv("STOP_LOSS_POINTS", "300"))
TAKE_PROFIT_POINTS = int(os.getenv("TAKE_PROFIT_POINTS", "600"))
TRADE_MAGIC = int(os.getenv("TRADE_MAGIC", "100"))
PERFORMANCE_LOOKBACK_DAYS = int(os.getenv("PERFORMANCE_LOOKBACK_DAYS", "30"))
TRADE_BATCH_COUNT = int(os.getenv("TRADE_BATCH_COUNT", "1"))
FORCE_ACTION = os.getenv("FORCE_ACTION", "").upper()
USE_FORCE_ACTION = os.getenv("USE_FORCE_ACTION", "false").lower() == "true"
TRAILING_STOP_POINTS = int(os.getenv("TRAILING_STOP_POINTS", "250"))
TRAILING_TP_POINTS = int(os.getenv("TRAILING_TP_POINTS", "600"))
HOLD_TRADES_MODE = os.getenv("HOLD_TRADES_MODE", "true").lower() == "true"
ENABLE_TRAILING = os.getenv("ENABLE_TRAILING", "true").lower() == "true"
MIN_HOLD_MINUTES = int(os.getenv("MIN_HOLD_MINUTES", "60"))
CONTINUOUS_TRADING = os.getenv("CONTINUOUS_TRADING", "true").lower() == "true"
CHECK_INTERVAL_SECONDS = int(os.getenv("CHECK_INTERVAL_SECONDS", "60"))
ONLY_NEW_CANDLE = os.getenv("ONLY_NEW_CANDLE", "false").lower() == "true"

RISK_PER_TRADE = float(os.getenv("RISK_PER_TRADE", "0.02"))
MAX_DAILY_LOSS = float(os.getenv("MAX_DAILY_LOSS", "0.05"))
MAX_OPEN_TRADES = int(os.getenv("MAX_OPEN_TRADES", "3"))
MAX_CONSECUTIVE_LOSSES = int(os.getenv("MAX_CONSECUTIVE_LOSSES", "2"))
MAX_EQUITY_DRAWDOWN = float(os.getenv("MAX_EQUITY_DRAWDOWN", "0.02"))

# Conservative execution controls to reduce overtrading in weak market regimes.
MIN_MODEL_ACCURACY = float(os.getenv("MIN_MODEL_ACCURACY", "0.55"))
MIN_QUANT_CONFIDENCE = float(os.getenv("MIN_QUANT_CONFIDENCE", "0.58"))
DECISION_BUY_THRESHOLD = float(os.getenv("DECISION_BUY_THRESHOLD", "0.12"))
DECISION_SELL_THRESHOLD = float(os.getenv("DECISION_SELL_THRESHOLD", "-0.12"))
MIN_ATR_PCT = float(os.getenv("MIN_ATR_PCT", "0.0015"))
MAX_ATR_PCT = float(os.getenv("MAX_ATR_PCT", "0.02"))
MIN_ADX = float(os.getenv("MIN_ADX", "18"))
MIN_DIRECTIONAL_VOTES = int(os.getenv("MIN_DIRECTIONAL_VOTES", "2"))
MAX_RSI_FOR_BUY = float(os.getenv("MAX_RSI_FOR_BUY", "62"))
MIN_RSI_FOR_SELL = float(os.getenv("MIN_RSI_FOR_SELL", "38"))

# Runtime kill-switch: disable new entries when rolling model quality is weak.
MODEL_ACCURACY_WINDOW = int(os.getenv("MODEL_ACCURACY_WINDOW", "5"))
WEAK_MODEL_MAX_STREAK = int(os.getenv("WEAK_MODEL_MAX_STREAK", "3"))

# Offline backtest controls.
BACKTEST_WARMUP_BARS = int(os.getenv("BACKTEST_WARMUP_BARS", "220"))