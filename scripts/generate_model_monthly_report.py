from __future__ import annotations

import csv
import json
import math
import statistics
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"

FIELDS = [
    "prediction_month", "cohort", "target_scope", "horizon_days", "horizon_class",
    "observations", "unique_cards", "confirmed_observations", "proxy_observations",
    "median_abs_error_pct", "mean_abs_error_pct", "mean_bias_pct", "rmse_pct",
    "within_10_pct", "success_rate_pct",
]


def _float(v):
    try:
        if v in (None, ""):
            return None
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def _int(v, default=0):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def _read(path: Path):
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return [dict(r) for r in csv.DictReader(f)]


def _metrics(rows):
    errors = [_float(r.get("error_pct")) for r in rows]
    errors = [x for x in errors if x is not None]
    abs_errors = [abs(x) for x in errors]
    successes = [_int(r.get("success_flag"), -1) for r in rows]
    successes = [x for x in successes if x in {0, 1}]
    return {
        "observations": len(rows),
        "unique_cards": len({r.get("id_product") for r in rows}),
        "confirmed_observations": sum(1 for r in rows if r.get("evidence_quality") in {"CONFIRMED", "CONFIRMED_FX_FALLBACK"}),
        "proxy_observations": sum(1 for r in rows if r.get("evidence_quality") in {"PROXY", "TRANSACTION_REFERENCE", "ACTIVE_ASK"}),
        "median_abs_error_pct": "" if not abs_errors else round(statistics.median(abs_errors), 3),
        "mean_abs_error_pct": "" if not abs_errors else round(statistics.mean(abs_errors), 3),
        "mean_bias_pct": "" if not errors else round(statistics.mean(errors), 3),
        "rmse_pct": "" if not errors else round(math.sqrt(statistics.mean([x * x for x in errors])), 3),
        "within_10_pct": "" if not errors else round(100 * sum(abs(x) <= 10 for x in errors) / len(errors), 1),
        "success_rate_pct": "" if not successes else round(100 * sum(successes) / len(successes), 1),
    }


def main() -> int:
    rows = [r for r in _read(OUT / "model_outcomes.csv") if _float(r.get("realised_value_eur")) is not None]
    grouped = defaultdict(list)
    for r in rows:
        month = str(r.get("snapshot_date") or "")[:7]
        if not month:
            continue
        for cohort in ("ROLLING", "WEEKLY_BENCHMARK"):
            if cohort == "WEEKLY_BENCHMARK" and _int(r.get("is_weekly_benchmark")) != 1:
                continue
            key = (month, cohort, r.get("target_scope"), _int(r.get("horizon_days")), r.get("horizon_class"))
            grouped[key].append(r)

    output = []
    for (month, cohort, scope, horizon, hclass), sample in sorted(grouped.items()):
        output.append({
            "prediction_month": month,
            "cohort": cohort,
            "target_scope": scope,
            "horizon_days": horizon,
            "horizon_class": hclass,
            **_metrics(sample),
        })

    path = OUT / "model_monthly_report.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(output)

    latest_month = max((r["prediction_month"] for r in output), default=None)
    latest = [r for r in output if r["prediction_month"] == latest_month]
    (OUT / "model_monthly_report.json").write_text(json.dumps({
        "as_of": date.today().isoformat(),
        "latest_prediction_month": latest_month,
        "latest_rows": latest,
        "note": "90/180d holding rows are reported separately and are not used to recalibrate short-horizon fair-value confidence.",
    }, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
