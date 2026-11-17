
"""Kafka-to-Feast historical feature and buffered-state integration.

Development replay. A durable consumer-group commit,
watermarking, transactional persistence and late-event
handling are required before production deployment.
"""

from pathlib import Path
import json
import os
import sys

import numpy as np
import pandas as pd
from feast import FeatureStore

project = Path(os.environ["AIML_PROJECT"])
local = Path(os.environ["AIML_LOCAL"])
repo = local / "feast_repo"

sys.path.insert(0, str(project / "scripts"))

from fraud_streaming_state import HourBufferedAccountState
from fraud_serving_features import build_features

store = FeatureStore(repo_path=str(repo))
messages = pd.read_parquet(local / "messages.parquet")
source = pd.read_parquet(local / "historical.parquet")
reference = pd.read_parquet(local / "reference.parquet")

assert len(messages) == len(source) == len(reference) == 40

origin_fields = [
    "origin_previous_count",
    "origin_previous_total",
    "origin_previous_mean",
    "origin_hours_since_previous"
]
destination_fields = [
    "destination_previous_count",
    "destination_previous_total",
    "destination_previous_mean",
    "destination_hours_since_previous"
]

# Historical values were generated from strictly
# previous hours. All current events are at step 377.
timestamp = pd.Timestamp(
    "2026-01-01T00:00:00Z"
) + pd.Timedelta(hours=377)

def account_rows(account, fields):
    cols = [account] + fields
    frame = source[cols].copy()

    # For repeated accounts in the same hour,
    # previous-hour features must not differ.
    for field in fields:
        assert (
            frame.groupby(account)[field]
            .nunique(dropna=False).le(1).all()
        ), f"Inconsistent same-hour state: {field}"

    frame = frame.drop_duplicates(
        subset=[account]
    ).reset_index(drop=True)

    frame["event_timestamp"] = timestamp
    return frame

origin = account_rows("nameOrig", origin_fields)
destination = account_rows(
    "nameDest", destination_fields
)

# Real Feast 0.67.0 online writes.
store.write_to_online_store(
    feature_view_name="origin_account_history",
    df=origin
)
store.write_to_online_store(
    feature_view_name="destination_account_history",
    df=destination
)

feature_refs = [
    "origin_account_history:" + x
    for x in origin_fields
] + [
    "destination_account_history:" + x
    for x in destination_fields
]

raw = store.get_online_features(
    features=feature_refs,
    entity_rows=messages[
        ["nameOrig", "nameDest"]
    ].to_dict("records"),
    full_feature_names=True
).to_dict()

history = pd.DataFrame(index=range(len(messages)))

for field in origin_fields + destination_fields:
    view = (
        "origin_account_history"
        if field.startswith("origin_")
        else "destination_account_history"
    )
    key = view + "__" + field
    assert key in raw, f"Missing Feast field: {key}"
    history[field] = raw[key]

assert history.notna().all().all()

state = HourBufferedAccountState()
state.advance_to(377)

# Initialize state from the verified prior-hour
# Feast features. This is a bootstrap, not a claim
# of replaying the complete historical transaction log.
for i, event in messages.iterrows():
    for role, account_column in (
        ("origin", "nameOrig"),
        ("destination", "nameDest")
    ):
        account = str(event[account_column])
        count = int(history.loc[
            i, role + "_previous_count"
        ])
        total = float(history.loc[
            i, role + "_previous_total"
        ])
        age = int(history.loc[
            i, role + "_hours_since_previous"
        ])

        key = state._key(role, account)
        if key in state.committed:
            continue

        if count == 0:
            assert age == -1
            assert np.isclose(total, 0)
        else:
            assert age >= 1
            state.committed[key] = {
                "count": count,
                "total": total,
                "last_step": 377 - age
            }

checks = 0
mismatches = 0

for i, event in messages.iterrows():
    before = {
        **state.snapshot(
            "origin", str(event["nameOrig"]), 377
        ),
        **state.snapshot(
            "destination", str(event["nameDest"]), 377
        )
    }

    for field in origin_fields + destination_fields:
        checks += 1
        if not np.isclose(
            float(before[field]),
            float(history.loc[i, field]),
            rtol=1e-7, atol=1e-8
        ):
            mismatches += 1

    # Same-hour events are buffered and cannot
    # change another step-377 transaction's history.
    state.observe_transaction(
        str(event["nameOrig"]),
        str(event["nameDest"]),
        377,
        float(event["amount"])
    )

current = messages[
    ["type", "amount", "oldbalanceOrg", "oldbalanceDest"]
]

calculated = build_features(current, history)

order = json.loads(
    (project / "features/XGBoost_Feature_Contract.json")
    .read_text(encoding="utf-8")
)["feature_names_ordered"]

assert list(calculated.columns) == order

details = []

for feature in order:
    actual = calculated[feature].to_numpy(float)
    expected = reference[feature].to_numpy(float)
    matched = np.isclose(
        actual, expected,
        rtol=1e-7,
        atol=1e-8,
        equal_nan=False
    )
    details.append({
        "feature": feature,
        "matched": int(matched.sum()),
        "mismatched": int((~matched).sum())
    })

feature_mismatches = sum(
    x["mismatched"] for x in details
)

pd.DataFrame(details).to_csv(
    local / "integration_parity.csv", index=False
)

result = {
    "kafka_events": len(messages),
    "origin_accounts": len(origin),
    "destination_accounts": len(destination),
    "online_feature_nulls": int(
        history.isna().sum().sum()
    ),
    "state_snapshot_checks": checks,
    "state_snapshot_mismatches": mismatches,
    "model_feature_comparisons": (
        len(messages) * len(order)
    ),
    "model_feature_mismatches": int(
        feature_mismatches
    ),
    "same_hour_events_buffered": len(messages),
    "online_hour_boundary_updates_tested": False,
    "durable_consumer_offset_commits_tested": False,
    "scoring_integrated": False
}

print("RESULT_BEGIN")
print(json.dumps(result, indent=2))
print("RESULT_END")
