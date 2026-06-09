class DecisionAgent:

    def generate_trade_decision(
        self,
        df,
        sentiment,
        prediction,
        quant_confidence,
        model_accuracy,
        min_model_accuracy,
        min_quant_confidence,
        buy_threshold,
        sell_threshold,
        min_atr_pct,
        max_atr_pct,
        min_adx,
        min_directional_votes,
        max_rsi_for_buy,
        min_rsi_for_sell,
    ):
        latest = df.iloc[-1]

        breakout = self._breakout_signal(df)
        ict = self._ict_signal(df)
        macd = self._macd_signal(latest)
        smart_money = self._smart_money_signal(df)
        model_quality_ok = float(model_accuracy) >= float(min_model_accuracy)
        quant_quality_ok = float(quant_confidence) >= float(min_quant_confidence)
        quant_enabled = (
            model_quality_ok
            and quant_quality_ok
        )

        if quant_enabled:
            quant = 1 if int(prediction) == 1 else -1
        else:
            quant = 0
        sentiment_score = 1 if sentiment > 0.05 else (-1 if sentiment < -0.05 else 0)

        weights = {
            "breakout": 0.34,
            "ict": 0.18,
            "macd": 0.14,
            "smart_money": 0.24,
            "quant": 0.07,
            "sentiment": 0.03,
        }

        # Weighted consensus across all strategies.
        weighted_breakout = weights["breakout"] * breakout
        weighted_ict = weights["ict"] * ict
        weighted_macd = weights["macd"] * macd
        weighted_smart_money = weights["smart_money"] * smart_money
        weighted_quant = weights["quant"] * quant
        weighted_sentiment = weights["sentiment"] * sentiment_score
        weighted_score = (
            weighted_breakout
            + weighted_ict
            + weighted_macd
            + weighted_smart_money
            + weighted_quant
            + weighted_sentiment
        )

        rsi = float(latest["rsi"])
        adx = float(latest.get("adx_14", 0.0) or 0.0)
        trend_ok_buy = float(latest["Close"]) >= float(latest["sma_50"])
        trend_ok_sell = float(latest["Close"]) <= float(latest["sma_50"])

        bullish_structure = breakout > 0 or ict > 0 or smart_money > 0
        bearish_structure = breakout < 0 or ict < 0 or smart_money < 0

        atr_value = float(latest.get("atr_14", 0.0) or 0.0)
        close_value = float(latest.get("Close", 0.0) or 0.0)
        atr_pct = (atr_value / close_value) if close_value > 0 else 0.0
        volatility_ok = float(min_atr_pct) <= atr_pct <= float(max_atr_pct)

        # If price-action structure shows an opening, reduce dependence on quant accuracy.
        effective_buy_threshold = float(buy_threshold)
        effective_sell_threshold = float(sell_threshold)
        if not quant_enabled:
            effective_buy_threshold = max(effective_buy_threshold, 0.12)
            effective_sell_threshold = min(effective_sell_threshold, -0.12)

        bullish_votes = sum(1 for s in (breakout, ict, macd, smart_money, quant, sentiment_score) if s > 0)
        bearish_votes = sum(1 for s in (breakout, ict, macd, smart_money, quant, sentiment_score) if s < 0)
        strong_trend = adx >= float(min_adx)

        if (
            weighted_score >= effective_buy_threshold
            and rsi <= float(max_rsi_for_buy)
            and trend_ok_buy
            and bullish_structure
            and bullish_votes >= int(min_directional_votes)
            and bullish_votes > bearish_votes
            and strong_trend
            and volatility_ok
        ):
            action = "BUY"
        elif (
            weighted_score <= effective_sell_threshold
            and rsi >= float(min_rsi_for_sell)
            and trend_ok_sell
            and bearish_structure
            and bearish_votes >= int(min_directional_votes)
            and bearish_votes > bullish_votes
            and strong_trend
            and volatility_ok
        ):
            action = "SELL"
        else:
            action = "HOLD"

        confidence = min(0.95, max(0.50, 0.50 + abs(weighted_score)))
        if confidence >= 0.78:
            risk_level = "high"
        elif confidence >= 0.62:
            risk_level = "moderate"
        else:
            risk_level = "low"

        buy_contributors = []
        sell_contributors = []

        components = [
            ("breakout", breakout, weighted_breakout),
            ("ict", ict, weighted_ict),
            ("macd", macd, weighted_macd),
            ("smart_money", smart_money, weighted_smart_money),
            ("quant", quant, weighted_quant),
            ("sentiment", sentiment_score, weighted_sentiment),
        ]

        for name, signal_value, weighted_value in components:
            if signal_value > 0:
                buy_contributors.append(f"{name}(+{weighted_value:.3f})")
            elif signal_value < 0:
                sell_contributors.append(f"{name}({weighted_value:.3f})")

        blockers = []
        if action == "BUY":
            if not trend_ok_buy and not bullish_structure:
                blockers.append("trend_or_structure_not_bullish")
            if rsi >= 70:
                blockers.append("rsi_overbought_filter")
            if bullish_votes < int(min_directional_votes):
                blockers.append("insufficient_bullish_consensus")
            if not strong_trend:
                blockers.append("weak_trend_filter")
        elif action == "SELL":
            if not trend_ok_sell and not bearish_structure:
                blockers.append("trend_or_structure_not_bearish")
            if rsi <= 30:
                blockers.append("rsi_oversold_filter")
            if bearish_votes < int(min_directional_votes):
                blockers.append("insufficient_bearish_consensus")
            if not strong_trend:
                blockers.append("weak_trend_filter")
        else:
            if weighted_score < buy_threshold and weighted_score > sell_threshold:
                blockers.append("consensus_score_in_neutral_zone")
            if not trend_ok_buy and not trend_ok_sell:
                blockers.append("trend_filter_conflict")
            if not volatility_ok:
                blockers.append("volatility_regime_filter")
            if not quant_enabled:
                blockers.append("quant_disabled_low_accuracy")

        detailed_reasoning = (
            f"took {action} because weighted_score={weighted_score:.3f} "
            f"(buy>= {effective_buy_threshold:.2f}, sell<= {effective_sell_threshold:.2f}); "
            f"buy_contributors={buy_contributors if buy_contributors else ['none']}; "
            f"sell_contributors={sell_contributors if sell_contributors else ['none']}; "
            f"filters: rsi={rsi:.2f}, trend_ok_buy={trend_ok_buy}, trend_ok_sell={trend_ok_sell}, "
            f"bullish_structure={bullish_structure}, bearish_structure={bearish_structure}, "
            f"bullish_votes={bullish_votes}, bearish_votes={bearish_votes}, "
            f"atr_pct={atr_pct:.4f}, adx={adx:.2f}, strong_trend={strong_trend}, "
            f"volatility_ok={volatility_ok}, quant_confidence={float(quant_confidence):.2f}, "
            f"quant_enabled={quant_enabled}; "
            f"blockers={blockers if blockers else ['none']}"
        )

        return {
            "action": action,
            "confidence": f"{confidence:.2f}",
            "risk_level": risk_level,
            "reasoning": detailed_reasoning,
            "strategy_scores": {
                "breakout": breakout,
                "ict": ict,
                "macd": macd,
                "smart_money": smart_money,
                "quant": quant,
                "sentiment": sentiment_score,
                "weighted": round(weighted_score, 3),
                "weighted_components": {
                    "breakout": round(weighted_breakout, 3),
                    "ict": round(weighted_ict, 3),
                    "macd": round(weighted_macd, 3),
                    "smart_money": round(weighted_smart_money, 3),
                    "quant": round(weighted_quant, 3),
                    "sentiment": round(weighted_sentiment, 3),
                },
                "thresholds": {
                    "buy": round(effective_buy_threshold, 3),
                    "sell": round(effective_sell_threshold, 3),
                },
            },
        }

    def _breakout_signal(self, df, lookback=20):
        if len(df) <= lookback:
            return 0

        recent = df.iloc[-(lookback + 1):-1]
        latest = df.iloc[-1]

        prev_high = float(recent["High"].max())
        prev_low = float(recent["Low"].min())
        close = float(latest["Close"])

        if close > prev_high:
            return 1
        if close < prev_low:
            return -1
        return 0

    def _ict_signal(self, df):
        if len(df) < 12:
            return 0

        latest = df.iloc[-1]
        prev = df.iloc[-2]
        swings = df.iloc[-12:-2]

        swing_high = float(swings["High"].max())
        swing_low = float(swings["Low"].min())

        bullish_sweep = float(latest["Low"]) < swing_low and float(latest["Close"]) > swing_low
        bearish_sweep = float(latest["High"]) > swing_high and float(latest["Close"]) < swing_high

        bos_bull = float(latest["Close"]) > float(prev["High"])
        bos_bear = float(latest["Close"]) < float(prev["Low"])

        if bullish_sweep and bos_bull:
            return 1
        if bearish_sweep and bos_bear:
            return -1
        return 0

    def _macd_signal(self, latest):
        macd = float(latest["macd"])
        signal = float(latest["macd_signal"])
        if macd > signal:
            return 1
        if macd < signal:
            return -1
        return 0

    def _smart_money_signal(self, df):
        if len(df) < 25:
            return 0

        c1 = df.iloc[-3]
        c3 = df.iloc[-1]
        latest = df.iloc[-1]

        bullish_fvg = float(c1["High"]) < float(c3["Low"])
        bearish_fvg = float(c1["Low"]) > float(c3["High"])

        bodies = (df["Close"] - df["Open"]).abs().iloc[-21:-1]
        avg_body = float(bodies.mean()) if len(bodies) > 0 else 0.0
        latest_body = abs(float(latest["Close"]) - float(latest["Open"]))
        displacement = avg_body > 0 and latest_body > (1.5 * avg_body)

        vol_mean = float(df["Volume"].iloc[-21:-1].mean())
        vol_spike = vol_mean > 0 and float(latest["Volume"]) > (1.2 * vol_mean)

        if bullish_fvg and displacement and vol_spike:
            return 1
        if bearish_fvg and displacement and vol_spike:
            return -1
        return 0