"""Demo entry point with an explicitly configured case database."""

import os
from analyst_cases import create_app

app = create_app(
    database_path="/app/case_state/cases.db",
    api_key=os.environ["AIML01_CASES_API_KEY"],
)
