# Dashboard

Status: optional read-only UI for scanner v0.12, deployed through Streamlit Community Cloud.


## Provider usage telemetry

Provider/API consumption is an operational diagnostic, not a market or BUY signal. Persist request counts and documented/provider-confirmed credit units by run, keep providers separate, and show daily/7d/30d/month usage under Model health. Never invent a credit conversion. Optimisation should remove duplicate/low-value calls before weakening identity/language/condition/finish validation.

## Purpose

Make the existing scanner easier to inspect without moving pricing, identity, source-role, or BUY logic into the UI.

The dashboard is a display layer only. `main`, SQLite, deterministic Python, and the existing scanner outputs remain authoritative.

## UX design contract

The dashboard follows a decision-first UX hierarchy informed by the project UX references (Interaction Design Foundation, Qt UX guidance, and Michael Filipiuk's UI-design principles). These references guide presentation only; they never change scanner logic, evidence roles, fair value, or BUY gates.

Core rules:

1. **User task before model internals.** For an owned card, show exact identity, what was paid, landed cost, current comparable market asks, modelled exit/profit when available, and only then model diagnostics.
2. **Progressive disclosure.** PCS/LQS/ECS/BOS, raw route fields, market diagnostics and audit data remain available but normally sit behind expanders.
3. **Exact identity is always visible.** Card name alone is insufficient; show set, collector number, Cardmarket ID and relevant language/condition/finish context.
4. **Consistency across cards.** Owned-card, routed-card and detail views should use the same labels, value hierarchy and terminology wherever the evidence is equivalent.
5. **Findability over density.** Search, review-set selection and clear stage labels should make cards easy to locate without flattening every data point onto the first screen.
6. **Do not confuse asks with exits.** Active Cardmarket/CardTrader asks are competitive-market references, not realised sale prices. Gross room to an ask is not profit.
7. **No fabricated precision.** If finish, language, condition, shipping, route or exit evidence is unresolved, display the missing state instead of filling it with a proxy.
8. **Artwork follows exact identity.** Small card images may be shown only from an explicit Cardmarket-product → TCGdex mapping. Never fuzzy-match artwork in the UI; if the mapping is missing, show no image.
9. **Keep orientation chrome compact.** Version, freshness and review counters should use minimal vertical space so the first actionable review content appears quickly; governance detail can move to tooltips or progressive disclosure.
10. **Prefer direct-selection controls for small filter sets.** Use segmented buttons/pills instead of dropdowns when choices are few and stable; hide no-op filters when only one value exists, and keep free-text search separate.

## Data modes

### Local mode

If `db/pokemon_deal_scanner.sqlite` exists, the dashboard opens it read-only and reads current scanner outputs including `output/market_routes.csv`, `output/market_signals.csv`, `output/market_quality.csv` and `output/top_flips.csv`.

### Hosted mode

If the SQLite database is absent, the dashboard reads:

`dashboard/data/dashboard_snapshot.json`

The daily GitHub Action generates this snapshot after a successful scanner run and attempts to commit only that whitelisted file back to `main`. The publish step is non-critical: if it fails, the scanner remains successful and the hosted page simply keeps the previous snapshot.

The hosted snapshot contains scanner market/model fields plus the explicitly user-approved owned/tracked-card decision dataset. It still excludes API secrets, seller identities, addresses and scanner credentials.

`dashboard/data/owned_market.json` is refreshed independently from the main scanner so current owned-card ask checks cannot hold the core daily scan hostage. It contains public-safe per-card acquisition economics and comparable-market summaries only; raw seller identities and secrets are not exported.

`dashboard/data/card_images.json` stores exact Cardmarket-product → TCGdex artwork references. The repository stores the mapping, not Pokémon artwork binaries. Streamlit requests small WebP assets from TCGdex at display time; missing/unverified mappings degrade to text-only cards.

Snapshot schema v3 adds market-profile diagnostics to routed cards by joining existing `market_signals.csv` and `market_quality.csv` evidence. These fields explain current market state; they do not recalculate fair value, scores or route decisions.

## Current screens

### Today

The Today screen is the primary scanner review surface.

- scanner version, data mode and snapshot freshness;
- counts of existing `RESELL_TEST`, `WATCH_ONLY` and evidence/revalidation signals;
- **Priority review** cards showing validated buy, best modeled net exit, net spread, ROI, EU fair value and PCS/LQS/ECS/BOS;
- filters by review set, scanner route signal, price band and card-name search;
- a broader **Discovery queue** explicitly labelled as pre-route sourcing evidence, not a final resale recommendation;
- full routed-card and raw-field views available on demand.

Each routed card has a **Market profile** diagnostic block:

- **Trend** — existing market-signal label plus Cardmarket 30-day move when available;
- **Trend confidence** — existing market-signal confidence and evidence coverage count;
- **Transaction velocity** — TCGplayer 30d/90d transaction counts plus tracked eBay sale signals when available;
- **Exact supply** — live Cardmarket EN/NM seller/unit depth when present, tracked eBay live listings, and exact TCGplayer seller/quantity depth;
- **Volatility / dispersion** — EU and US cross-source price dispersion.

Important interpretation limits:

- trend confidence is evidence-coverage confidence, not a promise of future price direction;
- tracked eBay sale signals can include conservative inferred quick-sale evidence and are labelled accordingly;
- EU/US dispersion is cross-source price dispersion, not yet a full historical realised-sale volatility model;
- none of these diagnostics creates a new BUY gate.

The dashboard may reorder existing signals for readability, but it must never promote, downgrade or manufacture a signal.

### Owned cards

`dashboard/pages/1_Owned_cards.py` is the first-class decision surface for cards deliberately bought/tracked for resale review. Bundle-only €1 hero inventory is excluded unless explicitly promoted later.

For each owned card the first screen shows:

- exact card/set/collector number/Cardmarket ID;
- language, condition and finish-matching rule;
- **item price actually paid**;
- **allocated landed cost** including basket shipping allocation;
- current exact-comparable **Cardmarket EN/NM literal floor** when available;
- current exact-comparable **CardTrader EN/NM literal floor** when available;
- a **robust ask** for each source when available, defined as the median of the cheapest three already-fetched comparable asks;
- the lowest comparable active floor, lowest robust ask and gross room versus landed cost;
- **historical reference confidence**, a display-only consistency diagnostic derived from Cardmarket Trend/1d/7d/30d summary marks;
- routed model net exit, owner-specific modelled profit and owner-specific ROI when a routed net exit exists.

Active asks are explicitly labelled as competition references, not realised exits. The literal floor can be an edge-case seller/copy; the robust ask is intended to show whether the next few comparable asks support that floor. Neither is a realised sale price. Gross room is before selling fees, outbound postage and execution slippage.

Historical reference confidence is deliberately narrow. It does **not** claim Cardmarket's historical sale series is English/NM/finish-clean. The dashboard uses the spread among positive Trend/1d/7d/30d summary marks only: fewer than three marks = `INSUFFICIENT`; max/min ≥2.0× = `LOW`; max/min ≥1.35× = `MEDIUM`; otherwise `HIGH`. This is a market-history warning/diagnostic, not a new fair value, score or BUY gate.

The owned-card acquisition ledger is `data/reference/owned_resale_cards.csv`. Basket shipping is currently allocated equally per card while the original item price remains separately visible. This makes the allocation transparent and reversible rather than hiding it inside one opaque cost number.

The independent workflow `.github/workflows/owned_market_refresh.yml` refreshes Cardmarket/CardTrader comparable asks separately from the core scanner. A comparable ask must match exact product identity, English, NM/raw status and the stored finish rule. If finish cannot be verified, the dashboard withholds the floor and shows `VERIFY_FINISH` instead.

Code-only edits to `scripts/refresh_owned_market.py` do not automatically run the paid live refresh. They are validated by CI and take effect on the next normal/manual refresh. A change to the owned-card ledger still triggers an immediate refresh because a newly bought card benefits from a current market check. This prevents avoidable Parse/Cardmarket credit use during development.

### Cross-price research

`dashboard/pages/2_Cross-price_research.py` is a research-only comparison surface balanced across Cardmarket 30-day reference-value bands. It does not alter v0.12 BUY signals, fair values or route gates.

Alongside screening acquisition, absolute euro headroom and percentage gap, the table shows **historical reference confidence** and the max/min summary spread. This makes cards such as thin vintage holos visibly different from cards whose Trend/1d/7d/30d marks agree. A low-confidence historical reference should prompt investigation rather than be interpreted as a precise fair value.

### Card detail

The Card detail selector covers every exact Cardmarket product present in the current dashboard dataset, not only cards that already have an immutable model forecast. It can therefore show routed cards, forecast-only cards, pre-route discovery candidates, owned/tracked cards and explicit research watches while keeping those stages visibly distinct.

For routed/forecast cards it shows:

- exact Cardmarket product id plus card/set/number when available;
- EU fair value and validated buy;
- Deal Score and route signal;
- EU PCS, EU LQS, ECS, BOS;
- expanded Market profile diagnostics;
- simplified current route evidence plus expandable raw route fields;
- an **Immutable forecast · audit view** when a stored model prediction exists;
- latest matured outcomes available for the selected card.

For discovery-only cards it shows the existing candidate sourcing evidence such as candidate buy, Cardmarket averages, gap, Deal Score and CardTrader visible supply. These remain explicitly labelled **pre-route** and do not become route recommendations merely because they are visible in Card detail.

For `RESEARCH_WATCH` cards it shows the available research-market observations and the research note without creating a BUY, fair-value override or route signal.

### Model health

- T+7 and T+30 matured observation counts;
- unique-card counts;
- progress toward the experience-store governance gates in `docs/EXPERIENCE_STORE.md`;
- source sync state;
- current dashboard data mode.

## Guardrails

- Open SQLite in read-only mode.
- Hosted mode reads generated/whitelisted market data only.
- Do not calculate a new fair value in the dashboard.
- Do not create a second set of BUY or SELL gates.
- Do not fuzzy-match cards in the UI.
- Do not mutate predictions or outcomes.
- Do not include secrets, seller identities, addresses, private credentials or API tokens in hosted files.
- User-approved acquisition costs may be displayed for the owned-card decision view because they are necessary to evaluate realised economics.
- Discovery candidates must remain clearly labelled as pre-route sourcing evidence.
- Missing files/data should degrade to informative empty states, not fabricated values.
- Market-profile fields are diagnostics only and cannot silently change scanner scores/signals.
- Robust asks and historical-reference confidence are diagnostics only and cannot silently change scanner scores/signals.
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

No scanner API keys are required in Streamlit. The web app only reads the safe snapshots committed by GitHub Actions.

After the one-time deployment, the normal flow is:

`07:00 Dublin scanner -> scanner snapshot publish -> independent owned-card ask refresh -> hosted dashboard refresh`

## Snapshot generation

To generate the same hosted scanner payload manually after a local scanner run:

```bash
python scripts/export_dashboard_snapshot.py
```

Owned-card ask data is refreshed separately with:

```bash
python scripts/refresh_owned_market.py
```

## Future UI / analytics

Deferred ideas and maturity gates are indexed in `docs/FUTURE_IDEAS.md`. The next analytics sequence is intentionally deferred until enough outcomes mature:

`relative strength -> inventory risk -> probability-based expected value`

Keep the dashboard replaceable: if Streamlit later becomes limiting, the underlying scanner/database contracts should allow another UI without changing model semantics.
