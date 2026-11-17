import os

from fastapi import FastAPI
from fraud_api_deployment import app as scoring_app
from analyst_cases import create_app

database_path = os.environ["AIML01_CASE_DATABASE_PATH"]
cases_key = os.environ["AIML01_CASES_API_KEY"]

cases_app = create_app(
    database_path=database_path,
    api_key=cases_key,
)

app = FastAPI(
    title="AIML-01 Render Deployment",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

app.mount("/case-service", cases_app)
# Expose the original Case API routes for the Next.js proxy.
app.include_router(cases_app.router)

app.mount("/", scoring_app)
