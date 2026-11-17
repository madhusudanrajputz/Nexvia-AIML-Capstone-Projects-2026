# AIML-01: Render Deployment Guide

## Hosting

Target platform: Render.

Services declared in the project root `render.yaml`:

1. `aiml01-fraud-api`: Docker backend with a persistent disk.
2. `aiml01-dashboard`: Next.js web application.

The backend requires a paid Render service with disk support.
Review pricing and approve billing before creating resources.

## Before Deployment

- Verify that the approved XGBoost model is included.
- Verify the Feast seed manifest and snapshot checksum.
- Keep original datasets, runtime databases and credentials private.
- Push the cleaned project to a private GitHub repository first.
- Confirm Render has access to the repository.
- Review `render.yaml` before creating services.

## Backend

Dockerfile:

`deployment/render/Dockerfile`

Application startup:

`deployment/render/render_launcher.py`

Public routes include:

- `GET /health`
- `POST /predict`
- `GET /cases`
- `POST /cases`
- `GET /cases/{case_id}`
- `PATCH /cases/{case_id}`

The equivalent case API is also mounted under `/case-service`.

Private backend access requires the matching `x-api-key`
header. Do not put API keys in client-side JavaScript.

## Persistent Case Storage

Attach a Render persistent disk at `/var/data`.

Set:

`AIML01_CASE_DATABASE_PATH=/var/data/cases.db`

The launcher refuses to start if the disk mount is missing.
SQLite is configured for one backend instance; do not assume
multi-replica write safety.

## Environment Variables

Backend:

- `AIML01_DEPLOYMENT_API_KEY`
- `AIML01_CASES_API_KEY`
- `AIML01_CASE_DATABASE_PATH`

Dashboard:

- `AIML01_BACKEND_URL`
- `AIML01_CASES_SERVICE_URL`
- `AIML01_BACKEND_API_KEY`
- `AIML01_CASES_API_KEY`
- `AIML01_DASHBOARD_ACCESS_CODE`

For the current combined Render backend, both dashboard service
URLs should refer to the public backend origin.

The dashboard backend API key must equal the backend service's
deployment API key. The dashboard case API key must equal the
backend case API key.

Configure secrets privately in Render. Do not commit real values
to Git or print them in public deployment logs.

## Deployment Procedure

1. Review and push the cleaned repository to GitHub.
2. Connect GitHub to Render.
3. Create the services using the repository's `render.yaml`.
4. Review billing before enabling the paid backend and disk.
5. Configure required dashboard environment variables.
6. Deploy the backend and verify `GET /health`.
7. Deploy the dashboard and verify its public URL.
8. Test unauthorized requests and authenticated predictions.
9. Test a verified demonstration transaction and case creation.
10. Verify case persistence across a controlled restart.
11. Save public URLs and final test evidence for submission.

## Expected Demonstration

Historical event: `paysim:5393914`

Expected model probability: approximately `0.9998253`

Expected result: `FLAGGED_FOR_REVIEW`

This requires the included verified Feast demo seed. It does not
demonstrate complete streaming feature coverage.

## Important Limitations

- The Feast snapshot is a fixed-hour demonstration seed.
- The original Kafka consumer is not deployed by this Blueprint.
- Continuous Kafka processing is not yet verified publicly.
- Automatic retraining in production is not verified.
- Docker build and Render public HTTP deployment require testing.
- Actual payment and service creation require explicit approval.
