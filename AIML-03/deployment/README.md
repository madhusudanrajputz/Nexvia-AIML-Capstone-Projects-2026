# AIML-03: Personalized Recommendation Engine

**Organization: Nexvia Technologies**

## Overview

Two-stage movie recommendation prototype using:

- TensorFlow Recommenders: Two-Tower retrieval
- FAISS: vector similarity search
- Wide & Deep neural ranking
- Popularity and genre-based cold-start fallback
- FastAPI: recommendation endpoints
- Redis: optional recommendation caching

## Project structure

AIML-03/
  models/
  faiss_index/
  deployment/
    recommendation_engine.py
    app.py
    requirements.txt
    README.md
    user_snapshot.parquet
    movie_snapshot.parquet
    movies_metadata.parquet
    cold_start_catalog.parquet
    seen_history.parquet

## Installation

Use a compatible Python environment.

Install dependencies:

    pip install -r requirements.txt

## Start the API

Open a terminal inside the deployment directory.

Run:

    uvicorn app:app --host 127.0.0.1 --port 8000

## API Documentation

http://127.0.0.1:8000/docs

## Health Endpoint

GET /health

## Recommendation Endpoint

POST /recommend

Existing user example:

    {"user_id": 100, "top_k": 10}

New user example:

    {"user_id": 99999999, "top_k": 10,
     "preferred_genres": ["Sci-Fi"]}

## Redis Caching

Redis runs on 127.0.0.1:6379.
The API can work without Redis.
Cache expiration: 3600 seconds.

## Evaluation Limitations

- Current recommendation metrics are preliminary.
- Retrieval and ranking training cutoffs differ.
- MovieLens ratings are relevance proxies, not clicks.
- New-item recommendation support is implemented; production-scale effectiveness has not been established.

## Deployment Status

- Fresh-process API tests passed.
- Standalone FastAPI HTTP recommendation requests passed.
- Redis cache MISS/HIT behavior was verified locally.
- NVIDIA Triton 2.74.0 HTTP inference passed on CPU.
- Scheduled Airflow validation and one-epoch retraining smoke tests passed in Colab.
- Strict point-in-time historical-feature checks passed; end-to-end leakage freedom remains unproven.
- Persistent production deployment and monitoring remain unverified.
