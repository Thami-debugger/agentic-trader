from app.trading.mt5_client import mt5


class RiskManager:

    def compute_consecutive_loss_streak(self, deals):
        closed_entries = {
            getattr(mt5, "DEAL_ENTRY_OUT", 1),
            getattr(mt5, "DEAL_ENTRY_OUT_BY", 3),
        }

        closed_deals = []
        for deal in deals or []:
            if getattr(deal, "entry", None) not in closed_entries:
                continue

            pnl = (
                float(getattr(deal, "profit", 0.0))
                + float(getattr(deal, "swap", 0.0))
                + float(getattr(deal, "commission", 0.0))
            )
            deal_time = getattr(deal, "time_msc", None)
            if deal_time is None:
                deal_time = getattr(deal, "time", 0)
            closed_deals.append((deal_time, pnl))

        closed_deals.sort(key=lambda item: item[0])

        streak = 0
        for _, pnl in reversed(closed_deals):
            if pnl < 0:
                streak += 1
            else:
                break

        return streak

    def compute_equity_drawdown_ratio(self, balance, equity):
        if balance <= 0:
            return 0.0

        drawdown = max(0.0, float(balance) - float(equity))
        return drawdown / float(balance)

    def calculate_position_size(
        self,
        balance,
        risk_per_trade,
        stop_loss_distance,
        value_per_point_per_lot=1.0,
        min_lot=0.01,
        max_lot=100.0,
        lot_step=0.01,
    ):

        risk_amount = balance * risk_per_trade

        if stop_loss_distance <= 0 or value_per_point_per_lot <= 0:
            return min_lot

        # Position size in lots from: risk amount / (SL points * value per point per lot)
        raw_position_size = risk_amount / (
            stop_loss_distance * value_per_point_per_lot
        )

        # Snap to broker lot step and clamp to allowed lot range.
        stepped = round(raw_position_size / lot_step) * lot_step
        position_size = max(min_lot, min(max_lot, stepped))

        return round(position_size, 2)

    def can_trade(
        self,
        current_daily_loss,
        max_daily_loss,
        consecutive_loss_streak=0,
        max_consecutive_losses=None,
        equity_drawdown_ratio=0.0,
        max_equity_drawdown=None,
    ):

        if current_daily_loss >= max_daily_loss:
            return False

        if max_consecutive_losses is not None and consecutive_loss_streak >= max_consecutive_losses:
            return False

        if max_equity_drawdown is not None and equity_drawdown_ratio >= max_equity_drawdown:
            return False

        return True

    def compute_daily_loss_ratio(
        self,
        day_realized_pnl,
        balance,
    ):
        if balance <= 0:
            return 0.0

        losses_only = min(0.0, float(day_realized_pnl))
        return abs(losses_only) / float(balance)