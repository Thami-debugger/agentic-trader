from app.trading.market_data import MarketDataAgent
from app.trading.indicators import IndicatorAgent
from app.trading.news_agent import NewsAgent
from app.trading.quant_model import QuantModel
from app.trading.executor import TradeExecutor
from app.trading.risk_manager import RiskManager
from app.trading.decision_agent import DecisionAgent
from app.trading.performance import PerformanceTracker
from app.trading.mt5_client import mt5
from app.config import AUTO_TRADE, DEFAULT_SYMBOL, LOT_SIZE, MT5_LOGIN, MT5_PASSWORD, MT5_SERVER, MT5_TERMINAL_PATH, STOP_LOSS_POINTS, TAKE_PROFIT_POINTS, TRADE_MAGIC, PERFORMANCE_LOOKBACK_DAYS, TRADE_BATCH_COUNT, FORCE_ACTION, TRAILING_STOP_POINTS, TRAILING_TP_POINTS, RISK_PER_TRADE, MAX_DAILY_LOSS, MAX_OPEN_TRADES, MAX_CONSECUTIVE_LOSSES, MAX_EQUITY_DRAWDOWN, USE_FORCE_ACTION, HOLD_TRADES_MODE, ENABLE_TRAILING, MIN_HOLD_MINUTES, CONTINUOUS_TRADING, CHECK_INTERVAL_SECONDS, ONLY_NEW_CANDLE, MIN_MODEL_ACCURACY, MIN_QUANT_CONFIDENCE, DECISION_BUY_THRESHOLD, DECISION_SELL_THRESHOLD, MIN_ATR_PCT, MAX_ATR_PCT, MIN_ADX, MIN_DIRECTIONAL_VOTES, MAX_RSI_FOR_BUY, MIN_RSI_FOR_SELL, MODEL_ACCURACY_WINDOW, WEAK_MODEL_MAX_STREAK
from datetime import datetime, timezone
from collections import deque
import time

def monitor_open_positions(trade_executor):
    connection = trade_executor.connect(
        MT5_LOGIN,
        MT5_PASSWORD,
        MT5_SERVER,
        terminal_path=MT5_TERMINAL_PATH,
    )

    if not connection["connected"]:
        print(f"Open Trade Monitor: MT5 connection failed: {connection['error']}")
        return

    open_positions = mt5.positions_get(symbol=DEFAULT_SYMBOL)
    if open_positions is None:
        open_positions = []

    open_strategy_positions = [
        p for p in open_positions if getattr(p, "magic", None) == TRADE_MAGIC
    ]
    tickets = [getattr(p, "ticket", 0) for p in open_strategy_positions]

    if ENABLE_TRAILING:
        trailing_result = trade_executor.update_trailing_targets(
            symbol=DEFAULT_SYMBOL,
            magic=TRADE_MAGIC,
            trailing_stop_points=TRAILING_STOP_POINTS,
            trailing_tp_points=TRAILING_TP_POINTS,
            min_hold_minutes=MIN_HOLD_MINUTES,
        )
        print(f"Open Trade Monitor Trailing: {trailing_result}")

    print(f"Open Trade Monitor: {len(open_strategy_positions)} open strategy positions | Tickets: {tickets}")


def run_once(last_candle_time=None, auto_trade_enabled_for_cycle=AUTO_TRADE):

    print("Starting Agentic Trading System...")

    market_agent = MarketDataAgent()
    indicator_agent = IndicatorAgent()
    news_agent = NewsAgent()
    quant_agent = QuantModel()
    risk_manager = RiskManager()
    decision_agent = DecisionAgent()
    trade_executor = TradeExecutor()
    performance_tracker = PerformanceTracker()

    # Fetch data
    df = market_agent.get_gold_data()

    # Add indicators
    df = indicator_agent.add_indicators(df)

    latest_candle_time = str(df.index[-1])
    if ONLY_NEW_CANDLE and last_candle_time == latest_candle_time:
        print(
            f"\nNo new candle yet ({latest_candle_time}). "
            "Skipping entry signal this cycle."
        )
        monitor_open_positions(trade_executor)
        return {
            "latest_candle_time": latest_candle_time,
            "model_accuracy": None,
            "decision_action": "SKIP",
            "trade_placed": False,
        }

    # Fetch news
    news = news_agent.fetch_news()

    sentiment = news_agent.analyze_sentiment(news)

    # Train quant model
    model, accuracy = quant_agent.train_model(df)

    print(f"Model Accuracy: {accuracy}")

    latest = df.iloc[-1]

    prediction, quant_confidence = quant_agent.predict_with_confidence(
        model,
        latest
    )

    # Multi-strategy consensus decision
    decision = decision_agent.generate_trade_decision(
        df,
        sentiment,
        prediction,
        quant_confidence=quant_confidence,
        model_accuracy=accuracy,
        min_model_accuracy=MIN_MODEL_ACCURACY,
        min_quant_confidence=MIN_QUANT_CONFIDENCE,
        buy_threshold=DECISION_BUY_THRESHOLD,
        sell_threshold=DECISION_SELL_THRESHOLD,
        min_atr_pct=MIN_ATR_PCT,
        max_atr_pct=MAX_ATR_PCT,
        min_adx=MIN_ADX,
        min_directional_votes=MIN_DIRECTIONAL_VOTES,
        max_rsi_for_buy=MAX_RSI_FOR_BUY,
        min_rsi_for_sell=MIN_RSI_FOR_SELL,
    )

    print("\nAI Decision:")
    print(f"Action: {decision['action']}")
    print(f"Confidence: {decision['confidence']}")
    print(f"Risk Level: {decision['risk_level']}")
    print(f"Reasoning: {decision['reasoning']}")
    print(f"Strategy Scores: {decision['strategy_scores']}")
    print(f"SMA(50): {latest['sma_50']}")

    if USE_FORCE_ACTION and FORCE_ACTION in {"BUY", "SELL", "HOLD"}:
        decision["action"] = FORCE_ACTION
        print(f"Forced Action: {FORCE_ACTION}")

    trade_placed = False
    trade_retcode = None
    trade_error = None
    batch_results = []
    position_size_used = LOT_SIZE
    daily_loss_ratio = 0.0
    consecutive_loss_streak = 0
    equity_drawdown_ratio = 0.0
    risk_allowed = True
    effective_stop_loss_points = STOP_LOSS_POINTS
    effective_take_profit_points = TAKE_PROFIT_POINTS

    if auto_trade_enabled_for_cycle and decision['action'] in {"BUY", "SELL"}:
        connection = trade_executor.connect(
            MT5_LOGIN,
            MT5_PASSWORD,
            MT5_SERVER,
            terminal_path=MT5_TERMINAL_PATH,
        )

        if connection["connected"]:
            account_info = mt5.account_info()
            if account_info is None:
                print("\nTrade Execution: could not read account info, no trade placed.")
                trade_error = f"account_info_failed: {mt5.last_error()}"
                risk_allowed = False

            if risk_allowed:
                start_of_day = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                deals = mt5.history_deals_get(start_of_day, datetime.now())

                day_realized_pnl = 0.0
                closed_entries = {
                    getattr(mt5, "DEAL_ENTRY_OUT", 1),
                    getattr(mt5, "DEAL_ENTRY_OUT_BY", 3),
                }

                if deals is not None:
                    for deal in deals:
                        if getattr(deal, "entry", None) not in closed_entries:
                            continue

                        pnl = (
                            float(getattr(deal, "profit", 0.0))
                            + float(getattr(deal, "swap", 0.0))
                            + float(getattr(deal, "commission", 0.0))
                        )
                        day_realized_pnl += pnl

                daily_loss_ratio = risk_manager.compute_daily_loss_ratio(
                    day_realized_pnl,
                    float(account_info.balance),
                )
                consecutive_loss_streak = risk_manager.compute_consecutive_loss_streak(deals)
                equity_drawdown_ratio = risk_manager.compute_equity_drawdown_ratio(
                    float(account_info.balance),
                    float(account_info.equity),
                )
                risk_allowed = risk_manager.can_trade(
                    daily_loss_ratio,
                    MAX_DAILY_LOSS,
                    consecutive_loss_streak=consecutive_loss_streak,
                    max_consecutive_losses=MAX_CONSECUTIVE_LOSSES,
                    equity_drawdown_ratio=equity_drawdown_ratio,
                    max_equity_drawdown=MAX_EQUITY_DRAWDOWN,
                )

            if risk_allowed:
                open_positions = mt5.positions_get(symbol=DEFAULT_SYMBOL)
                if open_positions is None:
                    open_positions = []

                open_strategy_positions = [
                    p for p in open_positions if getattr(p, "magic", None) == TRADE_MAGIC
                ]

                if len(open_strategy_positions) >= MAX_OPEN_TRADES:
                    risk_allowed = False
                    trade_error = (
                        f"risk_limit_open_trades_reached: {len(open_strategy_positions)} "
                        f">= {MAX_OPEN_TRADES}"
                    )

            if risk_allowed:
                symbol_info = mt5.symbol_info(DEFAULT_SYMBOL)
                if symbol_info is not None and symbol_info.trade_tick_size > 0 and symbol_info.point > 0:
                    atr_value = float(latest.get("atr_14", 0.0) or 0.0)
                    atr_points = int(max(1, round(atr_value / float(symbol_info.point))))

                    if HOLD_TRADES_MODE:
                        effective_stop_loss_points = max(STOP_LOSS_POINTS, atr_points * 3)
                        effective_take_profit_points = max(TAKE_PROFIT_POINTS, atr_points * 8)

                    value_per_point_per_lot = (
                        float(symbol_info.trade_tick_value)
                        * (float(symbol_info.point) / float(symbol_info.trade_tick_size))
                    )
                    position_size_used = risk_manager.calculate_position_size(
                        balance=float(account_info.balance),
                        risk_per_trade=RISK_PER_TRADE,
                        stop_loss_distance=effective_stop_loss_points,
                        value_per_point_per_lot=max(value_per_point_per_lot, 0.0001),
                        min_lot=float(symbol_info.volume_min),
                        max_lot=float(symbol_info.volume_max),
                        lot_step=float(symbol_info.volume_step),
                    )

            if not risk_allowed:
                print("\nTrade Execution: risk manager blocked trade.")
                print(f"Daily loss ratio: {daily_loss_ratio:.4f} (limit {MAX_DAILY_LOSS:.4f})")
                print(f"Consecutive loss streak: {consecutive_loss_streak} (limit {MAX_CONSECUTIVE_LOSSES})")
                print(f"Equity drawdown ratio: {equity_drawdown_ratio:.4f} (limit {MAX_EQUITY_DRAWDOWN:.4f})")
                print(f"Risk block reason: {trade_error if trade_error else 'loss circuit breaker triggered'}")
            else:
                print(
                    f"\nRisk Manager: daily_loss_ratio={daily_loss_ratio:.4f}, "
                    f"position_size={position_size_used}"
                )
                print(
                    f"Execution Targets: SL points={effective_stop_loss_points}, "
                    f"TP points={effective_take_profit_points}, hold_mode={HOLD_TRADES_MODE}"
                )
                print(f"Management: trailing_enabled={ENABLE_TRAILING}, min_hold_minutes={MIN_HOLD_MINUTES}")
            print(f"\nTrade Execution: placing {TRADE_BATCH_COUNT} trades")
            if risk_allowed:
                for i in range(TRADE_BATCH_COUNT):
                    if decision['action'] == "BUY":
                        result = trade_executor.place_buy_order(
                            symbol=DEFAULT_SYMBOL,
                            volume=position_size_used,
                            stop_loss_points=effective_stop_loss_points,
                            take_profit_points=effective_take_profit_points,
                            magic=TRADE_MAGIC,
                        )
                    else:
                        result = trade_executor.place_sell_order(
                            symbol=DEFAULT_SYMBOL,
                            volume=position_size_used,
                            stop_loss_points=effective_stop_loss_points,
                            take_profit_points=effective_take_profit_points,
                            magic=TRADE_MAGIC,
                        )

                    batch_results.append(result)
                    print(f"Trade #{i + 1}: {result}")

                    if isinstance(result, dict) and result.get("success") is False:
                        trade_error = result.get("error")
                    elif hasattr(result, "retcode"):
                        is_done = result.retcode == mt5.TRADE_RETCODE_DONE
                        trade_placed = trade_placed or is_done
                        trade_retcode = result.retcode
                        if not is_done:
                            trade_error = getattr(result, "comment", None)
                    else:
                        trade_placed = True

                if ENABLE_TRAILING:
                    trailing_result = trade_executor.update_trailing_targets(
                        symbol=DEFAULT_SYMBOL,
                        magic=TRADE_MAGIC,
                        trailing_stop_points=TRAILING_STOP_POINTS,
                        trailing_tp_points=TRAILING_TP_POINTS,
                        min_hold_minutes=MIN_HOLD_MINUTES,
                    )
                    print(f"Trailing Update: {trailing_result}")
                else:
                    print("Trailing Update: skipped (trailing disabled)")

                open_after_send = mt5.positions_get(symbol=DEFAULT_SYMBOL)
                if open_after_send is None:
                    open_after_send = []
                open_strategy_positions = [
                    p for p in open_after_send if getattr(p, "magic", None) == TRADE_MAGIC
                ]
                tickets = [getattr(p, "ticket", 0) for p in open_strategy_positions]
                print(f"Open Strategy Positions: {len(open_strategy_positions)} | Tickets: {tickets}")
                print(f"Trade placed: {trade_placed}")
        else:
            print("\nTrade Execution: MT5 connection failed, no trade placed.")
            print(f"MT5 Error: {connection['error']}")
            trade_error = connection['error']
    else:
        print("\nTrade Execution: disabled or HOLD, no trade placed.")

    performance_tracker.log_signal(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "symbol": DEFAULT_SYMBOL,
            "action": decision["action"],
            "confidence": decision["confidence"],
            "model_accuracy": accuracy,
            "close": latest["Close"],
            "rsi": latest["rsi"],
            "macd": latest["macd"],
            "ema_20": latest["ema_20"],
            "sma_50": latest["sma_50"],
            "sentiment": sentiment,
            "prediction": int(prediction),
            "quant_confidence": round(float(quant_confidence), 4),
            "auto_trade_enabled": auto_trade_enabled_for_cycle,
            "trade_placed": trade_placed,
            "trade_retcode": trade_retcode,
            "trade_error": str(trade_error) if trade_error is not None else "",
            "trade_batch_count": TRADE_BATCH_COUNT,
            "position_size": position_size_used,
            "effective_stop_loss_points": effective_stop_loss_points,
            "effective_take_profit_points": effective_take_profit_points,
            "hold_trades_mode": HOLD_TRADES_MODE,
            "daily_loss_ratio": daily_loss_ratio,
            "risk_allowed": risk_allowed,
            "breakout_score": decision.get("strategy_scores", {}).get("breakout"),
            "ict_score": decision.get("strategy_scores", {}).get("ict"),
            "smart_money_score": decision.get("strategy_scores", {}).get("smart_money"),
            "macd_score": decision.get("strategy_scores", {}).get("macd"),
            "consensus_score": decision.get("strategy_scores", {}).get("weighted"),
        }
    )

    report = performance_tracker.generate_mt5_report(
        login=MT5_LOGIN,
        password=MT5_PASSWORD,
        server=MT5_SERVER,
        terminal_path=MT5_TERMINAL_PATH,
        symbol=DEFAULT_SYMBOL,
        magic=TRADE_MAGIC,
        lookback_days=PERFORMANCE_LOOKBACK_DAYS,
    )

    print("\nPerformance Report:")
    if report.get("available"):
        print(f"Closed Trades: {report['closed_trades']}")
        print(f"Win Rate (%): {report['win_rate_pct']}")
        print(f"Total PnL: {report['total_pnl']}")
        print(f"Expectancy/Trade: {report['expectancy_per_trade']}")
        print(f"Max Drawdown: {report['max_drawdown']}")
    else:
        print(f"Could not generate report: {report.get('error')}")

    if not trade_placed:
        monitor_open_positions(trade_executor)

    return {
        "latest_candle_time": latest_candle_time,
        "model_accuracy": float(accuracy),
        "decision_action": decision["action"],
        "trade_placed": trade_placed,
    }


def main():
    if not CONTINUOUS_TRADING:
        run_once(auto_trade_enabled_for_cycle=AUTO_TRADE)
        return

    print(
        "Starting continuous trading loop "
        f"(interval={CHECK_INTERVAL_SECONDS}s, only_new_candle={ONLY_NEW_CANDLE})"
    )
    last_candle_time = None
    model_acc_window = deque(maxlen=max(1, MODEL_ACCURACY_WINDOW))
    weak_model_streak = 0

    while True:
        try:
            print(f"\n--- Cycle at {datetime.now(timezone.utc).isoformat()} ---")

            rolling_acc = (
                (sum(model_acc_window) / len(model_acc_window))
                if len(model_acc_window) > 0
                else None
            )
            kill_switch_by_streak = weak_model_streak >= WEAK_MODEL_MAX_STREAK
            kill_switch_by_rolling = (
                rolling_acc is not None and rolling_acc < MIN_MODEL_ACCURACY
            )
            auto_trade_enabled_for_cycle = (
                AUTO_TRADE and not kill_switch_by_streak and not kill_switch_by_rolling
            )

            if AUTO_TRADE and not auto_trade_enabled_for_cycle:
                print(
                    "Kill-switch active: auto trade disabled this cycle "
                    f"(weak_streak={weak_model_streak}, "
                    f"rolling_accuracy={rolling_acc if rolling_acc is not None else 'n/a'}, "
                    f"threshold={MIN_MODEL_ACCURACY})"
                )

            cycle_result = run_once(
                last_candle_time=last_candle_time,
                auto_trade_enabled_for_cycle=auto_trade_enabled_for_cycle,
            )
            last_candle_time = cycle_result.get("latest_candle_time", last_candle_time)

            cycle_accuracy = cycle_result.get("model_accuracy")
            if cycle_accuracy is not None:
                model_acc_window.append(cycle_accuracy)
                if cycle_accuracy < MIN_MODEL_ACCURACY:
                    weak_model_streak += 1
                else:
                    weak_model_streak = 0

                updated_rolling = sum(model_acc_window) / len(model_acc_window)
                print(
                    "Model quality state: "
                    f"last_accuracy={cycle_accuracy:.4f}, "
                    f"rolling_accuracy={updated_rolling:.4f}, "
                    f"weak_streak={weak_model_streak}/{WEAK_MODEL_MAX_STREAK}"
                )
        except KeyboardInterrupt:
            print("\nContinuous trading stopped by user.")
            break
        except Exception as exc:
            print(f"\nCycle failed: {exc}")

        time.sleep(max(5, CHECK_INTERVAL_SECONDS))

if __name__ == "__main__":
    main()