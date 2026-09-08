# Vinted market research strategy

Last updated: 2026-09-08

## Purpose

Use Vinted as an additional source of Pokémon TCG buyer-demand and sold-lot evidence, especially for bundles, mixed lots, themed packs and cross-border consumer demand. Keep Vinted evidence source-labelled and separate from Adverts.ie, Cardmarket and eBay.

## Compliance / access rule

Do not build direct automated scraping or crawling of Vinted. Current Vinted terms prohibit automated systems/software used to extract data, bots, and data scraping without prior written consent. Use manual discovery and third-party/public search-index evidence for repeatable research.

## Sold-state evidence hierarchy

1. Public/indexed Vinted result explicitly says `Sold` / `Vendu` / `Verkauft` / `Venduto` / equivalent and identifies the item.
2. A sold result can give high confidence that the item sold while the displayed public price remains only medium-confidence realized-price evidence, because a private negotiated offer may have been used.
3. `Removed!` without an explicit sold marker is not a sale and must be recorded as removed/unknown.
4. Listing disappearance alone is not a sale.

## Local-location discovery heuristic

Vinted does not expose a straightforward seller-location filter in the same way as Adverts.ie. Manual keyword discovery can still be useful: searches such as `pokemon dublin`, `pokemon cork`, `pokemon galway`, etc. may surface sellers/items associated with those places.

Treat the location keyword as a **discovery heuristic, not proof of seller location**. After discovery, validate locality from the seller profile, visible item/shipping origin, other seller items, or corroborating public-index evidence where available.

Recommended workflow:

1. Manually search Vinted for `pokemon dublin` and other Irish-city terms.
2. Save promising item URLs and seller identifiers.
3. For the same seller, inspect other Pokémon listings and record composition/pricing.
4. Later use third-party search-index queries on the saved item IDs/titles to recover sold markers and indexed prices.
5. Keep seller-market/locality confidence separate from sold-state confidence.

## Current Dublin discovery test

Two Vinted items supplied by the user after searching `pokemon dublin` resolve to the same internal seller identifier on the public item pages, suggesting they belong to the same seller:

- item `9870782497`: `Pokémon vintage card lot – 55+ cards | XY & Sun & Moon`
- item `9860182963`: `Pokémon Furious Fists 29-card vintage lot – XY 2014`

At the 2026-09-08 check both pages showed `Removed!` and no explicit sold marker. Therefore neither should be counted as a confirmed sale. Their indexed metadata remains useful for title, card-count, set/era and description recovery.

The two-item test supports adding **location-keyword seller discovery** to the Vinted research plan, while preserving the rule that locality must be verified separately and `Removed!` is not sold evidence.

## Expanded sold-lot benchmark: roughly 30–75 cards

A second public-search-index pass on 2026-09-08 expanded `data/reference/vinted_sold_lot_probe_20260908.csv` to 22 clean sold-state observations across Vinted regional surfaces. Two rows are custom/fan-art products and are excluded from genuine-card bundle pricing. This leaves 20 genuine/official-card sold-state observations in the working sample.

Important caveats:

- These are clean **sold-state** observations, not 20 independent sellers or product designs. A recurring `Mazzo carte pokemon 60` format appears multiple times at different item IDs and is useful as repeated-sales evidence rather than independent cross-sectional evidence.
- Displayed public price is medium-confidence realized-price evidence because Vinted private offers can change the amount actually paid.
- Two rows have list prices reconstructed from buyer-protection-inclusive indexed figures and are labelled lower-confidence for price.
- Premium older-era and hit-heavy lots should not be mixed blindly with ordinary kids/bulk bundles.

### Ordinary/comparable pricing signal

Excluding the clearly premium HGSS row and the 5-EX premium outlier, the 18 ordinary/comparable genuine-card observations have a raw displayed-price median of about **€6.50** and mean of about **€6.45**. Collapsing the repeated 60-card seller format to a single representative observation produces a very similar center (about €6.75), so the conclusion is not being driven only by that one seller.

The repeated 60-card Italian product is particularly useful demand evidence: genuine cards, no duplicates, no Energy, sold repeatedly around **€5.80–€6.80**, with another shiny-heavy version around €6.50.

Closer curated/premium comparators include:

- 30 cards + 3 shiny + 1 Venusaur V: **€10 Sold**.
- 50 cards + Mega-Latias EX: **€5 Sold**.
- 50 reverse cards: **€7 Sold**.
- 50-card gift/collector-style set: about **€8 Sold** (price reconstructed from indexed buyer-protection total).
- 60 cards + 9 holo/reverse, no duplicates: **€4 Sold**.
- 74-card Nuit Noire lot: **€11 Sold**.
- 70 cards + 240-slot binder: **€12 Sold**.
- 50 HGSS cards including 4 holo/reverse: **€17 Sold**, but this is an older-era premium comparator.
- 50 cards + 5 EX Ultra Rares: very high premium outlier; exclude from ordinary bundle pricing.

### Pricing implication for our planned 50-card curated kids bundle

The evidence now supports a clearer three-tier read:

- **€9.99**: safest launch price and clearly defensible against the sold sample.
- **€10.99**: preferred Vinted test price if the bundle visibly delivers the planned differentiation: guaranteed V/ex hero, multiple holo/reverse cards, no duplicates, recognizable/theme-led Pokémon, hero card in a nice sleeve, and tidy gift-style presentation.
- **€11.99**: too ambitious as the default. Use only for a stronger premium version, unusually appealing hero/theme, or accessory-enhanced pack.

Recommended Vinted launch strategy: list the standard curated bundle at **€10.99**, be comfortable accepting approximately **€9.50–€10**, and test a multi-buy offer around **2 for €20**. Keep Adverts around €10 initially. If Vinted conversion is weak after a reasonable exposure period, move the standard Vinted price to €9.99 before changing bundle composition.

Because Vinted adds buyer-protection cost and shipping on top, the displayed all-in buyer cost matters more than the nominal list price. Avoid pushing the standard bundle to €11.99 until actual sales of our own product justify it.

## Why this matters for the bundle project

Vinted can complement Adverts.ie by broadening the buyer pool beyond Ireland and by exposing more consumer-style Pokémon lots. High-value research targets include:

- 20–60 card curated lots;
- kids/starter bundles;
- themed lots (Pikachu, Eevee, Dragonite, starters, etc.);
- older-era mixed lots;
- lots with guaranteed V/ex/holo content;
- visually packaged gift-style bundles.

For each recovered sale, store platform, item ID, title, seller market/locality confidence, public price, sold status, sold-price confidence, card count/composition, condition, source URL and evidence type.
