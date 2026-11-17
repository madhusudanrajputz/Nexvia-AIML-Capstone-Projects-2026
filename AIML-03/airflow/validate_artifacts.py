
from pathlib import Path
import json
import numpy as np
import pandas as pd


def validate_artifacts(project_dir):

    project_dir = Path(project_dir)

    models = project_dir / "models"
    index_dir = project_dir / "faiss_index"
    deployment = project_dir / "deployment"

    required = [
        models / "user_tower.keras",
        models / "movie_tower.keras",
        models / "wide_deep_ranking_model.keras",
        models / "ranking_feature_scaler.joblib",
        models / "user_ids.npy",
        models / "movie_ids.npy",
        models / "rank_user_ids_final.npy",
        models / "rank_movie_ids_final.npy",
        index_dir / "movie_embeddings.index",
        index_dir / "indexed_movie_ids.npy",
        deployment / "movies_metadata.parquet",
        deployment / "cold_start_catalog.parquet",
        deployment / "user_snapshot.parquet",
        deployment / "movie_snapshot.parquet",
        deployment / "seen_history.parquet",
        deployment / "new_item_catalog.parquet"
    ]

    missing = [
        str(path)
        for path in required
        if not path.is_file() or path.stat().st_size == 0
    ]

    if missing:
        raise FileNotFoundError(
            "Missing or empty artifacts: " + str(missing)
        )

    catalog = pd.read_parquet(
        deployment / "cold_start_catalog.parquet"
    )

    if catalog.empty:
        raise ValueError("Cold-start catalog is empty")

    if catalog["movieId"].isna().any():
        raise ValueError("Null movie IDs detected")

    if catalog["movieId"].duplicated().any():
        raise ValueError("Duplicate movie IDs detected")

    if (catalog["rating_count"] < 0).any():
        raise ValueError("Negative rating counts detected")

    indexed_ids = np.load(
        index_dir / "indexed_movie_ids.npy"
    )

    if len(indexed_ids) == 0:
        raise ValueError("FAISS movie ID list is empty")

    if len(np.unique(indexed_ids)) != len(indexed_ids):
        raise ValueError("Duplicate FAISS movie IDs")

    # Check that indexed IDs belong to retrieval vocabulary
    retrieval_ids = np.load(models / "movie_ids.npy")

    if not np.isin(indexed_ids, retrieval_ids).all():
        raise ValueError(
            "FAISS contains movie IDs outside retrieval vocabulary"
        )

    return {
        "status": "PASS",
        "artifacts_checked": len(required),
        "catalog_movies": int(len(catalog)),
        "indexed_movies": int(len(indexed_ids))
    }
