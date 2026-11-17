
from pathlib import Path
import pandas as pd
import numpy as np


def validate_evaluation(project_dir):

    results_dir = Path(project_dir) / "results"

    path = results_dir / "Four_Model_Preliminary_Comparison.csv"

    if not path.exists():
        raise FileNotFoundError(
            "Model comparison results not found"
        )

    df = pd.read_csv(path)

    required_columns = [
        "Model",
        "Evaluated_Users",
        "Mean_Recall_at_10",
        "Mean_NDCG_at_10"
    ]

    missing = [
        col for col in required_columns
        if col not in df.columns
    ]

    if missing:
        raise ValueError(
            f"Missing evaluation columns: {missing}"
        )

    if df.empty:
        raise ValueError("Evaluation results are empty")

    if df["Model"].duplicated().any():
        raise ValueError("Duplicate model names")

    if (df["Evaluated_Users"] <= 0).any():
        raise ValueError("Invalid evaluated user counts")

    for metric in [
        "Mean_Recall_at_10",
        "Mean_NDCG_at_10"
    ]:
        values = pd.to_numeric(
            df[metric], errors="coerce"
        )

        if not np.isfinite(values).all():
            raise ValueError(
                f"Invalid numeric values in {metric}"
            )

        if not values.between(0, 1).all():
            raise ValueError(
                f"{metric} outside [0,1]"
            )

    return {
        "status": "PASS",
        "models_checked": int(len(df)),
        "metrics": [
            "Recall@10",
            "NDCG@10"
        ],
        "evaluation_type": "preliminary"
    }
