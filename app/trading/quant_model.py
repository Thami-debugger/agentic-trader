import pandas as pd

try:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import train_test_split
    SKLEARN_AVAILABLE = True
except Exception:
    SKLEARN_AVAILABLE = False


class HeuristicDirectionModel:

    def predict(self, features):
        row = features.iloc[0]
        score = (
            float(row.get('trend_gap', 0.0))
            + float(row.get('macd_pct', 0.0))
            - (0.3 * float(row.get('atr_pct', 0.0)))
        )
        return [1 if score >= 0 else 0]

    def predict_proba(self, features):
        row = features.iloc[0]
        score = (
            float(row.get('trend_gap', 0.0))
            + float(row.get('macd_pct', 0.0))
            - (0.3 * float(row.get('atr_pct', 0.0)))
        )
        bullish = max(0.0, min(1.0, 0.5 + (score * 10)))
        bearish = 1.0 - bullish
        return [[bearish, bullish]]

class QuantModel:

    def _build_features(self, latest_row):
        close = float(latest_row['Close']) if float(latest_row['Close']) != 0 else 1.0
        return {
            'rsi': float(latest_row['rsi']),
            'macd_pct': float(latest_row['macd']) / close,
            'trend_gap': (float(latest_row['ema_20']) - float(latest_row['sma_50'])) / close,
            'atr_pct': float(latest_row.get('atr_14', 0.0)) / close,
            'bb_width': (float(latest_row.get('bb_high', close)) - float(latest_row.get('bb_low', close))) / close,
        }

    def train_model(self, df):

        df = df.copy()
        df = df.dropna()

        # Regime-aware features reduce sensitivity to raw price scale.
        df['macd_pct'] = df['macd'] / df['Close'].replace(0, 1)
        df['trend_gap'] = (df['ema_20'] - df['sma_50']) / df['Close'].replace(0, 1)
        df['atr_pct'] = df['atr_14'] / df['Close'].replace(0, 1)
        df['bb_width'] = (df['bb_high'] - df['bb_low']) / df['Close'].replace(0, 1)
        df = df.dropna()

        df['target'] = (
            df['Close'].shift(-1) > df['Close']
        ).astype(int)

        features = [
            'rsi',
            'macd_pct',
            'trend_gap',
            'atr_pct',
            'bb_width',
        ]

        X = df[features]
        y = df['target']

        if SKLEARN_AVAILABLE and len(df) > 40:
            X_train, X_test, y_train, y_test = train_test_split(
                X,
                y,
                test_size=0.2,
                shuffle=False
            )

            model = RandomForestClassifier(
                n_estimators=300,
                max_depth=6,
                min_samples_leaf=5,
                random_state=42,
                class_weight='balanced_subsample',
                n_jobs=1,
            )

            model.fit(X_train, y_train)

            accuracy = model.score(X_test, y_test)
        else:
            model = HeuristicDirectionModel()
            class_balance = float(y.mean()) if len(y) > 0 else 0.5
            accuracy = max(class_balance, 1.0 - class_balance)

        return model, accuracy

    def predict(self, model, latest_row):

        prediction, _ = self.predict_with_confidence(model, latest_row)
        return prediction

    def predict_with_confidence(self, model, latest_row):

        features = pd.DataFrame([self._build_features(latest_row)])

        prediction = int(model.predict(features)[0])

        quant_confidence = 0.5
        if hasattr(model, "predict_proba"):
            probabilities = model.predict_proba(features)
            if probabilities is not None and len(probabilities) > 0:
                row = probabilities[0]
                if len(row) >= 2:
                    quant_confidence = float(max(row))

        return prediction, quant_confidence