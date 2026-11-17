
import os
os.environ.setdefault("TF_USE_LEGACY_KERAS", "1")

from pathlib import Path
import numpy as np
import pandas as pd
import joblib
import faiss
import tf_keras
import keras


class RecommendationEngine:

    def __init__(self, project_dir):

        self.project_dir = Path(project_dir)
        model_dir = self.project_dir / "models"
        faiss_dir = self.project_dir / "faiss_index"
        deploy_dir = self.project_dir / "deployment"

        # Load retrieval models (legacy Keras)
        self.user_tower = tf_keras.models.load_model(
            str(model_dir / "user_tower.keras"),
            compile=False
        )

        self.movie_tower = tf_keras.models.load_model(
            str(model_dir / "movie_tower.keras"),
            compile=False
        )

        # Load ranking model (Keras 3)
        self.ranking_model = keras.models.load_model(
            str(model_dir / "wide_deep_ranking_model.keras"),
            compile=False
        )

        # Load FAISS
        self.index = faiss.read_index(
            str(faiss_dir / "movie_embeddings.index")
        )

        self.indexed_movie_ids = np.load(
            faiss_dir / "indexed_movie_ids.npy"
        ).astype(int)

        assert self.index.ntotal == len(self.indexed_movie_ids)

        # Retrieval vocabulary
        user_ids = np.load(model_dir / "user_ids.npy")
        movie_ids = np.load(model_dir / "movie_ids.npy")

        self.user_map = {
            int(uid): i + 1
            for i, uid in enumerate(user_ids)
        }

        self.movie_map = {
            int(mid): i + 1
            for i, mid in enumerate(movie_ids)
        }

        # Ranking vocabulary
        rank_user_ids = np.load(
            model_dir / "rank_user_ids_final.npy"
        )

        rank_movie_ids = np.load(
            model_dir / "rank_movie_ids_final.npy"
        )

        self.rank_user_map = {
            int(uid): i + 1
            for i, uid in enumerate(rank_user_ids)
        }

        self.rank_movie_map = {
            int(mid): i + 1
            for i, mid in enumerate(rank_movie_ids)
        }

        # Feature scaler
        self.scaler = joblib.load(
            model_dir / "ranking_feature_scaler.joblib"
        )

        # Feature snapshots
        self.user_snapshot = pd.read_parquet(
            deploy_dir / "user_snapshot.parquet"
        ).set_index("userId")

        self.movie_snapshot = pd.read_parquet(
            deploy_dir / "movie_snapshot.parquet"
        ).set_index("movieId")

        # Catalog
        self.metadata = pd.read_parquet(
            deploy_dir / "movies_metadata.parquet"
        )

        self.cold_catalog = pd.read_parquet(
            deploy_dir / "cold_start_catalog.parquet"
        )

        # Seen history
        history = pd.read_parquet(
            deploy_dir / "seen_history.parquet"
        )

        self.seen_by_user = {
            int(uid): set(group["movieId"].astype(int))
            for uid, group in history.groupby("userId")
        }

        print("Standalone recommendation engine loaded!")

    def cold_start(self, top_k=10, preferred_genres=None):

        df = self.cold_catalog.copy()

        if preferred_genres:
            preferred = {
                genre.strip().lower()
                for genre in preferred_genres
            }

            df = df[
                df["genres"].fillna("").apply(
                    lambda genres: bool(
                        preferred.intersection(
                            g.strip().lower()
                            for g in genres.split("|")
                        )
                    )
                )
            ]

        df = df[df["rating_count"] > 0]

        df = df.sort_values(
            ["popularity_score", "rating_count"],
            ascending=False
        )

        result = df[
            [
                "movieId",
                "title",
                "genres",
                "rating_count",
                "popularity_score"
            ]
        ].head(top_k).copy()

        result["recommendation_type"] = "cold_start"

        return result.reset_index(drop=True)

    def recommend(
        self,
        user_id=None,
        top_k=10,
        preferred_genres=None,
        candidates=200
    ):

        if top_k < 1 or top_k > 50:
            raise ValueError("top_k must be between 1 and 50")

        if user_id is None or int(user_id) not in self.user_map:
            return self.cold_start(top_k, preferred_genres)

        user_id = int(user_id)

        # Stage 1: Two-Tower embedding
        user_vector = self.user_tower.predict(
            np.array(
                [self.user_map[user_id]],
                dtype=np.int32
            ),
            verbose=0
        ).astype(np.float32)

        # FAISS candidate retrieval
        _, positions = self.index.search(
            np.ascontiguousarray(user_vector),
            self.index.ntotal
        )

        seen = self.seen_by_user.get(user_id, set())

        candidate_ids = []

        for pos in positions[0]:
            if pos < 0:
                continue

            mid = int(self.indexed_movie_ids[pos])

            if mid not in seen:
                candidate_ids.append(mid)

            if len(candidate_ids) >= max(candidates, top_k):
                break

        if not candidate_ids:
            return self.cold_start(top_k, preferred_genres)

        # User features
        if user_id in self.user_snapshot.index:
            stats = self.user_snapshot.loc[user_id]
            user_activity = np.log1p(stats["user_count"])
            user_avg = float(stats["user_avg"])
        else:
            user_activity = 0.0
            user_avg = 3.5

        # Movie features
        rows = []

        for mid in candidate_ids:

            if mid in self.movie_snapshot.index:
                stats = self.movie_snapshot.loc[mid]
                movie_count = float(stats["movie_count"])
                movie_avg = float(stats["movie_avg"])
            else:
                movie_count = 0.0
                movie_avg = 3.5

            rows.append([
                user_activity,
                user_avg,
                np.log1p(movie_count),
                movie_avg
            ])

        feature_columns = [
            "user_activity",
            "user_historical_avg",
            "movie_popularity",
            "movie_historical_avg"
        ]

        numeric_df = pd.DataFrame(
            rows,
            columns=feature_columns
        )

        numeric_scaled = self.scaler.transform(
            numeric_df
        ).astype(np.float32)

        # Ranking inputs
        inputs = {
            "user_input": np.full(
                len(candidate_ids),
                self.rank_user_map.get(user_id, 0),
                dtype=np.int32
            ),
            "movie_input": np.array(
                [
                    self.rank_movie_map.get(mid, 0)
                    for mid in candidate_ids
                ],
                dtype=np.int32
            ),
            "numeric_input": numeric_scaled
        }

        # Stage 2: Deep ranking
        scores = self.ranking_model.predict(
            inputs,
            batch_size=256,
            verbose=0
        ).reshape(-1)

        result = pd.DataFrame({
            "movieId": candidate_ids,
            "ranking_score": scores
        })

        # Known-user genre filtering
        if preferred_genres:
            preferred = {
                genre.strip().lower()
                for genre in preferred_genres
            }

            result = result.merge(
                self.metadata,
                on="movieId",
                how="left"
            )

            result = result[
                result["genres"].fillna("").apply(
                    lambda genres: bool(
                        preferred.intersection(
                            g.strip().lower()
                            for g in genres.split("|")
                        )
                    )
                )
            ]

            result = result.sort_values(
                "ranking_score",
                ascending=False
            ).head(top_k)

        else:
            result = result.sort_values(
                "ranking_score",
                ascending=False
            ).head(top_k)

            result = result.merge(
                self.metadata,
                on="movieId",
                how="left"
            )

        result["recommendation_type"] = "personalized"

        return result[
            [
                "movieId",
                "title",
                "genres",
                "ranking_score",
                "recommendation_type"
            ]
        ].reset_index(drop=True)
