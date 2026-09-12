# Future ideas / deferred roadmap

Status: durable backlog index for ideas that are useful but intentionally deferred until the scanner has enough evidence to justify them.

## How to use this file

- GitHub Issues are the actionable reminders / implementation tickets.
- This file is the stable index so future ideas are not scattered across chat history.
- Do not implement deferred analytics merely because they sound plausible. Respect the maturity, leakage and validation rules in `AGENTS.md`, `docs/MODEL_VALIDATION.md` and `docs/EXPERIENCE_STORE.md`.

## Current deferred ideas

### Post-v0.12 research roadmap

See issue #1: validate the existing model and T+7 outcomes before adding correlated price sources or extra valuation votes.

### Experience-driven decision analytics

See issue #4: **relative strength → survival/time-to-sale modeling → inventory risk → probability-based expected value**.

Planned order:

1. **Relative strength** — compare a card against leakage-safe peer cohorts such as price band, set age, rarity/treatment and, where useful, Pokémon/evolution family.
2. **Survival / time-to-sale modeling** — use sold and still-active listings to estimate probability of sale over time while handling right-censored observations correctly.
3. **Inventory risk** — convert calibrated time-to-sale / sale-probability estimates into capital-at-risk and holding-friction measures.
4. **Probability-based expected value** — use calibrated exit probabilities and realistic net outcome scenarios. Do not relabel today's modelled profit as EV.

#### Survival / time-to-sale research plan

Use survival analysis as the preferred framework for the future question: **"How long is this specific card likely to remain unsold?"**

Model order:

- start with **Cox Proportional Hazards** as an interpretable benchmark;
- test **Accelerated Failure Time** models, especially Weibull and log-normal, because median time-to-sale is directly useful for inventory decisions;
- consider **Random Survival Forests** only as a later challenger if listing-event history becomes large enough to justify non-linear interactions;
- avoid DeepSurv / heavy deep-learning dependencies unless simpler approaches clearly fail and sample size is genuinely sufficient.

Candidate covariates should favor relative market position over raw nominal price:

- asking-price premium/discount versus contemporaneous realised-sale or executable reference;
- trailing 30d / 90d transaction velocity;
- competing exact-print listings at or below the target price;
- total exact-print supply / seller depth;
- EU/US price dispersion or later realised-sale volatility;
- condition, language, graded/raw status and grade tier where exact data is reliable;
- set age, rarity/treatment and price band;
- validated relative-strength context;
- event/context flags only as explanatory inputs, not assumed causal multipliers.

Required listing history should preserve listing episodes with exact identity, first-seen and end timestamps, duration, asking price over time, contemporaneous market context, and an explicit event type. Keep confirmed sold, strongly inferred sold, withdrawn/expired, relisted/repriced, and still-active/right-censored states distinct. **Do not treat every disappearance as a sale.** If price changes are observed during a listing's life, use time-varying covariates / interval-split episodes rather than one static price.

Validation rules:

- active unsold listings are valid right-censored observations;
- do not assume Pokémon time-to-sale is log-normal without testing alternatives;
- do not arbitrarily convert old listings into sales;
- a fixed 90-day horizon is acceptable for a question such as `P(sale <= 90d)`, but cards remaining active beyond 90 days are not automatically invalid data;
- consider withdrawal/relisting as competing events if data quality supports it;
- use chronological holdouts / walk-forward validation rather than random train/test splits;
- preferred outputs: `P(sale <= 7d)`, `P(sale <= 30d)`, `P(sale <= 90d)`, predicted median time-to-sale when identifiable, and calibration by price band / liquidity regime.

Starting maturity gates:

- >=500 matured T+7 observations;
- >=100 unique cards;
- >=10 usable leakage-safe comparable cases in the relevant scope/horizon;
- for holding-period / inventory-risk work, prefer >=200 matured T+30 observations across >=50 unique cards;
- survival modeling additionally requires enough listing episodes and actual sale events across relevant price/liquidity regimes.

All features remain diagnostic unless chronological walk-forward validation demonstrates incremental out-of-sample value.

### Comparable historical experience / AI critic

The architecture for comparable-case retrieval and later optional AI critic is documented in `docs/EXPERIENCE_STORE.md`. Deterministic SQL/Python remains authoritative; any AI critic stays advisory and cannot bypass identity, source-role, maturity or BUY gates.

## Implemented from prior idea backlog

The dashboard now exposes a market-profile diagnostic layer using existing v0.12 evidence:

- price trend;
- trend confidence / evidence coverage;
- transaction velocity;
- exact observed supply;
- EU/US price dispersion.

These fields explain current market state but do not create new BUY gates or change fair value.
