# TCGplayer reference ingestion

Last reviewed: 2026-09-11

v0.9 uses TCGplayer as a **valuation and liquidity confirmation market**, not an automatic source of inventory and not an exit route.

## Normalized file

The scanner reads:

`data/reference/tcgplayer_market_reference.csv`

Canonical key: **Cardmarket `id_product`**.

Supported fields:

- `id_product`
- `name`
- `tcgplayer_product_id`
- `market_price_usd` / `low_price_usd`
- `market_price_eur` / `low_price_eur`
- `fx_usd_to_eur`
- `listing_count`
- `sales_30d`
- `reference_strength`
- `checked_at`
- `source`
- `notes`

EUR values are preferred when the provider already converted at a current rate. When only USD is supplied, the market-quality model can use the row-level FX rate or the configured fallback. Fallback FX lowers the operational quality of the observation even though it remains useful as broad confirmation.

## Provider-neutral importer

Use:

```bash
python scripts/import_tcgplayer_reference.py provider_output.json --source apify_lowlanddata
```

or provide a CSV instead of JSON.

The importer deliberately **rejects rows that cannot be tied to an exact Cardmarket product ID**. It accepts an explicit `id_product` / Cardmarket product-id field, or extracts `idProduct` from a Cardmarket product URL when the provider returns one.

It does **not** map by card name or collector number alone. Those fields are useful for validation but are not sufficiently safe as canonical joins for arbitrage.

## Current Apify options

The community actor `lowlanddata/tcg-price-arbitrage` compares Cardmarket trend with TCGplayer market price and converts the US price to EUR. Its public description says it matches card-by-card via collector number and returns aggregate prices plus Cardmarket/TCGplayer links. It does not provide seller-level listings or seller depth.

That makes it useful primarily for **PCS / fair-value confirmation**. If its exported Cardmarket link contains the exact `idProduct`, the provider-neutral importer can safely normalize that row. If not, the row should be rejected rather than guessed.

Other TCGplayer-oriented providers can expose listing counts and/or sales-history estimates. Those extra fields improve **LQS** because the model can measure depth and transaction velocity instead of price convergence alone.

## Strength guidance

- `STRONG`: exact product identity, fresh market price, and meaningful transaction/depth evidence.
- `MEDIUM`: exact product identity and fresh aggregate market price, but limited/no transaction detail.
- `WEAK`: stale, thin, or otherwise incomplete exact-product evidence.
- `VERY_WEAK`: context only; should have little influence on fair value.

A new provider should default to `MEDIUM` until its identity matching and price accuracy have been compared against manually verified cards.

## Why TCGplayer does not receive full independent-market weight

TCGplayer and US eBay are both heavily exposed to US/global collector demand. Treating them as two fully independent confirmations would overstate confidence. The v0.9 breadth model therefore counts TCGplayer at a discounted weight relative to Cardmarket, CardTrader and eBay.

The objective is not to maximize the number of price feeds. It is to estimate whether several partially independent markets agree on the same fair value and whether the chosen exit is actually executable.
