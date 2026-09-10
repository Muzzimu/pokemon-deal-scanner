# Academic research signals for Pokémon resale

Last updated: 2026-09-10

## Heck et al. (2026) — prospective eBay field study

Source: *Sales characteristics of Pokémon trading cards: A prospective one-year field study*, PLOS One 21(3), e0334289.

### What is useful for this project

Treat this paper as **research-prior / feature-selection evidence**, not as a current pricing source.

The study followed 300 privately owned Pokémon cards listed on eBay in Germany between 28 May 2024 and 27 May 2025; 220/300 (73.3%) sold. The sample is dominated by older Wizards-era cards, so the numerical effects should not be transplanted directly to modern Scarlet & Violet-era singles or kids bundles.

Useful signals:

- **Holofoil status is a strong liquidity/value signal in this sample.** Sold holofoils had a median sale price of €13.03 vs €1.85 for matte cards and median time-to-sale of 17 vs 78 days. In the multivariable Cox model, holofoils had HR 3.18 vs matte.
- **Uncommon cards can be liquid despite low value.** Median survival time was ~48 days vs ~110 days for Common cards; multivariable HR for Uncommon vs Common was 1.68. This suggests the scanner should distinguish *liquidity/velocity* from *absolute value/margin*.
- **Rarity contributes heavily to revenue concentration.** Rare cards were only 19.1% of sold cards but generated 58.8% of revenue; holofoils were 10.9% of sold cards but generated 44.7% of revenue.
- **Set/popularity effects matter**, but the specific Team Rocket / Gym Challenge coefficients are historical-set effects and should not be generalized to modern sets. In the multivariable model, Team Rocket HR was 1.98 and Gym Challenge HR 3.49 vs Base Set 2.
- **Local-language fit can affect liquidity.** German-language cards sold faster than non-German in the German-only market (multivariable HR 2.35). For this project, use this only as a general reminder that local-language demand matters; it is not direct evidence that English has a specific multiplier in Ireland.
- **AI price estimates work best as decision support, not autopricing.** The human seller overrode the AI-proposed price range for 34.8% of cards after checking current eBay competition. For cards where the AI range was adopted initially and the card sold, 87.2% sold within that range. This supports the project’s current human-validated pricing workflow rather than replacing market evidence with an AI estimate.
- **ABC / prioritization logic is relevant.** The study found a skewed revenue distribution and used ABC analysis; this supports prioritizing a smaller set of higher-value / higher-liquidity inventory for detailed tracking while keeping low-value bulk in coarse buckets.

### Important limits

Do **not** use the paper’s euro prices as present-day fair values or resale targets. Do **not** directly apply the reported holo, rarity or set hazard ratios as scanner multipliers.

The authors explicitly note limited generalizability because of the narrow convenience sample, uneven sets/languages/conditions, low number of high-value items, subjective condition grading, sparse categories, and the posted-price design. The study also analyzes revenue rather than profit because original acquisition costs were unknown, and shipping was excluded from the analysis.

The paper calls for future work on modern rarity categories and reverse holofoils, so its classic holofoil result is **not evidence that modern reverse holos should receive the same premium**.

### Practical scanner implication

Potential future feature design:

- keep **value score** and **liquidity score** separate;
- include card treatment / rarity / recognizability as candidate liquidity features;
- use live Cardmarket/CardTrader/eBay/Irish evidence for pricing and margin;
- use academic findings only as low-weight priors or feature-selection justification until validated on our own modern-market data.

### High-value next step

If the paper’s supplementary **S1 Dataset (XLSX)** can be obtained, import it as a separate research dataset and reproduce a simple survival / sale-probability benchmark. This would be useful as a pipeline test, but should remain isolated from production deal scoring until validated against modern cards and Irish/European data.
