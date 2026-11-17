
import os
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import joblib
import keras

from sklearn.preprocessing import StandardScaler


FEATURE_COLUMNS = [
    "user_activity",
    "user_historical_avg",
    "movie_popularity",
    "movie_historical_avg"
]


def build_model(num_users, num_movies):

    user_input = keras.Input(
        shape=(), dtype="int32", name="user_input"
    )

    movie_input = keras.Input(
        shape=(), dtype="int32", name="movie_input"
    )

    numeric_input = keras.Input(
        shape=(4,), dtype="float32",
        name="numeric_input"
    )

    user_embedding = keras.layers.Embedding(
        num_users + 1, 32
    )(user_input)

    movie_embedding = keras.layers.Embedding(
        num_movies + 1, 32
    )(movie_input)

    wide = keras.layers.Dense(1)(numeric_input)

    combined = keras.layers.Concatenate()([
        user_embedding,
        movie_embedding,
        numeric_input
    ])

    x = keras.layers.Dense(
        128, activation="relu"
    )(combined)

    x = keras.layers.Dropout(0.2)(x)

    x = keras.layers.Dense(
        64, activation="relu"
    )(x)

    x = keras.layers.Dense(
        32, activation="relu"
    )(x)

    deep = keras.layers.Dense(1)(x)

    combined_score = keras.layers.Add()([
        wide, deep
    ])

    output = keras.layers.Activation(
        "sigmoid"
    )(combined_score)

    model = keras.Model(
        inputs={
            "user_input": user_input,
            "movie_input": movie_input,
            "numeric_input": numeric_input
        },
        outputs=output,
        name="Wide_Deep_Ranking_Model"
    )

    model.compile(
        optimizer=keras.optimizers.Adam(0.001),
        loss="binary_crossentropy",
        metrics=[
            keras.metrics.BinaryAccuracy(name="accuracy"),
            keras.metrics.AUC(name="auc"),
            keras.metrics.AUC(
                curve="PR", name="pr_auc"
            )
        ]
    )

    return model


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--project-dir", required=True
    )

    parser.add_argument(
        "--output-name", required=True
    )

    parser.add_argument(
        "--epochs", type=int, default=1
    )

    parser.add_argument(
        "--smoke", action="store_true"
    )

    args = parser.parse_args()

    if args.epochs < 1:
        raise ValueError("epochs must be positive")

    if not args.output_name or not all(
        c.isalnum() or c in "_-"
        for c in args.output_name
    ):
        raise ValueError("Invalid output name")

    keras.utils.set_random_seed(42)

    project = Path(args.project_dir)

    processed = project / "data" / "processed"

    train = pd.read_parquet(
        processed / "ranking_internal_train.parquet"
    )

    val = pd.read_parquet(
        processed / "ranking_internal_validation.parquet"
    )

    required = [
        "userId", "movieId", "rating", "timestamp"
    ] + FEATURE_COLUMNS

    for name, frame in [
        ("train", train), ("validation", val)
    ]:
        missing = set(required) - set(frame.columns)
        if missing:
            raise ValueError(
                f"{name} missing columns: {missing}"
            )

    # Preserve the original chronological boundary
    assert train["timestamp"].max() < val["timestamp"].min()

    if args.smoke:
        # Small, quick execution test only
        train = train.sort_values(
            ["timestamp", "userId", "movieId"]
        ).tail(12000).copy()

        val = val.sort_values(
            ["timestamp", "userId", "movieId"]
        ).head(3000).copy()

    train = train.reset_index(drop=True)
    val = val.reset_index(drop=True)

    if not (
        np.isfinite(
            train[FEATURE_COLUMNS].to_numpy(
                dtype=np.float32
            )
        ).all()
        and np.isfinite(
            val[FEATURE_COLUMNS].to_numpy(
                dtype=np.float32
            )
        ).all()
    ):
        raise ValueError("Non-finite ranking features")

    user_ids = np.sort(train["userId"].unique())
    movie_ids = np.sort(train["movieId"].unique())

    user_map = {
        int(uid): i + 1
        for i, uid in enumerate(user_ids)
    }

    movie_map = {
        int(mid): i + 1
        for i, mid in enumerate(movie_ids)
    }

    scaler = StandardScaler()

    x_train_numeric = scaler.fit_transform(
        train[FEATURE_COLUMNS]
    ).astype(np.float32)

    x_val_numeric = scaler.transform(
        val[FEATURE_COLUMNS]
    ).astype(np.float32)

    def prepare_inputs(frame, numeric):
        return {
            "user_input": (
                frame["userId"]
                .map(user_map)
                .fillna(0)
                .to_numpy(dtype=np.int32)
            ),
            "movie_input": (
                frame["movieId"]
                .map(movie_map)
                .fillna(0)
                .to_numpy(dtype=np.int32)
            ),
            "numeric_input": numeric
        }

    x_train = prepare_inputs(train, x_train_numeric)
    x_val = prepare_inputs(val, x_val_numeric)

    y_train = (
        train["rating"] >= 4.0
    ).astype(np.float32).to_numpy()

    y_val = (
        val["rating"] >= 4.0
    ).astype(np.float32).to_numpy()

    model = build_model(
        len(user_ids), len(movie_ids)
    )

    print("Training rows:", len(train))
    print("Validation rows:", len(val))

    history = model.fit(
        x_train,
        y_train,
        validation_data=(x_val, y_val),
        epochs=args.epochs,
        batch_size=512,
        verbose=1
    )

    output_dir = (
        project / "staging" / args.output_name
    )

    if output_dir.exists():
        raise FileExistsError(
            f"Staging already exists: {output_dir}"
        )

    output_dir.mkdir(parents=True)

    model.save(
        str(output_dir / "ranking_model.keras")
    )

    np.save(
        output_dir / "ranking_user_ids.npy",
        user_ids
    )

    np.save(
        output_dir / "ranking_movie_ids.npy",
        movie_ids
    )

    joblib.dump(
        scaler,
        output_dir / "ranking_scaler.joblib"
    )

    metrics = model.evaluate(
        x_val, y_val,
        return_dict=True,
        verbose=0
    )

    report = {
        "status": "TRAINED_NOT_PROMOTED",
        "smoke_test": bool(args.smoke),
        "training_rows": int(len(train)),
        "validation_rows": int(len(val)),
        "training_end_timestamp": int(
            train["timestamp"].max()
        ),
        "validation_start_timestamp": int(
            val["timestamp"].min()
        ),
        "validation_metrics": {
            key: float(value)
            for key, value in metrics.items()
        },
        "evaluation_note":
            "Observed-rating classification only; "
            "not Recall@10 or NDCG@10."
    }

    (output_dir / "training_metrics.json").write_text(
        json.dumps(report, indent=4),
        encoding="utf-8"
    )

    print("Ranking artifacts saved:", output_dir)
    print("Ranking smoke training completed!")


if __name__ == "__main__":
    main()
