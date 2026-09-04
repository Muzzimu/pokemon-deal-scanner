# v0.4 design inspiration

This project reviewed public repositories with adjacent Pokémon / TCG pricing and resale goals. The useful ideas were reimplemented for this scanner's Ireland-first sourcing workflow; no code was copied from repositories that do not publish a reuse licence.

## GabrieleBottai01/TCG-Archive

Useful concepts:

- source-labelled European pricing rather than one blended "market price"
- keeping eBay active asks separate from stronger sale evidence
- tracking listings over time and treating disappearance as a possible sale signal rather than a certainty
- using medians and explicit confidence/strength to contain noisy small samples
- maintaining permanent compact reference history while raw observations can expire

v0.4 adaptation:

- Ireland / continental EU / UK / Global are separate regions
- raw single-card matching is conservative and excludes slabs/lots/custom cards
- a listing must miss two successful scans before being called gone
- short-lived disappearance is labelled `INFERRED_QUICK_SALES`, never `CONFIRMED_SALES`

## northproxy/pokemon-cardmarket-bi

Useful concepts:

- daily Cardmarket history is valuable because the public guide is only a snapshot
- Cardmarket generic `low` is noisy and should not be a valuation or buy signal by itself
- new products need a stabilisation period before price-spike/growth signals are trusted
- explainable signal rules are preferable to opaque prediction

v0.4 adaptation:

- `top_flips.csv` suppresses products younger than 14 days when `date_added` is known
- the existing generic-low discovery guardrail remains unchanged

## Huang-Frederic/I.R.I.S

Useful concepts:

- exact product identity matters more than fuzzy name matching
- inventory, listing and sold states should be distinct
- long-lived price history needs bounded storage rather than indefinite raw growth

v0.4 adaptation:

- eBay watch rows are keyed to exact Cardmarket `id_product` and explicit required title tokens
- source evidence is stored as active asks / inferred quick-sales / confirmed sold evidence
- Cardmarket history is downsampled after 90 days and one year; raw CardTrader offers expire after 30 days

## TomasPereiraa/Pokemon-Card-Tracking

Useful concepts:

- language, condition and variant awareness belong in the identity/pricing workflow
- failed/ambiguous pricing should remain visible rather than silently substituted

v0.4 adaptation:

- Cardmarket sourcing still requires English + NM + Ireland deliverability
- eBay matching abstains on obvious non-English or graded variants
- missing eBay credentials produce an explicit disabled status rather than a fabricated fallback price

## What v0.4 deliberately does not copy

The scanner does not scrape Cardmarket or bypass anti-bot controls. Cardmarket sourcing evidence that is not present in the official public files remains manually observed evidence. The optional eBay module uses the official Browse API and runs only when the user supplies their own eBay application credentials.
