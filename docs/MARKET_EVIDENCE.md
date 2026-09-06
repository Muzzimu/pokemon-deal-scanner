# Market evidence hierarchy and manual-source policy

Last reviewed: 2026-09-06

This document preserves the project rules for interpreting manual resale/local-market evidence. It complements `docs/PROJECT_CONTEXT.md` and `docs/EBAY_API_COMPLIANCE.md`.

## eBay manual evidence hierarchy

For manual card-by-card resale validation, use the following order of confidence:

1. **eBay Product Research actual sold data — strongest manual evidence**
   - Prefer exact-card matches, raw/ungraded, correct language/condition where identifiable, and the relevant geographic market.
   - Product Research can expose actual sold outcomes, including Best Offer outcomes where eBay provides them.
   - Treat this as the preferred manual eBay reference when available.

2. **Still-live eBay sold/completed page — strong evidence**
   - Useful when the page clearly shows the exact card, sold/completed state, price, condition and location.
   - Verify that the item is not a lot, slab, proxy, wrong language/version, or otherwise mismatched.

3. **Archived exact listing (Wayback / archive.today or equivalent) — corroborating evidence**
   - Useful when the archived page preserves the exact listing identity and sold/completed details.
   - Treat it as corroboration rather than automatically equal to current Product Research data because captures may be incomplete or stale.

4. **Search-engine snippet / third-party price tracker — weaker contextual evidence**
   - Useful for discovery and cross-checking only.
   - Do not promote a snippet or tracker estimate to confirmed sold evidence unless the underlying exact transaction can be independently verified.

### eBay Product Research operating procedure

Product Research is the preferred manual eBay source for this project because it provides up to three years of eBay sales data and can show actual sold prices, including accepted Best Offers where eBay exposes them. It is accessed through the ordinary seller account / Seller Hub rather than the Developer API.

For each card we validate:

1. Search the **exact card identity**, normally `Pokemon name + set code + collector number`, e.g. `Mega Lucario ex MEP 033`.
2. Exclude mismatches: slabs/graded cards, lots, jumbo cards, proxies/custom cards, Japanese/other languages when evaluating English, and different collector numbers or print variants.
3. Prefer **raw English** examples and match condition as closely as Product Research allows.
4. Start with a recent window such as **90 days** to measure current price/liquidity; expand to **365 days** or longer when the sample is thin or we want seasonality/history.
5. Prefer **Ireland / continental-European seller-location evidence** where sufficient. UK evidence is useful secondary context; US/global evidence is tertiary context for Irish resale decisions.
6. Record the useful normalized outputs rather than copying proprietary raw datasets: search term/exact card, date window, sold count/sample, representative sold prices or median/range, shipping context where relevant, region, currency, and any important exclusion notes.
7. Where Product Research shows actual accepted Best Offer outcomes, use the realized sold amount rather than a crossed-out/original asking price.
8. Treat one unusual transaction cautiously. Multiple clean exact-card sales are stronger than a single outlier.
9. Product Research evidence may support a manual resale decision, but must still be combined with acquisition cost, Cardmarket EN/NM, CardTrader supply, fees/postage and sale velocity.

### Export / data-capture note

As of the 2026-09-06 review, eBay's official Product Research documentation does **not** document a CSV/XLSX export for the Product Research market-results table itself. Seller Hub **Reports** can export the user's own orders/listings/marketing data, but that is a different feature and is not a Product Research market-data export.

For this project:

- Prefer manual review of Product Research and save only normalized summary evidence in `data/reference/ebay_product_research_summary.csv`.
- For small result sets, manually copy/paste visible table rows into a spreadsheet or share screenshots for analysis.
- Do not build browser automation, network interception, scraping, or other bulk extraction around Product Research unless eBay explicitly permits that use.
- Re-check eBay documentation before assuming this limitation is permanent; the UI/features may change.

### Access notes

- eBay currently describes Product Research as free to sellers and available under **Seller Hub → Research → Product Research**.
- eBay's help/seller documentation has varied over time on the precise eligibility needed to opt into Seller Hub/Product Research. If a new account does not show the Research tab, complete legitimate seller onboarding and use a genuine listing/sale path rather than creating artificial/self-transactions.
- The mobile eBay app also exposes Product Research for eligible sellers, but desktop Seller Hub is preferred for this project because filtering and review are easier.

Official eBay references for this workflow:

- https://www.ebay.com/help/selling/selling-tools/terapeak?id=4853
- https://www.ebay.com/sellercenter/growth/ebay-research-tools
- https://www.ebay.com/sellercenter/selling/how-to-sell/seller-hub
- https://export.ebay.com/en/services-tools/seller-hub/seller-hub-reports/

### Manual-evidence rules

- Exact-card identity matters: set, collector number, version, language, condition and raw/graded status must match.
- Ireland / continental-Europe evidence is preferred for Irish resale decisions; UK and US evidence are context unless deliberately converted and caveated.
- Active asking prices are not sold prices.
- A disappeared listing is not a sale unless there is separate evidence of completion.
- Search snippets and price trackers should not drive an automatic `RESELL_TEST` decision by themselves.
- Do not commit eBay screenshots, raw proprietary datasets, seller personal data, or other eBay content to this public repository unless redistribution/storage is clearly permitted. Keep the repository to rules, normalized project metadata, and evidence templates.
- This manual hierarchy does **not** remove the API-compliance constraints recorded in `docs/EBAY_API_COMPLIANCE.md`.

## DoneDeal role in the project

DoneDeal is useful as an additional **Irish sourcing and asking-price context source**, especially for local bulk lots, binders, collections and individual cards that may not appear on Adverts.ie.

### What DoneDeal evidence means

- **Active listing price**: Irish asking-price / sourcing context only; not realized value.
- **Visible price reduction**: useful negotiation and seller-motivation signal; still not a sale price.
- **Ad no longer available**: unknown outcome. It may have sold, expired, been withdrawn, deleted or relisted. Do not call it sold without corroboration.
- **Seller rating / verification / tenure / response rate**: transaction-risk context only, not card-value evidence.
- For any potential purchase, compare the item against Cardmarket English/NM, relevant CardTrader supply and stronger resale evidence before calling it a deal.

### DoneDeal access constraint

DoneDeal's current Terms prohibit using robots, spiders, website search/retrieval applications or other automated means to access/retrieve/index the site, and prohibit accessing/retrieving/indexing the site for constructing or populating a database. Its published API policy is for specifically authorised vehicle-dealer tooling and is not intended for aggregation/comparison marketplaces unless explicitly approved.

Therefore:

1. **Do not add an automated DoneDeal scraper to the scanner.**
2. Use DoneDeal manually / ad hoc for current Irish sourcing and market context.
3. Do not persist a systematic DoneDeal listing database in this repository.
4. Do not treat an unavailable DoneDeal ad as sold evidence.
5. Re-check DoneDeal Terms before changing this policy.

Official references reviewed:

- https://hello.donedeal.ie/hc/en-us/articles/201251761-Terms-Conditions-of-Use-of-DoneDeal
- https://hello.donedeal.ie/hc/en-us/articles/42060430206737-DoneDeal-API-Usage-Policy
