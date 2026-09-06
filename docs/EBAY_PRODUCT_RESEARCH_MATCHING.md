# eBay Product Research exact-card matching

Last reviewed: 2026-09-06

Product Research title searches can both **undercount** and **overcount** Pokemon card sales:

- Exact searches such as `Dragonite V PGO 076` miss valid listings whose title only says `Dragonite V`.
- Broad searches such as `Dragonite V` can mix multiple sets, collector numbers, languages and variants.

Use a two-pass manual workflow:

1. **Precision pass** — search exact identifiers, including useful title variants such as `Dragonite V PGO 076` and `Dragonite V 076/078`. This gives a high-confidence minimum sample.
2. **Recall pass** — search the broader card name, select the CCG Individual Cards category, then use category-specific item filters where available (for example Set = Pokemon GO, Card Number = 076/078 or 076, Character/Card Name = Dragonite/Dragonite V, Ungraded). This can recover valid sales whose seller omitted the set/number from the title.
3. Manually review ambiguous rows/images when item specifics are missing or inconsistent. Exclude wrong art/print, lots, graded cards, other languages when evaluating English, and mismatched collector numbers.
4. Do **not** use the Product Research headline average/sell-through as an exact-card benchmark until the result set has been sufficiently cleaned. Prefer normalized clean matched rows and record the matching method/sample limitations.
5. Keep marketplace and seller-location context separate: ebay.com/US evidence is not UK/EU/Ireland evidence even when the same card is being researched.

Official eBay Product Research documentation confirms that category selection exposes dynamic category-specific filters and that advanced search/exclusion logic is supported:
- https://www.ebay.com/help/selling/selling-tools/product-research?id=4853

This matching rule is manual evidence policy and does not authorize automated extraction or scraping of Product Research.
