# Recommendation Relevance Labeling Guide

Label each business once per user profile in `recommendation_relevance.csv`.

## Scale

- `2` — Highly relevant: feasible with the user's capital, a credible fit for their skills, compatible with the preferred setup and available time, and plausible for the selected local market.
- `1` — Possible: one major gap remains, such as needing more capital, missing a core skill, or requiring a different setup.
- `0` — Not relevant: multiple major gaps, infeasible budget, incompatible setup, or a poor local-market fit.

## Rules

1. Judge the business for the specific profile in that row, not for a generic entrepreneur.
2. Use the profile's capital, skills, experience, available time, setup, and location.
3. Do not copy the model score. The score is one signal, not the answer.
4. A business can be relevant even if it is not in the current displayed results. The first rows match the app's displayed results; later rows are additional candidates. Skill-restricted profiles show fewer app results, so their worksheet has fewer rows.
5. If you are unsure, use `1` and explain the uncertainty in `notes`.
6. Leave `relevance` blank only while labeling is still in progress.
7. Put your name or initials in `labeled_by`.

## Suggested review order

1. Check whether the start-small capital is feasible.
2. Check whether the business needs skills the user does not have.
3. Check setup and time compatibility.
4. Check whether the local market makes the business plausible.
5. Assign `2`, `1`, or `0`.

## Labeling completion

The benchmark is ready for evaluation only when every row has a value in `relevance`.
