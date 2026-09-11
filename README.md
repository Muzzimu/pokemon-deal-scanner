# Pokémon Deal Scanner v0.9

Python + SQLite scanner for Pokémon TCG sourcing, local deal discovery, resale evidence and small-scale arbitrage, tuned for an Ireland-based buyer.

## What v0.9 adds

v0.9 adds a **financial-market-style quality layer** so an apparent price gap is judged by liquidity, fair-value confidence and exit executability rather than headline spread alone.

- **TCGplayer is now a fourth confirmation market** for valuation/liquidity. Normalized exact-card observations live in `data/reference/tcgplayer_market_reference.csv` and are keyed to Cardmarket `id_product` rather than name-only matching.
- TCGplayer is **not** an automatic buy source or selected exit venue in v0.9. It only confirms/challenges fair value, listing depth, sales velocity and the selected exit price.
- **LQS (Liquidity Quality Score, 0–100)** combines transaction velocity, CardTrader/TCGplayer depth, cross-market price convergence, market breadth and immediacy.
- **PCS (Price Confidence Score, 0–100)** combines cross-market convergence, transaction evidence, freshness, liquidity and identity/mapping confidence.
- **ECS (Exit Confidence Score, 0–100)** is specific to the modeled sell channel. A card can have high PCS but low ECS when fair value is well known yet the selected CardTrader ask looks unexecutable.
- Fair value is a **weighted median** of Cardmarket, eBay, TCGplayer and depth-discounted CardTrader evidence. CardTrader active asks cannot dominate simply because they are high.
- TCGplayer receives a correlation discount in market breadth because US TCGplayer and US eBay demand are not fully independent markets.
- A `RESELL_TEST` now also has to pass quality gates: standard routes require LQS ≥65 / PCS ≥75 / ECS ≥65; acquisition cost ≥€50 requires LQS ≥70 / PCS ≥80 / ECS ≥70.
- A failing market-quality gate can only **downgrade** a route to `WATCH_ONLY`; it cannot manufacture a stronger signal.
- `output/market_quality.csv`, `output/market_routes.csv` and `output/core_watch_universe.csv` expose fair value, dispersion, TCGplayer evidence, LQS/PCS/ECS and the quality-gate result.

See [`docs/MARKET_QUALITY_MODEL.md`](docs/MARKET_QUALITY_MODEL.md) for the scoring model.

v0.9 also keeps the CardTrader mapping-confidence guard introduced after v0.8.2: multi-ID CardTrader blueprints are blocked from arbitrage until exact mapping is resolved, with diagnostics in `output/cardtrader_mapping_audit.csv`.

## What v0.8.2 adds

v0.8.2 adds a **targeted live Cardmarket validation layer** on top of the official daily Cardmarket feed and the v0.8.1 CM/CT route engine.

- `output/core_watch_universe.csv` remains the cheap first-stage filter. Only priority A/B cards with sufficiently high CT-lag scores are eligible for a live lookup.
- The current optional provider is Parse.bot's Cardmarket `get_card_listings` wrapper, called by exact numeric Cardmarket `idProduct` with English + NM filters.
- The default cap is **3 cards per daily run**, sized to remain within the current free-tier credit budget; the delay remains conservative for the provider's rate limit.
- `output/cardmarket_live_validation.csv` records the live article floor, robust median of the cheapest sample, seller/unit depth, comparison with the prior validated landed source, and a validation state.
- A lower live article price becomes `LIVE_CHEAPER_VERIFY_SHIPPING`; it **cannot** create a new BUY because Ireland shipping/landed cost has not been proved.
- If the live article market has moved materially above the old validated source, the route becomes `REVALIDATE_SOURCE` and a CardTrader `RESELL_TEST` is downgraded to `WATCH_ONLY` until the Cardmarket source is checked again.
- The scanner never sends Cardmarket account credentials/cookies to the provider and does not implement proxy rotation, browser-fingerprint spoofing, Cloudflare challenge solving or direct Cardmarket anti-bot bypass.
- The live layer is fail-open for the rest of the scanner: without `PARSE_API_KEY`, the normal daily feed, CardTrader, eBay, Gumtree and route outputs still run.

See [`docs/CARDMARKET_LIVE_DATA_OPTIONS.md`](docs/CARDMARKET_LIVE_DATA_OPTIONS.md) for provider and evidence policy.

## What v0.8.1 adds

v0.8.1 makes the Cardmarket -> CardTrader route engine more risk-aware instead of using one universal profit threshold.

- **Dynamic price-band gates:** higher-capital cards require larger absolute profit before they can become a `RESELL_TEST`. The default bands are €0–10 (≥€2.50 / 35% ROI), €10–30 (≥€5 / 30%), €30–50 (≥€8 / 25%), €50–100 (≥€15 / 25%), and €100+ (≥€25 / 20%).
- **€100+ manual-verification gate:** even when the numbers pass, high-value raw cards stay `WATCH_ONLY` until exact printing, photos/condition and the intended exit route are checked manually.
- **CardTrader / Cardmarket lag score:** routes receive a 0–100 score combining net CM->CT gap, CT seller depth, CT unit depth and eBay confirmation. A large CT ask from one isolated seller therefore cannot rank like a broad cross-market gap.
- **Dynamic Core watch universe:** `output/core_watch_universe.csv` contains covered cards in the configured €15–€120 value range that have enough CT depth plus either stronger eBay evidence or at least three CT sellers. It is evidence-driven rather than a hard-coded list of famous Pokémon.
- `output/cardtrader_resale_candidates.csv` and `output/market_routes.csv` now include the price band, required profit/ROI, manual-verification flag, CM->CT gap percentages and lag score/label.

The Core watch universe is intentionally built only from cards for which the scanner already has sufficiently strong mapped/validated evidence. It is not a claim to represent the 100 most liquid Pokémon cards on the whole market.

## What v0.8 adds

v0.8 formalizes the **source × role architecture** and turns CardTrader into an explicit **resale / exit channel**, not just an alternative supply source.

- `docs/SOURCE_ROLE_MATRIX.md` defines which sites can be used for acquisition, valuation, resale, local/bundle context and discovery.
- `data/reference/source_role_matrix.csv` is the machine-readable mirror of that policy.
- Validated Cardmarket sourcing products are now pulled into the CardTrader marketplace sync even when they are not part of the original cheap/popular discovery candidate set.
- CardTrader Direct and CardTrader Zero are evaluated separately as exit channels using current English/NM active marketplace offers.
- CardTrader net proceeds subtract configurable seller commission, VAT on commission and small operating reserves before spread/ROI is calculated.
- CardTrader active asks are **not** treated as confirmed sold prices. A `RESELL_TEST` requires minimum competing-seller depth; thinner markets are downgraded to `WATCH_ONLY`.
- `output/cardtrader_resale_candidates.csv` shows Cardmarket -> CardTrader exit tests.
- `output/market_routes.csv` answers, for cards with validated sourcing evidence: where the validated buy route is, what the current value references are, and which modeled exit channel produces the best net proceeds.
- Existing eBay resale evidence is compared against CardTrader Direct/Zero on a net basis; the best modeled exit is surfaced rather than assuming one marketplace is always superior.
- CardTrader exit edges are also merged into `output/arbitrage_candidates.csv` so cross-market opportunities appear in the existing arbitrage view.

Current default CardTrader fee assumptions are the conservative post-March-2026 EU seller rates: 5.3% Direct and 7.3% Zero, with VAT added to commission. The Ireland-tuned configuration currently assumes 23% VAT. These are configurable planning assumptions, not tax advice.

## v0.7 Gumtree and arbitrage layer

v0.7 added **Gumtree UK / Northern Ireland discovery** and a conservative **cross-market arbitrage layer**.

- Gumtree broad discovery covers Northern Ireland plus UK-wide results; Northern Ireland is classified separately because acquisition friction is lower.
- Exact-card Gumtree watches are keyed to Cardmarket `id_product`. The first pilot cards are Dragonite V PGO 076/078 and Origin Forme Palkia VSTAR CRZ GG67.
- Broad collection/binder listings stay discovery-only. They cannot become an automatic deal merely because an image or title resembles a valuable printing.
- The exact-printing guard remains mandatory: set + collector number + value-changing variant must be verified before an actionable signal.
- English and NM must be explicit before a Gumtree listing can become actionable. Unknown language/condition produces `VERIFY_CONDITION_LANGUAGE`, not BUY.
- GBP/USD are converted to EUR using a live ECB-derived Frankfurter feed. Configured fallback FX keeps reports running but can never create `STRONG_ARBITRAGE`.
- Gumtree acquisition cost includes configurable friction reserves. Northern Ireland has a lower reserve than mainland Great Britain.
- Exit references prefer validated Cardmarket English/NM evidence and qualifying eBay evidence; weak asks cannot silently become sold-market evidence.
- Arbitrage output uses net spread and ROI after an exit-cost reserve, with `STRONG_ARBITRAGE`, `POSSIBLE_ARBITRAGE`, verification states and `NO_EDGE`.
- Gumtree fetch failure is non-destructive: it never implies a listing sold or disappeared.

## v0.6 market-trend layer

v0.6 added the market-state model used for flip-vs-hold decisions. It combines:

- Cardmarket price trend / 7-day / 30-day movement;
- eBay sales velocity;
- exact-listing available supply;
- cross-market confirmation;
- recorded event context.

Labels are `ACCELERATING`, `FIRMING`, `PULLBACK`, `COOLING`, `DECLINING`, `DIVERGENT_NOISY` and `MIXED_STABLE`, with an explicit confidence level. Event flags are context, not proof of causation.

## Pricing / identification guardrails

1. **Cardmarket generic low** is discovery-only. It may be another language or condition and cannot qualify a flip.
2. Actionable Cardmarket acquisition evidence is **English + NM**, with Ireland deliverability and landed cost where required.
3. Dense binder/photo listings must be identified by **exact printing**, not visual resemblance. Confirm set, collector number and variant (holo/non-holo, reverse, stamp/promo, language, edition, etc.).
4. If the exact printing cannot be verified, use `VERIFY_VARIANT` / watch-only and request a close-up or collector number.
5. Confirmed sold evidence outranks inferred quick-sale evidence; active asking prices remain weak context.
6. Regional markets and currencies remain separate until an explicit FX conversion is performed.
7. A higher CardTrader active price than Cardmarket does not by itself prove liquidity; v0.8+ requires net economics plus competing-seller depth before a resale test becomes actionable.
8. Capital at risk matters: v0.8.1+ applies stricter absolute-profit gates as acquisition value increases.
9. Live third-party Cardmarket article prices are verification evidence, not Ireland-landed acquisition evidence unless shipping is independently known.
10. TCGplayer is confirmation evidence only in v0.9; it cannot create a buy or exit route by itself and is correlation-discounted against US eBay.
11. CardTrader multi-ID mappings are blocked from arbitrage until resolved to an exact Cardmarket `id_product`.

This prevents the common false positives the project is designed around: a cheap non-English/low-condition Cardmarket listing being mistaken for an English/NM floor, a visually similar vintage/variant card being priced as the wrong printing, a thin active marketplace ask being mistaken for a realized resale price, or a €70 card being recommended for only a few euro of nominal upside.

## Source roles

The canonical policy lives in [`docs/SOURCE_ROLE_MATRIX.md`](docs/SOURCE_ROLE_MATRIX.md). In short:

- **Buy:** Adverts/Gumtree/Cardmarket first; CardTrader is a secondary acquisition source.
- **Value:** Cardmarket history + stronger eBay sold evidence + TCGplayer confirmation; CardTrader active offers are supporting context.
- **Sell:** eBay and CardTrader are modeled exit channels; TCGplayer is not an exit route in v0.9; Vinted/Adverts remain useful consumer/local channels for bundles and selected cards.
- **Bundle/local market:** Adverts, Vinted and Facebook Marketplace are more useful than specialist single-card markets for pricing kid-focused bundles.

## Gumtree regions and arbitrage assumptions

`NORTHERN_IRELAND` and `GREAT_BRITAIN` are scored separately. The configured friction values are **planning reserves only**; they are not tax, customs, postage or legal determinations for a particular transaction.

A Gumtree result can become `STRONG_ARBITRAGE` only when all of the following are true:

- exact watched printing matched;
- explicit English evidence;
- explicit NM / pack-fresh claim;
- live FX available;
- trustworthy Cardmarket EN/NM and/or medium/strong eBay reference;
- minimum configured net spread and ROI survive friction and exit-cost reserves.

Everything else is downgraded to verification, possible-arbitrage or no-edge status.

## Existing market evidence architecture

The scanner retains the regional/evidence architecture from v0.4-v0.9:

- eBay Ireland, continental EU, UK and Global evidence kept separate;
- physical item location required for regional eBay evidence;
- graded/slab/proxy/custom/code-card/lot filtering before raw-single evidence is used;
- repeated-miss requirement before an eBay listing can be marked gone;
- inferred quick-sale evidence kept below confirmed sold evidence;
- active eBay asks never represented as confirmed sales;
- active CardTrader asks never represented as confirmed sales;
- third-party live Cardmarket offers never represented as confirmed Ireland-landed buys unless shipping is separately verified;
- TCGplayer confirmation kept separate from acquisition and exit execution;
- new-product flip guard;
- bounded Cardmarket/CardTrader/eBay history retention.

The detailed manual resale-evidence hierarchy and DoneDeal interpretation policy are in [`docs/MARKET_EVIDENCE.md`](docs/MARKET_EVIDENCE.md). A machine-readable policy mirror lives in `data/reference/resale_evidence_hierarchy.csv`.

## Adverts.ie and DoneDeal

Adverts.ie remains a **manual/local research source**, not a direct automated scraper. Follow [`docs/ADVERTS_DISCOVERY.md`](docs/ADVERTS_DISCOVERY.md): use the high-recall query matrix, overlap windows for late-indexed ads, exact listing IDs and full photo/description inspection. Do not add a direct Adverts scraper.

DoneDeal remains manual additional Irish sourcing/asking-price context unless a permitted stable integration is explicitly implemented later.

## Main outputs

- `output/cheap_ex.csv`
- `output/top_flips.csv`
- `output/dragonite.csv`
- `output/bundle_candidates.csv`
- `output/seller_baskets.csv`
- `output/cardmarket_sourcing.csv`
- `output/ebay_market_reference.csv`
- `output/resale_candidates.csv`
- `output/cardtrader_resale_candidates.csv`
- `output/market_routes.csv`
- `output/core_watch_universe.csv`
- `output/cardmarket_live_validation.csv`
- `output/cardtrader_mapping_audit.csv`
- `output/market_quality.csv`
- `output/market_signals.csv`
- `output/gumtree_candidates.csv`
- `output/arbitrage_candidates.csv`
- `output/gumtree_arbitrage_status.json`
- `output/pgo076_test.json`
- `output/scanner_status.json`

## Durable project context

Business strategy, standing interpretation rules, local Irish benchmark policy, bundle concepts, deal-evaluation conventions and conversation-continuity instructions are preserved in [`docs/PROJECT_CONTEXT.md`](docs/PROJECT_CONTEXT.md).

Before changing scanner behavior or interpreting a run in a new chat/session, review that file together with `docs/SOURCE_ROLE_MATRIX.md`, `docs/MARKET_QUALITY_MODEL.md`, `docs/CARDMARKET_LIVE_DATA_OPTIONS.md`, `docs/ADVERTS_DISCOVERY.md`, `docs/MARKET_EVIDENCE.md`, `docs/EBAY_API_COMPLIANCE.md`, `config.yaml`, relevant `data/reference/` files and recent commits. Material new decisions should be written back to GitHub rather than left only in conversation history.

## Workflow scheduling

The production GitHub Actions workflow targets one full scan per Dublin calendar day once local time has reached **07:00**. Redundant UTC attempts cover Irish DST and GitHub scheduling delays; concurrency plus a daily-success marker prevent duplicate full scans. Manual workflow dispatch remains supported.

The workflow runs tests first, then the normal scanner, market-trend signals, Gumtree discovery/arbitrage, and diagnostic checks. `output/*.csv` and `output/*.json` are uploaded as the daily artifact, so the CardTrader resale, market-route, Core watch, optional live Cardmarket validation, mapping audit and market-quality reports are included automatically.
