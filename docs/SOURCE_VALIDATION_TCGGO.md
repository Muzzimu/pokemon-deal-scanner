# TCGGO / Pokemon-API graded eBay sold validation

Validation date: 2026-09-11

## Decision

Do **not** use TCGGO/Pokemon-API eBay graded medians as a production fair-value input, BUY trigger, DQS input, BOS input, or independent market vote at this stage.

Research role: `EBAY_GRADED_SOLD_PROXY`.

Potential future uses: manual graded validation, grading-EV research, graded liquidity/sold-count context, and Monte Carlo research after freshness and identity controls improve.

## Tests performed

### 1. Exact-card freshness / coverage

Ten liquid modern cards were checked at exact set + collector-number level. Latest sold row currently associated with each TCGGO card page:

| Card | Latest associated row | Age on 2026-09-11 |
|---|---|---:|
| Gengar VMAX FST 271 | 2026-07-19 | 54d |
| Rayquaza VMAX EVS 218 | 2026-08-22 | 20d |
| Dragonite V EVS 192 | 2026-07-19 | 54d |
| Pikachu VMAX VIV 188 | 2026-07-19 | 54d |
| Lugia V SIT 186 | 2026-07-23 | 50d |
| Giratina VSTAR CRZ GG69 | 2026-07-22 | 51d |
| Charizard ex MEW 199 | 2026-07-18 | 55d |
| Umbreon VMAX EVS 215 | 2026-07-23 | 50d |
| Magikarp PAL 203 | 2026-07-18 | 55d |
| Aerodactyl V LOR 180 | 2026-07-21 | 52d |

Mean age: 49.5 days. Nine of ten are older than 30 days.

The global TCGGO `Latest eBay Sold` feed is current to roughly 1–2 days, so this is not a total feed outage. It is a card-level association/coverage problem. Independent PriceCharting evidence shows exact Gengar VMAX FST 271 PSA10 eBay sales through 2026-09-09 while the TCGGO card page remains associated only through July.

### 2. Current-price control

Initial 10-card PSA10 controls showed TCGGO medians typically below independently visible recent PriceCharting/eBay records. Freshness explains a substantial portion of the gap in rising markets; do not fit a universal adjustment factor.

Gengar example:

- TCGGO PSA10 median: $2,044
- five latest exact PSA10 PriceCharting/eBay records used in the control: $2,500, $2,600, $2,500, $2,100, $2,125
- latest-five median: $2,500
- TCGGO difference: -18.2%

A stable card such as Pikachu VMAX VIV 188 can remain close despite stale observations, showing why freshness must be explicit rather than inferred from price agreement.

### 3. Benchmark methodology / shipping

PriceCharting states that it builds prices from actual sold data, uses recency/outlier controls, classifies grades from listing title/description, and **does not include shipping costs** in displayed prices.

Therefore shipping cannot explain the TCGGO-vs-PriceCharting gap observed in the initial control.

### 4. Median arithmetic and sample size

TCGGO API examples commonly expose `sample_size` values no higher than 5 for a grade median.

Transparent low-sample control:

- Faba LOT 208 PSA10 sales: $49.17 and $61.67
- TCGGO median: $55.42
- exact arithmetic midpoint: $55.42

The median calculation itself is sensible on a transparent sample.

Recommended confidence ceiling if later ingested:

- sample 1–2: LOW / diagnostic only
- sample 3–4: MEDIUM-LOW
- sample 5: MEDIUM maximum

### 5. Outlier robustness

Pokémon Fan Club POP4 9 PSA9 shows a roughly $256 median and ~$350 average while a $1,408 sale is visible in the history. The median is more robust to this thin-market outlier than the mean.

### 6. Exact-printing / reprint contamination

Critical failure: TCGGO's live recent-sold feed currently maps listings explicitly titled as **2021 Celebrations Classic Collection Umbreon Gold Star #17** to the **original POP Series 5 Umbreon Star #17** entity.

The original POP Series 5 page consequently shows an eBay PSA10 median around $275 with 180 supposed sales while its raw Cardmarket level is tens of thousands of euros. This is direct evidence that reprint transactions can contaminate the wrong vintage entity.

This is a hard blocker for trusting the pre-aggregated card median.

PriceCharting also exhibits occasional title/collector-number noise, so exact-print filtering is mandatory for any aggregator.

### 7. Regional provenance

TCGGO's roadmap still lists `eBay Sold Prices by Region (Europe / US / UK)` as planned. Current graded sold observations therefore must not be treated as a clean US series or clean EU series.

## Production rules if revisited

Required fields / controls:

- exact set and collector number;
- explicit variant/reprint guard;
- grader and numeric grade;
- sample size;
- latest accepted sale date;
- raw listing title where possible;
- listing/item identifier for de-duplication;
- regional provenance when available;
- rejected-sale audit trail and rejection reason.

Freshness policy:

- <=7 days: eligible only as corroborative graded-sold evidence;
- 8–30 days: stale warning and strong downweight;
- >30 days: diagnostic only, zero effect on current fair value / DQS / BOS / BUY.

Do not double-count the same eBay-derived information as independent evidence when PriceCharting or another aggregator represents overlapping transactions.

## Revisit criteria

Re-test when one or more of these becomes true:

1. exact card pages routinely surface sold rows no older than 7 days;
2. Europe / US / UK sold-price provenance is released;
3. the sold-offers endpoint exposes enough raw metadata for our own exact-print classifier;
4. TCGGO announces sold-data mapping improvements;
5. repeated >=20-card controls show acceptable identity accuracy and price error against independently visible current sold records.

See GitHub issues #2 and #3 for the revalidation and raw sold-offers research tasks.