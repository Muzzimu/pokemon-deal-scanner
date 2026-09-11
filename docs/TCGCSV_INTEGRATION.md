# TCGCSV integration (v0.12)

Last updated: 2026-09-11

v0.12 adds an automatic, no-key US market-price feed through TCGCSV. TCGCSV is treated as a cached TCGplayer-derived market source, not as an acquisition venue and not as proof of Near Mint seller depth.

## Exact identity bridge

The scanner does **not** match TCGCSV cards to Cardmarket by name or collector number.

The accepted chain is:

`Cardmarket id_product <- CardTrader blueprint -> CardTrader tcg_player_id -> TCGCSV productId`

CardTrader's explicit `tcg_player_id` is persisted on the blueprint table. A blueprint that maps to more than one Cardmarket product is rejected. A Cardmarket product that resolves to more than one TCGplayer product id is also rejected.

This preserves the scanner's exact-printing guardrail.

## Daily flow

On each normal daily run:

1. CardTrader refreshes `tcg_player_id` values for the expansions already queried by the scanner.
2. The current route/core-watch universe is combined with still-live walk-forward forecast cards so old T+90/T+180 observations continue to receive market marks.
3. Missing TCGplayer product ids are located in TCGCSV's Pokemon group/product catalog and cached in SQLite.
4. Only the TCGCSV group price endpoints needed for tracked cards are queried.
5. Today's price rows are stored in `tcgcsv_price_snapshots`.
6. Unambiguous exact-product Market Price observations are normalized into `data/reference/tcgplayer_market_reference.csv` before the market-quality model runs.
7. The same Market Price can be published into the walk-forward research table as a clearly labelled **US proxy**, not as a confirmed realised sale.

TCGCSV's public documentation asks consumers to cache data and avoid aggressive request rates. The default scanner delay is 0.25 seconds between requests.

## Source semantics

TCGCSV supplies product-level price rows such as:

- `marketPrice`
- `lowPrice`
- `midPrice`
- `highPrice`
- `directLowPrice`
- `subTypeName`

The scanner interprets them conservatively:

- **Market Price** -> US fair-value reference / walk-forward market proxy.
- **lowPrice** -> condition-agnostic context only.
- **mid/high/directLow** -> retained in the TCGCSV diagnostic output but not promoted to executable Ireland acquisition evidence.
- TCGCSV does **not** provide SKU-level condition/language, current seller count, current quantity, shipping, or an exact recent-sale timestamp. Those fields stay blank rather than being inferred.

Therefore TCGCSV cannot manufacture TCGplayer LQS/depth points and cannot create an Ireland BUY signal.

## Variant / subtype guard

One TCGplayer product can have several TCGCSV price rows, for example `Normal`, `Holofoil`, and `Reverse Holofoil`.

The scanner uses a row only when:

- there is exactly one subtype; or
- CardTrader's stored version explicitly identifies the relevant Holo/Reverse/Normal subtype.

Otherwise the card is recorded as `AMBIGUOUS_SUBTYPE` and excluded from the normalized TCGplayer reference for that day.

## Persistence

SQLite tables:

- `tcgcsv_groups`
- `tcgcsv_products`
- `tcgcsv_price_snapshots`

Daily outputs:

- `output/tcgcsv_market_reference.csv`
- `output/tcgcsv_mapping_audit.csv`
- normalized current reference: `data/reference/tcgplayer_market_reference.csv`

The mapping audit makes unresolved identity/subtype cases visible instead of silently guessing.

## Model validation

TCGCSV Market Price is useful for continuous T+1/T+3/T+7/T+14/T+30 US market marks and for 90/180-day holding research. It is stored with evidence quality `PROXY` so confirmed sold evidence can outrank it whenever available.

It does **not** replace confirmed TCGplayer/eBay transactions for realised-sale calibration. The distinction between market mark and realised sale remains explicit.
