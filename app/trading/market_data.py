import yfinance as yf
import pandas as pd

class MarketDataAgent:

    def _normalize_frame(self, df):
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        return df

    def get_gold_data(self):
        symbol = "GC=F"

        df = yf.download(
            symbol,
            period="30d",
            interval="1h"
        )

        df = self._normalize_frame(df)

        return df

    def get_bitcoin_data(self):
        symbol = "BTC-USD"

        df = yf.download(
            symbol,
            period="30d",
            interval="1h"
        )

        df = self._normalize_frame(df)

        return df