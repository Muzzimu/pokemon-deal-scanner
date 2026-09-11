# CardTrader ↔ Cardmarket mapping-confidence policy

Last updated: 2026-09-11

## Why this exists

CardTrader Blueprints can expose one or more Cardmarket `idProduct` values. A live CardTrader offer belongs to one Blueprint, so blindly attaching that offer to every mapped Cardmarket product can create a false cross-market price gap when the IDs represent different printings or variants.

The scanner therefore treats CardTrader's explicit `card_market_ids` field as the starting evidence, but it does not assume that a multi-ID mapping is safe for arbitrage.

## Mapping states

- `EXACT`: exactly one current CardTrader `card_market_ids` value exists in the current Cardmarket catalogue. This can participate in normal route scoring.
- `VERIFIED_MULTI`: CardTrader currently exposes multiple valid Cardmarket IDs, but a human-reviewed override selects one exact `idProduct`. This can participate in route scoring.
- `AMBIGUOUS_MULTI`: multiple current Cardmarket IDs exist and no verified override selects one. The CardTrader offer is retained for diagnostics but its `id_product` is set to NULL for the current snapshot, so it cannot influence Cardmarket/CardTrader floors, baskets or arbitrage.
- `UNMAPPED`: no current CardTrader Cardmarket ID resolves to the current Cardmarket catalogue.
- `MAPPING_CONFLICT`: a saved override disagrees with CardTrader's current mapping. The offer is blocked until reviewed again.

## Current-source rule

The audit uses the Blueprint's current `card_market_ids_json`, not merely every row historically present in `cardtrader_blueprint_map`. This protects against a stale mapping row surviving after CardTrader changes a Blueprint's external mapping.

## Human overrides

Verified resolutions live in:

`data/reference/cardtrader_mapping_overrides.csv`

Schema:

`blueprint_id,id_product,status,reason,checked_at`

Allowed verified statuses are `VERIFIED`, `VERIFIED_MULTI`, and `EXACT_OVERRIDE`. The selected Cardmarket `idProduct` must still be one of CardTrader's current valid mapped IDs; otherwise the row becomes `MAPPING_CONFLICT` and remains blocked.

Use an override only after checking the exact printing/variant. Collector number and normalized name are audit hints, not sufficient automatic proof by themselves.

## Output

Every daily run writes:

`output/cardtrader_mapping_audit.csv`

Problem mappings are sorted first. The audit includes current CardTrader IDs, valid Cardmarket IDs, collector-number matches, normalized-name matches, any override, the mapping state and the resolved product ID.

`scanner_status.json` also records mapping-state counts and how many current-snapshot offers were reassigned or blocked.

## Conservative principle

A missed opportunity from an ambiguous mapping is preferable to a false arbitrage signal on the wrong printing. Exact identity remains mandatory before the scanner can recommend a Cardmarket ↔ CardTrader trade.
