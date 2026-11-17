
import os
os.environ["TF_USE_LEGACY_KERAS"] = "1"
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import tensorflow as tf
import tensorflow_recommenders as tfrs


class RetrievalModel(tfrs.Model):

    def __init__(self, user_tower, movie_tower):
        super().__init__()
        self.user_tower = user_tower
        self.movie_tower = movie_tower
        self.retrieval_task = tfrs.tasks.Retrieval()

    def compute_loss(self, features, training=False):
        user_vectors = self.user_tower(features["user"])
        movie_vectors = self.movie_tower(features["movie"])

        return self.retrieval_task(
            user_vectors,
            movie_vectors,
            compute_metrics=False
        )


def build_tower(vocabulary_size, name):

    return tf.keras.Sequential(
        [
            tf.keras.layers.Input(
                shape=(),
                dtype=tf.int32
            ),
            tf.keras.layers.Embedding(
                input_dim=vocabulary_size + 1,
                output_dim=32
            ),
            tf.keras.layers.Dense(
                32,
                activation="relu"
            )
        ],
        name=name
    )


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--project-dir",
        required=True
    )

    parser.add_argument(
        "--epochs",
        type=int,
        default=1
    )

    parser.add_argument(
        "--smoke",
        action="store_true"
    )

    parser.add_argument(
        "--output-name",
        type=str,
        default=None
    )

    args = parser.parse_args()

    if args.epochs < 1:
        raise ValueError("epochs must be positive")

    tf.keras.utils.set_random_seed(42)

    project_dir = Path(args.project_dir)

    source = (
        project_dir
        / "data/processed/two_tower_train_sample.csv"
    )

    df = pd.read_csv(
        source,
        usecols=["userId", "movieId", "rating", "timestamp"]
    )

    df = df[df["rating"] >= 4.0].copy()

    df = df.sort_values(
        ["timestamp", "userId", "movieId"]
    ).reset_index(drop=True)

    if args.smoke:
        df = df.head(4096).copy()

    if len(df) < 100:
        raise ValueError("Insufficient training interactions")

    # Strict internal chronological split
    cutoff_index = int(len(df) * 0.85)

    train = df.iloc[:cutoff_index].copy()
    validation = df.iloc[cutoff_index:].copy()

    assert train["timestamp"].max() <= validation["timestamp"].min()

    # Build vocabularies from training interactions only
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

    # Validation rows must have known IDs
    validation = validation[
        validation["userId"].isin(user_map)
        & validation["movieId"].isin(movie_map)
    ].copy()

    if validation.empty:
        raise ValueError(
            "No warm-start validation interactions"
        )

    def to_dataset(data, shuffle=False):

        user_index = (
            data["userId"].map(user_map)
            .to_numpy(dtype=np.int32)
        )

        movie_index = (
            data["movieId"].map(movie_map)
            .to_numpy(dtype=np.int32)
        )

        dataset = tf.data.Dataset.from_tensor_slices({
            "user": user_index,
            "movie": movie_index
        })

        if shuffle:
            dataset = dataset.shuffle(
                min(len(data), 10000),
                seed=42
            )

        return dataset.batch(256).prefetch(
            tf.data.AUTOTUNE
        )

    train_ds = to_dataset(train, shuffle=True)
    val_ds = to_dataset(validation)

    user_tower = build_tower(
        len(user_ids), "User_Tower"
    )

    movie_tower = build_tower(
        len(movie_ids), "Movie_Tower"
    )

    model = RetrievalModel(
        user_tower,
        movie_tower
    )

    model.compile(
        optimizer=tf.keras.optimizers.Adagrad(
            learning_rate=0.1
        )
    )

    print("Training interactions:", len(train))
    print("Validation interactions:", len(validation))
    print("Training users:", len(user_ids))
    print("Training movies:", len(movie_ids))

    history = model.fit(
        train_ds,
        validation_data=val_ds,
        epochs=args.epochs,
        verbose=1
    )

    # Never overwrite currently deployed models
    run_name = (
        "retrieval_smoke"
        if args.smoke
        else "retrieval_candidate"
    )

    output_name = args.output_name or run_name

    if (
        not output_name
        or not all(
            c.isalnum() or c in "_-"
            for c in output_name
        )
    ):
        raise ValueError("Invalid output folder name")

    output_dir = (
        project_dir / "staging" / output_name
    )

    if output_dir.exists():
        raise FileExistsError(
            f"Staging output already exists: {output_dir}"
        )

    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    user_tower.save(
        str(output_dir / "user_tower.keras")
    )

    movie_tower.save(
        str(output_dir / "movie_tower.keras")
    )

    np.save(
        output_dir / "user_ids.npy",
        user_ids
    )

    np.save(
        output_dir / "movie_ids.npy",
        movie_ids
    )

    metrics = {
        "status": "TRAINED_NOT_PROMOTED",
        "smoke_test": args.smoke,
        "training_interactions": len(train),
        "validation_interactions": len(validation),
        "train_end_timestamp": int(
            train["timestamp"].max()
        ),
        "validation_start_timestamp": int(
            validation["timestamp"].min()
        ),
        "final_train_loss": float(
            history.history["loss"][-1]
        ),
        "final_validation_loss": float(
            history.history["val_loss"][-1]
        )
    }

    (output_dir / "training_metrics.json").write_text(
        json.dumps(metrics, indent=4),
        encoding="utf-8"
    )

    print("Training artifacts saved:", output_dir)
    print("Training script completed!")


if __name__ == "__main__":
    main()
