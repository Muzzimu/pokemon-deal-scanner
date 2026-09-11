# Walk-forward model validation (v0.11)

Last updated: 2026-09-11

v0.11 turns the scanner into a continuous walk-forward research system. Forecasts are frozen at time T, future evidence is attached only after the relevant horizon matures, and historical predictions are never rewritten with future information.

## Two clocks

The scanner keeps both:

1. **Daily rolling forecasts** — every successful daily run creates an immutable prediction snapshot for all cards present in `market_routes.csv`. These observations are the richer research panel.
2. **Weekly benchmark cohort** — the first successful scanner snapshot in each ISO week is flagged as the benchmark cohort. This reduces dependence between adjacent T+7 observations and is the preferred sample for clean weekly model reporting.

A missed Monday does not lose the week: the first successful snapshot in that ISO week becomes the benchmark.

## Horizons

### Fair-value / confidence calibration

The primary calibration horizons are:

- T+1
- T+3
- T+7
- T+14
- T+30

These use the forward window from T+1 through T+H. They are intended to test whether the model at T described the near-term market correctly.

### Holding diagnostics

The scanner also records:

- T+90
- T+180

These are **not** used to calibrate short-horizon fair value or PCS. At 3–6 months, genuine market moves, releases, tournament results, rotations, reprints and collector demand regimes increasingly dominate the original pricing error.

For 90/180d the target is therefore a terminal mark around T+H (default ±2 days), not the median of the whole preceding period. These horizons answer: “How did the card perform as a holding?” rather than “Was the price at T correct?”

## Immutable predictions

`model_predictions` stores the exact model state at T, including:

- EU fair value / EU PCS / EU LQS;
- US fair value / US PCS / US LQS;
- ECS and BOS;
- validated acquisition cost;
- selected exit route and modeled gross/net exit;
- optional Deal Score when available;
- the complete route row as JSON;
- model version.

The primary key includes snapshot date, card and model version. Re-running the same model on the same date does not overwrite the original prediction.

## Realised evidence

`model_realised_sales` stores exact observed sale records from normalized evidence such as `ebay_sold_evidence.csv` and the generic `data/reference/realised_sales.csv` input.

`model_market_observations` stores weaker or structural daily observations needed when exact sales are unavailable or for long-horizon diagnostics:

- Cardmarket `avg1` as a broad EU transaction-price **proxy**;
- TCGplayer Most Recent Sale as a US transaction **reference**;
- CardTrader current active floor as **bridge-persistence evidence**, never as a confirmed sale.

Confirmed realised sales outrank proxy observations. Evidence quality is exported with every outcome so confirmed and proxy validation can be analysed separately.

## Outcomes

`model_outcomes` attaches matured results without changing the original forecast. For EU/US fair value it records:

- realised median value;
- observation count;
- evidence quality/source;
- signed forecast error;
- absolute forecast error;
- return relative to the validated acquisition cost, when available.

For CardTrader routes, `BRIDGE_PERSISTENCE` is also tracked. This is deliberately conservative: the CardTrader active floor must persist near the modeled exit and the US reference must also support it. This is a bridge-market diagnostic, not proof that a CardTrader sale executed.

## Calibration outputs

The daily run writes:

- `output/model_predictions.csv`
- `output/model_outcomes.csv`
- `output/model_calibration.csv`
- `output/model_validation_summary.json`
- `output/model_monthly_report.csv`
- `output/model_monthly_report.json`

`model_calibration.csv` reports rolling and weekly-benchmark cohorts separately, including:

- sample size and unique cards;
- confirmed vs proxy outcomes;
- median / mean absolute percentage error;
- mean bias;
- RMSE;
- percentage within ±5%, ±10% and ±20%;
- success rates;
- score-band calibration;
- Spearman rank relationships between model score and future error/return when the relevant score exists.

## Statistical discipline

### Overlapping observations

Daily T+7 forecasts overlap heavily. They remain useful for research but are not treated as independent weekly experiments. The weekly benchmark cohort is therefore the cleaner evaluation set.

### Walk-forward only

Future model fitting should use chronological walk-forward splits, not random train/test splits. When a T+H target is used, training/test boundaries should be purged/embargoed by at least H days so forward windows cannot leak into each other.

### Recalibration threshold

The scanner does **not** automatically change score weights in v0.11. It only reports calibration. Default eligibility for considering a recalibration is:

- at least 200 matured outcome rows; and
- at least 50 distinct cards.

Any future change in weights should then be tested out-of-sample against later cohorts before replacing the production model.

### Long-horizon data

90/180d outcomes should be used for portfolio/holding research: drawdowns, long-run returns, regime dependence and collector/investment behaviour. They must not automatically reduce or increase PCS merely because a card genuinely moved after the original short-term forecast.

## Persistence

The model-validation tables live in the scanner SQLite database, which is restored/saved by the existing GitHub Actions state cache. Daily report artifacts are retained for 90 days. The database is the canonical rolling history; CSV/JSON outputs are human-readable exports.

For especially important manual sales, add exact rows to `data/reference/realised_sales.csv` so they remain reproducible evidence even if an external listing later disappears.
