# Vinted market research strategy

Last updated: 2026-09-08

## Purpose

Use Vinted as an additional source of Pokémon TCG buyer-demand and sold-lot evidence, especially for bundles, mixed lots, themed packs and cross-border consumer demand. Keep Vinted evidence source-labelled and separate from Adverts.ie, Cardmarket and eBay.

## Compliance / access rule

Do not build direct automated scraping or crawling of Vinted. Current Vinted terms prohibit automated systems/software used to extract data, bots, and data scraping without prior written consent. Use manual discovery and third-party/public search-index evidence for repeatable research.

## Sold-state evidence hierarchy

1. Public Vinted page or indexed result explicitly says `Sold` and identifies the item.
2. Public Vinted page says `Sold` but displayed price may reflect the public listing price rather than a negotiated transaction price; therefore sold state can be high confidence while realized price remains medium confidence until independently validated.
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

## Why this matters for the bundle project

Vinted can complement Adverts.ie by broadening the buyer pool beyond Ireland and by exposing more consumer-style Pokémon lots. High-value research targets include:

- 20–60 card curated lots;
- kids/starter bundles;
- themed lots (Pikachu, Eevee, Dragonite, starters, etc.);
- older-era mixed lots;
- lots with guaranteed V/ex/holo content;
- visually packaged gift-style bundles.

For each recovered sale, store platform, item ID, title, seller market/locality confidence, public price, sold status, sold-price confidence, card count/composition, condition, source URL and evidence type.
