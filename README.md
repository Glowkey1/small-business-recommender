# Small Business Idea Recommender & Business Pathway System

A Machine Learning-powered web platform that analyzes entrepreneur attributes (capital, skills, experience, commitment, and setup preference) to recommend feasible small businesses and generate actionable, phased launch pathways.

## Architecture
- **Recommendation System:** Skill-connected filtering via the curated catalog + capital feasibility gating + TF-IDF skill cosine similarity + multi-attribute scoring. When skills are selected, only businesses linked to those skills are returned (fewer than five if not enough exist), and over-budget matches stay visible with their budget gap.
- **Pathway Generator:** Dynamically extracts requirements, risks, and strategies from catalog data and calculates skill gaps.
- **Success Classification Analysis:** Calibrated, app-only advisory estimate trained from Dataset 1. It is not part of ranking while its weight is `0.0`.

## Getting Started
1. Place your raw files into `data/raw/dataset_1/` and `data/raw/dataset_2/`.
2. Run data preprocessing: `python ml/preprocessing.py`
3. Train the success model: `python train_success_models.py`
4. Seed database: `python seed_real_data.py`
5. Run the web application: `python app.py`

The success model uses only inputs the app collects: initial capital, financial record keeping, internet usage, marketing effort, partnership, and industry experience. It is advisory: `Config.RECOMMENDATION_WEIGHTS["success"]` is `0.0`, so it does not affect recommendation ranking. Training writes `models/success_model.joblib`, `models/model_metrics.json`, and `models/success_model_card.json`.

## Recommendation Evaluation

1. Generate the 30-profile benchmark and labeling worksheet:
   `python create_recommendation_benchmark.py`
   The first rows per profile match the app's displayed results; later rows are additional candidates. Skill-restricted profiles return fewer rows when fewer businesses connect to the selected skills.
2. Label every row in `data/eval/recommendation_relevance.csv` using `data/eval/recommendation_labeling_guide.md`.
3. Evaluate the current ranking:
   `python evaluate_recommender.py`
4. Tune only after labeling:
   `python tune_recommender.py`

Until every worksheet row is labeled, the evaluator reports coverage, diversity, and budget feasibility only, and exits with status `2`. Once labeled, it writes Precision@k, Recall@k, NDCG@k, MAP@k, coverage, diversity, and feasibility to `models/recommendation_metrics.json`.

Recall and NDCG use the full catalog only when every profile has full-catalog labels. The worksheet produces a `partial_labeled_candidates` scope, so those two metrics are relative to the labeled candidates, not the whole catalog.

The tuner refuses incomplete labels. It searches 27 restricted weight variants, keeps the success weight at `0.0`, reports profile-level cross-validation, and writes the selected weights to `models/recommendation_weights.json`. The recommender loads that file automatically when present; delete it to revert to `Config.RECOMMENDATION_WEIGHTS`.

### Provisional draft pass

Draft labels are useful for checking the pipeline, not for claiming real-world accuracy:

```
python create_draft_relevance.py --all-businesses
python evaluate_recommender.py --relevance data/eval/recommendation_relevance_draft_full.csv --output models/recommendation_metrics_draft_full.json
python tune_recommender.py --relevance data/eval/recommendation_relevance_draft_full.csv --output models/recommendation_weights_draft.json --report models/recommendation_tuning_report_draft.json
```

The draft pass writes separate `*_draft*` files and does not activate the weights. Replace the draft labels with human labels before treating any tuning result as evidence. To activate reviewed weights, copy the chosen file to `models/recommendation_weights.json`; delete that file to revert.
