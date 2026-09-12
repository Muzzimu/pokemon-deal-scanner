# Future ideas / deferred roadmap

Status: durable backlog index for ideas that are useful but intentionally deferred until the scanner has enough evidence to justify them.

## How to use this file

- GitHub Issues are the actionable reminders / implementation tickets.
- This file is the stable index so future ideas are not scattered across chat history.
- Do not implement deferred analytics merely because they sound plausible. Respect the maturity, leakage and validation rules in `AGENTS.md`, `docs/MODEL_VALIDATION.md` and `docs/EXPERIENCE_STORE.md`.

## Current deferred ideas

### Post-v0.12 research roadmap

See issue #1: validate the existing model and T+7 outcomes before adding correlated price sources or extra valuation votes.

### Condition-specific pricing and grading normalization

See issue #5: build a future condition-aware valuation layer only after enough reliable condition-specific evidence exists.

Core design principles:

- model an exact card as `printing × language × condition × treatment/finish`, rather than one undifferentiated asset;
- learn NM/LP/MP/HP/DMG-style condition effects empirically rather than hard-coding universal discount multipliers;
- estimate condition discount curves by relevant cohorts such as era/set age, price band, rarity/treatment and scarcity/liquidity regime;
- build an explicit cross-market normalization layer instead of silently equating different marketplace grading systems;
- keep graded cards (`grader + numeric grade`) separate from raw-condition tiers;
- preserve realised-sale evidence, active asks, sample counts, freshness and source confidence separately;
- use robust statistics such as median/MAD/IQR for thin/skewed markets and flag suspicious outliers as condition/anomaly risk rather than automatically reclassifying seller condition;
- for sparse condition slices, prefer cohort/hierarchical shrinkage or `INSUFFICIENT_EVIDENCE` over fabricated point estimates;
- treat condition as a future covariate in survival/time-to-sale modeling, because condition-specific sell-through may differ materially by era and scarcity.

Potential future outputs:

- condition-specific fair/executable values where supported;
- condition/NM ratios by validated cohort;
- condition-specific liquidity and time-to-sale diagnostics;
- sample count, freshness, dispersion and confidence for each condition slice.

Current production acquisition target remains English + NM unless a later validated model/version explicitly changes that rule. Condition-aware outputs should begin as research/diagnostics and only enter valuation or BUY logic after chronological out-of-sample validation.

### Ask-side depth and supply concentration

See issue #6: research the **shape, concentration and depletion of visible ask-side supply**. Do not describe this as true order-book imbalance because collectible marketplaces do not expose a symmetric bid/ask book.

Candidate diagnostics:

- **floor depth** — copies and unique sellers within a narrow band above the best executable ask;
- **near-floor depth** — copies/sellers within a wider band such as +10%;
- **next-wall gap** — price jump from the current floor to the next meaningful dense supply cluster;
- **price-tier depth profile** — copies/sellers by price band rather than one aggregate listing count;
- **seller concentration** — top-1 share, top-3 share, median copies/seller and optional HHI/concentration-adjusted depth;
- **copies-vs-sellers decomposition** — distinguish depletion, consolidation and fragmentation;
- **supply runway** — continue to prefer copies divided by observed sales velocity over seller-count-only ratios;
- **historical depletion velocity** — daily/weekly changes in total copies, near-floor copies and unique sellers.

Preserve raw quantities even when using capped/log-transformed seller contributions for concentration diagnostics. A large seller really is supply; the adjustment is only to avoid confusing one seller with many independent sources of liquidity.

Potential descriptive states include thin floor / dense wall above, broad deep supply, supply depletion with stable sellers, seller attrition with stable copies, consolidating supply, fragmenting supply, and tightening supply with continued sales. Keep these labels observational: do not infer "whale buying", "panic selling", "fake walls" or other causal stories without external evidence.

Persist exact-print listing snapshots where permitted so order-book shape can be reconstructed prospectively. Test whether depth/concentration features add incremental out-of-sample value beyond existing price trend, transaction velocity, aggregate supply change, PCS/LQS/ECS/BOS and supply-runway metrics. Candidate targets include 7d/30d realised-price direction, floor movement, ECS improvement and future time-to-sale outcomes. Keep this diagnostic unless chronological walk-forward validation shows stable incremental predictive value.

### Structural card fundamentals and demand resilience

See issue #7: add a future **card-fundamentals / structural demand** research layer to complement market technicals. The purpose is not to claim a literal intrinsic value for collectibles, but to model persistent supply/demand traits that may help explain long-horizon price floors, resilience, peer-relative strength and downside risk.

Core feature groups:

- **set age / release date** as a continuous lifecycle feature;
- **rarity and treatment** as categorical metadata, not one universal ordinal ladder across eras;
- **distribution type** such as pack-pulled, guaranteed box/ETB promo, stamped promo, league/event, tournament/prize or other fixed-distribution channel;
- **credible pull-rate evidence** stored with source/date/confidence rather than assumed exact;
- **observable print/reprint lifecycle state** based on evidence, without inventing precise reprint probabilities before calibration;
- **Pokémon / character popularity** as a continuous, refreshable demand feature rather than a fixed hand-written tier list;
- **character-family context** where useful, such as Eeveelutions, starters or legendaries, but only after validation;
- **artwork class / treatment** and **artist identity** as features, with artist effects estimated only after controlling for Pokémon, rarity/treatment, set, scarcity and price band;
- **competitive usage** including tournament deck share, copies per successful deck and recent top-cut usage;
- **legality / days to rotation**, including a future test of `competitive usage × rotation proximity` to identify utility-driven premiums that may decay.

Modeling guardrails:

- keep collector-demand and competitive-demand features separate and let models learn interactions;
- do not use hand-built formulas such as `rarity_ordinal × pull_rate_inverse` or `popularity × artist_score / competitive_index` unless they demonstrate incremental value empirically;
- do not assume rarity labels are linearly ordered across eras;
- preserve missingness and source confidence for sparse/uncertain features instead of fabricating certainty;
- avoid target leakage: popularity, artist, competitive and lifecycle features used for a forecast at date D must only use information available by D;
- start with interpretable diagnostics / peer-group effects before moving to complex ML.

Potential uses:

- construct better leakage-safe peer groups for relative-strength analysis;
- separate **collector-driven** from **utility-driven** premiums;
- study structural resilience during market drawdowns;
- test whether fundamentals improve T+90/T+180 forecasts;
- test whether they improve survival/time-to-sale and inventory-risk estimates when combined with condition and market-depth features.

Useful peer dimensions may eventually include modern/vintage regime, price band, set age, rarity/treatment, distribution type, collector-demand regime, competitive-dependency regime and liquidity/supply depth. Keep this layer diagnostic until chronological walk-forward validation shows stable incremental out-of-sample value over simpler baselines.

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
