# Adverts.ie discovery v2

Last reviewed: 2026-09-08

## Purpose

This document defines the manual/public-index discovery procedure to use when the user asks to scan Adverts.ie for newly listed or newly updated Pokémon TCG deals.

It was added after listing `40981248` (`Pokemon cards in binder`) was missed by a 2026-09-08 scan even though it was a highly relevant, fast-moving binder/collection listing. The failure was primarily a **fresh-discovery/index-latency problem**, not a valuation/scoring problem: the advert had not yet propagated into the third-party search results being used by the scan.

This procedure is separate from the automated Cardmarket/CardTrader scanner. An "Adverts scan" in chat is manual market research unless explicitly stated otherwise.

## Compliance boundary

Adverts.ie Terms were re-checked on 2026-09-08 (Terms last updated 2025-12-05). Clause 8 prohibits robots, spiders, website search/retrieval applications, or other automated means used to access/retrieve/index Adverts.ie, and also prohibits retrieving/indexing the service to construct or populate a database.

Therefore:

- **Do not add a direct Adverts.ie scraper, crawler, RSS poller, app/API reverse-engineering client, or scheduled direct-site fetcher to this repository.**
- Adverts' own saved-search / alert features are the preferred near-real-time safety net on the user's side.
- Third-party public search indexes and public web archives may be used as discovery/corroboration sources, subject to their own terms.
- A user-supplied Adverts link, screenshot, saved-search alert, or alert email can be inspected directly for the specific transaction/deal question.
- Do not persist a systematic mirror/database of live Adverts listings.

Official terms reference: https://www.adverts.ie/terms

## Why discovery v1 failed

The old chat workflow leaned too heavily on recently indexed web-search results. That has three weaknesses:

1. **Index latency:** a new Adverts listing can exist and receive an offer before a search engine has indexed it.
2. **Ranking bias:** broad search results are not guaranteed to be sorted by Adverts listing time.
3. **Query brittleness:** generic titles such as `Pokemon cards`, `Pokemon cards in binder`, `bundle`, or `collection` may be poorly ranked despite being exactly the kind of sourcing opportunity we want.

The listing `40981248` is the regression example for this failure mode. Future protocol changes should be checked against whether they would improve the chance of surfacing that kind of listing quickly.

## Discovery v2 procedure

### 1. Alert-first freshness check

If Adverts saved-search alerts / alert emails are available to the user, review fresh alert links first. This is the only platform-native near-real-time discovery mechanism currently approved for the project.

Recommended saved-search families:

- pokemon cards
- pokemon tcg
- pokemon binder
- pokemon collection
- pokemon bulk
- pokemon card bundle

Secondary saved searches can target `pokemon ex`, `pokemon v`, `pikachu cards`, `illustration rare`, `holo`, and `reverse holo` if alert volume is manageable.

If alert data is unavailable to the current chat/run, the report must not silently pretend third-party indexing is complete.

### 2. High-recall third-party search sweep

Run the query matrix in `data/reference/adverts_discovery_queries.csv` rather than a single generic query. Prefer several broad searches over one over-fitted query.

Searches should cover both:

- **inventory forms:** binder, collection, bulk, lot, bundle, tin;
- **hit forms:** ex, V, Pikachu, holo, reverse holo, illustration rare / IR.

Do not require the title to contain every keyword. Relevant wording may appear only in the indexed description/snippet.

### 3. Use a rolling overlap window

For a scan that runs about every two hours, re-check at least the previous **6 hours** of surfaced/indexed candidates rather than assuming everything from the previous run was already visible then.

Reason: a listing can be created at 18:00, absent from the 18:45 and 20:45 search index, then appear later. When it finally becomes indexed, it should still be treated as a candidate even though its listing timestamp predates the immediately previous scan.

### 4. Dedupe by exact listing ID

Extract the numeric Adverts listing ID whenever possible and use it as the primary identity key.

- Same ID + changed ask/title/description/comment evidence = **updated listing**.
- New ID = **new listing**.
- Same/similar title with a different ID is a different advert until proven otherwise.

Do not reject a candidate merely because the title is generic.

### 5. Priority triage before valuation

Escalate a candidate for page/photo review when one or more of these are present:

- binder / collection / job lot / bulk at a low total ask;
- many photos relative to a low asking price;
- `open to offers`, `clearing out`, `selling as lot`, `house clearance`, `all cards`, or similar motivation language;
- guaranteed ex/V/IR/holo/reverse content;
- recognizable Pokémon such as Pikachu, Eeveelutions, Charizard, Dragonite, Gengar, starters, Lucario, Greninja or Gyarados;
- old/vintage/WOTC plus modern mix;
- low-view or poorly titled listings that may be under-discovered;
- whole-lot prices under roughly €100 where photo-level inspection could reveal enough value to justify a quick decision.

This stage should favor **recall over precision**. It is better to inspect several mediocre €20–€80 binders than to miss a €65 collection that sells in minutes.

### 6. Open the candidate before calling it a deal

For any candidate that could plausibly qualify:

- read the full description;
- inspect all available photos when accessible;
- verify whether the displayed price is for the whole lot, per card, a placeholder, or an invitation to offer;
- identify visible ex/V/IR/SIR/full-art/vintage cards where possible;
- check language and likely condition;
- note duplicate risk and useful Trainer content for deckbuilding/bundle stock;
- verify title/card-number/photo consistency.

The Dragonite V incident from 2026-09-07 is a standing regression rule: **do not value a single from the title/collector number alone when the photo shows a different printing.**

### 7. Value only after discovery/identity validation

Use current references as appropriate:

1. Cardmarket **English + NM** for European specialist-market value;
2. eBay sold/completed evidence for realistic resale context, with region/currency separated;
3. Irish Adverts accepted/sold evidence and standing seller benchmarks;
4. Facebook Marketplace / other Irish local evidence when accessible and useful;
5. active asks only as context, never as realized sale evidence.

For bulk/binders, estimate practical break-up/bundle value rather than summing aspirational retail prices for every common card.

### 8. Report every run

Keep the user-facing report concise and include:

- best finds;
- asking price;
- rough market/practical value;
- BUY / WATCH / PASS judgement;
- whether the listing is genuinely new, newly indexed, or newly updated when known.

If nothing qualifies, include the requested sentence:

`No worthwhile new deals found.`

If the run had only third-party-index coverage and no fresh Adverts alert inputs, add a short coverage qualifier such as `Freshness coverage: third-party index only; very new Adverts listings can appear before indexing.` This avoids overclaiming completeness.

## Miss-audit procedure

When the user supplies a listing that the scan missed:

1. Record the exact listing ID/title and approximate time it was live.
2. Check whether the prior discovery queries could recover it from the third-party index.
3. Classify the miss as one of:
   - `INDEX_LATENCY`
   - `QUERY_COVERAGE`
   - `RESULT_RANKING/CUTOFF`
   - `DEDUPE/STATE`
   - `TRIAGE/SCORING`
   - `VALUATION/IDENTITY`
4. If it was absent from the index at scan time, do **not** "fix" scoring thresholds; improve freshness/alert coverage instead.
5. Add a query/protocol regression only when it would genuinely have surfaced the missed listing.

## Current known limitation

Without platform-native saved-search alerts (or user-supplied alert messages), no compliant third-party-search workflow can guarantee detection of an advert within minutes of posting. Search-index delay is an external constraint.

For fast-moving local bargains, the recommended architecture is therefore:

**Adverts native alert on the user's side -> deal link/message supplied to the chat -> immediate photo/description valuation**, with the recurring third-party-index scan acting as a secondary catch-net.
