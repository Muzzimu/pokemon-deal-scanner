# Dashboard MVP

Status: optional read-only UI for scanner v0.12.

## Purpose

Make the existing scanner easier to inspect without moving pricing, identity, source-role, or BUY logic into the UI.

The dashboard is a display layer only. `main`, SQLite, deterministic Python, and the existing scanner outputs remain authoritative.

## Current screens

### Today

- latest immutable forecast date;
- number of cards forecast;
- current actionable routes from `output/market_routes.csv`;
- matured T+7 count;
- current opportunities ranked by existing scanner fields;
- latest immutable predictions.

### Card detail

- exact Cardmarket product id plus card/set/number;
- EU fair value and validated buy;
- Deal Score and route signal;
- EU PCS, EU LQS, ECS, BOS;
- current route evidence;
- matured outcomes already stored for the selected card.

### Model health

- T+7 and T+30 matured observation counts;
- unique-card counts;
- progress toward the experience-store governance gates in `docs/EXPERIENCE_STORE.md`;
- source sync state;
- configured database/output paths.

## Guardrails

- Open SQLite in read-only mode.
- Do not calculate a new fair value in the dashboard.
- Do not create a second set of BUY gates.
- Do not fuzzy-match cards in the UI.
- Do not mutate predictions or outcomes.
- Missing files/data should degrade to informative empty states, not fabricated values.
- AI/LLM logic is not part of this MVP.

## Run locally

From the repository root:

```bash
python -m pip install -r requirements-dashboard.txt
streamlit run dashboard/app.py
```

Run the normal scanner first so `db/pokemon_deal_scanner.sqlite` and `output/market_routes.csv` exist.

## Next UI increments

Only add these if the MVP proves useful:

1. richer source-health/freshness badges;
2. filters by route, price band, set, character, PCS/LQS/BOS and manual-verification status;
3. charts for forecast calibration and matured outcomes;
4. experience-store cohort/comparable-case panels after maturity gates are met;
5. business/inventory views if we decide to connect purchases and realised resale P&L.

Keep the dashboard replaceable: if Streamlit later becomes limiting, the underlying scanner/database contracts should allow another UI without changing model semantics.
