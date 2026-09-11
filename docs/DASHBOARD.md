# Dashboard

Status: optional read-only UI for scanner v0.12, deployed through Streamlit Community Cloud.

## Purpose

Make the existing scanner easier to inspect without moving pricing, identity, source-role, or BUY logic into the UI.

The dashboard is a display layer only. `main`, SQLite, deterministic Python, and the existing scanner outputs remain authoritative.

## Data modes

### Local mode

If `db/pokemon_deal_scanner.sqlite` exists, the dashboard opens it read-only and reads the current scanner outputs, including `output/market_routes.csv` and `output/top_flips.csv`.

### Hosted mode

If the SQLite database is absent, the dashboard reads:

`dashboard/data/dashboard_snapshot.json`

The daily GitHub Action generates this snapshot after a successful scanner run and attempts to commit only that whitelisted file back to `main`. The publish step is non-critical: if it fails, the scanner remains successful and the hosted page simply keeps the previous snapshot.

The hosted snapshot contains market/model fields only. It intentionally excludes secrets, personal inventory, seller-level data, API tokens and mutable scanner state.

Snapshot schema v2 adds a capped `discovery_candidates` surface from `top_flips.csv` plus richer route-quality labels/reasons. These are presentation inputs only; no dashboard code recalculates scanner decisions.

## Current screens

### Today

The Today screen is the primary decision-review surface.

- scanner version, data mode and snapshot freshness;
- counts of existing `RESELL_TEST`, `WATCH_ONLY` and evidence/revalidation signals;
- **Priority review** cards showing validated buy, best modeled net exit, net spread, ROI, EU fair value and PCS/LQS/ECS/BOS;
- filters by scanner route signal, price band and card-name search;
- a simplified **All routed cards** table, with `NO_EDGE` hidden by default but available on demand;
- a broader **Discovery queue** sourced from `top_flips.csv` and explicitly labelled as pre-route sourcing evidence, not a final resale recommendation;
- immutable forecasts moved into an expandable audit view rather than dominating the main screen.

The dashboard may reorder existing signals for readability, but it must never promote, downgrade or manufacture a signal.

### Card detail

- exact Cardmarket product id plus card/set/number when available;
- EU fair value and validated buy;
- Deal Score and route signal;
- EU PCS, EU LQS, ECS, BOS;
- simplified current route evidence plus expandable raw route fields;
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
- Discovery candidates must remain clearly labelled as pre-route sourcing evidence.
- Missing files/data should degrade to informative empty states, not fabricated values.
- AI/LLM logic is not part of this dashboard.

## Run locally

From the repository root:

```bash
python -m pip install -r requirements-dashboard.txt
streamlit run dashboard/app.py
```

Run the normal scanner first if you want the latest local SQLite/output state.

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

## Snapshot generation

To generate the same hosted payload manually after a local scanner run:

```bash
python scripts/export_dashboard_snapshot.py
```

This replaces only `dashboard/data/dashboard_snapshot.json`.

## Next UI increments

Add only when they improve decisions without duplicating scanner logic:

1. source-health/freshness badges and clearer stale/degraded warnings;
2. charts for forecast calibration and matured outcomes;
3. experience-store cohort/comparable-case panels after maturity gates are met;
4. business/inventory views only if a separate privacy-safe design is agreed first.

Keep the dashboard replaceable: if Streamlit later becomes limiting, the underlying scanner/database contracts should allow another UI without changing model semantics.
