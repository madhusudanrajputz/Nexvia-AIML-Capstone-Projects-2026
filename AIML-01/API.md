# AIML-01 API Documentation

## 1. Hosted Application

URL:
https://aiml01-fraud-detection-demo.netlify.app/

The deployed application uses Next.js server-side API routes.
It is separate from the original Python FastAPI services.

## 2. Hosted Prediction Route

POST /api/netlify-predict

Implementation:
dashboard/app/api/netlify-predict/route.js

Purpose:
Score a supported historical transaction using the
approved XGBoost model and historical feature snapshot.

The hosted model uses a 23-feature contract and
decision threshold of 0.48456997.

Authentication and request formatting must follow the
deployed application implementation.

## 3. Scoring and Review Route

POST /api/netlify-score-and-review

Implementation:
dashboard/app/api/netlify-score-and-review/route.js

Purpose:
Provide historical scoring and review-related behavior.

The Netlify deployment must not be described as having
persistent analyst-case storage.

## 4. Original Python Services

Relevant implementation files include:

- api/fraud_api.py
- api/fraud_api_deployment.py
- api/analyst_cases.py
- api/cases_deployment.py

These services are distinct from the hosted Next.js API.

The Python service dependencies, feature-store configuration,
API authentication and storage requirements must be
configured for the selected runtime.

## 5. Verified Example

Historical transaction ID:
paysim:5393914

Original XGBoost fraud probability:
approximately 0.9998253

Expected fraud classification:
true

This is a historical demonstration example,
not a claim of live financial transaction processing.

## 6. Operational Limitations

- Hosted historical data coverage is limited.
- Kafka is not continuously running on Netlify.
- Persistent case management is not available on Netlify.
- Production retraining is disabled.
- API callers must not use this prototype for real
  financial decisions.

Refer to the route source for exact request/response schemas.
No unverified request fields are documented here.
