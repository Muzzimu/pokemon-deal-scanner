# eBay Product Research workflow

Last reviewed: 2026-09-06

This is the manual operating procedure for using eBay Product Research as resale evidence for the Pokemon TCG project.

## Important UI detail: select the card category first

If Product Research is left on **All Categories**, the Condition filter can show generic eBay conditions such as New, Like New, Used or Very Good. Those are not the trading-card-specific filters we want.

Before filtering condition, choose the single-card CCG category:

**Toys & Hobbies -> Collectible Card Games -> CCG Individual Cards**

Then rerun the search. eBay's trading-card condition model for this category uses **Graded** and **Ungraded**. For this project, use **Ungraded** / raw only unless the user explicitly asks about slabs.

If obvious slabs still appear because sellers miscategorised them, also exclude common grader/slab terms from the query, for example:

`-PSA -CGC -BGS -Beckett -SGC -ACE -graded -slab`

## Standard card-validation flow

1. Search exact identity, e.g. `Mega Lucario ex MEP 033`.
2. Select **Toys & Hobbies -> Collectible Card Games -> CCG Individual Cards**.
3. Set **Condition = Ungraded**.
4. Start with **Last 90 days**.
5. Exclude lots, jumbo cards, proxies/customs, wrong collector numbers and wrong languages where relevant.
6. Prefer English raw sales that match the target card as closely as possible.
7. Prefer Ireland / continental-European seller-location evidence where sufficient; use UK secondarily and US/global as broader context.
8. Record normalized observations only: sold count/sample, representative sold prices or median/range, shipping context, region/currency and exclusions.
9. Do not treat Product Research averages as trustworthy if the result set still visibly contains graded cards or other mismatches.

Official references:

- https://www.ebay.com/help/selling/selling-tools/terapeak?id=4853
- https://www.ebay.com/sellercenter/selling/what-to-sell/selling-trading-cards
- https://ocsnext.ebay.com/help/selling/listings/creating-managing-listings/item-conditions-category?id=4765
