# AIML-01 Fraud Analyst Dashboard

Next.js frontend for the AIML-01 fraud detection capstone.

## Current status

- UI foundation: implemented
- Prediction form and secure server-side API proxy: pending
- Analyst alerts and persistent case management: pending
- Authentication and authorization: pending
- Live Kafka streaming: not connected
- Public deployment: pending

The existing FastAPI backend currently supports fixed-hour
(step 377) development scoring. Do not represent it as a
live production fraud detection service.

Never expose the backend API key through NEXT_PUBLIC variables.
