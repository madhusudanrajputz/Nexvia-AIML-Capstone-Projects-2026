# Large-Scale Personalized Recommendation Engine

**Project ID:** AIML-03
**Organization:** Nexvia Technologies
**Project Type:** AI/ML Internship Capstone
**Dataset:** MovieLens 25M
**Status:** Functional research prototype

## Abstract

This project presents a personalized movie recommendation engine using a two-stage neural recommendation architecture. A Two-Tower model generates user and movie representations, FAISS retrieves candidate movies, and a Wide & Deep model reranks the candidates using interaction and historical features. FastAPI provides prediction endpoints, while Redis supports optional response caching. Apache Airflow was used to test reproducible model retraining and artifact validation workflows. The project also investigates cold-start recommendations, ONNX model portability, offline evaluation, and temporal data leakage.

## 1. Introduction

Recommendation systems help users discover relevant content from large item catalogs. Movie recommendation becomes challenging when user preferences, item popularity, sparse interactions, and computational efficiency must be considered simultaneously.

The objective of this project was to design and evaluate a two-stage recommendation prototype that separates candidate retrieval from candidate ranking, while exposing predictions through an API.

### 1.1 Objectives

- Process and explore the MovieLens 25M dataset.
- Implement Two-Tower neural retrieval.
- Use FAISS for candidate search.
- Implement Wide & Deep candidate ranking.
- Support new-user and new-item recommendation scenarios.
- Develop API inference and optional caching.
- Test Airflow-triggered retraining workflows.
- Evaluate recommendation quality and temporal integrity.

## 2. Dataset and Preprocessing

The project uses MovieLens 25M, containing approximately 25 million ratings from 162,541 users across 62,423 movies. Apache Spark was used for data processing. The initial neural experiments used a sampled subset of the training interactions rather than all ratings.

A chronological partition separated historical training interactions from subsequent validation and test periods. The retrieval training sample contained 195,359 ratings, while the selected retrieval validation sample contained 1,069 positive interactions from 55 users.

The ranking experiment used an internal chronological partition containing 166,055 training rows and 29,304 validation rows.

## 3. System Architecture

The engine follows a retrieval-and-ranking architecture.

1. Interaction data is transformed into model features.
2. The Two-Tower model generates embedding representations.
3. FAISS retrieves potential recommendation candidates.
4. Historical user and movie features are prepared.
5. A Wide & Deep model scores and reranks candidates.
6. FastAPI returns the recommended movies.
7. Redis optionally caches repeated responses.

The repository provides a detailed architecture diagram in ARCHITECTURE.md.

## 4. Recommendation Methodology

### 4.1 Two-Tower Retrieval

The retrieval system uses separate user and movie towers to represent users and movies in a shared embedding space. The tested prototype uses 32-dimensional embeddings and TensorFlow Recommenders.

### 4.2 FAISS Candidate Search

Movie embeddings are indexed using FAISS IndexFlatIP, which performs exact inner-product search over the indexed embedding vectors. The tested retrieval index contains 7,028 candidate movies. Previously seen movies are excluded from recommendations.

### 4.3 Wide & Deep Ranking

A Wide & Deep ranking model estimates the probability of a positive user-item interaction. Model inputs include mapped user identifiers, mapped movie identifiers, and four numerical features describing historical activity and rating patterns.

The original ranking experiment achieved a preliminary validation ROC AUC of approximately 0.7594. This classification metric is distinct from Recall@10 and NDCG@10.

### 4.4 Cold-Start Recommendations

New users receive a popularity-based recommendation list. Genre preferences can filter eligible movies. A separate content-based method recommends items with no interactions in the sampled training dataset, using genre-set similarity.

## 5. Deployment and Automation

### 5.1 FastAPI

FastAPI exposes health-check, recommendation, and new-item recommendation endpoints. Local HTTP tests successfully exercised the service. A fresh Python process also successfully loaded saved models and generated known-user and cold-start recommendations.

### 5.2 Redis Caching

Redis supports optional response caching. In a local benchmark, cached requests were substantially faster than uncached requests. These measurements are environment-specific and do not establish production latency.

### 5.3 Apache Airflow

Airflow workflows were tested for retrieval model training, FAISS rebuilding, ranking training, and staged-artifact validation. These were manually executed smoke workflows. Automatic model promotion remains disabled.

### 5.4 ONNX and Triton Preparation

The ranking model was exported to ONNX and evaluated with ONNX Runtime on CPU. Across 100 synthetic inputs, the maximum absolute difference compared with Keras predictions was approximately 1.79e-7.

The ranking ONNX model was deployed through NVIDIA Triton Inference Server 2.74.0 using the ONNX Runtime CPU backend. Live HTTP inference returned status 200. The Triton prediction (0.5337831378) matched direct ONNX Runtime inference exactly for the tested input (maximum absolute difference: 0.0). The observed single-request latency was 4.21 ms; this is not a production latency benchmark.

## 6. Experimental Results

### 6.1 Preliminary Offline Model Comparison

The evaluation covers the same selected 55 users.

| Metric | Popularity Baseline | Two-Stage + Ranking |
|---|---:|---:|
| Recall@10 | 0.044186 | 0.024384 |
| NDCG@10 | 0.077582 | 0.041228 |

### 6.2 Paired Bootstrap Evaluation

A paired percentile-bootstrap analysis was performed by resampling the same evaluation users.

- Recall@10 difference (Two-Stage minus Popularity): -0.019803; 95% CI [-0.031743, -0.009280].
- NDCG@10 difference (Two-Stage minus Popularity): -0.036354; 95% CI [-0.060687, -0.011235].

Popularity performed better than the Two-Stage model on both measured metrics for this selected sample. The analysis does not establish the same result for all MovieLens users or real online traffic.

## 7. Validation and Data Leakage Audit

The project performed artifact inventory checks, saved-model loading tests, FAISS index-alignment checks, and point-in-time historical-feature verification.

All 22 artifacts in the defined inventory were present. The clean-load test passed for personalized and cold-start inference.

The strict timestamp audit verified 158,028 user-timestamp groups with zero historical-feature mismatches. Movie historical counts and averages also matched independent calculations.

The historical-feature audit passed. The overall pipeline audit remains a partial pass because complete end-to-end reproducibility and all evaluation assumptions have not been independently established.

## 8. Limitations

- Neural experiments used sampled interactions.
- The principal offline comparison uses only 55 selected users.
- Popularity currently outperforms the Two-Stage model.
- Retrieval and ranking components use different training cutoffs.
- Full dataset-scale model quality has not been established.
- Triton CPU inference passed a local functional test; production load, availability and GPU serving have not been verified.
- The Airflow workflows are smoke tests, not scheduled production jobs.
- No real online A/B test or CTR uplift has been measured.

## 9. Future Scope

Future work includes consistent-cutoff retraining, larger and more representative offline evaluations, improved retrieval and ranking architectures, hard-negative sampling, systematic hyperparameter tuning, production-scale Triton serving validation, and controlled online experimentation where real traffic is available.

## 10. Conclusion

The project demonstrates an integrated personalized recommendation prototype combining neural retrieval, FAISS indexing, deep ranking, API delivery, caching, and training automation. Engineering tests confirm that key components execute successfully. However, the evaluated popularity baseline performs better than the current two-stage model on the selected offline sample. The project therefore establishes a working experimental foundation rather than claiming superior recommendation accuracy or production deployment readiness.

## References

1. GroupLens Research. MovieLens 25M Dataset. https://grouplens.org/datasets/movielens/25m/
2. TensorFlow Recommenders documentation. https://www.tensorflow.org/recommenders
3. FAISS documentation. https://github.com/facebookresearch/faiss
4. Apache Airflow documentation. https://airflow.apache.org/docs/
5. NVIDIA Triton Inference Server documentation. https://docs.nvidia.com/deeplearning/triton-inference-server/


## 11. Implementation Verification Update (3 November 2026)

### 11.1 Scheduled Airflow Validation

The daily validation DAG completed a scheduler-triggered run
successfully. Artifact and evaluation validation tasks passed.

Evidence: `results/airflow_validation/scheduled_validation_evidence.json`

### 11.2 Scheduled Retrieval Retraining

The weekly retrieval smoke-retraining DAG completed a
scheduler-triggered run successfully.

- DAG ID: `aiml03_retrieval_training_pipeline`
- Run ID: `scheduled__2026-10-31T20:30:00+00:00`
- Run type: `scheduled`
- Final state: `success`
- Training mode: one-epoch smoke test
- Retrieval training: PASS
- FAISS rebuilding: PASS
- Staging validation: PASS
- Production model promotion: disabled

The workflow demonstrates scheduled execution in a temporary
Google Colab runtime, not persistent production automation.

Evidence: `results/airflow_validation/scheduled_retraining_evidence.json`

### 11.3 Synthetic A/B Testing

A reproducible demonstration assigned 55 evaluated users
between two variants:

- Control A: Popularity Baseline, 28 users
- Treatment B: Two-Stage V1 + Ranking, 27 users
- Total synthetic impressions: 550
- Total synthetic clicks: 23
- Control synthetic CTR: 3.5714%
- Treatment synthetic CTR: 4.8148%
- Synthetic CTR difference (B minus A):
  1.2434%
- Bootstrap 95% confidence interval:
  [-1.9977%,
  4.1935%]

Clicks were generated using an arbitrary probability rule
independent of recommendation relevance. Consequently,
these CTR results do not establish actual online performance,
a causal treatment effect, or model superiority.

The preliminary paired offline evaluation instead favors
the Popularity Baseline on Recall@10 and NDCG@10.
Automatic treatment promotion remains disabled.

Evidence: `results/ab_testing/AB_V2_Final_Experiment_Report.json`

### 11.4 ONNX CPU Inference Verification

The existing ranking ONNX model was loaded and executed
using ONNX Runtime on CPU.

- Inference status: PASS
- Synthetic input prediction: 0.53378314
- NVIDIA Triton server HTTP inference: VERIFIED (CPU, single-request functional test)

Direct ONNX Runtime execution confirmed model executability. A subsequent live Triton HTTP request confirmed functional model serving and produced an identical prediction.

Evidence: `results/triton_validation/ONNX_CPU_Inference_Evidence.json` and `results/triton_validation/Triton_Live_HTTP_Inference_Evidence.json`

### 11.5 Outstanding Limitations

- Production-grade Triton load testing, high availability and GPU serving have not been verified.
- Continuous unattended Airflow operation has not been established.
- Full-scale scheduled retraining has not been verified.
- Real online A/B testing has not been performed.
- Preliminary offline evaluation has known limitations.
- Final production deployment and monitoring are pending.

### 11.6 Apache Spark Preprocessing Reproducibility

The preprocessing pipeline was reconstructed in
`preprocessing/build_spark_features.py` using MovieLens 25M
and a candidate global cutoff of `1466837397`.

The script was executed independently in an isolated output
directory. All five regenerated Parquet datasets matched the
existing datasets in row counts, column sets and compared
values, with zero mismatched rows under a numerical tolerance
of `1e-6` for floating-point columns.

| Dataset | Rows | Mismatches |
|---|---:|---:|
| movie_features | 34,461 | 0 |
| user_features | 137,883 | 0 |
| movie_catalog | 62,423 | 0 |
| user_genre_features | 2,256,087 | 0 |
| popularity_baseline | 8,806 | 0 |

This verifies reproducibility of these five feature datasets.
It does not independently prove that every downstream model
uses leakage-free features or a consistent training cutoff.

Evidence: `results/spark_validation/Spark_Reproducibility_Evidence.json`

### 11.7 Live Redis and Triton Verification

The local FastAPI recommendation endpoint was exercised
with Redis enabled. Repeated identical requests demonstrated
a cache MISS followed by a HIT while preserving recommendation
results. Observed local timings were approximately 1018.50 ms
and 5.11 ms, respectively. These are illustrative local
measurements, not production benchmarks.

NVIDIA Triton 2.74.0 successfully served the ranking model
through its HTTP inference endpoint using the CPU ONNX Runtime
backend. The returned prediction matched direct ONNX Runtime
execution exactly for the tested sample.

Evidence: `results/triton_validation/Triton_Live_HTTP_Inference_Evidence.json`
