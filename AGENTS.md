# AGENTS.md — Pokémon Deal Scanner Guardrails

This file is the concise operating contract for any coding/research agent modifying `Muzzimu/pokemon-deal-scanner`.

## 1. Source of truth

- `main` is the implementation source of truth.
- Current scanner version: **v0.12**.
- Before changing code/config, read:
  - `docs/PROJECT_CONTEXT.md`
  - `docs/MARKET_QUALITY_MODEL.md`
  - `docs/MODEL_VALIDATION.md`
  - `docs/SOURCE_ROLE_MATRIX.md`
  - `docs/TCGCSV_INTEGRATION.md`
  - `docs/DASHBOARD.md` when changing the UI/display layer
  - relevant recent commits/issues.
- Do not silently revert newer rules because an older chat, note, or example differs.
- Add/update tests whenever changing pricing guardrails, market-role logic, source eligibility, identity mapping, model validation, or workflow scheduling.

## 2. Exact identity is mandatory

Never merge evidence across ambiguous printings.

- Primary identity is the exact Cardmarket `idProduct` plus set/card identity.
- Language and condition remain explicit where relevant; the default acquisition target is **English + Near Mint**.
- CardTrader/TCGplayer/TCGCSV joins must use explicit ID bridges when available, not fuzzy name matching.
- Ambiguous CardTrader→Cardmarket or TCGCSV subtype mappings are blocked, not guessed.
- Photo/title/card-number conflicts must be resolved before valuing a card.
- Reprint/variant collisions are a hard data-quality failure.

## 3. Source × role discipline

Do not treat every price as an independent fair-value vote.

### EU market
Primary market for an Irish buyer.

- Cardmarket official catalogue/price guide: discovery/history/reference.
- Targeted Cardmarket live EN/NM validation: executable acquisition evidence only after shipping/eligibility checks.
- Irish / continental-European sold evidence: strongest local resale evidence when exact and verified.

### US/global reference

- TCGCSV `marketPrice`: US/global market proxy only.
- TCGCSV `lowPrice`: context only; never executable.
- TCGCSV does not provide condition/language/seller-depth/current-shipping data; do not invent those fields.
- TCGplayer-derived aggregators are correlated sources, not independent markets.

### Bridge market

- CardTrader is a route/bridge market, not a third fair-value vote.
- CT asking prices are not realised sales.
- BOS must penalize unsupported CardTrader premiums.

### Quarantined / research-only

- TCGGO/Pokemon-API graded sold feed currently has **zero production valuation weight** because freshness and exact-printing validation failed. See `docs/SOURCE_VALIDATION_TCGGO.md`.

## 4. Core market fields

Preserve EU/US/bridge separation:

- `eu_fair_value_eur`
- `eu_price_confidence_score`
- `eu_market_count`
- `eu_dispersion_pct`
- `eu_executable_value_eur`
- `eu_executable_source`
- `us_fair_value_eur`
- `us_price_confidence_score`
- `us_liquidity_score`
- `us_market_count`
- `us_dispersion_pct`
- `bridge_opportunity_score`
- `bridge_us_support_pct`
- `bridge_ct_premium_vs_eu_pct`
- `bridge_ct_premium_vs_us_pct`

Legacy `fair_value_eur`, `price_confidence_score`, and `liquidity_score` remain EU/Ireland-facing for backward compatibility unless a versioned migration explicitly changes them.

## 5. Decision-score semantics

Keep these concepts separate:

- **PCS**: confidence that fair value is correctly estimated.
- **LQS**: liquidity / probability and speed of sale.
- **ECS**: confidence the modeled exit can actually be achieved.
- **BOS**: quality of a CardTrader/global bridge opportunity.
- **Deal Score / DQS**: acquisition attractiveness, not fair value itself.

BOS weights currently reflect economic edge, US/global support, CT depth, EU confidence, and liquidity. Unsupported CT premium must reduce BOS.

Do not mechanically improve one score merely because another is high.

## 6. Walk-forward / anti-leakage rules

`src/deal_scanner/model_validation.py` is the core validation layer.

- Freeze immutable card × date × model-version predictions daily.
- Never rewrite historical predictions using later information.
- Outcomes mature later at T+1, T+3, T+7, T+14, T+30, T+90, T+180.
- T+7 is the primary weekly calibration horizon.
- T+90/T+180 are holding/investment research horizons, not short-horizon PCS calibration.
- Use chronological walk-forward validation; never random train/test splitting for time-series calibration.
- Avoid leakage across horizon windows; use purge/embargo logic where applicable.
- No-sale periods are valid liquidity/execution observations even when fair value is unobservable.
- Do not auto-reweight the model from small samples. Current minimum before considering reweighting: **>=200 matured observations AND >=50 unique cards**.

## 7. Fair value vs executable value

These are different quantities.

- Confirmed realised sales are strongest valuation evidence.
- Active offers/depth inform executability and liquidity, not realised value.
- A stale historical sale can be informative but must not override a clearly lower current executable market.
- Cardmarket generic/public low is discovery only.
- A BUY decision must use landed acquisition economics: price + postage/fees/FX where material.
- Active asks, accepted-message placeholders, disappearance, and inferred sales must remain explicitly lower-confidence than confirmed sold transactions.

## 8. Workflow robustness

Prefer deterministic Python for identity, calculations, gates, persistence, and execution.

- AI/LLM components, if added later, are advisory/critic layers only unless a versioned design explicitly changes this.
- Optional UI/dashboard code is a display layer: it must not create alternative fair values, BUY gates, fuzzy identity joins, or mutable forecast history.
- Optional data sources should degrade gracefully: `OK`, `STALE`, `DEGRADED`, `RATE_LIMITED`, `MAPPING_UNCERTAIN`, `UNAVAILABLE`, or `QUARANTINED` rather than silently fabricating values.
- One source outage must not poison unrelated sources.
- Never expose secrets in logs, commits, docs, or chat.
- Durable research state is backed up to the private backup repo through the production workflow.

## 9. Development workflow

Before coding:

1. inspect current code and recent commits;
2. explain the intended change and affected invariants;
3. make the smallest change that solves the problem;
4. run the relevant unit tests and full test suite;
5. preserve backward compatibility unless a version bump/migration is intentional;
6. document new source roles or model semantics.

Useful commands:

```bash
pytest -q
python scripts/run_daily.py --help
```

Do not add heavy frameworks, vector databases, or LLM dependencies when the same result can be produced deterministically with SQLite/Python.

## 10. Research evolution

The next research layer should use the existing immutable predictions/outcomes as empirical memory. See `docs/EXPERIENCE_STORE.md`.

Initial rule: **SQL/statistics first; no vector DB and no LLM in the retrieval path.** Comparable-experience retrieval, cross-card/set memory, and an optional AI critic are later phases only after enough matured observations exist.
