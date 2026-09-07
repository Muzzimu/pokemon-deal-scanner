# Vinted market research strategy

Last updated: 2026-09-08

## Purpose

Use Vinted as an additional source of Pokémon TCG buyer-demand and sold-lot evidence, especially for bundles, mixed lots, themed packs and cross-border consumer demand. Keep Vinted evidence source-labelled and separate from Adverts.ie, Cardmarket and eBay.

## Compliance / access rule

Do not build direct automated scraping or crawling of Vinted. Current Vinted terms prohibit automated systems/software used to extract data, bots, and data scraping without prior written consent. Use manual discovery and third-party/public search-index evidence for repeatable research.

## Sold-state evidence hierarchy

1. Public/indexed Vinted result explicitly says `Sold` and identifies the item.
2. A sold result can give high confidence that the item sold while the displayed public price remains only medium-confidence realized-price evidence, because a private negotiated offer may have been used.
3. `Removed!` without an explicit `Sold` marker is not a sale and must be recorded as removed/unknown.
4. Listing disappearance alone is not a sale.

## Local-location discovery heuristic

Vinted does not expose a straightforward seller-location filter in the same way as Adverts.ie. Manual keyword discovery can still be useful: searches such as `pokemon dublin`, `pokemon cork`, `pokemon galway`, etc. may surface sellers/items associated with those places.

Treat the location keyword as a **discovery heuristic, not proof of seller location**. After discovery, validate locality from the seller profile, visible item/shipping origin, other seller items, or corroborating public-index evidence where available.

Recommended workflow:

1. Manually search Vinted for `pokemon dublin` and other Irish-city terms.
2. Save promising item URLs and seller identifiers.
3. For the same seller, inspect other Pokémon listings and record composition/pricing.
4. Later use third-party search-index queries on the saved item IDs/titles to recover `Sold` markers and indexed prices.
5. Keep seller-market/locality confidence separate from sold-state confidence.

## Current Dublin discovery test

Two Vinted items supplied by the user after searching `pokemon dublin` resolve to the same internal seller identifier on the public item pages, suggesting they belong to the same seller:

- item `9870782497`: `Pokémon vintage card lot – 55+ cards | XY & Sun & Moon`
- item `9860182963`: `Pokémon Furious Fists 29-card vintage lot – XY 2014`

At the 2026-09-08 check both pages showed `Removed!` and no explicit `Sold` marker. Therefore neither should be counted as a confirmed sale. Their indexed metadata remains useful for title, card-count, set/era and description recovery.

The two-item test supports adding **location-keyword seller discovery** to the Vinted research plan, while preserving the rule that locality must be verified separately and `Removed!` is not sold evidence.

## First sold-lot benchmark pass: 30–75 cards

A manual/public-index pass on 2026-09-08 targeted sold Pokémon lots in roughly the 30–75 card range. The clean sample was smaller than the desired 20–50 rows because many search-index results expose card-count/price candidates without tying the `Sold` marker to that exact candidate strongly enough. Do not pad the benchmark with ambiguous rows.

Clean confirmed/indexed sold examples saved in `data/reference/vinted_sold_lot_probe_20260908.csv`:

- 50+ Forbidden Light cards: public price €3, Sold.
- 50 HGSS cards including 4 holo/reverse: public price €17, Sold.
- 60 genuine Italian cards, no duplicates and no Energy: public price €6.50, Sold.
- 40-card Pokémon lot: public price €8, Sold (count linkage medium-high confidence because the page later 404'd while the count-targeted index still exposed the row).

For these four rows, displayed public-price median is €7.25 and mean is €8.63. The sample is too small and heterogeneous for a robust market price; HGSS is an older-era premium outlier and the €3 Forbidden Light lot is a very cheap result. Excluding the HGSS premium row, the three-row median is €6.50.

Implication for the planned curated kids bundle: the data supports testing around €9–€10 more strongly than immediately assuming €12. A themed 50-card bundle with a guaranteed V/ex hero, holos/reverses, no duplicates and better presentation can plausibly sit above generic €6–€8 sold lots, but a €12 Vinted ask should be treated as an experiment rather than the default until a larger sold sample confirms it.

## Why this matters for the bundle project

Vinted can complement Adverts.ie by broadening the buyer pool beyond Ireland and by exposing more consumer-style Pokémon lots. High-value research targets include:

- 20–60 card curated lots;
- kids/starter bundles;
- themed lots (Pikachu, Eevee, Dragonite, starters, etc.);
- older-era mixed lots;
- lots with guaranteed V/ex/holo content;
- visually packaged gift-style bundles.

For each recovered sale, store platform, item ID, title, seller market/locality confidence, public price, sold status, sold-price confidence, card count/composition, condition, source URL and evidence type.
