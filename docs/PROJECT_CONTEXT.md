# Pokémon Deal Scanner — Durable Project Context

Last consolidated: 2026-09-05

This file is the durable carry-forward memory for the Pokémon TCG sourcing/resale project. It exists so that important decisions agreed in ChatGPT conversations do not disappear when a chat is replaced, shared, truncated, or moved.

## Source of truth and change management

- The GitHub repository `Muzzimu/pokemon-deal-scanner` is the implementation source of truth for the scanner.
- Before interpreting a scanner run, changing thresholds, or modifying code/configuration, review the current `main` branch and recent commits first. Do not silently revert a newer agreed rule by relying on an older chat assumption.
- Material business/scanner agreements made in chat should be reflected in GitHub whenever practical: documentation for policy/strategy, `config.yaml` for thresholds, `data/reference/` for benchmark/evidence rows, and tests for behavioral guarantees.
- If a current explicit user decision conflicts with this document, the newest explicit decision wins; update GitHub so the conflict does not recur.
- Do not put unrelated personal, medical, financial-account, credential, or other sensitive information in this repository. Only retain project-relevant business/scanner context.

## What “run the scanner/script” means

When the user says “run the scanner”, “run the script”, or equivalent, that means the actual GitHub project/workflow and its generated outputs, not merely a manual web search.

Manual Adverts/eBay/web research may supplement scanner results, but it must be labelled separately so manual research is not presented as scanner output.

## Project goal

Build a small-scale, low-risk Pokémon TCG sourcing/resale workflow for Ireland, combining:

1. selective individual-card flips;
2. inexpensive inventory for kids’ bundles;
3. themed mini-bundles built around recognizable Pokémon;
4. local Irish resale intelligence; and
5. disciplined acquisition decisions based on landed cost and realistic resale evidence rather than headline asking prices.

The objective is not maximum inventory turnover at any cost. Prefer asymmetric opportunities with modest capital at risk, clear buyer appeal, and enough margin to absorb postage, fees, negotiation, and slow sales.

## Standing pricing and sourcing rules

### Cardmarket

- For Pokémon price/value comparisons, use **English-language, Near Mint (NM)** cards unless the user explicitly asks for another language/condition.
- Cardmarket generic/public low is **discovery only**. It must not be described as the actionable English+NM floor.
- A Cardmarket buy decision requires, where applicable:
  - English;
  - NM;
  - ships to Ireland;
  - confirmed shipping/landed or basket-adjusted cost; and
  - seller-risk consideration.
- Prefer a robust planning floor (for example, the median of the cheapest eligible offers after seller-history filtering) over one anomalously cheap listing.
- Article price alone is not the correct acquisition cost when postage materially changes the economics.

### CardTrader

- Use CardTrader EN/NM as an independent live European supply reference.
- Keep CardTrader evidence source-labelled rather than merging it silently with Cardmarket.
- CardTrader Zero/consolidated-shipping mechanics can materially improve landed economics and should be considered when relevant.

### eBay

- Use eBay primarily as resale evidence, not as a substitute for verified Cardmarket sourcing cost.
- Prefer Ireland/continental-European evidence for Irish resale decisions.
- Keep Ireland, continental EU, UK, and Global evidence separate. Do not silently mix EUR/GBP/USD.
- For regional evidence, physical item location matters; the marketplace website alone does not establish that the item is local/EU stock.
- Confirmed sold evidence is stronger than active asking prices.
- Active asks are context/ceiling evidence only and must never be relabelled as sold prices.
- Listing disappearance is not automatically a sale. The scanner’s repeated-miss/inferred-quick-sale logic must remain explicitly lower confidence than a verified sold transaction.

## Local Irish market evidence

### Adverts.ie evidence hierarchy

Use local evidence according to confidence:

1. platform explicitly states the item is sold + visible accepted price/offer;
2. platform explicitly states sold, realized price unknown;
3. seller explicitly marks an item/subset sold;
4. concrete accepted offer without sold state;
5. PM/DM/contact placeholder acceptance;
6. disappearance/withdrawal;
7. active asking price only.

Never assume that an accepted PM/DM or a disappeared listing completed at the advertised price.

Adverts.ie tracking must remain manual/public-index based where required by the platform’s current Terms. Do not build unauthorized automated scraping/indexing of Adverts.ie.

### Standing seller/retail benchmarks

- **Rocco_jr — Adverts member 1462668**: use asking prices as a **high-retail Irish ceiling**, not fair market value. Give substantially more weight to actual offers, accepted offers with corroboration, sold-marked items, and other evidence of what buyers really pay.
- **PokeDub — Adverts member 2946433**: local singles/master-set/part-out benchmark. Preserve the existing evidence rules showing that PM/DM acceptance can fall through.
- **PW Card Co — Dublin pop-ups**: use visible sticker prices as face-to-face Irish retail-ceiling evidence and occasional sourcing leads. In-person inspection/no postage can justify a modest premium over Cardmarket, not an unlimited one. Keep English/Japanese comparisons separate.

When possible, compare local Irish evidence against Cardmarket EN/NM and European eBay evidence rather than relying on one venue in isolation.

## Business strategy and product concepts

### Kids’ bundles

Standing concepts from the original business discussion:

- approximately **50-card bundle at €10**;
- approximately **20-card bundle at €6**;
- optional inexpensive presentation upgrades such as a foldable deck box or child-friendly packaging;
- perceived value matters: a recognizable hero card, holo/reverse holo, or inexpensive ex/V can make the bundle meaningfully more attractive than random bulk;
- benchmark against competing local/online bulk bundles before assuming €10 is justified.

A bundle should offer a reason to choose it over generic bulk: recognizable Pokémon, coherent theme, nicer presentation, or a visibly attractive hero card.

### Themed mini-bundles

Useful concepts include 3–5 card groups around:

- Dragonite;
- Pikachu;
- starters (Bulbasaur/Squirtle/Charmander families);
- Eeveelutions;
- Gengar;
- Greninja;
- Lucario;
- Gyarados;
- Arcanine;
- sharks / shark-like Pokémon; and
- other highly recognizable child-friendly Pokémon.

Do not assume that a theme automatically creates a premium. Validate local willingness to pay; some coherent mini-groups still sit unsold at near-market pricing.

### Hero-card sourcing

- Cheap ex/V/GX/VMAX-style cards can be useful as perceived-value anchors for kids’ bundles.
- The correct target is not simply “cheapest ex”; consider character popularity, artwork, supply, condition, and landed cost.
- A €4–€5 card inside a €10 bundle is usually too expensive unless the rest of the bundle is exceptionally cheap or the product can command a higher price. Prefer low-cost attractive hits when building margin-sensitive bundles.

## Deal-evaluation format

For individual sourcing opportunities, default to showing:

- purchase price / maximum buy price;
- realistic resale price (not aspirational asking price);
- likely gross/net spread after relevant postage/fees;
- ROI percentage;
- confidence in the resale reference;
- likely sale speed / liquidity; and
- classification such as **quick flip**, **good hold**, **bundle stock**, **collection buy**, **watch**, or **avoid**.

Separate collector appeal from business economics. A card the user personally likes may still be a reasonable hold even when it is not an optimal short-term flip; label that distinction explicitly.

## Margin and evidence discipline

Current automated resale thresholds in `config.yaml` are the implementation rule unless explicitly changed:

- minimum gross spread: €2.00;
- minimum gross ROI: 25%;
- weaker resale evidence should require a larger cushion than strong sold evidence.

Do not call something a “deal” merely because Cardmarket low is below Cardmarket average. For a real resale recommendation, consider landed acquisition cost, realistic exit price, fees/postage, demand, evidence quality, and sale velocity.

## Popularity / buyer appeal

The scanner currently encodes explicit popularity weights for several Pokémon. Business analysis should also use real-world buyer appeal, particularly recognizable characters for children and casual collectors. Dragonite and Pikachu are especially important recurring themes in this project.

Popularity is a resale factor, not proof of profitability. A popular character bought at retail price may still be a bad flip.

## Inventory / sourcing preferences carried from chat

- Prefer low-capital experiments over large speculative positions.
- Bulk lots can be attractive when a few identifiable cards or useful bundle components effectively pay for much of the acquisition.
- For bulk, calculate per-card cost and distinguish truly useful bundle inventory from filler.
- Local collection can improve economics by eliminating postage; distant collection should be treated as a real friction/cost rather than ignored.
- Consolidated postage matters. Several cheap cards from one seller can be superior to individually cheaper cards spread across multiple sellers.
- Sealed product should be evaluated separately as: open for inventory, hold sealed, or skip. Do not automatically treat sealed products as investments.

## Known historical calibration points

These are context, not permanent market prices:

- The project has previously sourced 50-card lots around €5 (and another around €5 + €2.50 postage), showing that inexpensive bulk inventory is achievable.
- A local competing example was observed offering 50 English cards including a V/ex plus holo/reverse-holo content around €7, with two bundles negotiated around €13 including postage. This is useful calibration for the proposed €10 50-card product: our bundle should have a clearer theme, presentation, or hero-card advantage.
- A Marnie Premium Tournament Collection was acquired around €17 as a one-unit experiment; sealed-vs-open should be decided from current product economics rather than treated as a standing investment rule.

Do not reuse these historical prices as current market quotes without fresh verification.

## Scanner architecture rules worth preserving

- New-product guard suppresses generic flip signals during the first 14 days to reduce launch-week noise.
- Cardmarket history is retained at decreasing granularity over time; raw CardTrader history is bounded.
- eBay disappearance requires repeated successful scans before inferred sale logic is allowed.
- eBay confirmed/inferred/ask evidence must stay source-labelled with confidence levels.
- Stale Cardmarket price rows not present in the current catalogue must be handled safely rather than crashing/poisoning the pipeline.
- Tests should be added/updated when changing pricing guardrails, sourcing eligibility, market-evidence interpretation, or workflow scheduling.

## Workflow scheduling

The production GitHub Actions scanner is intended to run once per day during the **07:00 Europe/Dublin hour**, with redundant scheduled attempts and a daily success marker so only one full scheduled scan completes. Manual workflow dispatch remains supported.

Temporary push-trigger diagnostic workflows used for testing should be removed/restored so the production workflow returns to scheduled/manual operation after validation.

## Conversation continuity rule

When starting a new Business Ideas chat, do not rebuild project assumptions from scratch. Read this document, `README.md`, `config.yaml`, relevant `data/reference/` files, and recent commits first. Then use current live evidence for anything time-sensitive.

This document is intentionally broader than the code README: README explains the scanner; this file preserves the business decisions and interpretation rules that would otherwise live only in ChatGPT conversation history.
