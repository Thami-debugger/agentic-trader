import ta

class IndicatorAgent:

    def add_indicators(self, df):

        df['rsi'] = ta.momentum.RSIIndicator(
            df['Close']
        ).rsi()

        macd = ta.trend.MACD(df['Close'])

        df['macd'] = macd.macd()
        df['macd_signal'] = macd.macd_signal()

        df['ema_20'] = ta.trend.EMAIndicator(
            df['Close'],
            window=20
        ).ema_indicator()

        df['sma_50'] = ta.trend.SMAIndicator(
            df['Close'],
            window=50
        ).sma_indicator()

        bb = ta.volatility.BollingerBands(df['Close'])

        df['bb_high'] = bb.bollinger_hband()
        df['bb_low'] = bb.bollinger_lband()

        atr = ta.volatility.AverageTrueRange(
            high=df['High'],
            low=df['Low'],
            close=df['Close'],
            window=14,
        )
        df['atr_14'] = atr.average_true_range()

        adx = ta.trend.ADXIndicator(
            high=df['High'],
            low=df['Low'],
            close=df['Close'],
            window=14,
        )
        df['adx_14'] = adx.adx()

        return df