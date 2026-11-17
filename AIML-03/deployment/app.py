
import os
os.environ.setdefault("TF_USE_LEGACY_KERAS", "1")

import json
import hashlib
from pathlib import Path
from contextlib import asynccontextmanager

import numpy as np
import pandas as pd
import redis

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from recommendation_engine import RecommendationEngine
from new_item_recommender import NewItemRecommender


PROJECT_DIR = Path(__file__).resolve().parent.parent

CACHE_TTL = 3600
CACHE_VERSION = "aiml03_standalone_v1"


class RecommendationRequest(BaseModel):
    user_id: int | None = None
    top_k: int = Field(default=10, ge=1, le=50)
    preferred_genres: list[str] | None = None


def make_cache_key(payload):
    normalized = {
        "user_id": payload.user_id,
        "top_k": payload.top_k,
        "preferred_genres": sorted({
            genre.strip().lower()
            for genre in (payload.preferred_genres or [])
        })
    }

    raw = json.dumps(normalized, sort_keys=True)

    digest = hashlib.sha256(
        raw.encode("utf-8")
    ).hexdigest()

    return f"{CACHE_VERSION}:{digest}"


def clean_records(df):
    clean = df.replace(
        [np.inf, -np.inf],
        np.nan
    ).astype(object)

    clean = clean.where(pd.notna(clean), None)
    return clean.to_dict(orient="records")


@asynccontextmanager
async def lifespan(app: FastAPI):

    # Load model once per application process
    app.state.engine = RecommendationEngine(PROJECT_DIR)
    app.state.new_item_engine = NewItemRecommender(PROJECT_DIR)

    # Redis is optional for availability
    app.state.redis = None

    try:
        cache = redis.Redis(
            host="127.0.0.1",
            port=6379,
            db=0,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2
        )
        cache.ping()
        app.state.redis = cache
        print("Redis connected!")

    except redis.RedisError:
        print("Redis unavailable. Running without cache.")

    yield

    if app.state.redis is not None:
        app.state.redis.close()


app = FastAPI(
    title="AIML-03 Recommendation API",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/health")
def health(request: Request):
    return {
        "status": "ok",
        "model_loaded": hasattr(
            request.app.state, "engine"
        ),
        "redis_connected": (
            request.app.state.redis is not None
        )
    }


@app.post("/recommend")
def recommend(
    payload: RecommendationRequest,
    request: Request
):

    cache_key = make_cache_key(payload)
    cache = request.app.state.redis

    # Try cache first
    if cache is not None:
        try:
            cached = cache.get(cache_key)

            if cached is not None:
                response = json.loads(cached)
                response["cache_status"] = "HIT"
                return response

        except redis.RedisError:
            pass

    try:
        result = request.app.state.engine.recommend(
            user_id=payload.user_id,
            top_k=payload.top_k,
            preferred_genres=payload.preferred_genres
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc)
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Recommendation generation failed"
        ) from exc

    response = {
        "user_id": payload.user_id,
        "recommendation_count": len(result),
        "recommendations": clean_records(result),
        "cache_status": "MISS"
    }

    if cache is not None:
        try:
            cache.set(
                name=cache_key,
                value=json.dumps(response),
                ex=CACHE_TTL
            )
        except redis.RedisError:
            pass

    return response


class NewItemRequest(BaseModel):
    preferred_genres: list[str] = Field(min_length=1)
    top_k: int = Field(default=10, ge=1, le=50)


@app.post("/recommend/new-items")
def recommend_new_items_api(
    payload: NewItemRequest,
    request: Request
):
    try:
        result = request.app.state.new_item_engine.recommend(
            preferred_genres=payload.preferred_genres,
            top_k=payload.top_k
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc)
        ) from exc

    return {
        "recommendation_count": len(result),
        "recommendation_type": "new_item_content",
        "recommendations": clean_records(result)
    }
