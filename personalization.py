import pandas as pd


RISK_MAP = {
    "Low": 1,
    "Medium": 2,
    "High": 3
}


def calculate_interest_match(user_sectors, stock_tags):

    if len(user_sectors) == 0:
        return 50

    matches = 0

    for sector in user_sectors:
        if sector in stock_tags:
            matches += 1

    return (matches / len(user_sectors)) * 100


def calculate_risk_fit(user_risk, stock_risk):

    difference = abs(
        RISK_MAP[user_risk] - RISK_MAP[stock_risk]
    )

    if difference == 0:
        return 100

    elif difference == 1:
        return 70

    return 40


def calculate_market_fit(user_market, stock_market):

    return 100 if user_market == stock_market else 50


def calculate_style_fit(user_style, stock_style):

    return 100 if user_style == stock_style else 60


def calculate_horizon_fit(user_horizon, stock_horizon):

    return 100 if user_horizon == stock_horizon else 65


def calculate_personalized_score(user, stock):

    interest_match = calculate_interest_match(
        user["favorite_sectors"],
        stock["tags"]
    )

    risk_fit = calculate_risk_fit(
        user["risk_level"],
        stock["risk"]
    )

    market_fit = calculate_market_fit(
        user["market"],
        stock["market"]
    )

    style_fit = calculate_style_fit(
        user["style"],
        stock["style"]
    )

    horizon_fit = calculate_horizon_fit(
        user["time_horizon"],
        stock["time_horizon"]
    )

    personalized_score = (
        stock["alpha_score"] * 0.35 +
        interest_match * 0.25 +
        risk_fit * 0.15 +
        stock["momentum_score"] * 0.10 +
        market_fit * 0.05 +
        style_fit * 0.05 +
        horizon_fit * 0.05
    )

    return round(personalized_score, 2)