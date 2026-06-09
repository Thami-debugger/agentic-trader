import json
from datetime import datetime, timezone
from pathlib import Path

from app.config import (
    BACKTEST_WARMUP_BARS,
    DECISION_BUY_THRESHOLD,
    DECISION_SELL_THRESHOLD,
    MAX_ATR_PCT,
    MAX_RSI_FOR_BUY,
    MIN_ADX,
    MIN_ATR_PCT,
    MIN_DIRECTIONAL_VOTES,
    MIN_MODEL_ACCURACY,
    MIN_QUANT_CONFIDENCE,
    MIN_RSI_FOR_SELL,
)
from app.trading.decision_agent import DecisionAgent
from app.trading.indicators import IndicatorAgent
from app.trading.market_data import MarketDataAgent
from app.trading.quant_model import QuantModel


class BacktestRunner:
    def __init__(self, data_dir="data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.report_path = self.data_dir / "backtest_report.json"

    def _compute_stats(self, trade_pnls, buy_count, sell_count, hold_count, model_accuracies):
        total_trades = len(trade_pnls)
        wins = sum(1 for pnl in trade_pnls if pnl > 0)
        losses = sum(1 for pnl in trade_pnls if pnl < 0)
        total_pnl = sum(trade_pnls)
        expectancy = (total_pnl / total_trades) if total_trades else 0.0
        win_rate = ((wins / total_trades) * 100.0) if total_trades else 0.0

        equity = 0.0
        peak = 0.0
        max_drawdown = 0.0
        for pnl in trade_pnls:
            equity += pnl
            if equity > peak:
                peak = equity
            drawdown = peak - equity
            if drawdown > max_drawdown:
                max_drawdown = drawdown

        avg_model_accuracy = (
            sum(model_accuracies) / len(model_accuracies) if model_accuracies else 0.0
        )

        return {
            "total_cycles": buy_count + sell_count + hold_count,
            "total_trades": total_trades,
            "buys": buy_count,
            "sells": sell_count,
            "holds": hold_count,
            "wins": wins,
            "losses": losses,
            "win_rate_pct": round(win_rate, 2),
            "total_pnl_points": round(total_pnl, 4),
            "expectancy_points_per_trade": round(expectancy, 4),
            "max_drawdown_points": round(max_drawdown, 4),
            "avg_model_accuracy": round(avg_model_accuracy, 4),
        }

    def run_mode(
        self,
        df,
        mode_name,
        warmup_bars,
        buy_threshold,
        sell_threshold,
        min_model_accuracy,
        min_quant_confidence,
        min_atr_pct,
        max_atr_pct,
        min_adx,
        min_directional_votes,
        max_rsi_for_buy,
        min_rsi_for_sell,
        slippage_points=0.1,
    ):
        quant_model = QuantModel()
        decision_agent = DecisionAgent()

        if len(df) <= warmup_bars + 1:
            return {
                "mode": mode_name,
                "error": "not_enough_data",
                "bars_available": int(len(df)),
            }

        trade_pnls = []
        model_accuracies = []
        buy_count = 0
        sell_count = 0
        hold_count = 0

        warmup_history = df.iloc[: warmup_bars + 1].copy()
        model, accuracy = quant_model.train_model(warmup_history)

        for idx in range(warmup_bars, len(df) - 1):
            history = df.iloc[: idx + 1].copy()
            latest = history.iloc[-1]

            prediction, quant_confidence = quant_model.predict_with_confidence(model, latest)
            decision = decision_agent.generate_trade_decision(
                history,
                sentiment=0.0,
                prediction=prediction,
                quant_confidence=quant_confidence,
                model_accuracy=accuracy,
                min_model_accuracy=min_model_accuracy,
                min_quant_confidence=min_quant_confidence,
                buy_threshold=buy_threshold,
                sell_threshold=sell_threshold,
                min_atr_pct=min_atr_pct,
                max_atr_pct=max_atr_pct,
                min_adx=min_adx,
                min_directional_votes=min_directional_votes,
                max_rsi_for_buy=max_rsi_for_buy,
                min_rsi_for_sell=min_rsi_for_sell,
            )

            action = decision["action"]
            model_accuracies.append(float(accuracy))

            entry = float(latest["Close"])

            if action in ["BUY", "SELL"]:
                atr = float(latest.get("atr_14", 3.0))
                sl_dist = atr * 3.0
                tp_dist = atr * 8.0

                if action == "BUY":
                    buy_count += 1
                    sl_price = entry - sl_dist
                    tp_price = entry + tp_dist
                    pnl = 0
                    for j in range(idx + 1, len(df)):
                        future = df.iloc[j]
                        if float(future["Low"]) <= sl_price:
                            pnl = sl_price - entry - slippage_points
                            break
                        if float(future["High"]) >= tp_price:
                            pnl = tp_price - entry - slippage_points
                            break
                    if pnl == 0 and idx + 1 < len(df):
                        pnl = float(df.iloc[-1]["Close"]) - entry - slippage_points
                    trade_pnls.append(pnl)
                
                elif action == "SELL":
                    sell_count += 1
                    sl_price = entry + sl_dist
                    tp_price = entry - tp_dist
                    pnl = 0
                    for j in range(idx + 1, len(df)):
                        future = df.iloc[j]
                        if float(future["High"]) >= sl_price:
                            pnl = entry - sl_price - slippage_points
                            break
                        if float(future["Low"]) <= tp_price:
                            pnl = entry - tp_price - slippage_points
                            break
                    if pnl == 0 and idx + 1 < len(df):
                        pnl = entry - float(df.iloc[-1]["Close"]) - slippage_points
                    trade_pnls.append(pnl)
            else:
                hold_count += 1

        stats = self._compute_stats(
            trade_pnls,
            buy_count,
            sell_count,
            hold_count,
            model_accuracies,
        )
        stats["mode"] = mode_name
        stats["warmup_bars"] = warmup_bars
        stats["thresholds"] = {
            "buy": buy_threshold,
            "sell": sell_threshold,
            "min_model_accuracy": min_model_accuracy,
            "min_quant_confidence": min_quant_confidence,
            "min_atr_pct": min_atr_pct,
            "max_atr_pct": max_atr_pct,
            "min_adx": min_adx,
            "min_directional_votes": min_directional_votes,
            "max_rsi_for_buy": max_rsi_for_buy,
            "min_rsi_for_sell": min_rsi_for_sell,
        }
        return stats

    def run_comparison(self):
        market_agent = MarketDataAgent()
        indicator_agent = IndicatorAgent()
        df = market_agent.get_gold_data()
        df = indicator_agent.add_indicators(df)
        df = df.dropna().copy()

        baseline = self.run_mode(
            df=df,
            mode_name="baseline",
            warmup_bars=BACKTEST_WARMUP_BARS,
            buy_threshold=0.04,
            sell_threshold=-0.04,
            min_model_accuracy=0.0,
            min_quant_confidence=0.0,
            min_atr_pct=0.0,
            max_atr_pct=1.0,
            min_adx=0.0,
            min_directional_votes=1,
            max_rsi_for_buy=70.0,
            min_rsi_for_sell=30.0,
        )
        guarded = self.run_mode(
            df=df,
            mode_name="guarded",
            warmup_bars=BACKTEST_WARMUP_BARS,
            buy_threshold=DECISION_BUY_THRESHOLD,
            sell_threshold=DECISION_SELL_THRESHOLD,
            min_model_accuracy=MIN_MODEL_ACCURACY,
            min_quant_confidence=MIN_QUANT_CONFIDENCE,
            min_atr_pct=MIN_ATR_PCT,
            max_atr_pct=MAX_ATR_PCT,
            min_adx=MIN_ADX,
            min_directional_votes=MIN_DIRECTIONAL_VOTES,
            max_rsi_for_buy=MAX_RSI_FOR_BUY,
            min_rsi_for_sell=MIN_RSI_FOR_SELL,
        )

        summary = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "symbol": "GC=F",
            "comparison": [baseline, guarded],
        }

        with self.report_path.open("w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        return summary


def main():
    runner = BacktestRunner()
    report = runner.run_comparison()

    print("Backtest comparison complete")
    for mode in report["comparison"]:
        if mode.get("error"):
            print(f"{mode['mode']}: error={mode['error']}")
            continue
        print(
            f"{mode['mode']}: trades={mode['total_trades']} | "
            f"win_rate={mode['win_rate_pct']}% | "
            f"expectancy={mode['expectancy_points_per_trade']} | "
            f"max_dd={mode['max_drawdown_points']} | "
            f"avg_acc={mode['avg_model_accuracy']}"
        )


if __name__ == "__main__":
    main()
