# Pokémon Bundle Business Cost Tracking

Last updated: 2026-09-08

## Purpose

This folder is the durable source of truth for the small Pokémon bundle business: inventory purchases, packaging costs, bundle recipes, sales, and research/test spending.

The goal is to keep **actual cash spending** separate from **product cost of goods sold (COGS)** so that bundle margins and break-even are not distorted by personal collection purchases or competitor-research samples.

## Accounting buckets

### 1. Business inventory / COGS

Inventory bought specifically to make sellable bundles belongs in `data/business/inventory_lots.csv`.

Current opening lot:

- purchase cost: **€20.00**
- assumed total cards: **800**
- assumed holo/reverse-holo cards: **100**
- assumed other cards: **700**
- average acquisition cost: **€0.025 per card**

Until the lot is sorted more precisely, all cards in the lot use the same €0.025 cost basis. Holo/reverse cards are tracked as a scarce production resource, but are not assigned a higher acquisition cost unless later evidence justifies a weighted allocation.

### 2. Hero-card assumption

Until actual hero-card purchases are entered, use a planning assumption of **€0.75 per V/ex card** (midpoint of the agreed €0.70–€0.80 range). This is stored in `data/business/cost_assumptions.csv` and should be replaced by actual landed cost whenever known.

### 3. Packaging / presentation

Actual purchases of penny sleeves, Dragon Shield sleeves, clear bags, stickers, envelopes, rigid/cardboard protection, etc. belong in `data/business/packaging_purchases.csv`.

Do not permanently rely on rough estimates once an actual purchase has been made. Enter quantity and landed cost so the real per-unit cost can be calculated.

### 4. Competitor/test purchases

Competitor samples bought for product research belong in `data/business/research_marketing.csv`.

The €5 and €7.50 test bundles are classified as **competitor/product research**, not normal product inventory and not marketing/advertising. Because the cards will be retained in the personal collection, they are:

- included in **all-in project cash spent** if we want to know every euro spent because of the project;
- excluded from bundle COGS and sellable inventory;
- excluded from operating break-even unless the user explicitly wants an all-in project break-even measure.

This gives two useful break-even views:

- **Operating break-even:** recover business inventory + packaging + selling costs.
- **All-in project cash break-even:** operating spend + research/test spend.

## Current bundle recipes

The current product plan is stored in `data/business/bundle_recipes.csv`.

### Standard — Adverts €5

- 10 themed Pokémon
- 25 regular Pokémon
- 10 holo/reverse-holo
- 5 Trainers
- 0 V/ex
- 50 cards total

Raw card cost from the €20/800-card bulk lot: **50 × €0.025 = €1.25** before packaging.

### Premium — Adverts €7

- 10 themed Pokémon
- 26 regular Pokémon
- 8 holo/reverse-holo
- 5 Trainers
- 1 V/ex
- 50 cards total

Raw card cost using the current assumptions:

- 49 bulk cards × €0.025 = **€1.225**
- 1 V/ex = **€0.75**
- total raw card cost = **€1.975 (~€1.98)** before packaging.

Current Vinted test prices are €5.99 Standard and €7.99 Premium; these are sales-price experiments, not guaranteed realized prices.

## Current production constraint from the opening lot

If the estimate of **100 holo/reverse cards** is approximately correct, holo supply is more restrictive than total card count:

- Standard uses 10 holo/RH → opening lot supports about **10 Standard bundles** from holo stock.
- Premium uses 8 holo/RH → opening lot supports about **12 Premium bundles** from holo stock, assuming enough V/ex cards are sourced.
- A 5 Standard + 5 Premium mix uses **90 holo/RH**, leaving about 10 holo/RH from this lot.

The 800-card total alone could theoretically supply 16 fifty-card bundles, but the planned shiny-card density means holo/reverse availability is likely to become the bottleneck first.

## Files

- `data/business/inventory_lots.csv` — bulk/card inventory acquisitions.
- `data/business/cost_assumptions.csv` — temporary planning assumptions such as V/ex unit cost.
- `data/business/packaging_purchases.csv` — actual presentation and mailing-material purchases.
- `data/business/research_marketing.csv` — competitor samples, product tests, and later genuine marketing spend.
- `data/business/bundle_recipes.csv` — current Standard/Premium recipes and platform test prices.
- `data/business/bundle_sales.csv` — realized sales and selling costs.

## Rules

1. Buyer-paid postage is not product revenue; record it separately when relevant.
2. Seller-paid postage/fees should be recorded as selling costs against the sale.
3. Personal collection cards are not business inventory unless deliberately transferred into bundle stock.
4. Actual landed purchase cost overrides assumptions.
5. Keep Adverts and Vinted realized selling prices separate so platform pricing can be tested empirically.
6. Update the bundle recipes whenever the agreed composition or price changes.
