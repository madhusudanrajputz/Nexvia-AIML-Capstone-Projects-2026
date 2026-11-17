
from pathlib import Path
import pandas as pd


def check_model_promotion(project_dir):

    project_dir = Path(project_dir)

    path = (
        project_dir
        / "results"
        / "Four_Model_Preliminary_Comparison.csv"
    )

    df = pd.read_csv(path)

    baseline = df.loc[
        df["Model"] == "Popularity Baseline"
    ]

    candidate = df.loc[
        df["Model"] == "Two-Stage V1 + Ranking"
    ]

    if len(baseline) != 1 or len(candidate) != 1:
        raise ValueError(
            "Expected baseline or candidate missing/duplicated"
        )

    baseline = baseline.iloc[0]
    candidate = candidate.iloc[0]

    baseline_recall = float(baseline["Mean_Recall_at_10"])
    candidate_recall = float(candidate["Mean_Recall_at_10"])

    baseline_ndcg = float(baseline["Mean_NDCG_at_10"])
    candidate_ndcg = float(candidate["Mean_NDCG_at_10"])

    # Both metrics must be at least as good
    # as the existing baseline.
    metrics_pass = (
        candidate_recall >= baseline_recall
        and candidate_ndcg >= baseline_ndcg
    )

    # Preliminary evaluation cannot authorize deployment.
    # Promotion requires a separate approved evaluation.
    return {
        "status": "HOLD",
        "metrics_pass": bool(metrics_pass),
        "promotion_approved": False,
        "reason": (
            "Preliminary metrics are insufficient for "
            "automatic promotion"
        ),
        "baseline_recall": baseline_recall,
        "candidate_recall": candidate_recall,
        "baseline_ndcg": baseline_ndcg,
        "candidate_ndcg": candidate_ndcg
    }
