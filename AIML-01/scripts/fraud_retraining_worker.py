
"""Isolated XGBoost challenger training. Never promotes a model."""

from pathlib import Path
from tempfile import TemporaryDirectory
import json
import math
import os

import duckdb
import numpy as np
import xgboost as xgb
from sklearn.metrics import average_precision_score


def train_challenger(
    dataset_path,
    contract_path,
    output_dir,
    *,
    approved=False,
    rounds=80,
):
    if approved is not True:
        raise PermissionError(
            "Explicit training approval required"
        )

    if not isinstance(rounds, int) or not 1 <= rounds <= 500:
        raise ValueError("Invalid boosting rounds")

    dataset = Path(dataset_path).resolve()
    contract_file = Path(contract_path).resolve()
    output = Path(output_dir).resolve()

    if not dataset.is_file() or not contract_file.is_file():
        raise FileNotFoundError("Training input missing")

    model_file = output / "challenger_model.json"
    report_file = output / "challenger_report.json"

    if model_file.exists() or report_file.exists():
        raise FileExistsError(
            "Existing challenger artifacts must be preserved"
        )

    contract = json.loads(
        contract_file.read_text(encoding="utf-8")
    )

    names = contract["feature_names_ordered"]
    expressions = contract["feature_sql_expressions"]

    if (
        len(names) != 23
        or len(set(names)) != 23
        or any(name not in expressions for name in names)
    ):
        raise ValueError("Invalid 23-feature contract")

    for name in names:
        if not isinstance(expressions[name], str):
            raise ValueError("Invalid feature expression")

    projections = ", ".join(
        f'({expressions[name]}) AS "{name}"'
        for name in names
    )

    # Explicitly exclude the chronological test split.
    connection = duckdb.connect(":memory:")

    try:
        frames = {}

        for split, condition in (
            ("train", "step BETWEEN 1 AND 323"),
            ("validation", "step BETWEEN 324 AND 377"),
        ):
            frames[split] = connection.execute(
                f"""
                SELECT isFraud AS label, {projections}
                FROM read_parquet(?)
                WHERE {condition}
                """,
                [str(dataset)],
            ).fetchdf()

    finally:
        connection.close()

    train = frames["train"]
    validation = frames["validation"]

    if train.empty or validation.empty:
        raise ValueError("Empty chronological split")

    y_train = train["label"].to_numpy(dtype=np.int32)
    y_val = validation["label"].to_numpy(dtype=np.int32)

    if not (
        set(np.unique(y_train)) == {0, 1}
        and set(np.unique(y_val)) == {0, 1}
    ):
        raise ValueError(
            "Both chronological splits need both classes"
        )

    X_train = train[names].to_numpy(dtype=np.float32)
    X_val = validation[names].to_numpy(dtype=np.float32)

    if not (
        np.isfinite(X_train).all()
        and np.isfinite(X_val).all()
    ):
        raise ValueError("Non-finite model features")

    negatives = int(np.sum(y_train == 0))
    positives = int(np.sum(y_train == 1))
    weight = math.sqrt(negatives / positives)

    dtrain = xgb.DMatrix(
        X_train, label=y_train, feature_names=names
    )
    dval = xgb.DMatrix(
        X_val, label=y_val, feature_names=names
    )

    model = xgb.train(
        {
            "objective": "binary:logistic",
            "eval_metric": "aucpr",
            "tree_method": "hist",
            "max_depth": 5,
            "eta": 0.08,
            "scale_pos_weight": weight,
            "seed": 42,
            "nthread": 2,
        },
        dtrain,
        num_boost_round=rounds,
        evals=[(dval, "validation")],
        verbose_eval=False,
    )

    probability = model.predict(dval)

    if not np.isfinite(probability).all():
        raise ValueError("Invalid predictions")

    ap = float(
        average_precision_score(y_val, probability)
    )

    report = {
        "status": "CHALLENGER_EVALUATED",
        "model": "XGBoost weighted challenger",
        "evaluation": "chronological_validation",
        "train_rows": len(train),
        "validation_rows": len(validation),
        "train_positive_rows": positives,
        "validation_positive_rows": int(y_val.sum()),
        "feature_count": len(names),
        "positive_class_weight": weight,
        "boosting_rounds": rounds,
        "validation_pr_auc": ap,
        "test_split_used": False,
        "incumbent_replaced": False,
        "model_promoted": False,
        "mlflow_run_logged": False,
        "note": (
            "A challenger requires separate incumbent "
            "comparison and independent approval."
        ),
    }

    output.mkdir(parents=True, exist_ok=True)

    # Stage output outside the approved model directory.
    with TemporaryDirectory(
        prefix="aiml01_challenger_stage_"
    ) as temporary:
        staging = Path(temporary)
        staged_model = staging / "model.json"

        model.save_model(str(staged_model))

        # Hard linking with exclusive creation prevents overwrite.
        os.link(staged_model, model_file)

        try:
            with report_file.open("x", encoding="utf-8") as file:
                json.dump(report, file, indent=2)
        except Exception:
            model_file.unlink()
            raise

    return report
