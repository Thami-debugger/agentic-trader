from datetime import datetime, timezone

from app.trading.mt5_client import MT5_AVAILABLE, mt5

class TradeExecutor:

    def _prepare_symbol(self, symbol):
        info = mt5.symbol_info(symbol)
        if info is None:
            return False, f"Symbol not found: {symbol}"

        if not info.visible:
            if not mt5.symbol_select(symbol, True):
                return False, f"Could not select symbol: {symbol}"

        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return False, f"No market tick available for symbol: {symbol}"

        return True, tick

    def connect(self, login, password, server, terminal_path=None):

        if not MT5_AVAILABLE or mt5 is None:
            return {
                "connected": False,
                "error": "MetaTrader5 package is not available in this environment",
            }

        if terminal_path:
            initialized = mt5.initialize(path=terminal_path)
        else:
            initialized = mt5.initialize()

        if not initialized:
            return {
                "connected": False,
                "error": mt5.last_error(),
            }

        authorized = mt5.login(
            login=login,
            password=password,
            server=server
        )

        if not authorized:
            return {
                "connected": False,
                "error": mt5.last_error(),
            }

        return {
            "connected": True,
            "error": None,
        }

    def place_order(
        self,
        order_type,
        symbol="XAUUSD",
        volume=0.01,
        stop_loss_points=300,
        take_profit_points=600,
        magic=100
    ):

        if not MT5_AVAILABLE or mt5 is None:
            return {
                "success": False,
                "error": "MetaTrader5 package is not available in this environment",
            }

        ok, tick_or_error = self._prepare_symbol(symbol)
        if not ok:
            return {
                "success": False,
                "error": tick_or_error,
            }

        tick = tick_or_error

        if order_type == mt5.ORDER_TYPE_BUY:
            price = tick.ask
            comment = "AI Gold Buy"
            point = mt5.symbol_info(symbol).point
            digits = mt5.symbol_info(symbol).digits
            sl = round(tick.bid - (stop_loss_points * point), digits)
            tp = round(tick.ask + (take_profit_points * point), digits)
        else:
            price = tick.bid
            comment = "AI Gold Sell"
            point = mt5.symbol_info(symbol).point
            digits = mt5.symbol_info(symbol).digits
            sl = round(tick.ask + (stop_loss_points * point), digits)
            tp = round(tick.bid - (take_profit_points * point), digits)

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": order_type,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": 20,
            "magic": magic,
            "comment": comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)

        if result is None:
            return {
                "success": False,
                "error": mt5.last_error(),
            }

        return result

    def place_buy_order(
        self,
        symbol="XAUUSD",
        volume=0.01,
        stop_loss_points=300,
        take_profit_points=600,
        magic=100
    ):
        return self.place_order(
            mt5.ORDER_TYPE_BUY,
            symbol,
            volume,
            stop_loss_points,
            take_profit_points,
            magic,
        )

    def place_sell_order(
        self,
        symbol="XAUUSD",
        volume=0.01,
        stop_loss_points=300,
        take_profit_points=600,
        magic=100
    ):

        return self.place_order(
            mt5.ORDER_TYPE_SELL,
            symbol,
            volume,
            stop_loss_points,
            take_profit_points,
            magic,
        )

    def update_trailing_targets(
        self,
        symbol,
        magic=100,
        trailing_stop_points=250,
        trailing_tp_points=600,
        min_hold_minutes=60,
    ):
        if not MT5_AVAILABLE or mt5 is None:
            return {
                "success": False,
                "error": "MetaTrader5 package is not available in this environment",
                "updated": 0,
            }

        positions = mt5.positions_get(symbol=symbol)
        if positions is None:
            return {
                "success": False,
                "error": mt5.last_error(),
                "updated": 0,
            }

        info = mt5.symbol_info(symbol)
        tick = mt5.symbol_info_tick(symbol)
        if info is None or tick is None:
            return {
                "success": False,
                "error": f"Could not read symbol/tick for {symbol}",
                "updated": 0,
            }

        point = info.point
        digits = info.digits
        updated = 0

        for position in positions:
            if getattr(position, "magic", None) != magic:
                continue

            opened_at = datetime.fromtimestamp(position.time, tz=timezone.utc)
            age_minutes = (datetime.now(timezone.utc) - opened_at).total_seconds() / 60.0
            if age_minutes < float(min_hold_minutes):
                continue

            if position.type == mt5.POSITION_TYPE_BUY:
                new_sl = round(tick.bid - (trailing_stop_points * point), digits)
                new_tp = round(tick.ask + (trailing_tp_points * point), digits)

                should_update_sl = position.sl == 0.0 or new_sl > position.sl
                should_update_tp = position.tp == 0.0 or new_tp > position.tp
            else:
                new_sl = round(tick.ask + (trailing_stop_points * point), digits)
                new_tp = round(tick.bid - (trailing_tp_points * point), digits)

                should_update_sl = position.sl == 0.0 or new_sl < position.sl
                should_update_tp = position.tp == 0.0 or new_tp < position.tp

            if not should_update_sl and not should_update_tp:
                continue

            request = {
                "action": mt5.TRADE_ACTION_SLTP,
                "position": position.ticket,
                "symbol": symbol,
                "sl": new_sl if should_update_sl else position.sl,
                "tp": new_tp if should_update_tp else position.tp,
                "magic": magic,
            }

            result = mt5.order_send(request)
            if result is not None and result.retcode == mt5.TRADE_RETCODE_DONE:
                updated += 1

        return {
            "success": True,
            "updated": updated,
        }