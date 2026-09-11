# Dashboard MVP

Status: optional read-only UI for scanner v0.12, ready for Streamlit Community Cloud.

## Purpose

Make the existing scanner easier to inspect without moving pricing, identity, source-role, or BUY logic into the UI.

The dashboard is a display layer only. `main`, SQLite, deterministic Python, and the existing scanner outputs remain authoritative.

## Data modes

### Local mode

If `db/pokemon_deal_scanner.sqlite` exists, the dashboard opens it read-only and reads the current `output/market_routes.csv`.

### Hosted mode

If the SQLite database is absent, the dashboard reads:

`dashboard/data/dashboard_snapshot.json`

The daily GitHub Action generates this snapshot after a successful scanner run and attempts to commit only that whitelisted file back to `main`. The publish step is non-critical: if it fails, the scanner remains successful and the hosted page simply keeps the previous snapshot.

The hosted snapshot contains market/model fields only. It intentionally excludes secrets, personal inventory, seller-level data, API tokens and mutable scanner state.

## Current screens

### Today

- latest immutable forecast date;
- number of cards forecast;
- current actionable routes;
- matured T+7 count;
- current opportunities ranked by existing scanner fields;
- latest immutable predictions.

### Card detail

- exact Cardmarket product id plus card/set/number;
- EU fair value and validated buy;
- Deal Score and route signal;
- EU PCS, EU LQS, ECS, BOS;
- current route evidence;
- latest matured outcomes available for the selected card.

### Model health

- T+7 and T+30 matured observation counts;
- unique-card counts;
- progress toward the experience-store governance gates in `docs/EXPERIENCE_STORE.md`;
- source sync state;
- current dashboard data mode.

## Guardrails

- Open SQLite in read-only mode.
- Hosted mode reads a generated, whitelisted snapshot only.
- Do not calculate a new fair value in the dashboard.
- Do not create a second set of BUY gates.
- Do not fuzzy-match cards in the UI.
- Do not mutate predictions or outcomes.
- Do not include secrets, user inventory, seller-level/private data, or API credentials in the hosted snapshot.
- Missing files/data should degrade to informative empty states, not fabricated values.
- AI/LLM logic is not part of this MVP.

## Run locally

From the repository root:

```bash
python -m pip install -r requirements-dashboard.txt
streamlit run dashboard/app.py
```

Run the normal scanner first so `db/pokemon_deal_scanner.sqlite` and `output/market_routes.csv` exist.

## Deploy as a web page

The repository is deployment-ready for Streamlit Community Cloud.

One-time setup:

1. Sign in to Streamlit Community Cloud with GitHub.
2. Create a new app from `Muzzimu/pokemon-deal-scanner`.
3. Branch: `main`.
4. Main file path: `dashboard/app.py`.
5. Deploy.

No scanner API keys are required in Streamlit. The web app only reads the safe snapshot committed by GitHub Actions.

After the one-time deployment, the normal flow is:

`07:00 Dublin scanner -> snapshot export -> snapshot commit -> hosted dashboard refresh`

The first populated hosted page appears after a scanner run using the updated workflow. Until then the committed placeholder snapshot is intentionally empty.

## Snapshot generation

To generate the same hosted payload manually after a local scanner run:

```bash
python scripts/export_dashboard_snapshot.py
```

This replaces only `dashboard/data/dashboard_snapshot.json`.

## Next UI increments

Only add these if the MVP proves useful:

1. richer source-health/freshness badges;
2. filters by route, price band, set, character, PCS/LQS/BOS and manual-verification status;
3. charts for forecast calibration and matured outcomes;
4. experience-store cohort/comparable-case panels after maturity gates are met;
5. business/inventory views only if a separate privacy-safe design is agreed first.

Keep the dashboard replaceable: if Streamlit later becomes limiting, the underlying scanner/database contracts should allow another UI without changing model semantics.
