# eBay Product Research — Pokémon raw-card filters

Last reviewed: 2026-09-06

Use this when manually validating Pokémon TCG resale prices in eBay Product Research.

## Required filter

For ordinary raw-card comparisons, set the trading-card **Condition** filter to **Ungraded**. eBay treats `Graded` and `Ungraded` as distinct trading-card conditions. Do not mix graded/slab sales with raw-card resale evidence.

## Search exclusions

If graded listings still appear because sellers miscategorised them, exclude common grading/slab terms from the search title. Useful exclusions include:

- PSA
- CGC
- BGS
- Beckett
- SGC
- ACE
- graded
- slab

Product Research supports exclusions with `-keyword` and `AND NOT` syntax. If one syntax is stripped or behaves unexpectedly in the current UI, try the other and manually inspect the remaining sample.

Example starting search:

`Mega Lucario ex MEP 033 -PSA -CGC -BGS -Beckett -SGC -ACE -graded -slab`

Then apply **Condition: Ungraded** and relevant seller-location / date-range filters.

## Evidence rule

A sale that is clearly graded/slabbed is excluded from the raw-card sample even if it survives the filters. Exact-card identity, language, condition and raw/graded status must all match before using the result as strong resale evidence.

Official references reviewed:

- https://www.ebay.com/help/selling/selling-tools/product-research?id=4853
- https://www.ebay.com/help/selling/listings/creating-managing-listings/item-conditions-catagory?id=4765
