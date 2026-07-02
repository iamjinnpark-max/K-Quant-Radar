from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

# Features used by the model
FEATURE_COLUMNS = [
    # Technical
    "return_1d",
    "return_5d",
    "return_20d",
    "ma20",
    "ma60",
    "volume_ratio",
    "rsi",
    "volatility_20d",

    # Investor flow
    "foreign_5d",
    "foreign_20d",
    "institution_5d",
    "institution_20d",
    "individual_5d",
    "smart_money_5d",
    "smart_money_20d",

    # Fundamentals
    "bps",
    "per",
    "pbr",
    "eps",
    "div",
    "dps",
    "eps_growth_20d",
    "bps_growth_20d",
    "value_score",
    

    "bb_width",
    "bb_position",

    "adx_14",
    "plus_di",
    "minus_di",

    "revenue",
    "ebitda",
    "net_income",
    "operating_margin",
    "net_margin",
    "roe",
    "debt_ratio",
    "free_cash_flow",
    "financial_score",
    "news_score",
]


def train_prediction_model(df):
    """
    Train a Random Forest model and return:
    - trained model
    - backtest accuracy
    - latest bullish probability
    """

    # Prepare feature matrix (X) and target (y)
    print(FEATURE_COLUMNS)
    X = df[FEATURE_COLUMNS]
    y = df["target"]

    # Train/test split
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.25,
        shuffle=False
    )

    # Build the model
    model = RandomForestClassifier(
        n_estimators=150,
        max_depth=5,
        random_state=42
    )

    # Train
    model.fit(X_train, y_train)

    # Test accuracy
    predictions = model.predict(X_test)
    accuracy = accuracy_score(y_test, predictions)

    # Get probability for the latest day
    latest_features = X.iloc[[-1]]
    probabilities = model.predict_proba(latest_features)[0]
    classes = list(model.classes_)
    if 1 in classes:
        bullish_probability = probabilities[classes.index(1)]
    else:
        bullish_probability = 1.0 if classes[0] == 1 else 0.0

    return model, accuracy, bullish_probability
