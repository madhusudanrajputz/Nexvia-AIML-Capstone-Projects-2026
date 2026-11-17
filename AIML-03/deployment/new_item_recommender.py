
from pathlib import Path
import pandas as pd


class NewItemRecommender:

    def __init__(self, project_dir):
        path = (
            Path(project_dir)
            / "deployment"
            / "new_item_catalog.parquet"
        )

        self.catalog = pd.read_parquet(path)

    def recommend(self, preferred_genres, top_k=10):

        if not 1 <= top_k <= 50:
            raise ValueError(
                "top_k must be between 1 and 50"
            )

        preferred = {
            str(g).strip().lower()
            for g in (preferred_genres or [])
            if str(g).strip()
        }

        if not preferred:
            raise ValueError(
                "At least one preferred genre is required"
            )

        df = self.catalog.copy()

        def similarity(genres):
            movie_genres = {
                g.strip().lower()
                for g in str(genres).split("|")
            }

            intersection = preferred & movie_genres
            union = preferred | movie_genres

            return (
                len(intersection) / len(union)
                if union else 0.0
            )

        df["content_score"] = df["genres"].apply(
            similarity
        )

        df = df[df["content_score"] > 0]

        df = df.sort_values(
            ["content_score", "movieId"],
            ascending=[False, True]
        )

        result = df[
            [
                "movieId",
                "title",
                "genres",
                "rating_count",
                "content_score"
            ]
        ].head(top_k).copy()

        result["recommendation_type"] = "new_item_content"

        return result.reset_index(drop=True)
