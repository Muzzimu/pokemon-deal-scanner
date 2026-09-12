# Vinted validation — sourcing, resale and liquidity research

Date: 2026-09-12

Status: **passes as a research/discovery channel; does not yet pass as automated exact-card acquisition or realised-sale valuation evidence**

Scanner version: v0.12 (no model, fair-value, BUY-gate, score, or route changes)

## Executive conclusion

Vinted is materially useful to the Pokémon project, but its best role is narrower than a normal TCG marketplace.

It is useful for:

- opportunistic single-card discovery;
- raw lots / collections / kid-oriented bundle discovery;
- a potential resale channel, especially because standard selling has no platform selling fee and buyers pay integrated shipping;
- prospective supply and sell-through research if stable listing IDs are monitored over time;
- competitive intelligence for our €5/€7/€10 bundle product.

It is **not** currently suitable as:

- an automatic exact EN/NM acquisition feed from search results alone;
- a direct fair-value source;
- a source of confirmed realised sale prices;
- an automatic BUY input.

The most important practical finding is that Vinted search is fuzzy, multilingual and sometimes stale. Category + brand filtering improves topical precision dramatically, but exact printing, language, condition and current item state still need a second-stage detail check. Search-visible listings were found whose item page already said **Removed!**. Removal cannot be interpreted as a sale.

For resale, Vinted is particularly relevant to the user's bundle business, but Vinted's commercial-selling rules mean regular inventory acquired for resale should not simply be operated through a standard personal account. Pro eligibility/status must be verified before treating it as a scaled business channel.

## Sources reviewed

### Vinted itself

- https://www.vinted.ie/catalog
- https://www.vinted.ie/catalog/4875-single-trading-cards
- https://www.vinted.ie/catalog-rules
- https://www.vinted.ie/help/342-buyer-protection-fee-on-vinted
- https://www.vinted.ie/help/4/373-is-selling-on-vinted-free
- https://www.vinted.ie/help/234
- https://www.vinted.ie/help/5/260-buying-a-bundle
- https://www.vinted.ie/help/258-i-want-to-make-an-offer-or-suggest-a-different-price
- https://www.vinted.ie/help/918
- https://www.vinted.ie/help/3/1120-commercial-selling
- https://www.vinted.ie/help/392/551-information-for-sellers

### Provider research

- ScrapeBadger Vinted docs: https://docs.scrapebadger.com/vinted/overview
- ScrapeBadger search endpoint: https://docs.scrapebadger.com/api-reference/endpoint/vinted/search-items
- ScrapeBadger detail endpoint: https://docs.scrapebadger.com/api-reference/endpoint/vinted/get-item-detail
- Lobstr Vinted API/scraper overview: https://www.lobstr.io/blog/vinted-api
- Pawikoski wrapper: https://github.com/Pawikoski/vinted-api-wrapper

## Ireland marketplace economics and execution

### Buyer Protection

Vinted Ireland states Buyer Protection is mandatory on orders and is usually calculated as **5% + €0.70**, although the exact fee can vary with the item/order/bundle.

The live test repeatedly exposed totals consistent with this formula:

| Ask | Displayed total incl. Buyer Protection | Protection uplift before shipping |
|---:|---:|---:|
| €1 | €1.75 | 75.0% |
| €2 | €2.80 | 40.0% |
| €3 | €3.85 | 28.3% |
| €5 | €5.95 | 19.0% |
| €7 | €8.05 | 15.0% |
| €10 | €11.20 | 12.0% |
| €15 | €16.45 | 9.7% |
| €20 | €21.70 | 8.5% |
| €40 | €42.70 | 6.8% |
| €100 | €105.70 | 5.7% |

This is before delivery. Consequently, ultra-cheap Vinted singles can look attractive at the listed ask while becoming poor acquisition economics after Buyer Protection and shipping. Bundles from one seller are structurally more attractive because fixed friction is shared.

### Seller fee

Vinted Ireland says there are **no fees to upload or sell** on a standard account: after a successful sale, the seller receives the full selling price into Vinted Balance.

That is potentially attractive for our bundle/resale operation because the buyer, not the seller, bears Buyer Protection and integrated shipping.

### Shipping

Vinted Ireland currently lists integrated shipping through:

- An Post;
- DHL Express;
- Drop2Shop;
- DPD.

It also states **Ireland is connected with France**.

The buyer purchases the integrated shipping label at checkout and the seller receives the Vinted-generated label/code. This is operationally attractive for resale, but it creates a sourcing-data problem: exact shipping price is dependent on the order/location/parcel and is not reliably exposed in public search results. Therefore a Vinted acquisition is not executable in our scanner until landed cost is known.

Recommended production state for a promising Vinted listing:

`VERIFY_VINTED_CHECKOUT`

until actual shipping/eligibility is confirmed.

### Offers and bundles

Vinted supports:

- buyer/seller offers up to 40% below the listed item price;
- multi-listing bundle purchases from the same seller;
- bundle discounts for standard sellers;
- up to 100 items in one bundle order.

Offers are not binding until the buyer completes `Buy now`, and offers do not reduce shipping/fees.

This makes Vinted especially interesting for **multi-card seller consolidation**, not just isolated singles.

## Critical commercial-selling constraint

Vinted's Catalogue Rules explicitly allow trading cards, but they also say standard members must not use Vinted for commercial resale activity. Indicators of commercial activity include, among other things:

- regular income/profit;
- high transaction volume;
- many similar/low-value items;
- items bought specifically for resale.

Vinted also says commercial selling is for Pro sellers and has a Vinted Pro help page that currently names Ireland among supported seller-registration countries, while another commercial-selling help page contains a country list that omits Ireland. The documentation is therefore not perfectly internally consistent.

For this project the safe operating conclusion is:

**do not scale the Pokémon bundle business through a standard personal Vinted account. Verify actual Vinted Pro eligibility/account setup in Ireland before treating Vinted as a production resale channel.**

There is also a different return/friction regime for Pro sellers, including consumer withdrawal rights, so a later execution-cost model must distinguish standard vs Pro sales.

## Catalogue / product restrictions relevant to Pokémon

Vinted explicitly allows trading cards.

The Catalogue Rules also state:

- counterfeit items are prohibited;
- graded cards without authenticity certificates are prohibited;
- bundle/set listings must identify themselves as such and use a total bundle price;
- items already included in a bundle listing cannot simultaneously be listed separately;
- stock/internet photos are not allowed as the listing's item photos;
- standard accounts cannot be used for commercial resale as described above.

For graded-card research, certificate/serial verification therefore needs to be part of identity validation rather than assuming that the word `PSA` is enough.

# Live Vinted test battery

The tests below were run live on `vinted.ie` on 2026-09-12. They were deliberately broad enough to test exact-card retrieval, vintage ambiguity, language, graded cards and lots/bundles.

The search result counts are Vinted's displayed counts/caps and should be interpreted as discovery scale, not unique exact-card inventory.

## A. Modern exact-card searches

| # | Query | Displayed results | First-page finding | Verdict |
|---:|---|---:|---|---|
| 1 | `Zeraora VMAX GG42` | 48 | Multiple GG42/GG70 results near top, but mixed language/graded/ambiguous and later noise | Useful with second-stage validation |
| 2 | `Origin Forme Palkia VSTAR GG67` | 108 | Search mixed target concept with Japanese VSTAR Universe and other Palkia versions | Weak exact-print precision |
| 3 | `Dragonite V 076/078 Pokemon GO` | 240 | One clearly relevant 076/078 among first 10; many unrelated/wrong variants | Weak exact-print precision |
| 4 | `Pikachu VMAX SWSH286` | 411 | Exact promo, jumbo, French, paired-card listings and unrelated cards mixed together | Useful discovery, unsafe direct match |

### Pikachu SWSH286 examples

First page included:

- `Pikachu Vmax SWSH286` — €5, €5.95 incl. Buyer Protection;
- `Carte pokémon jumbo pikachu VMAX swsh286` — €3 — wrong physical product for normal single-card use;
- `Carte Pokémon : Pikachu Vmax swsh286 - Rare francaise` — €7 — wrong language for EN acquisition;
- `Pikachu Vmax promo SWSH286` — €4;
- a Pikachu lot and unrelated card results.

Conclusion: collector-number/title search helps but **does not eliminate jumbo, language or bundle variants**.

## B. Vintage exact-card searches

| # | Query | Displayed results | First-page finding | Verdict |
|---:|---|---:|---|---|
| 5 | `Charizard 4/102 Base Set` | 500 | Base Set, French graded, Celebrations 4/102, other Charizards and non-card noise coexist | High identity risk |
| 6 | `Dragonite 4/62 Fossil` | 175 | Several plausible Fossil 4/62 listings plus language/edition/grade ambiguity and noise | Manual/image validation required |
| 7 | `Blastoise 2/102 Base Set` | 500 | A likely exact 2/102 result appears, but wrong Blastoise printings and unrelated items remain high | High identity risk |
| 8 | `Gengar 5/62 Fossil` | 215 | Exact-looking `Pokemon Fossil Gengar Holo 5/62` €89 and `Gengar 5/62 fossile US` €140 appear, mixed with other Gengars and unrelated cards | Useful research shortlist |

Vintage cards are especially unsafe for title-only automation because edition, language, holo/non-holo/reprint and grading materially affect value.

## C. Broad character searches

| # | Query | Displayed results | Finding |
|---:|---|---:|---|
| 9 | `Charizard Pokemon card` | 500 | Strong card discovery, mixed languages/eras/raw/graded |
| 10 | `Pikachu Pokemon card` | 500 | Strong discovery, mixed singles/slabs/jumbo and other cards |
| 11 | `Gengar Pokemon card` | 500 | Strong discovery but includes fan art, wrong Pokémon/results and slabs |
| 12 | `Eevee Pokemon card` | 500 | Eevee/Eeveelutions mixed with unrelated cards and graded products |

Broad character search is therefore suitable for **opportunity discovery**, not exact Cardmarket-product mapping.

## D. Language-query tests

| # | Query | Displayed results | Finding |
|---:|---|---:|---|
| 13 | `Zeraora VMAX GG42 English` | 123 | One strong English target at top, then heavy unrelated/non-card noise |
| 14 | `Zeraora VMAX GG42 French` | 121 | Search still returned the English target prominently; heavy unrelated noise |
| 15 | `Zeraora VMAX GG42 Japanese` | 124 | English target still appeared; heavy unrelated noise |
| 16 | `Charizard 4/102 English` | 160 | Mostly wrong/non-card in first page; language term did not constrain identity reliably |

**Conclusion: free-text language words are not a reliable language filter.**

Language must be established from item detail/title/description/photos or an explicit structured field if a provider exposes one. For our EN/NM acquisition rule, unknown language remains ineligible.

## E. Graded-card searches

| # | Query | Displayed results | Finding |
|---:|---|---:|---|
| 17 | `Zeraora VMAX GG42 PSA` | 105 | Very noisy; exact-card + grade search did not reliably retrieve slabs |
| 18 | `Charizard 4/102 PSA` | 245 | Very noisy, many wrong/non-card first-page results |
| 19 | `Pikachu PSA 10` | 500 | Good general graded-Pikachu discovery; multiple explicit PSA 10 listings |
| 20 | `Pokemon card graded` | 500 | Rich graded-card inventory but mixed graders/prints and some raw ambiguity |

Example `Pikachu PSA 10` results included explicit McDonald's, Yu Nagaba, Gym Event and other PSA 10 Pikachu slabs.

Therefore Vinted can support graded-card discovery, but exact-print + grade automation still needs certification/serial and image checks. Vinted's own rules make certificate/authenticity evidence particularly important.

## F. Lot / bundle searches

| # | Query | Displayed results | Finding |
|---:|---|---:|---|
| 21 | `Pokemon cards lot` | 500 | Many real card lots, plus sealed boxes, jumbo cards and ambiguous listings |
| 22 | `Pokemon card bundle` | 500 | Strong bundle discovery, mixed with individual cards and graded products |
| 23 | `Pokemon collection cards` | 500 | Collections, singles, sealed and non-Pokémon TCG noise mixed together |
| 24 | `lot cartes pokemon` | 500 | Strong French-language lot discovery plus singles and sealed products |

This is one of Vinted's strongest roles for us: **manual collection/lot sourcing**, where exact individual-card identity can be extracted from photos after a promising lot is found.

# Category-filter test — important improvement

The generic search above is noisy. We therefore repeated exact-card searches inside Vinted's **Single trading cards** category (`catalog/4875-single-trading-cards`).

## Zeraora VMAX GG42 category-filtered

Displayed results: 69.

First 10 were all Pokémon/Zeraora GG42-related rather than random household items. Examples:

| Title | Ask | Buyer-protection total | Identity note |
|---|---:|---:|---|
| `Carte Pokémon Zeraora Vmax alternative English` | €27 | €29.05 | explicit English; detail says GG42/GG70 |
| `Zeraora Vmax GG42/GG70 Fr` | €70 | €74.20 | explicit French |
| `Zeraora VMAX GG42/GG70 Zénith Suprême` | €65 | €68.95 | exact printing likely; language not explicit in title |
| `Zeraora Vmax gg42/gg70` | €64 | €67.90 | exact printing likely; language unknown |
| `Zeraora Vmax GG42/GG70` | €72 | €76.30 | exact printing likely; language unknown |
| `Zeraora vmax alternative gg42/gg70` | €60.99 | €64.74 | exact printing likely; language unknown |
| `Zeraora Vmax GG42/GG70` | €55 | €58.45 | exact printing likely; language unknown |
| `Carte Pokémon VF - Zeraora VMax GG42 - Zenith Suprême` | €75 | €79.45 | explicit French |

Category filtering therefore **dramatically improves topical precision**, but still does not solve language or Pokémon-condition normalization.

## Palkia GG67 category-filtered

Displayed results: 150.

The first 10 were all trading-card-relevant, but predominantly Japanese `VSTAR Universe 259/172`, other Palkia VSTAR cards or related Palkia printings. There was **no clearly exact English Crown Zenith GG67 raw target in the first 10**.

This is strong evidence that Vinted search ranking is semantic/fuzzy rather than an exact TCG identity engine. The collector number in a query does not guarantee collector-number matching.

# Search staleness / listing-state test

This was the most important technical result.

The category-filtered search returned:

`Carte Pokémon Zeraora Vmax alternative English` — item `9966910555` — at €27 / €29.05 incl. Buyer Protection.

Its item-page metadata explicitly described:

- `GG42/GG70`;
- `eng / english / anglais`;
- `Zenith supreme`.

However, opening the item page live showed:

**`Removed!`**

A second item from the same seller that remained visible through search also showed `Removed!` when the item page was opened.

This establishes two mandatory rules for any Vinted collector:

1. **search results are not sufficient proof that an item remains purchasable; detail-state confirmation is required;**
2. **Removed/disappeared must never be interpreted as sold.** It could represent deletion, moderation, withdrawal, relisting, sale, or another state.

If a provider exposes explicit `is_closed`, `is_hidden`, `is_reserved`, `can_buy` and similar fields, these state transitions should be collected prospectively rather than inferred from URL disappearance.

# Vinted as competition for our bundle product

Two extra searches were run specifically against our planned low-price bundle business.

## `50 pokemon cards`

Displayed results: 500.

Examples from the first page:

- `50 Pokemon Cards with Collectors Tin` — €9.99 (€11.19 incl. Buyer Protection);
- `Lots de cartes Pokémon - avec des brillantes !` — €8 (€9.10 incl.);
- `50 cartes pokemon + Motisma V` — €5 (€5.95 incl.);
- `50 cartes pokemon + Goupelin V` — €5 (€5.95 incl.);
- various generic lots and novelty/gold-colour card listings.

## `pokemon cards kids bundle`

Displayed results: 50.

Examples:

- `Pokemon english cards bulk mini bundle lot - cute & adorable artwork + mini tin` — €5.50 (€6.48 incl.);
- `Pokemon english mini bulk bundle lot with tin` — €7 (€8.05 incl.);
- `Pokémon Card Bundle (50 Cards) - No Duplicates! Includes Shiny Holo Cards` — €5 (€5.95 incl.);
- `50 Pokemon cards` — €5 (€5.95 incl.);
- `Pokémon Card Bundle – 25 Mixed Cards (Includes Reverse Holos)` — €8 (€9.10 incl.);
- `100 Pokémon Cards Lot – English Cards | Mixed Generations | Great for Collectors` — €14 (€15.40 incl.);
- some explicit `Fan Art Bundle - Non TCG` results.

### Implication for our bundle plan

Vinted is a real competitor at the **€5–€10** bundle tier. A plain “50 Pokémon cards” offer is heavily commoditised.

Our planned differentiation remains important:

- recognisable/icon Pokémon;
- better foil density;
- evolution lines;
- a visible V/ex/hero card;
- curated cute/power themes;
- no-duplicate promise where practical;
- attractive presentation/packaging.

Vinted also makes multi-item bundles cheap to transact because shipping is buyer-paid and seller fees are zero, so it may be a particularly relevant channel for a curated bundle proposition if the commercial/Pro account issue is resolved.

# Provider comparison for automated Vinted research

## ScrapeBadger

Current docs say it supports 27 Vinted markets including `ie`.

Useful endpoints/costs:

- search items — 5 credits;
- item detail — 10 credits;
- user profile — 3 credits;
- user items — 3 credits;
- brands — 3 credits;
- status/color dictionaries — 1 credit;
- market list — 0 credits.

Search supports query, market, page, up to 96 results/page, min/max price, category IDs, brand IDs, status IDs, ordering and seller country.

Documented fields include stable item ID, title, price/currency, service fee, total item price, brand, condition/status, photos, URL, seller summary, favourites, views and visibility/promotion fields.

The detail endpoint is especially valuable because the provider documents explicit state fields such as:

- `can_buy`;
- `instant_buy`;
- `can_bundle`;
- `can_reserve`;
- `is_reserved`;
- `is_closed`;
- `is_hidden`.

Their documentation maps these to active/reserved/sold/hidden states. This makes ScrapeBadger the strongest of the three candidates for **prospective listing-state research**, subject to our own validation.

Critical limitation: the public Vinted payload does not expose a confirmed buyer-paid sold price. A closed/sold listing can establish state/velocity, not a realised transaction amount.

## Lobstr

The Lobstr article describes a managed Vinted scraper with:

- search/catalog collection;
- 30+ attributes;
- JSON/CSV exports;
- Google Sheets/S3/email exports;
- scheduling and webhooks;
- proxy/headless anti-bot handling.

It appears attractive for inexpensive scheduled discovery. Its article advertises roughly 100 free results/month and pricing around $1 per 1,000 results at low scale, declining at larger scale.

Compared with ScrapeBadger, the documented model is more discovery/job-oriented and less compelling for detailed state-transition research on individual listings.

Recommended role: **cheap scheduled discovery challenger**, not first choice for our listing-episode store.

## Pawikoski `vinted-api-wrapper`

The open-source Python wrapper demonstrates direct use of Vinted's undocumented/internal endpoints and supports search/detail/user-style functions.

Advantages:

- source code available;
- no per-call vendor cost;
- useful prototype/reference for understanding Vinted payloads.

Risks:

- depends on undocumented Vinted API behaviour/cookies/proxies;
- higher anti-bot and maintenance burden;
- the README's supported domain list did not include `vinted.ie` when reviewed;
- production reliability would become our responsibility.

Recommended role: **reference/prototype only** unless an Ireland-specific fork is validated and maintenance burden proves acceptable.

## Provider ranking for this project

1. **ScrapeBadger** — best fit for search + item detail + explicit listing-state research.
2. **Lobstr** — potentially cheaper/easier discovery monitoring, weaker detail-state fit.
3. **Direct/open-source wrapper** — lowest external API cost but highest operational/maintenance risk; no current IE support documented.

# Recommended Vinted architecture

## Source roles

Do not call Vinted a realised-sale price source.

Use explicit roles:

- `VINTED_ACTIVE_DISCOVERY`
- `VINTED_LOT_DISCOVERY`
- `VINTED_RESALE_DIAGNOSTIC`
- `VINTED_SOLD_STATE_UNPRICED`

Do **not** create `VINTED_CONFIRMED_SOLD_PRICE` unless a later trustworthy source actually exposes/validates the transaction price.

## Two-stage collection

### Stage 1 — cheap discovery

Use category + brand filtering where possible:

- Single trading cards category;
- Pokémon brand;
- exact card query or lot/bundle query;
- price bands where useful.

### Stage 2 — detail verification

Only inspect detail for shortlisted candidates.

Required actionable checks:

- listing still active/buyable;
- exact card printing/set/collector number;
- raw vs graded;
- language;
- condition evidence;
- seller/location/eligibility;
- photos/manual condition check where relevant;
- shipping/landed cost at checkout before acquisition.

Vinted's generic condition such as `Very good` must **not** be mapped automatically to Pokémon `NM`.

## Prospective history table

If implemented, collect append-only snapshots/episodes rather than overwriting current state.

Suggested fields:

- `observed_at`
- `provider`
- `query_id`
- `item_id`
- `url`
- `title`
- `description_hash`
- `ask_eur`
- `buyer_protection_eur`
- `total_before_shipping_eur`
- `catalog_id`
- `brand_id`
- `vinted_condition`
- `seller_id`
- `seller_country`
- `favourite_count`
- `view_count`
- `can_buy`
- `is_reserved`
- `is_closed`
- `is_hidden`
- `parsed_card_name`
- `parsed_set`
- `parsed_collector_number`
- `parsed_language`
- `raw_graded_class`
- `identity_confidence`

Suggested derived states:

- `ACTIVE_VERIFIED`
- `RESERVED`
- `SOLD_STATE_UNPRICED`
- `HIDDEN`
- `REMOVED_UNKNOWN`
- `RELISTED_OR_POSSIBLE_RELIST`

Never convert `REMOVED_UNKNOWN` to sale automatically.

# Acceptance gates before any decision use

Before Vinted can affect acquisition or route decisions, collect a prospective validation sample.

Minimum suggested research gates:

- >=30 manually checked exact-card candidates across several sets/languages;
- >=30 observed listing-state transitions over repeated snapshots;
- exact-print precision >=95% for any row admitted into exact-card economics;
- raw/graded precision >=95%;
- explicit language or manual verification for EN acquisition;
- actual Ireland checkout/landed-cost evidence for executable acquisitions;
- no disappearance-as-sale rule;
- commercial/Pro account eligibility confirmed before production resale;
- separate validation of return/cancellation friction before Vinted exit economics enter ECS/EV.

For broader **lot discovery**, precision can be lower because results are manually inspected; this is a discovery workflow, not an automated BUY route.

# Recommended practical next step

## Data/research

Implement a **passive Vinted pilot**, not a BUY route:

- 5–10 exact-card watch queries;
- 3–5 lot/bundle queries;
- category + Pokémon-brand filtering;
- cheap search daily;
- item detail only for new/changed/shortlisted IDs;
- state-transition history stored append-only;
- no fair-value vote;
- dashboard diagnostic only.

## Resale experiment

Only after confirming correct commercial account setup:

- test 3–5 listings rather than moving the whole inventory;
- include at least one €7/€10 curated bundle and one mid-value single;
- record views, favourites, offers, accepted sale price, shipping workflow, cancellation/return, days-to-sale and labour;
- compare net contribution and time-to-sale with Adverts/Facebook/eBay.

# Final verdict

| Use case | Verdict |
|---|---|
| Find cheap/interesting singles | **YES — discovery, with detail verification** |
| Find collections/lots | **YES — strong use case** |
| Competitor research for €5–€10 bundles | **YES — strong use case** |
| Automatic exact EN/NM sourcing from search | **NO** |
| Automatic landed-cost BUY | **NO — checkout/shipping missing** |
| Realised-sale fair value | **NO** |
| Prospective liquidity/sell-through research | **YES — promising** |
| Resale channel | **YES, conditional on correct Pro/commercial setup and economics test** |
| Production BUY input today | **NO** |

The channel is worth continuing, but as a **market/discovery/liquidity research layer first**. That is fully consistent with the project's indicator-role governance: a source can be useful without being forced into BUY logic.
