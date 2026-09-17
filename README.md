# Small Business Idea Recommender & Business Pathway System

A Machine Learning-powered web platform that analyzes entrepreneur attributes (capital, skills, experience, commitment, and setup preference) to recommend feasible small businesses and generate actionable, phased launch pathways.

## Architecture
- **Recommendation System:** Capital feasibility gating + TF-IDF skill cosine similarity + multi-attribute scoring.
- **Pathway Generator:** Dynamically extracts requirements, risks, and strategies from catalog data and calculates skill gaps.
- **Success Classification Analysis:** Evaluates success factors from Dataset 1 for administrative insight.

## Getting Started
1. Place your raw files into `data/raw/dataset_1/` and `data/raw/dataset_2/`.
2. Run data preprocessing: `python ml/preprocessing.py`
3. Train ML models: `python ml/train_models.py`
4. Seed database: `python seed_real_data.py`
5. Run the web application: `python app.py`
