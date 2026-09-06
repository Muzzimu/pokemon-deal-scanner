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
