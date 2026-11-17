# AIML-03: A/B Experiment Report

## Experiment design

- Control A: Popularity Baseline
- Treatment B: Two-Stage V1 + Ranking
- Evaluated participants: 55
- Assignment: seeded, user-level, balanced
- Synthetic impressions per user: 10
- Real online traffic: No

## Synthetic CTR demonstration

| Metric | A | B |
|---|---:|---:|
| Users | 28 | 27 |
| Impressions | 280 | 270 |
| Synthetic clicks | 10 | 13 |
| Synthetic CTR | 3.57% | 4.81% |

CTR difference (B - A): 1.24%

95% user-bootstrap confidence interval:
[-2.00%,
4.19%]

These are artificial click events generated independently of
recommendation relevance. They do not establish online performance.

## Preliminary paired offline evaluation

| Metric | Popularity A | Two-Stage B | Difference B - A | 95% CI |
|---|---:|---:|---:|---|
| recall_at_10 | 0.04419 | 0.02438 | -0.01980 | [-0.03174, -0.00928] |
| ndcg_at_10 | 0.07758 | 0.04123 | -0.03635 | [-0.06069, -0.01123] |

## Limitations

- MovieLens does not supply live recommendation impression/click outcomes.
- Synthetic CTR does not estimate actual CTR.
- The offline evaluation covers only 55 selected users.
- Training cutoffs and historical feature leakage require further auditing.
- No causal online A/B uplift has been established.

## Decision

Retain the Popularity Baseline as the offline-preferred model.
Do not automatically promote the Two-Stage model.

## Implementation status

- User assignment: Implemented
- Synthetic event logging: Implemented
- CTR computation: Implemented
- User-level bootstrap: Implemented
- Offline comparison: Available
- Real online A/B testing: Not implemented
