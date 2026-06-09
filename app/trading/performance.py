import csv
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.trading.mt5_client import MT5_AVAILABLE, mt5


class PerformanceTracker:

    def __init__(self, data_dir="data"):
        configured_data_dir = os.getenv("DATA_DIR")
        if configured_data_dir:
            resolved_data_dir = configured_data_dir
        elif os.getenv("VERCEL") == "1":
            resolved_data_dir = "/tmp/data"
        else:
            resolved_data_dir = data_dir

        self.data_dir = Path(resolved_data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.signal_log_path = self.data_dir / "signal_log.csv"
        self.report_path = self.data_dir / "performance_report.json"

    def log_signal(self, record):
        headers = list(record.keys())
        write_header = not self.signal_log_path.exists()

        with self.signal_log_path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            if write_header:
                writer.writeheader()
            writer.writerow(record)

    def _compute_stats(self, deals, symbol=None, magic=None):
        closed_entries = {
            getattr(mt5, "DEAL_ENTRY_OUT", 1),
            getattr(mt5, "DEAL_ENTRY_OUT_BY", 3),
        }

        closed = []
        for deal in deals:
            if symbol and getattr(deal, "symbol", None) != symbol:
                continue
            if magic is not None and getattr(deal, "magic", None) != magic:
                continue
            if getattr(deal, "entry", None) not in closed_entries:
                continue

            pnl = (
                float(getattr(deal, "profit", 0.0))
                + float(getattr(deal, "swap", 0.0))
                + float(getattr(deal, "commission", 0.0))
            )
            closed.append(pnl)

        total = len(closed)
        wins = sum(1 for pnl in closed if pnl > 0)
        losses = sum(1 for pnl in closed if pnl < 0)
        total_pnl = round(sum(closed), 2)
        win_rate = round((wins / total) * 100, 2) if total else 0.0
        expectancy = round((sum(closed) / total), 2) if total else 0.0

        equity = 0.0
        peak = 0.0
        max_drawdown = 0.0
        for pnl in closed:
            equity += pnl
            if equity > peak:
                peak = equity
            drawdown = peak - equity
            if drawdown > max_drawdown:
                max_drawdown = drawdown

        return {
            "available": True,
            "symbol": symbol,
            "magic": magic,
            "closed_trades": total,
            "wins": wins,
            "losses": losses,
            "win_rate_pct": win_rate,
            "total_pnl": total_pnl,
            "expectancy_per_trade": expectancy,
            "max_drawdown": round(max_drawdown, 2),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def generate_mt5_report(
        self,
        login,
        password,
        server,
        terminal_path=None,
        symbol=None,
        magic=None,
        lookback_days=30,
    ):
        if not MT5_AVAILABLE or mt5 is None:
            return {
                "available": False,
                "error": "MetaTrader5 package is not available in this environment",
            }

        if terminal_path:
            initialized = mt5.initialize(path=terminal_path)
        else:
            initialized = mt5.initialize()

        if not initialized:
            return {
                "available": False,
                "error": f"initialize_failed: {mt5.last_error()}",
            }

        authorized = mt5.login(login=login, password=password, server=server)
        if not authorized:
            error = {
                "available": False,
                "error": f"login_failed: {mt5.last_error()}",
            }
            mt5.shutdown()
            return error

        date_to = datetime.now()
        date_from = date_to - timedelta(days=lookback_days)
        deals = mt5.history_deals_get(date_from, date_to)

        if deals is None:
            error = {
                "available": False,
                "error": f"history_failed: {mt5.last_error()}",
            }
            mt5.shutdown()
            return error

        stats = self._compute_stats(deals, symbol=symbol, magic=magic)
        with self.report_path.open("w", encoding="utf-8") as f:
            json.dump(stats, f, indent=2)

        mt5.shutdown()
        return stats
