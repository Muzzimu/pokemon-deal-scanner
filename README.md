# Pokémon Deal Scanner v0.7

Python + SQLite scanner for Pokémon TCG sourcing, local deal discovery, resale evidence and small-scale arbitrage, tuned for an Ireland-based buyer.

## What v0.7 adds

v0.7 adds **Gumtree UK / Northern Ireland discovery** and a conservative **cross-market arbitrage layer**.

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

New outputs:

- `output/gumtree_candidates.csv`
- `output/arbitrage_candidates.csv`
- `output/gumtree_arbitrage_status.json`

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

This prevents the two common false positives the project is designed around: a cheap non-English/low-condition Cardmarket listing being mistaken for an English/NM floor, and a visually similar vintage/variant card being priced as the wrong printing.

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

The scanner retains the regional/evidence architecture from v0.4-v0.6:

- eBay Ireland, continental EU, UK and Global evidence kept separate;
- physical item location required for regional eBay evidence;
- graded/slab/proxy/custom/code-card/lot filtering before raw-single evidence is used;
- repeated-miss requirement before an eBay listing can be marked gone;
- inferred quick-sale evidence kept below confirmed sold evidence;
- active eBay asks never represented as confirmed sales;
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
- `output/market_signals.csv`
- `output/gumtree_candidates.csv`
- `output/arbitrage_candidates.csv`
- `output/gumtree_arbitrage_status.json`
- `output/pgo076_test.json`
- `output/scanner_status.json`

## Durable project context

Business strategy, standing interpretation rules, local Irish benchmark policy, bundle concepts, deal-evaluation conventions and conversation-continuity instructions are preserved in [`docs/PROJECT_CONTEXT.md`](docs/PROJECT_CONTEXT.md).

Before changing scanner behavior or interpreting a run in a new chat/session, review that file together with `docs/ADVERTS_DISCOVERY.md`, `docs/MARKET_EVIDENCE.md`, `docs/EBAY_API_COMPLIANCE.md`, `config.yaml`, relevant `data/reference/` files and recent commits. Material new decisions should be written back to GitHub rather than left only in conversation history.

## Workflow scheduling

The production GitHub Actions workflow targets one full scan per Dublin calendar day once local time has reached **07:00**. Redundant UTC attempts cover Irish DST and GitHub scheduling delays; concurrency plus a daily-success marker prevent duplicate full scans. Manual workflow dispatch remains supported.

The workflow runs tests first, then the normal scanner, market-trend signals, Gumtree discovery/arbitrage, and diagnostic checks. Gumtree is an external classifieds page rather than a formal API, so its step is intentionally defensive and reports retrieval failures rather than fabricating listing state.
