# Experience Store Design — SQL/Statistics First

Status: design specification for the post-v0.12 research layer.

## Goal

Turn the scanner's existing immutable predictions and matured outcomes into an empirical memory system without introducing a vector database or LLM dependency.

The experience layer should answer questions such as:

> For cards that looked similar at decision time, what happened next?

Examples:

- Cards with similar PCS/LQS/ECS/BOS and price band: how often was T+7 fair value accurate?
- Similar bridge opportunities: how often did the CT premium persist at T+30?
- Similar low-liquidity cards: how often was an apparent discount still profitable after time-to-sale and execution friction?
- Similar model mistakes: what conditions were repeatedly associated with large forecast error?

The experience layer is **not** a new fair-value engine. It is a derived evidence/calibration layer built on the walk-forward dataset.

## Non-goals for phase 1

Do not add:

- FAISS, ChromaDB, Pinecone, or any vector store;
- embeddings;
- LLM summarisation or autonomous decisions;
- automatic model reweighting;
- retroactive rewriting of historical predictions;
- future information in similarity features.

All phase-1 retrieval must be reproducible with SQLite/Python statistics.

## Existing canonical tables

The current model-validation layer already provides the required source records:

### `model_predictions`
Immutable card × snapshot-date × model-version state, including:

- EU/US fair values;
- EU/US confidence/liquidity scores;
- ECS;
- BOS;
- validated buy and modeled exit;
- route signal;
- deal score;
- `features_json` containing decision-time features.

### `model_outcomes`
Matured horizon outcomes for T+1/T+3/T+7/T+14/T+30/T+90/T+180, including:

- realised value;
- evidence quality/source;
- forecast error;
- absolute error;
- entry return;
- success flag;
- observation count.

### `model_realised_sales`
Confirmed/manual realised-sale evidence where available.

These remain the source of truth. Phase 1 should avoid copying them into another mutable table unless performance later requires materialisation.

## Phase-1 architecture

Use a query/view layer called the **experience store**.

```text
model_predictions  ─┐
                    ├─> matured_experiences view/query ─> cohort statistics
model_outcomes     ─┘                                  └> nearest comparable cases
```

The important principle is that an experience exists only when its outcome was knowable at the as-of date.

## Leakage rule

For a candidate evaluated at date `D`, a historical experience may be used only if:

```text
experience.window_end < D
```

and its required outcome was already computed/available.

Never compare a 2026-09-01 candidate to a T+30 outcome whose window ended after 2026-09-01, even if the database contains that result today.

When backtesting an experience-based decision rule, use the candidate's historical as-of date, not today's full database.

## Recommended logical view

One row per prediction × matured horizon × target scope.

```sql
CREATE VIEW matured_experiences AS
SELECT
    p.snapshot_date,
    p.id_product,
    p.model_version,
    p.is_weekly_benchmark,
    p.benchmark_week,

    p.eu_fair_value_eur,
    p.eu_price_confidence_score,
    p.eu_liquidity_score,
    p.us_fair_value_eur,
    p.us_price_confidence_score,
    p.us_liquidity_score,
    p.exit_confidence_score,
    p.bridge_opportunity_score,
    p.best_validated_buy_eur,
    p.best_sell_channel,
    p.best_sell_gross_eur,
    p.best_sell_net_eur,
    p.route_signal,
    p.deal_score,
    p.features_json,

    o.horizon_days,
    o.horizon_class,
    o.target_scope,
    o.window_start,
    o.window_end,
    o.forecast_value_eur,
    o.realised_value_eur,
    o.observation_count,
    o.evidence_quality,
    o.outcome_source,
    o.error_pct,
    o.abs_error_pct,
    o.entry_return_pct,
    o.success_flag,
    o.computed_at
FROM model_predictions p
JOIN model_outcomes o
  ON o.snapshot_date = p.snapshot_date
 AND o.id_product = p.id_product
 AND o.model_version = p.model_version
WHERE o.realised_value_eur IS NOT NULL;
```

The exact production implementation may use a Python query rather than a persistent SQLite view; the semantics should remain the same.

## Decision-time feature set

Phase 1 similarity should use only variables frozen at prediction time.

Core numeric features:

- log price / price band;
- EU PCS;
- EU LQS;
- US PCS;
- US LQS;
- ECS;
- BOS;
- Deal Score;
- EU dispersion;
- US dispersion;
- EU market count;
- US market count;
- CT premium vs EU;
- CT premium vs US;
- validated discount to EU executable value;
- modeled net spread / ROI;
- recent price momentum if it was already present in `features_json` at prediction time.

Categorical filters/tags when available:

- exact target scope (EU/US/bridge);
- route signal;
- price band;
- set / era;
- rarity/product class;
- character/evolution family;
- new-product age bucket;
- language/condition class;
- source-quality regime.

Do not retroactively derive a feature from future data and attach it to an old prediction.

## Comparable-case retrieval

Start with deterministic filtering plus normalized numeric distance.

### Step 1 — eligibility filters

For candidate `C` at as-of date `D`:

1. only matured experiences with `window_end < D`;
2. same `target_scope` and requested `horizon_days`;
3. exclude known mapping/data-quality failures;
4. optionally require same broad price band or product class;
5. optionally limit model versions when a structural model change makes older states incomparable.

### Step 2 — robust standardisation

For each numeric feature, calculate centre/scale from the eligible historical pool only.

Prefer robust statistics:

```text
z_i = (x_i - median_i) / max(IQR_i / 1.349, epsilon)
```

This is less sensitive to thin-market outliers than mean/standard deviation.

### Step 3 — weighted distance

Initial distance:

```text
d(C,E) = Σ w_i * |z_i(C) - z_i(E)|
```

Suggested first-pass weights:

- PCS/ECS/BOS/LQS group: high;
- price band / discount / expected ROI: high;
- dispersion and market counts: medium;
- categorical mismatch penalties: explicit;
- character/set identity: low initially to avoid overfitting before sample sizes are large.

Weights must remain fixed/configured during a validation period; do not tune them against the same outcomes used to report performance.

### Step 4 — neighbor set

Return a minimum/maximum neighbor set, for example:

```text
preferred k = 20
minimum usable k = 10
maximum k = 50
```

If fewer than the minimum comparable cases exist, output `INSUFFICIENT_EXPERIENCE` rather than manufacturing certainty.

## Statistics returned for a candidate

For the selected comparable cases, calculate:

- `experience_count`;
- `unique_cards`;
- median and mean `entry_return_pct`;
- P10 / P25 / P50 / P75 / P90 return;
- probability of positive return;
- probability of return >= target threshold (e.g. 10%, 20%);
- median `abs_error_pct`;
- percentage within ±5%, ±10%, ±20%;
- success rate;
- confirmed-vs-proxy outcome composition;
- median observation count;
- score-band distribution;
- horizon-specific results.

For bridge cases also report:

- persistence of CT premium at T+7/T+30;
- downside frequency when US support was weak;
- exit-success rate conditional on BOS band.

No statistic should be displayed without its sample size.

## Cohort tables

Before nearest-neighbor retrieval is mature, simple cohorts will be more stable and interpretable.

Recommended cohorts:

```text
horizon × target_scope × price_band × PCS_band
horizon × target_scope × LQS_band × ECS_band
horizon × target_scope × BOS_band
horizon × route_signal × price_band
```

Each cohort should return observations, unique cards, median return, median absolute error, success rate, and evidence-quality mix.

This should be the first implementation because it is easy to audit and difficult to overfit.

## Reflection / model-mistake cohorts

Create deterministic diagnostic tags for repeated failure modes, for example:

- `HIGH_PCS_LARGE_ERROR` — high confidence but >20% absolute error;
- `HIGH_BOS_PREMIUM_COLLAPSE` — strong BOS followed by negative bridge outcome;
- `LOW_LQS_NO_EXECUTION` — attractive nominal spread with no usable realised/executable outcome;
- `STALE_SOURCE_ERROR` — error coincided with stale evidence;
- `MAPPING_FAILURE` — later audit found exact-print/subtype problem;
- `NEW_PRODUCT_NOISE` — launch-age effect caused unstable value.

These tags are deterministic labels for later statistical analysis. They are not LLM-generated narratives in phase 1.

## Output contract

A future `experience_summary` for a candidate should look conceptually like:

```json
{
  "status": "OK",
  "as_of_date": "2026-12-01",
  "horizon_days": 30,
  "target_scope": "EU",
  "experience_count": 24,
  "unique_cards": 18,
  "median_return_pct": 8.4,
  "p10_return_pct": -7.2,
  "p90_return_pct": 21.6,
  "positive_return_probability": 0.71,
  "median_abs_error_pct": 9.8,
  "confirmed_outcome_share": 0.58,
  "neighbor_method": "robust_l1_v1"
}
```

This output is advisory evidence. It must not silently override the existing valuation or BUY gates.

## Maturity gates

Do not activate comparable-experience recommendations simply because the code exists.

Suggested phase gates:

### Gate A — cohort reporting

Can begin once there are at least:

- **200 matured T+7 observations**;
- **50 unique cards**.

This matches the current minimum threshold before considering model reweighting and gives enough data for broad cohorts.

### Gate B — nearest comparable retrieval

Prefer at least:

- **500 matured T+7 observations**;
- **100 unique cards**;
- at least 10 usable neighbors in the relevant scope/horizon after leakage-safe filtering.

T+30 retrieval should remain research-only until there are at least ~200 matured T+30 observations across >=50 unique cards.

These are starting governance thresholds, not claims of statistical sufficiency. Reassess after observing actual feature coverage and cohort sparsity.

## Validation plan

The experience layer itself must be walk-forward tested.

For each historical candidate date:

1. build its neighbor/cohort pool using only experiences that had matured before that date;
2. produce the experience summary;
3. compare the summary against the candidate's subsequently realised outcome;
4. measure whether the experience signal adds information beyond existing PCS/LQS/ECS/BOS/DQS.

Useful tests:

- Spearman correlation of experience median return vs future return;
- Brier score for predicted probability of positive return;
- calibration curve by probability bucket;
- incremental MAE/RMSE reduction when experience features are added to a later model;
- stability by price band, set age, liquidity band, and model version.

If it does not add out-of-sample information, keep it diagnostic rather than adding it to the Deal Score.

## Future phase — explicitly deferred

After sufficient data maturity and successful walk-forward validation, consider:

1. richer comparable-case retrieval;
2. cross-card/set/character memory;
3. cross-market lead/lag experience features;
4. an optional LLM critic for high-value or conflicting cases.

Any AI critic must receive structured evidence and remain unable to override hard identity, source-role, maturity, or BUY gates. Deterministic Python/SQL remains authoritative for execution and guardrails.
