# System Weakness Analysis — Small Business Recommender

**Date:** 2026-10-20  
**Scope:** Flask web app, authentication, recommendation engine, success model, market data pipeline, templates, tests, deployment assets, and data artifacts.  
**Method:** Static code review of all Python/HTML/JS modules, data/artifact inspection, dependency and Git review, plus runtime checks against the loaded catalog and models.

---

## Executive Summary

The system works end-to-end for the happy path, but it has several **high-impact weaknesses** that affect production safety, data accuracy, and the credibility of the recommendations:

1. The app cannot be launched with the included `gunicorn` dependency using the standard `app:app` target, and startup performs `db.create_all()` plus seeding in every worker.
2. Authentication is under-hardened: no rate limiting, a known default admin password in a shipping script, weak password policy, and no password recovery/verification.
3. The landing page promises a "hard budget filter" and nationwide data coverage, but the engine does not filter by budget and only scores 133 CALABARZON municipalities.
4. The success model is fed partly fabricated or inconsistent feature values (including age medians that disagree with the trained model metadata), so its contribution is weak and potentially misleading.
5. Four market categories (28% of the catalog) always receive the same location score of `0.60` because their density columns were never built.
6. The source data pipeline is not reproducible: `data/raw/dataset_1/` is missing even though tests and README depend on it.
7. Financial profile data is stored in the client-side Flask session cookie rather than server-side state.
8. Key features are dead or misleading: "Saved" is never written, feedback cannot be tied to a recommendation, and the admin "live accuracy" is actually a satisfaction poll.

### Severity Overview

| Severity | Count | Themes |
|---|---:|---|
| Critical | 4 | Deployment, default admin credentials, data/claim mismatch, model validity |
| High | 8 | Session privacy, market scoring bug, reproducibility, concurrency, test isolation, auth hardening |
| Medium | 14 | Scoring logic, stale data, skill normalization, feedback, performance, dead features |
| Low | 12 | Code hygiene, UX, docs, dependencies, repository bloat |

---

## Critical Weaknesses

### C1. Production startup is broken or unsafe

- `app.py:85-88` only creates the Flask object inside `if __name__ == "__main__"`. There is no module-level `app`, so `gunicorn app:app` fails with an attribute error even though `gunicorn` is a declared dependency (`requirements.txt:13`).
- `create_app()` runs `db.create_all()` and `seed_database_if_empty()` on every application startup (`app.py:25-31`, `services/seed_service.py:10-51`). Under multiple Gunicorn workers this races: workers may seed simultaneously, produce duplicate-key failures, or hit SQLite "database is locked" errors.
- There are no migrations. `db.create_all()` does not alter existing tables, so schema changes require deleting the database.
- SQLite foreign keys are not enabled per connection, so `ondelete="CASCADE"` on users, recommendations, and skills is not enforced by default.

**Impact:** Standard production deployment can fail at startup, corrupt/duplicate seed data, or silently ignore referential integrity.  
**Fix:** Expose `app = create_app()` (or document `gunicorn 'app:create_app()'`), run migrations (Alembic/Flask-Migrate), seed via a one-off command, enable SQLite `PRAGMA foreign_keys=ON`, and use PostgreSQL/MySQL with proper connection pooling for multi-worker deployment.

### C2. Default admin account with a known password ships in the repo

`seed_real_data.py:65-69` creates `admin` / `admin123` with `role="admin"`. Anyone who runs the documented setup script gets a predictable administrator account.

**Impact:** Full access to the ML admin panel and model retraining endpoint if the script is run in production.  
**Fix:** Require admin credentials from environment variables, force a password change on first login, or create admins through an explicit CLI with a strong generated password. Add admin 2FA and audit logging.

### C3. UI and README claims contradict actual behavior

- The landing page says businesses above the user's budget are **"strictly excluded"** (`templates/main/landing.html:24-28`). In reality, `recommend()` scores **all** 127 catalog rows (`ml/recommendation_engine.py:322-336`) and never filters on `affordable` (`ml/recommendation_engine.py:339`). A runtime check with ₱1,000 returned an unaffordable business at 68.7% with a ₱2,000 gap.
- The landing page claims **119** business models (`templates/main/landing.html:9`); the catalog currently has **127** rows.
- The landing page and form claim **250 municipalities across 9 regions** (`templates/main/landing.html:41-44`, `templates/user/recommendations_form.html:136`). The market analyzer is locked to CALABARZON and loads **133** municipalities across 1 region and 6 province-level entries (`ml/market_analyzer.py:24-26`).
- The admin metrics page hardcodes dataset counts instead of reading the actual data (`routes/admin.py:42-49`), guaranteeing future drift.

**Impact:** Users make financial decisions based on false assumptions about feasibility and coverage.  
**Fix:** Either implement actual budget gating or rewrite the copy. Compute all displayed counts from the live catalog/database. Align location coverage claims with the actual market file.

### C4. Success model inputs are partly fabricated and inconsistent

The model is a real logistic regression, but the inference adapter does not faithfully map the user/business context:

- `TRAINING_MEDIANS["age"] = 35.0` (`ml/success_model_service.py:18`) conflicts with the trained model metadata median of **40.0** (`models/model_metrics.json:8-11`).
- `business_plan` is always `1.0` (`ml/success_model_service.py:76`), so the model's business-plan feature carries no user signal.
- `financial_record_keeping` is inferred from the **business's** `core_skills` containing "costing" (`ml/success_model_service.py:77`), not from the user, conflating a business attribute with an owner trait.
- `partnership` is set to `1.0` whenever `people_needed` exists and does not contain "solo" (`ml/success_model_service.py:78`). For `"1 person"`, partnership becomes `1.0`, which is incorrect.
- Several features are constants or heuristic placeholders (`age`, `education`, `parent_business_experience`, `owner_gender`, `professional_advice`), so predictions vary mostly by capital, setup, a few skills, and headcount.
- Raw probabilities observed at runtime had only **5 distinct values** for a beginner profile and **3** for an experienced profile across all 127 businesses.
- Scores are then min-max normalized per request (`ml/recommendation_engine.py:325-333`), turning a maximum raw probability of ~0.15 into a displayed `100%` success component for the least-bad option.

**Impact:** The "success" component looks scientific but is coarse, partly incorrect, and normalized relative to the catalog rather than an absolute probability. Presenting it as a percent can mislead users.  
**Fix:** Derive all features from a validated user schema; remove fabricated constants or flag them; derive medians from model metadata; fix the partnership mapping; use calibrated absolute probabilities; or remove the success component from ranking until it is validated.

---

## High-Severity Weaknesses

### H1. Financial profile data is stored client-side

`routes/recommendation.py:51` writes the full cleaned profile (capital, skills, experience, location) into `session["last_profile"]`. Flask's default session is a signed, **not encrypted**, client-side cookie.

**Impact:** Users (or anyone with access to the browser profile/traffic) can read the stored capital and location. It also risks cookie-size problems when many skills are selected.  
**Fix:** Store the last profile server-side keyed by user ID, or recompute it from the database. Keep only an opaque session identifier in the cookie.

### H2. Four market categories always receive a constant location score

`VALID_MARKET_CATEGORIES` lists 12 categories (`ml/market_analyzer.py:10-14`), but the CALABARZON feature build only creates density/count columns for 8 of them (`changes.py:143-200`): Food, Retail, Personal Services, Education, Tourism, Technology, Automotive, Accommodation.

For Financial Services, Healthcare, Professional Services, and Skilled Trades, the fallback lookup at `ml/market_analyzer.py:186-191` finds no column, sets `osm_count=0` and `density=0.0`, then assigns the `"zero"` tier (`ml/market_analyzer.py:231-232`) — always `0.60`, even in a dense city with real businesses. Runtime check: `Advertising Agency` and `Construction Contracting` in Imus both returned `osm_count=0`, `score=0.6`, `data_quality=HIGH`.

This affects **35 of 127 catalog businesses (~28%)**. Another **36** businesses have a blank market category and are excluded from location scoring entirely.

**Impact:** A large share of recommendations is ranked with an incorrect or omitted location signal.  
**Fix:** Build count/density columns for all 12 categories, or explicitly mark unsupported categories as `None` instead of scoring them as zero-density.

### H3. Location coverage is much narrower than advertised and often omitted

- The market file has 133 municipalities (`data/processed/calabarzon_market_features.csv`), not 250.
- 38 municipalities have fewer than 25 mapped records and therefore return no location score (`ml/market_analyzer.py:218-229`).
- One municipality is missing 2024 population and uses a fallback heuristic (`ml/market_analyzer.py:200-216`).
- The form offers every row in the file, so users can select a municipality that will silently omit location scoring.

**Impact:** Users may believe their location was analyzed when it was not.  
**Fix:** Show coverage/confidence in the UI, disable or annotate insufficient-data municipalities, and align the copy with actual coverage.

### H4. The data pipeline is not reproducible

- `data/raw/dataset_1/` does not exist, yet `tests/test_data.py:4` asserts it does and `ml/preprocessing.py:135-157` expects it.
- `process_dataset_1()` reads only `files[0]` (`ml/preprocessing.py:141`), silently ignoring any additional raw CSVs.
- `find_business_files()` looks for files containing "business" in `data/raw/dataset_2/`; none exist there, so it falls back to `data/backup/business.csv` (`ml/preprocessing.py:160-182`).
- `process_dataset_2()` overwrites `data/final/final_skill_dataset.csv` (`ml/preprocessing.py:288-298`), which can destroy the curated skill vocabulary produced by the separate `skill.py` / `create_skill_master.py` workflow.

**Impact:** A fresh clone cannot rebuild the catalog or success dataset from raw inputs, and re-running preprocessing can overwrite curated artifacts.  
**Fix:** Commit raw inputs or document their acquisition, remove the hidden backup fallback, make preprocessing idempotent, and separate raw/interim/final artifacts with explicit versioning.

### H5. Test isolation is broken in several tests

Three modules call `create_app()` first and only then override `SQLALCHEMY_DATABASE_URI`:

- `tests/test_security.py:9-11`
- `tests/test_schema.py:6-8`
- `tests/test_pathway.py:6-8`

Flask-SQLAlchemy binds the engine when `init_app()` runs, so changing the URI afterward does not redirect the engine. Those tests can create/drop tables and write users into the real `instance/app.db` instead of a test database. The current environment also lacks `pytest`, so the suite could not be executed during this review.

**Impact:** Tests are non-hermetic, can corrupt local data, and may pass/fail depending on prior state.  
**Fix:** Pass `test_config` into `create_app()` (as `test_auth.py` does), use an isolated temporary SQLite file, and add a CI job that runs the suite from a clean checkout.

### H6. Authentication is under-hardened

- No rate limiting or account lockout on `/login`, `/register`, or `/feedback` (`routes/auth.py`, `routes/recommendation.py`).
- Password policy is only **6 characters** (`routes/auth.py:31`) with no complexity or breached-password check.
- No email verification, password reset, or account recovery.
- Login accepts either email or username (`routes/auth.py:64`), which is fine functionally, but there is no lockout or audit trail for credential stuffing.
- No admin 2FA, and no logging of failed/successful admin actions.
- The CSRF token is constant for the session, never rotated on login, and CSRF is globally disabled when `TESTING` is true (`app.py:51`). The latter is convenient but risky if `TESTING` is ever set in production.

**Impact:** Brute-force, credential stuffing, and undetected admin abuse are feasible.  
**Fix:** Add Flask-Limiter, lockout/backoff, stronger password requirements, email verification/reset, admin 2FA, CSRF rotation, and explicit production-mode checks.

### H7. Session and HTTP security hardening is incomplete

Security headers currently include only `X-Content-Type-Options`, `X-Frame-Options`, and `Referrer-Policy` (`app.py:57-62`). Missing:

- `Content-Security-Policy` (the app uses inline styles/scripts, so this needs a nonce/hash strategy).
- `Strict-Transport-Security` (HTTPS).
- `Permissions-Policy`.
- `SESSION_COOKIE_SECURE`, `SESSION_COOKIE_SAMESITE`, explicit `SESSION_COOKIE_HTTPONLY`, and session lifetime settings.
- HTTPS enforcement / reverse-proxy awareness (`ProxyFix`).
- Host header validation (`TRUSTED_HOSTS` in newer Flask).

`SECRET_KEY` falls back to an ephemeral random value on every process start when unset (`config.py:31-34`). Under multiple workers, each worker gets a different key, breaking sessions and CSRF tokens; after a restart, all sessions are invalidated. The `.env.example` placeholder is also easy to deploy unchanged.

**Impact:** Session theft, mixed-content issues, unstable sessions, and CSRF failures in production.  
**Fix:** Fail fast when `SECRET_KEY` is missing in non-test mode, set all cookie flags, add CSP/HSTS, and document HTTPS termination.

### H8. Concurrency and data consistency around retraining and seeding

- `routes/recommendation.py:12` instantiates `HybridBusinessRecommender` at module import, which loads CSVs, the market file, and joblib models into every worker at startup.
- Admin retraining reloads the model only in the worker that handled the request (`routes/admin.py:64-73`), so other workers keep the old model until restart.
- Seeding runs concurrently in every worker (`app.py:25-31`), with no lock or migration step.
- Model retraining overwrites production artifacts in place (`train_success_models.py:115-117`) with no versioning, validation gate, or rollback.

**Impact:** Inconsistent recommendations across workers, corrupted/duplicated seed data, and the ability to deploy a bad model instantly.  
**Fix:** Load ML artifacts lazily/centrally, store model versions and metadata, reload via a controlled process, run seeding as a deployment job, and validate a candidate model before promotion.

---

## Medium-Severity Weaknesses

### M1. Skill normalization is inconsistent across three vocabularies

- `final_skill_dataset.csv` has 163 names, `skill_master.csv` has 158, and their union is **182**, with only 139 overlapping (runtime check). Examples: `Ads` vs `Advertising`, `Crm` vs `CRM`, `Ux` vs `UX Design`.
- `seed_service.py:34-48` seeds skills from both files, so the profile page can show duplicate/raw variants.
- The recommender's selectable list is derived separately from catalog aliases (`ml/recommendation_engine.py:97-104`), so a skill saved from the profile page may not appear in the recommender form and is silently dropped.
- `parse_skills_list()` splits on whitespace when no comma exists (`ml/skill_normalizer.py:64`), destroying multi-word skills such as "Customer Service".
- `GENERIC_STOP_FRAGMENTS` removes useful words such as `food`, `child`, `care`, `market`, and `basic` (`ml/skill_normalizer.py:37-40`), which can eliminate meaningful skills from matching and gaps.

**Impact:** Duplicate choices, inconsistent matching, and misleading skill-gap output.  
**Fix:** Define one canonical skill schema, derive the DB, form, and engine from it, preserve multi-word phrases, and only remove truly generic tokens.

### M2. Capital feasibility ignores the catalog's fuller capital fields

The catalog contains `full_start_capital` and `micro_start_capital`, but the engine scores and displays `min_capital` (`ml/recommendation_engine.py:337-371`, `templates/user/recommendations.html:30`). Eight businesses have `full_start_capital` materially higher than `min_capital`:

- Sari-sari Store: min ₱5,000 vs full ₱35,000.
- Home-Based Packed Meals: ₱3,000 vs ₱25,000.
- Motorcycle Wash: ₱3,500 vs ₱30,000.

The preprocessing heuristic also caps capital at ₱150,000 even for businesses needing 200 workers (`ml/preprocessing.py:63-73`). A user can therefore be told a business is affordable based on a micro-start figure while the UI calls it "Required Capital".

**Impact:** Capital feasibility is the highest-weight component, so this directly misranks businesses and can mislead financial decisions.  
**Fix:** Show and score the appropriate capital mode (micro vs full), explain the distinction, and derive tiers from real cost data rather than headcount.

### M3. "Diversity" re-ranking is largely cosmetic

`select_diverse_top_n()` penalizes candidates by only `0.02` for sharing a signature of `(min_capital, setup, experience)` (`ml/recommendation_engine.py:258-307`). Since `min_capital` has only a handful of discrete tiers, many businesses share a signature, but the penalty is tiny relative to score differences. After selection, the final list is re-sorted purely by raw score (`ml/recommendation_engine.py:433-435`), which does not restore diversity in ordering.

**Impact:** Users may see near-duplicate business ideas despite the diversity code.  
**Fix:** Penalize category/skill overlap more meaningfully, use a proper MMR (maximal marginal relevance) approach, and evaluate diversity with a measurable metric.

### M4. Location and success scoring are not calibrated or validated

- Recommendation weights are hand-set (`config.py:84-93`) and never tuned or validated against real outcomes.
- The location curve makes `mid` density (`0.90`) better than `high` (`0.85`) and `very_high` (`0.75`) (`config.py:74-82`), implicitly assuming saturation, but this is undocumented and unevidenced.
- The success model is trained on 250 records with 62 positives and 188 negatives (`models/model_metrics.json:3-6`). Its test set is only 50 records; reported 90% accuracy compares with a 75.2% majority baseline, and CV F1 varies by ±0.066 (`models/model_metrics.json:112-121`).
- The dataset filename suggests UMKM (Indonesian MSME) data (`data/backup/umkm_success_prediction_with_success.csv`) being applied to Philippine businesses, which is a domain-transfer risk.
- There is no precision@k, recall@k, NDCG, calibration curve, or user study for the recommender itself.

**Impact:** Scores appear authoritative but are not empirically validated; the success component may not transfer to the target population.  
**Fix:** Document assumptions, calibrate probabilities, validate against Philippine data, and report recommender quality metrics separately from the success classifier.

### M5. Success model failures are silent

`predict_success_scores()` catches every exception and returns `[None] * len(businesses)` (`ml/success_model_service.py:107-121`). `combine_scores()` then renormalizes the remaining weights (`ml/recommendation_engine.py:39-44`), so a broken model changes rankings without any user-visible or operational signal.

There is also no feature-contract check: training builds columns through `pd.get_dummies` (`train_success_models.py:42-43`), while inference passes a fixed 12-column list (`ml/success_model_service.py:10-15`). If the training schema changes, inference fails silently.

**Impact:** Model outages are invisible, and stale or mismatched artifacts can degrade recommendations indefinitely.  
**Fix:** Fail loudly/log at error level, assert feature schema and model version at load time, expose model health, and include tests that compare training/inference columns.

### M6. Duplicate and contradictory model artifacts

- Production inference uses `models/success_model.joblib` and `models/model_metrics.json` (`config.py:64-65`).
- `ml/evaluate_models.get_current_metrics()` reads `ml/models/success_metrics.pkl` (`ml/evaluate_models.py:14-16`).
- `ml/models/` also contains `success_model.pkl` and `success_model_features.pkl`.
- `MLService` wires these legacy paths but is not used by the app.

**Impact:** Different parts of the system can report different metrics or load different models.  
**Fix:** Keep one model registry/version directory, persist a manifest with schema and metrics, and delete stale artifacts.

### M7. Feedback cannot evaluate recommendations

`RecommendationFeedback` stores only `user_id` and `is_accurate` (`models/recommendation.py:16-21`). The `/feedback` endpoint (`routes/recommendation.py:124-134`) does not record which recommendation, business, or search session was rated, and treats any value other than `"yes"` as negative. The admin page labels the resulting ratio "live accuracy" / "Satisfaction Ratio" (`routes/admin.py:51-53`, `templates/admin/metrics.html:78-93`).

**Impact:** The feedback cannot be used for model evaluation or per-business quality, and the metric name is misleading.  
**Fix:** Link feedback to recommendation IDs and user profiles, store optional comments, and label it as satisfaction, not accuracy. Require a valid `"yes"`/`"no"` value.

### M8. The "Saved" feature is dead

`is_saved` is defined (`models/recommendation.py:11`) and queried (`routes/user.py:37-41`), but no route or template ever sets it to `True`. The `/saved` page is therefore always empty.

**Impact:** A visible feature that never works; user trust erosion.  
**Fix:** Add save/unsave POST endpoints with CSRF, show state on cards, and test the full round trip.

### M9. Profile updates bypass validation and can cause 500 errors

`routes/user.py:18-24`:

- `float(request.form.get("capital", 0))` raises `ValueError` on non-numeric input, producing a 500.
- Capital bounds (`MAX_CAPITAL`), experience, time, and setup are not validated.
- `available_time` and `preferred_setup` are free-text inputs (`templates/user/profile.html:22-26`), allowing arbitrary strings that later feed the scoring engine.
- The default `available_time="4-6 hours/day"` and `preferred_setup="Online / Home-Based"` (`models/user.py:17-18`) are not in `ALLOWED_TIMES` / `ALLOWED_SETUPS` (`config.py:68-72`).

**Impact:** Bad data, crashes, inconsistent profiles, and lost form selections.  
**Fix:** Reuse the same validation layer as `/find`, catch conversion errors, and use selects/checkboxes with canonical values.

### M10. Location validation has an unreachable error branch

`ml/validation.py:66-68` does `form_data.get("location", "").strip().zfill(10)`. An empty string becomes `"0000000000"`, which is truthy, so the intended "Please select a Philippine City / Municipality" error is bypassed and users instead get "invalid PSGC".

**Impact:** Confusing validation UX; the test suite does not cover an omitted location.  
**Fix:** Check for empty input before zero-padding.

### M11. Recommendation history grows unbounded and uses N+1 queries

Every `/find` POST inserts five `Recommendation` rows (`routes/recommendation.py:38-49`) with no deduplication or retention. `/history` loads all rows (`routes/user.py:31-35`), and each template access to `h.business` triggers a lazy relationship query (`templates/user/history.html:9-12`).

**Impact:** History grows without limit; page latency increases with usage.  
**Fix:** Add pagination, retention/archival, deduplication or search-session grouping, and eager loading (`joinedload`).

### M12. The database is not the single source of truth

Recommendations and pathways read from `engine.df_businesses` (CSV), while business details use the `Business` table (`routes/business.py:6-9`). Seeding only occurs when the table is empty (`services/seed_service.py:13`), so catalog edits are never synchronized. There are also two seeding paths with different behavior (`services/seed_service.py` vs `seed_real_data.py`), and `Category`, `BusinessPathway`, and `ModelMetric` tables are effectively unused.

**Impact:** CSV and DB can disagree; ID assumptions and catalog updates are fragile.  
**Fix:** Choose one source of truth, add a catalog import/update command, and remove or use the unused tables.

### M13. Admin dashboard metrics are hardcoded and disconnected

`routes/admin.py:42-49` hardcodes counts (119 business ideas, 163/158 skills, 152,657 OSM records, 250 municipalities, 250 success records). The catalog is 127, the market file has 133 municipalities, and the skills union is 182. The page also presents success-model cross-validation as if it were recommender performance, despite a disclaimer.

**Impact:** Admins see inaccurate operational data.  
**Fix:** Compute all metrics from the live DB/files, show timestamps and data versions, and separate classifier metrics from recommender metrics.

### M14. Error handling and observability are weak

- Recommendation persistence failures are swallowed with `except Exception: rollback()` and no logging (`routes/recommendation.py:38-49`).
- Model inference failures are swallowed (`ml/success_model_service.py:107-121`).
- There is no application logging configuration, request ID, structured logging, error tracker (Sentry), or health/readiness endpoint.
- `app.py:29-31` prints and re-raises startup errors; `app.py:72-74` returns a generic 500 page, which is good for users but leaves operators blind.
- No audit log for admin retraining or authentication events.

**Impact:** Failures are hard to detect and diagnose; silent degradation is likely.  
**Fix:** Add structured logging, a health endpoint that checks DB/CSV/model availability, error reporting, and audit logs for sensitive actions.

---

## Low-Severity / Code Quality Weaknesses

### L1. Significant dead code and unused abstractions

- `services/recommendation_service.py`, `business_service.py`, `pathway_service.py`, `skill_service.py`, and `user_service.py` are not used by routes.
- `ml/pathway_generator.py` is unused; the pathway is built inline in `routes/recommendation.py:91-101`.
- `ml/feature_engineering.py`, `ml/business_encoder.py`, `ml/skill_encoder.py`, and `ml/train_recommender.py` are unused.
- `BusinessPathway`, `Category`, and `ModelMetric` models/tables are unused.
- Unused imports include `re` in `routes/recommendation.py`, `MLService` in `routes/admin.py`, and `db` in `services/user_service.py`.

**Impact:** Higher maintenance cost and confusion about which path is authoritative.  
**Fix:** Delete dead modules or wire them in; add linting to catch unused imports.

### L2. Legacy generator/rewrite scripts remain in the repository

`upgrade_system.py` (1,291 lines) and `generate_project.py` (1,318 lines) contain full embedded copies of the application and are guarded only by an environment variable. `changes.py` rewrites source files such as `ml/market_analyzer.py`, tests, and `validate_datasets.py` from embedded strings (`changes.py:482-704`). Running these can silently overwrite current code and data.

**Impact:** High risk of accidental destructive changes; confusing provenance for new contributors.  
**Fix:** Move historical scripts to a clearly marked `tools/legacy/` directory, remove embedded source dumps, or delete them and rely on version control.

### L3. Repository bloat

- `data/processed/businesses_with_psa_population.csv` is **30.41 MB** and tracked.
- `data/processed/calabarzon_businesses_standardized.csv` is **3.08 MB** and tracked.
- Binary model artifacts are tracked in both `models/` and `ml/models/` despite being reproducible.
- `backup_before_upgrade/` contains tracked duplicates of application files, and `data/final/po.py` is an odd tracked script inside a data directory.

**Impact:** Slow clones, noisy diffs, and risk of stale artifacts.  
**Fix:** Use Git LFS or an external data store for large datasets, ignore generated artifacts, and keep only small fixtures needed for tests.

### L4. Documentation is stale and incomplete

- `README.md:13` instructs `python ml/train_models.py`, which does not exist.
- README describes "capital feasibility gating" that is not implemented.
- No instructions for `SECRET_KEY`, admin creation, data provenance, CALABARZON coverage, running tests, migrations, Gunicorn, or Docker.
- No LICENSE, CONTRIBUTING, or data dictionary.

**Impact:** New contributors and operators will follow incorrect steps.  
**Fix:** Rewrite setup/deployment docs, document data sources and limitations, and add a data dictionary.

### L5. Dependency and environment drift

`requirements.txt` pins Flask 3.0.3, pandas 2.2.2, numpy 1.26.4, and scikit-learn 1.5.0. The active environment used for this review has Flask 3.1.2, pandas 2.3.0, and scikit-learn 1.8.0; loading the committed model produced `InconsistentVersionWarning` messages. There is no lock file, no dev/prod split, and no automated dependency or vulnerability scanning.

**Impact:** Model artifacts may behave differently or fail when unpickled under another version; reproducibility is weak.  
**Fix:** Pin with a lock file, separate dev dependencies, test model loading in CI, and add dependency vulnerability scanning.

### L6. Unsafe deserialization of model artifacts

The app loads joblib/pickle artifacts (`ml/success_model_service.py:51`, `ml/recommendation_engine.py:111`) with no integrity check. Pickle/joblib files can execute code if tampered with. They are tracked in Git and writable by any process with repo access.

**Impact:** A compromised artifact becomes code execution at startup.  
**Fix:** Treat artifacts as trusted build outputs, verify hashes/signatures, restrict write access, and load only from a controlled artifact store.

### L7. Hardcoded URLs and fragile pathway links

Templates use literal paths (`/find`, `/login`, `/pathway/{{ business_type }}`) instead of `url_for`. History, dashboard, and saved pages link by business **name** (`templates/user/history.html:12`, `templates/user/dashboard.html:16`, `templates/user/saved.html:9`), which requires extra lookup and is fragile for names with slashes or special characters (for example `Hostel / PG`).

**Impact:** Broken links and unnecessary coupling.  
**Fix:** Link by `business_id` and use `url_for` everywhere.

### L8. No privacy, legal, or account-lifecycle features

The app stores email, capital, experience, location, and feedback with no privacy notice, consent, retention policy, export, or account deletion. This is a concern for Philippine Data Privacy Act compliance and general user trust. There is also no "remember me", account lockout, or recovery flow.

**Impact:** Compliance risk and poor user experience.  
**Fix:** Add privacy/terms pages, consent, data export/deletion, and a retention policy for feedback/history.

### L9. No CI, linting, type checking, or coverage gates

The repository has pytest tests but no CI workflow, no `ruff`/`flake8`, no `mypy`, no coverage threshold, and no pre-commit hooks. Tests depend on local files and, in some cases, the real database.

**Impact:** Regressions and environment-dependent failures are easy to introduce.  
**Fix:** Add GitHub Actions (or equivalent) for install, lint, type-check, tests, and model-load smoke tests against a clean checkout.

### L10. Test coverage gaps

There are useful tests for validation, CSRF, pathways, scoring determinism, and market evidence. Missing coverage includes:

- Admin authorization and retraining.
- `/feedback` validation and linkage.
- Save/unsave (currently impossible).
- Profile input errors and bounds.
- CSRF rejection (only the success path is tested).
- Session/cookie behavior.
- Model inference schema and failure handling.
- Concurrent seeding/startup.
- Empty location and empty skill edge cases.

**Impact:** The highest-risk paths are the least tested.  
**Fix:** Add the missing tests, make them hermetic, and run them in CI.

### L11. Minor UI and data-quality inconsistencies

- `templates/user/recommendations_form.html:136` claims 250 municipalities and 9 regions; the actual data is CALABARZON-only.
- `routes/recommendation.py:387-388` adds "Has relevant market presence in your location" whenever a location score exists, even when that score is the lowest tier (`0.60`).
- The success model percentage is shown alongside recommendation percentages without explaining that it is a relative, min-max normalized value.
- The landing page uses the phrase "Exact Skill Matching" (`templates/main/landing.html:33`), but matching is a mix of exact alias matching and TF-IDF cosine similarity.
- The profile time/setup defaults do not match the allowed option lists (see M9).

**Impact:** Users receive imprecise or overstated explanations.  
**Fix:** Align copy with implementation, explain relative scores, and use neutral wording for low-confidence evidence.

---

## Verified Runtime Evidence

These checks were run against the current checkout:

| Check | Result |
|---|---|
| Catalog size | 127 businesses (`data/final/final_business_dataset.csv`) |
| Landing/admin claim | 119 businesses |
| Market data size | 133 municipalities, 1 region, 6 province-level entries |
| Form/landing claim | 250 municipalities, 9 regions |
| Market rows with <25 OSM records | 38 |
| Market rows with missing 2024 population | 1 |
| Category map | 36 blank, 35 in unsupported categories |
| Unsupported-category location score | `Advertising Agency` / `Construction Contracting` -> `osm_count=0`, `score=0.6`, `data_quality=HIGH` |
| Skill vocabulary | 163 final, 158 master, 182 union, 139 overlap |
| Success dataset | 250 rows, 62 positive, 188 negative |
| Success model raw score variety | 5 distinct values (beginner), 3 (experienced) |
| Hardcoded vs trained age median | 35.0 vs 40.0 |
| Budget behavior | ₱1,000 profile returned a ₱3,000 business at 68.7% |
| Raw dataset 1 | `data/raw/dataset_1/` does not exist |
| Test execution | Not run; `pytest` is not installed in the active interpreter |

---

## Prioritized Remediation Roadmap

### Now (before any production use)

1. Fix deployment: expose a module-level `app` or a supported factory, move seeding to a one-off command, add migrations, and test with Gunicorn workers.
2. Remove the default admin account; require strong credentials from environment/CLI.
3. Make `SECRET_KEY` mandatory in non-test environments and set secure session cookie flags.
4. Either implement real budget gating or correct the landing/README claims.
5. Align all displayed dataset counts and location coverage with the live data.
6. Fix the success-model feature mapping (medians, partnership, business_plan, financial record keeping) or disable the component until validated.
7. Build the missing market-category columns or return `None` for unsupported categories.
8. Move `last_profile` out of the client-side session.

### Next (short term)

9. Add rate limiting, password reset/verification, admin 2FA, and auth audit logging.
10. Make the test suite hermetic and run it in CI.
11. Consolidate skill normalization into one canonical vocabulary.
12. Fix capital semantics (micro vs full) and surface both to users.
13. Make the feedback schema useful (recommendation ID, business ID, valid values).
14. Implement or remove the "Saved" feature.
15. Add structured logging, a health endpoint, and model-load/feature-contract checks.
16. Add CSP/HSTS/Permissions-Policy and HTTPS/proxy configuration.

### Later (quality and scale)

17. Calibrate and validate the success model on Philippine data; report calibration and recommender ranking metrics.
18. Replace the diversity heuristic with a measured MMR approach.
19. Add pagination, retention, eager loading, indexes, and a proper database engine for multi-worker deployment.
20. Reduce repository bloat, remove legacy generator scripts, and split data/artifacts from source.
21. Add privacy/legal pages, account deletion/export, and a retention policy.
22. Rewrite documentation and add a data dictionary, deployment guide, and model card.

---

## What Is Already Solid

To avoid an unfairly one-sided picture, these areas are in reasonable shape:

- CSRF protection is present on all POST routes (`app.py:43-55`) and covered by a test.
- Passwords use Werkzeug's password hashing (`models/user.py:24-28`).
- Redirect targets are validated against same-origin URLs (`routes/auth.py:10-15`).
- Templates autoescape by default; no obvious template-injection path was found.
- `/find` validates capital, skills, experience, time, setup, and location server-side (`ml/validation.py`).
- The recommender is deterministic and has tests for score range, weight sums, and repeatability.
- Security headers for framing and MIME sniffing are present (`app.py:57-62`).
- The recommendation disclaimer correctly states that the score is not a probability of success (`templates/user/recommendations.html:22-24`).

---

## Key Files Reviewed

`app.py`, `config.py`, `requirements.txt`, `README.md`, `models/*.py`, `routes/*.py`, `services/*.py`, `ml/*.py`, `templates/**/*.html`, `static/js/main.js`, `tests/*.py`, `seed_real_data.py`, `train_success_models.py`, `validate_datasets.py`, `skill.py`, `create_skill_master.py`, `changes.py`, `upgrade_system.py`, `generate_project.py`, and the current data/model artifacts.
