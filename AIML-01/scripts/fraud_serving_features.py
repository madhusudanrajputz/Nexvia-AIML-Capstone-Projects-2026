
"""PaySim 23-feature pre-authorization serving transformer.

Historical features must exclude current/same-hour events.
Hours-since-previous == -1 is an allowed history sentinel.
No fraud labels, future balances, or device/location proxies.
"""

import numpy as np
import pandas as pd

CURRENT_FIELDS = [
    "type", "amount", "oldbalanceOrg", "oldbalanceDest"
]

HISTORICAL_FIELDS = [
    "origin_previous_count",
    "origin_previous_total",
    "origin_previous_mean",
    "origin_hours_since_previous",
    "destination_previous_count",
    "destination_previous_total",
    "destination_previous_mean",
    "destination_hours_since_previous",
]

FEATURE_NAMES = [
    "amount_log",
    "origin_balance_log",
    "destination_balance_log",
    "type_cash_in",
    "type_cash_out",
    "type_debit",
    "type_payment",
    "type_transfer",
    "origin_previous_count",
    "origin_previous_total_log",
    "origin_previous_mean_log",
    "origin_hours_since_previous",
    "destination_previous_count",
    "destination_previous_total_log",
    "destination_previous_mean_log",
    "destination_hours_since_previous",
    "amount_vs_origin_mean",
    "amount_vs_destination_mean",
    "amount_to_origin_balance",
    "amount_to_destination_balance",
    "origin_has_history",
    "destination_has_history",
    "origin_balance_insufficient",
]

VALID_TYPES = {
    "CASH_IN", "CASH_OUT", "DEBIT", "PAYMENT", "TRANSFER"
}

HOUR_FIELDS = {
    "origin_hours_since_previous",
    "destination_hours_since_previous"
}


def build_features(transactions, historical):
    current = pd.DataFrame(transactions).reset_index(drop=True)
    history = pd.DataFrame(historical).reset_index(drop=True)

    if len(current) != len(history) or len(current) == 0:
        raise ValueError("Empty or misaligned input rows")

    for name in CURRENT_FIELDS:
        if name not in current:
            raise ValueError("Missing current field: " + name)

    for name in HISTORICAL_FIELDS:
        if name not in history:
            raise ValueError("Missing historical field: " + name)

    types = current["type"].astype(str)
    if not types.isin(VALID_TYPES).all():
        raise ValueError("Invalid transaction type")

    c = {}
    for name in CURRENT_FIELDS[1:]:
        values = pd.to_numeric(
            current[name], errors="raise"
        ).to_numpy(dtype=np.float64)

        if not np.isfinite(values).all() or (values < 0).any():
            raise ValueError("Invalid current numeric field: " + name)

        c[name] = values

    h = {}
    for name in HISTORICAL_FIELDS:
        values = pd.to_numeric(
            history[name], errors="raise"
        ).fillna(0).to_numpy(dtype=np.float64)

        if not np.isfinite(values).all():
            raise ValueError("Nonfinite historical field: " + name)

        if name in HOUR_FIELDS:
            # -1 represents no previous transaction.
            if ((values < 0) & (values != -1)).any():
                raise ValueError("Invalid historical hour sentinel: " + name)
        elif (values < 0).any():
            raise ValueError("Negative historical statistic: " + name)

        h[name] = values

    amount = c["amount"]
    origin_balance = c["oldbalanceOrg"]
    dest_balance = c["oldbalanceDest"]

    origin_mean = h["origin_previous_mean"]
    dest_mean = h["destination_previous_mean"]

    def ratio_when_positive(numerator, denominator):
        return np.divide(
            numerator,
            denominator,
            out=np.zeros_like(numerator),
            where=denominator > 0
        )

    features = {
        "amount_log": np.log1p(amount),
        "origin_balance_log": np.log1p(origin_balance),
        "destination_balance_log": np.log1p(dest_balance),
        "origin_previous_count": h["origin_previous_count"],
        "origin_previous_total_log": np.log1p(
            h["origin_previous_total"]
        ),
        "origin_previous_mean_log": np.log1p(
            origin_mean
        ),
        "origin_hours_since_previous": h[
            "origin_hours_since_previous"
        ],
        "destination_previous_count": h[
            "destination_previous_count"
        ],
        "destination_previous_total_log": np.log1p(
            h["destination_previous_total"]
        ),
        "destination_previous_mean_log": np.log1p(dest_mean),
        "destination_hours_since_previous": h[
            "destination_hours_since_previous"
        ],
        "amount_vs_origin_mean": ratio_when_positive(
            amount, origin_mean
        ),
        "amount_vs_destination_mean": ratio_when_positive(
            amount, dest_mean
        ),
        "amount_to_origin_balance": amount / (origin_balance + 1),
        "amount_to_destination_balance": amount / (dest_balance + 1),
        "origin_has_history": (
            h["origin_previous_count"] > 0
        ).astype(float),
        "destination_has_history": (
            h["destination_previous_count"] > 0
        ).astype(float),
        "origin_balance_insufficient": (
            amount > origin_balance
        ).astype(float),
    }

    for kind in VALID_TYPES:
        features["type_" + kind.lower()] = (
            types.to_numpy() == kind
        ).astype(float)

    output = pd.DataFrame({
        name: features[name] for name in FEATURE_NAMES
    })

    if not np.isfinite(output.to_numpy()).all():
        raise ValueError("Nonfinite model input")

    return output


def build_one(transaction, historical):
    return build_features(
        [transaction], [historical]
    ).iloc[0].to_dict()
