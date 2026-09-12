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

See issue #4: **relative strength → inventory risk → probability-based expected value**.

Planned order:

1. **Relative strength** — compare a card against leakage-safe peer cohorts such as price band, set age, rarity/treatment and, where useful, Pokémon/evolution family.
2. **Inventory risk** — estimate expected time-to-sale and combine it with capital tied up, downside and exit friction.
3. **Probability-based expected value** — use calibrated exit probabilities and realistic net outcome scenarios. Do not relabel today's modelled profit as EV.

Starting maturity gates:

- >=500 matured T+7 observations;
- >=100 unique cards;
- >=10 usable leakage-safe comparable cases in the relevant scope/horizon;
- for holding-period / inventory-risk work, prefer >=200 matured T+30 observations across >=50 unique cards.

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
