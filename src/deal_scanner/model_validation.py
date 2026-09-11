from __future__ import annotations

import csv
import hashlib
import json
import math
import statistics
from datetime import date, datetime, timedelta
from pathlib import Path


MODEL_SCHEMA = """
CREATE TABLE IF NOT EXISTS model_predictions (
    snapshot_date TEXT NOT NULL,
    id_product INTEGER NOT NULL,
    model_version TEXT NOT NULL,
    is_weekly_benchmark INTEGER NOT NULL DEFAULT 0,
    benchmark_week TEXT,
    eu_fair_value_eur REAL,
    eu_price_confidence_score INTEGER,
    eu_liquidity_score INTEGER,
    us_fair_value_eur REAL,
    us_price_confidence_score INTEGER,
    us_liquidity_score INTEGER,
    exit_confidence_score INTEGER,
    bridge_opportunity_score INTEGER,
    best_validated_buy_eur REAL,
    best_sell_channel TEXT,
    best_sell_gross_eur REAL,
    best_sell_net_eur REAL,
    route_signal TEXT,
    deal_score REAL,
    features_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (snapshot_date, id_product, model_version)
);

CREATE TABLE IF NOT EXISTS model_market_observations (
    observed_date TEXT NOT NULL,
    id_product INTEGER NOT NULL,
    scope TEXT NOT NULL,
    source TEXT NOT NULL,
    value_eur REAL NOT NULL,
    evidence_quality TEXT NOT NULL,
    sample_count INTEGER NOT NULL DEFAULT 1,
    meta_json TEXT,
    PRIMARY KEY (observed_date, id_product, scope, source)
);

CREATE TABLE IF NOT EXISTS model_realised_sales (
    sale_id TEXT PRIMARY KEY,
    id_product INTEGER NOT NULL,
    sale_date TEXT NOT NULL,
    market TEXT,
    region TEXT NOT NULL,
    price_value REAL NOT NULL,
    currency TEXT NOT NULL,
    price_eur REAL,
    condition TEXT,
    language TEXT,
    evidence_strength TEXT NOT NULL,
    source TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS model_outcomes (
    snapshot_date TEXT NOT NULL,
    id_product INTEGER NOT NULL,
    model_version TEXT NOT NULL,
    horizon_days INTEGER NOT NULL,
    horizon_class TEXT NOT NULL,
    target_scope TEXT NOT NULL,
    window_start TEXT NOT NULL,
    window_end TEXT NOT NULL,
    forecast_value_eur REAL,
    realised_value_eur REAL,
    observation_count INTEGER NOT NULL DEFAULT 0,
    evidence_quality TEXT,
    outcome_source TEXT,
    error_pct REAL,
    abs_error_pct REAL,
    entry_return_pct REAL,
    success_flag INTEGER,
    computed_at TEXT NOT NULL,
    notes TEXT,
    PRIMARY KEY (snapshot_date, id_product, model_version, horizon_days, target_scope)
);

CREATE INDEX IF NOT EXISTS idx_model_predictions_card_date
    ON model_predictions(id_product, snapshot_date);
CREATE INDEX IF NOT EXISTS idx_model_observations_card_date
    ON model_market_observations(id_product, observed_date, scope);
CREATE INDEX IF NOT EXISTS idx_model_sales_card_date
    ON model_realised_sales(id_product, sale_date, region);
CREATE INDEX IF NOT EXISTS idx_model_outcomes_horizon
    ON model_outcomes(horizon_days, target_scope, snapshot_date);
"""


PREDICTION_FIELDS = [
    "snapshot_date", "id_product", "model_version", "is_weekly_benchmark", "benchmark_week",
    "eu_fair_value_eur", "eu_price_confidence_score", "eu_liquidity_score",
    "us_fair_value_eur", "us_price_confidence_score", "us_liquidity_score",
    "exit_confidence_score", "bridge_opportunity_score", "best_validated_buy_eur",
    "best_sell_channel", "best_sell_gross_eur", "best_sell_net_eur", "route_signal", "deal_score",
]

OUTCOME_FIELDS = [
    "snapshot_date", "id_product", "model_version", "is_weekly_benchmark", "benchmark_week",
    "horizon_days", "horizon_class", "target_scope", "window_start", "window_end",
    "forecast_value_eur", "realised_value_eur", "observation_count", "evidence_quality",
    "outcome_source", "error_pct", "abs_error_pct", "entry_return_pct", "success_flag",
    "eu_price_confidence_score", "eu_liquidity_score", "us_price_confidence_score",
    "us_liquidity_score", "exit_confidence_score", "bridge_opportunity_score", "deal_score",
    "computed_at", "notes",
]

CALIBRATION_FIELDS = [
    "metric_family", "cohort", "target_scope", "horizon_days", "horizon_class", "score_band",
    "observations", "unique_cards", "confirmed_observations", "proxy_observations",
    "median_abs_error_pct", "mean_abs_error_pct", "mean_bias_pct", "rmse_pct",
    "within_5_pct", "within_10_pct", "within_20_pct", "success_rate_pct",
    "spearman_score_vs_abs_error", "spearman_score_vs_return",
]


def ensure_model_validation_schema(conn) -> None:
    conn.executescript(MODEL_SCHEMA)
    conn.commit()


def _float(value) -> float | None:
    try:
        if value in (None, ""):
            return None
        out = float(value)
        return out if math.isfinite(out) else None
    except (TypeError, ValueError):
        return None


def _int(value, default=0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return [dict(r) for r in csv.DictReader(f)]


def _write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _iso_week(day: date) -> str:
    y, w, _ = day.isocalendar()
    return f"{y}-W{w:02d}"


def _table_exists(conn, name: str) -> bool:
    row = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone()
    return bool(row)


def _weighted_median(values: list[tuple[float, int]]) -> float | None:
    clean = [(float(v), max(1, int(w))) for v, w in values if v is not None and math.isfinite(float(v))]
    if not clean:
        return None
    clean.sort(key=lambda x: x[0])
    total = sum(w for _, w in clean)
    halfway = total / 2.0
    running = 0
    for value, weight in clean:
        running += weight
        if running >= halfway:
            return round(value, 4)
    return round(clean[-1][0], 4)


def _median(values: list[float]) -> float | None:
    clean = [float(v) for v in values if v is not None and math.isfinite(float(v))]
    return None if not clean else float(statistics.median(clean))


def _mean(values: list[float]) -> float | None:
    clean = [float(v) for v in values if v is not None and math.isfinite(float(v))]
    return None if not clean else float(statistics.mean(clean))


def _rank(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i + 1
        while j < len(order) and values[order[j]] == values[order[i]]:
            j += 1
        avg_rank = (i + 1 + j) / 2.0
        for k in range(i, j):
            ranks[order[k]] = avg_rank
        i = j
    return ranks


def _spearman(xs: list[float], ys: list[float]) -> float | None:
    pairs = [(float(x), float(y)) for x, y in zip(xs, ys) if x is not None and y is not None]
    if len(pairs) < 3:
        return None
    x, y = zip(*pairs)
    rx, ry = _rank(list(x)), _rank(list(y))
    mx, my = statistics.mean(rx), statistics.mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    denx = math.sqrt(sum((a - mx) ** 2 for a in rx))
    deny = math.sqrt(sum((b - my) ** 2 for b in ry))
    if denx == 0 or deny == 0:
        return None
    return num / (denx * deny)


def _current_week_is_benchmark(conn, today: date) -> tuple[int, str]:
    week = _iso_week(today)
    row = conn.execute(
        "SELECT 1 FROM model_predictions WHERE benchmark_week=? AND is_weekly_benchmark=1 LIMIT 1",
        (week,),
    ).fetchone()
    return (0 if row else 1), week


def freeze_predictions(conn, cfg: dict, route_path: Path, today: date) -> int:
    rows = _read_csv(route_path)
    version = str(cfg.get("version") or "unknown")
    is_benchmark, benchmark_week = _current_week_is_benchmark(conn, today)
    now = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    inserted = 0
    for row in rows:
        pid = _int(row.get("id_product"))
        if pid <= 0:
            continue
        eu_fair = _float(row.get("eu_fair_value_eur")) or _float(row.get("fair_value_eur"))
        if eu_fair is None:
            continue
        values = (
            today.isoformat(), pid, version, is_benchmark, benchmark_week,
            eu_fair,
            _int(row.get("eu_price_confidence_score") or row.get("price_confidence_score")),
            _int(row.get("liquidity_score")),
            _float(row.get("us_fair_value_eur")), _int(row.get("us_price_confidence_score")),
            _int(row.get("us_liquidity_score")), _int(row.get("exit_confidence_score")),
            _int(row.get("bridge_opportunity_score")), _float(row.get("best_validated_buy_eur")),
            str(row.get("best_sell_channel") or ""), _float(row.get("best_sell_gross_eur")),
            _float(row.get("best_sell_net_eur")), str(row.get("route_signal") or ""),
            _float(row.get("deal_score")), json.dumps(row, sort_keys=True), now,
        )
        cur = conn.execute(
            """INSERT OR IGNORE INTO model_predictions(
              snapshot_date,id_product,model_version,is_weekly_benchmark,benchmark_week,
              eu_fair_value_eur,eu_price_confidence_score,eu_liquidity_score,
              us_fair_value_eur,us_price_confidence_score,us_liquidity_score,
              exit_confidence_score,bridge_opportunity_score,best_validated_buy_eur,
              best_sell_channel,best_sell_gross_eur,best_sell_net_eur,route_signal,deal_score,
              features_json,created_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            values,
        )
        inserted += max(0, cur.rowcount)
    conn.commit()
    return inserted


def _sale_id(row: dict, prefix: str) -> str:
    material = "|".join(str(row.get(k) or "") for k in (
        "id_product", "sale_date", "marketplace", "market", "region", "price_value", "currency", "source"
    ))
    return prefix + hashlib.sha1(material.encode("utf-8")).hexdigest()[:24]


def import_realised_sales(conn, cfg: dict, paths: list[Path]) -> int:
    inserted = 0
    usd_fx = float(cfg.get("fx", {}).get("fallback_usd_to_eur", 0.86))
    gbp_fx = float(cfg.get("fx", {}).get("fallback_gbp_to_eur", 1.16))
    for path in paths:
        for row in _read_csv(path):
            pid = _int(row.get("id_product"))
            sale_date = str(row.get("sale_date") or "")[:10]
            price = _float(row.get("price_value"))
            currency = str(row.get("currency") or "EUR").upper()
            if pid <= 0 or not sale_date or price is None or price <= 0:
                continue
            eur = _float(row.get("price_eur"))
            if eur is None:
                if currency == "EUR":
                    eur = price
                elif currency == "USD":
                    eur = round(price * usd_fx, 4)
                elif currency == "GBP":
                    eur = round(price * gbp_fx, 4)
            strength = str(row.get("evidence_strength") or "CONFIRMED").upper()
            sid = str(row.get("sale_id") or _sale_id(row, path.stem + "-"))
            cur = conn.execute(
                """INSERT OR IGNORE INTO model_realised_sales(
                  sale_id,id_product,sale_date,market,region,price_value,currency,price_eur,
                  condition,language,evidence_strength,source,notes
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    sid, pid, sale_date, str(row.get("market") or row.get("marketplace") or ""),
                    str(row.get("region") or "").upper(), price, currency, eur,
                    str(row.get("condition") or ""), str(row.get("language") or ""), strength,
                    str(row.get("source") or path.stem), str(row.get("notes") or ""),
                ),
            )
            inserted += max(0, cur.rowcount)
    conn.commit()
    return inserted


def _tracked_ids(conn, today: date, max_horizon: int, terminal_half_width: int) -> set[int]:
    cutoff = (today - timedelta(days=max_horizon + terminal_half_width + 7)).isoformat()
    rows = conn.execute(
        "SELECT DISTINCT id_product FROM model_predictions WHERE snapshot_date>=?", (cutoff,)
    ).fetchall()
    return {int(r["id_product"]) for r in rows}


def _insert_observation(conn, day: date, pid: int, scope: str, source: str, value: float | None,
                        quality: str, sample_count: int = 1, meta: dict | None = None) -> None:
    if value is None or value <= 0:
        return
    conn.execute(
        """INSERT OR IGNORE INTO model_market_observations(
          observed_date,id_product,scope,source,value_eur,evidence_quality,sample_count,meta_json
        ) VALUES(?,?,?,?,?,?,?,?)""",
        (day.isoformat(), pid, scope, source, float(value), quality, max(1, int(sample_count)), json.dumps(meta or {}, sort_keys=True)),
    )


def capture_market_observations(conn, cfg: dict, tcgplayer_reference_path: Path, today: date) -> int:
    vcfg = cfg.get("model_validation", {})
    horizons = [int(x) for x in (vcfg.get("calibration_horizons_days") or [1, 3, 7, 14, 30])]
    hold = [int(x) for x in (vcfg.get("holding_horizons_days") or [90, 180])]
    half = int(vcfg.get("terminal_window_half_width_days", 2))
    tracked = _tracked_ids(conn, today, max(horizons + hold), half)
    if not tracked:
        return 0
    before = conn.total_changes
    day_s = today.isoformat()
    placeholders = ",".join("?" for _ in tracked)

    # Cardmarket avg1 is a broad transaction-price proxy, not EN/NM-specific realised sales.
    if bool(vcfg.get("use_cardmarket_avg1_proxy", True)):
        rows = conn.execute(
            f"SELECT id_product,avg1 FROM price_snapshots WHERE snapshot_date=? AND id_product IN ({placeholders})",
            (day_s, *sorted(tracked)),
        ).fetchall()
        for r in rows:
            _insert_observation(conn, today, int(r["id_product"]), "EU", "CARDMARKET_AVG1_PROXY",
                                _float(r["avg1"]), "PROXY", 1)

    # Confirmed regional eBay medians are stronger than the Cardmarket proxy.
    if _table_exists(conn, "ebay_reference_history"):
        rows = conn.execute(
            f"""SELECT id_product,region,currency,confirmed_sale_median,confirmed_sales
                FROM ebay_reference_history
                WHERE snapshot_date=? AND id_product IN ({placeholders}) AND confirmed_sales>0""",
            (day_s, *sorted(tracked)),
        ).fetchall()
        usd_fx = float(cfg.get("fx", {}).get("fallback_usd_to_eur", 0.86))
        for r in rows:
            value = _float(r["confirmed_sale_median"])
            if value is None:
                continue
            region, currency = str(r["region"] or "").upper(), str(r["currency"] or "").upper()
            if region in {"IRELAND", "EU"} and currency == "EUR":
                _insert_observation(conn, today, int(r["id_product"]), "EU", "EBAY_CONFIRMED_SALES",
                                    value, "CONFIRMED", _int(r["confirmed_sales"], 1), {"region": region})
            elif region == "GLOBAL" and currency == "USD":
                _insert_observation(conn, today, int(r["id_product"]), "US", "EBAY_GLOBAL_CONFIRMED_SALES",
                                    value * usd_fx, "CONFIRMED_FX_FALLBACK", _int(r["confirmed_sales"], 1), {"region": region})

    # TCGplayer recent sale is a transaction reference. It can repeat on successive days,
    # so it is not interpreted as one new sale per daily observation.
    fallback_fx = float(cfg.get("fx", {}).get("fallback_usd_to_eur", 0.86))
    for row in _read_csv(tcgplayer_reference_path):
        pid = _int(row.get("id_product"))
        if pid not in tracked:
            continue
        checked = str(row.get("checked_at") or "")[:10]
        if checked and checked != day_s:
            continue
        recent = _float(row.get("most_recent_sale_eur"))
        if recent is None:
            usd = _float(row.get("most_recent_sale_usd"))
            fx = _float(row.get("fx_usd_to_eur")) or fallback_fx
            recent = None if usd is None else usd * fx
        _insert_observation(conn, today, pid, "US", "TCGPLAYER_RECENT_SALE_REFERENCE",
                            recent, "TRANSACTION_REFERENCE", 1)

    # CardTrader active floors are bridge persistence evidence only, never realised sales.
    ct_date_row = conn.execute("SELECT MAX(snapshot_date) AS d FROM cardtrader_offer_snapshots").fetchone()
    ct_day = str(ct_date_row["d"] or "") if ct_date_row else ""
    if ct_day == day_s:
        rows = conn.execute(
            f"""SELECT id_product,MIN(price_eur) AS floor_eur,COUNT(DISTINCT seller_id) AS sellers,SUM(quantity) AS units
                FROM cardtrader_offer_snapshots
                WHERE snapshot_date=? AND id_product IN ({placeholders})
                  AND language='en' AND lower(condition) IN ('near mint','near_mint','nm')
                  AND graded=0 AND on_vacation=0
                GROUP BY id_product""",
            (day_s, *sorted(tracked)),
        ).fetchall()
        for r in rows:
            _insert_observation(conn, today, int(r["id_product"]), "BRIDGE", "CARDTRADER_ACTIVE_FLOOR",
                                _float(r["floor_eur"]), "ACTIVE_ASK", _int(r["sellers"], 1),
                                {"units": _int(r["units"]), "sellers": _int(r["sellers"])})

    conn.commit()
    return conn.total_changes - before


def _window_for(pred_day: date, horizon: int, horizon_class: str, half_width: int) -> tuple[date, date, date]:
    if horizon_class == "HOLDING":
        center = pred_day + timedelta(days=horizon)
        start = center - timedelta(days=half_width)
        end = center + timedelta(days=half_width)
        mature = end
        return start, end, mature
    start = pred_day + timedelta(days=1)
    end = pred_day + timedelta(days=horizon)
    return start, end, end


def _outcome_values(conn, pid: int, scope: str, start: date, end: date, cfg: dict) -> tuple[float | None, int, str, str]:
    start_s, end_s = start.isoformat(), end.isoformat()
    if scope == "EU_FAIR_VALUE":
        regions = ("IRELAND", "EU")
    elif scope == "US_FAIR_VALUE":
        regions = ("US", "GLOBAL")
    else:
        regions = ()

    if regions:
        placeholders = ",".join("?" for _ in regions)
        rows = conn.execute(
            f"""SELECT price_eur,source,evidence_strength FROM model_realised_sales
                WHERE id_product=? AND sale_date BETWEEN ? AND ? AND region IN ({placeholders})
                  AND price_eur IS NOT NULL""",
            (pid, start_s, end_s, *regions),
        ).fetchall()
        values = [_float(r["price_eur"]) for r in rows]
        values = [v for v in values if v is not None and v > 0]
        if values:
            return round(float(statistics.median(values)), 4), len(values), "CONFIRMED", "REALISED_SALES"

    obs_scope = "EU" if scope == "EU_FAIR_VALUE" else ("US" if scope == "US_FAIR_VALUE" else "BRIDGE")
    obs = conn.execute(
        """SELECT value_eur,evidence_quality,sample_count,source
           FROM model_market_observations
           WHERE id_product=? AND scope=? AND observed_date BETWEEN ? AND ?""",
        (pid, obs_scope, start_s, end_s),
    ).fetchall()
    if not obs:
        return None, 0, "NONE", ""

    quality_rank = {"CONFIRMED": 0, "CONFIRMED_FX_FALLBACK": 1, "TRANSACTION_REFERENCE": 2, "PROXY": 3, "ACTIVE_ASK": 4}
    best_rank = min(quality_rank.get(str(r["evidence_quality"]), 9) for r in obs)
    chosen = [r for r in obs if quality_rank.get(str(r["evidence_quality"]), 9) == best_rank]
    weighted = [(_float(r["value_eur"]), _int(r["sample_count"], 1)) for r in chosen]
    weighted = [(v, w) for v, w in weighted if v is not None and v > 0]
    if not weighted:
        return None, 0, "NONE", ""
    value = _weighted_median(weighted)
    quality = str(chosen[0]["evidence_quality"])
    sources = "+".join(sorted({str(r["source"]) for r in chosen}))
    return value, sum(w for _, w in weighted), quality, sources


def _insert_outcome(conn, pred, horizon: int, horizon_class: str, scope: str,
                    start: date, end: date, realised: float | None, count: int,
                    quality: str, source: str, today: date, success_flag: int | None = None,
                    notes: str = "") -> int:
    if scope == "EU_FAIR_VALUE":
        forecast = _float(pred["eu_fair_value_eur"])
    elif scope == "US_FAIR_VALUE":
        forecast = _float(pred["us_fair_value_eur"])
    else:
        forecast = _float(pred["best_sell_gross_eur"])
    error = None if forecast in (None, 0) or realised is None else (realised / forecast - 1.0) * 100.0
    buy = _float(pred["best_validated_buy_eur"])
    entry_return = None if buy in (None, 0) or realised is None else (realised / buy - 1.0) * 100.0
    if success_flag is None and error is not None and scope in {"EU_FAIR_VALUE", "US_FAIR_VALUE"}:
        success_flag = int(abs(error) <= 10.0)
    cur = conn.execute(
        """INSERT OR IGNORE INTO model_outcomes(
          snapshot_date,id_product,model_version,horizon_days,horizon_class,target_scope,
          window_start,window_end,forecast_value_eur,realised_value_eur,observation_count,
          evidence_quality,outcome_source,error_pct,abs_error_pct,entry_return_pct,success_flag,
          computed_at,notes
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            pred["snapshot_date"], pred["id_product"], pred["model_version"], horizon, horizon_class, scope,
            start.isoformat(), end.isoformat(), forecast, realised, count, quality, source,
            None if error is None else round(error, 4), None if error is None else round(abs(error), 4),
            None if entry_return is None else round(entry_return, 4), success_flag,
            today.isoformat(), notes,
        ),
    )
    return max(0, cur.rowcount)


def mature_outcomes(conn, cfg: dict, today: date) -> int:
    vcfg = cfg.get("model_validation", {})
    cal = [int(x) for x in (vcfg.get("calibration_horizons_days") or [1, 3, 7, 14, 30])]
    hold = [int(x) for x in (vcfg.get("holding_horizons_days") or [90, 180])]
    half = int(vcfg.get("terminal_window_half_width_days", 2))
    inserted = 0
    preds = conn.execute("SELECT * FROM model_predictions ORDER BY snapshot_date,id_product").fetchall()
    for pred in preds:
        pred_day = date.fromisoformat(str(pred["snapshot_date"]))
        for horizon, hclass in [(h, "CALIBRATION") for h in cal] + [(h, "HOLDING") for h in hold]:
            start, end, mature = _window_for(pred_day, horizon, hclass, half)
            if today < mature:
                continue
            for scope in ("EU_FAIR_VALUE", "US_FAIR_VALUE"):
                if scope == "US_FAIR_VALUE" and _float(pred["us_fair_value_eur"]) is None:
                    continue
                realised, count, quality, source = _outcome_values(conn, int(pred["id_product"]), scope, start, end, cfg)
                inserted += _insert_outcome(conn, pred, horizon, hclass, scope, start, end, realised, count, quality, source, today)

            channel = str(pred["best_sell_channel"] or "")
            if channel.startswith("CARDTRADER") and _float(pred["best_sell_gross_eur"]):
                ct_value, ct_count, ct_quality, ct_source = _outcome_values(
                    conn, int(pred["id_product"]), "BRIDGE_PERSISTENCE", start, end, cfg
                )
                us_value, _, _, _ = _outcome_values(conn, int(pred["id_product"]), "US_FAIR_VALUE", start, end, cfg)
                forecast = _float(pred["best_sell_gross_eur"])
                success = None
                if forecast and ct_value is not None and us_value is not None:
                    success = int(ct_value >= 0.95 * forecast and us_value >= 0.90 * forecast)
                note = "Bridge success requires CT active floor >=95% of modeled exit and US realised/reference >=90%; active CT floor is persistence evidence, not a confirmed sale."
                inserted += _insert_outcome(conn, pred, horizon, hclass, "BRIDGE_PERSISTENCE",
                                            start, end, ct_value, ct_count, ct_quality, ct_source,
                                            today, success_flag=success, notes=note)
    conn.commit()
    return inserted


def _prediction_exports(conn) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT " + ",".join(PREDICTION_FIELDS) + " FROM model_predictions ORDER BY snapshot_date,id_product,model_version"
    ).fetchall()]


def _outcome_exports(conn) -> list[dict]:
    sql = """
    SELECT o.snapshot_date,o.id_product,o.model_version,p.is_weekly_benchmark,p.benchmark_week,
           o.horizon_days,o.horizon_class,o.target_scope,o.window_start,o.window_end,
           o.forecast_value_eur,o.realised_value_eur,o.observation_count,o.evidence_quality,
           o.outcome_source,o.error_pct,o.abs_error_pct,o.entry_return_pct,o.success_flag,
           p.eu_price_confidence_score,p.eu_liquidity_score,p.us_price_confidence_score,
           p.us_liquidity_score,p.exit_confidence_score,p.bridge_opportunity_score,p.deal_score,
           o.computed_at,o.notes
    FROM model_outcomes o
    JOIN model_predictions p USING(snapshot_date,id_product,model_version)
    ORDER BY o.snapshot_date,o.id_product,o.horizon_days,o.target_scope
    """
    return [dict(r) for r in conn.execute(sql).fetchall()]


def _band(value: float | None) -> str:
    if value is None:
        return "UNKNOWN"
    if value >= 90:
        return "90_100"
    if value >= 80:
        return "80_89"
    if value >= 70:
        return "70_79"
    if value >= 60:
        return "60_69"
    return "LT_60"


def _metrics(rows: list[dict], score_key: str | None = None) -> dict:
    errs = [_float(r.get("error_pct")) for r in rows]
    errs = [x for x in errs if x is not None]
    abs_errs = [abs(x) for x in errs]
    returns = [_float(r.get("entry_return_pct")) for r in rows]
    scores = [_float(r.get(score_key)) if score_key else None for r in rows]
    success = [_int(r.get("success_flag"), -1) for r in rows]
    success = [x for x in success if x in {0, 1}]
    return {
        "observations": len(rows),
        "unique_cards": len({str(r.get("id_product")) for r in rows}),
        "confirmed_observations": sum(1 for r in rows if str(r.get("evidence_quality")) in {"CONFIRMED", "CONFIRMED_FX_FALLBACK"}),
        "proxy_observations": sum(1 for r in rows if str(r.get("evidence_quality")) in {"PROXY", "TRANSACTION_REFERENCE", "ACTIVE_ASK"}),
        "median_abs_error_pct": None if not abs_errs else round(float(statistics.median(abs_errs)), 3),
        "mean_abs_error_pct": None if not abs_errs else round(float(statistics.mean(abs_errs)), 3),
        "mean_bias_pct": None if not errs else round(float(statistics.mean(errs)), 3),
        "rmse_pct": None if not errs else round(math.sqrt(statistics.mean([x * x for x in errs])), 3),
        "within_5_pct": None if not errs else round(100.0 * sum(abs(x) <= 5 for x in errs) / len(errs), 1),
        "within_10_pct": None if not errs else round(100.0 * sum(abs(x) <= 10 for x in errs) / len(errs), 1),
        "within_20_pct": None if not errs else round(100.0 * sum(abs(x) <= 20 for x in errs) / len(errs), 1),
        "success_rate_pct": None if not success else round(100.0 * sum(success) / len(success), 1),
        "spearman_score_vs_abs_error": None if not score_key else (_spearman(scores, [abs(_float(r.get("error_pct")) or 0.0) for r in rows])),
        "spearman_score_vs_return": None if not score_key else (_spearman(scores, returns)),
    }


def build_calibration_rows(outcomes: list[dict]) -> list[dict]:
    rows_out: list[dict] = []
    groups: dict[tuple, list[dict]] = {}
    for row in outcomes:
        if _float(row.get("realised_value_eur")) is None:
            continue
        for cohort in ("ROLLING", "WEEKLY_BENCHMARK"):
            if cohort == "WEEKLY_BENCHMARK" and _int(row.get("is_weekly_benchmark")) != 1:
                continue
            key = (cohort, row.get("target_scope"), _int(row.get("horizon_days")), row.get("horizon_class"))
            groups.setdefault(key, []).append(row)

    for (cohort, scope, horizon, hclass), rows in sorted(groups.items()):
        score_key = "eu_price_confidence_score" if scope == "EU_FAIR_VALUE" else (
            "us_price_confidence_score" if scope == "US_FAIR_VALUE" else "bridge_opportunity_score"
        )
        overall = _metrics(rows, score_key)
        rows_out.append({
            "metric_family": "FORECAST_ACCURACY" if scope != "BRIDGE_PERSISTENCE" else "BRIDGE_CALIBRATION",
            "cohort": cohort, "target_scope": scope, "horizon_days": horizon,
            "horizon_class": hclass, "score_band": "ALL", **overall,
        })
        for band in ("90_100", "80_89", "70_79", "60_69", "LT_60"):
            subset = [r for r in rows if _band(_float(r.get(score_key))) == band]
            if not subset:
                continue
            rows_out.append({
                "metric_family": "SCORE_BAND_CALIBRATION",
                "cohort": cohort, "target_scope": scope, "horizon_days": horizon,
                "horizon_class": hclass, "score_band": band, **_metrics(subset, score_key),
            })
    for row in rows_out:
        for k in ("spearman_score_vs_abs_error", "spearman_score_vs_return"):
            if row.get(k) is not None:
                row[k] = round(float(row[k]), 4)
    return rows_out


def _summary(cfg: dict, predictions: list[dict], outcomes: list[dict], calibration: list[dict], today: date) -> dict:
    vcfg = cfg.get("model_validation", {})
    weekly_7 = next((r for r in calibration if r["cohort"] == "WEEKLY_BENCHMARK" and r["target_scope"] == "EU_FAIR_VALUE" and r["horizon_days"] == 7 and r["score_band"] == "ALL"), None)
    rolling_7 = next((r for r in calibration if r["cohort"] == "ROLLING" and r["target_scope"] == "EU_FAIR_VALUE" and r["horizon_days"] == 7 and r["score_band"] == "ALL"), None)
    unique_cards = len({str(r.get("id_product")) for r in predictions})
    matured = [r for r in outcomes if _float(r.get("realised_value_eur")) is not None]
    min_n = int(vcfg.get("minimum_outcomes_before_recalibration", 200))
    min_cards = int(vcfg.get("minimum_unique_cards_before_recalibration", 50))
    eligible = len(matured) >= min_n and unique_cards >= min_cards
    return {
        "as_of": today.isoformat(),
        "model_version": str(cfg.get("version") or "unknown"),
        "prediction_rows": len(predictions),
        "unique_cards": unique_cards,
        "matured_outcome_rows": len(matured),
        "weekly_t7_eu": weekly_7,
        "rolling_t7_eu": rolling_7,
        "recalibration_eligible": eligible,
        "recalibration_policy": "REPORT_ONLY" if not bool(vcfg.get("auto_recalibrate", False)) else "AUTO_ENABLED",
        "minimum_outcomes_before_recalibration": min_n,
        "minimum_unique_cards_before_recalibration": min_cards,
        "calibration_horizons_days": vcfg.get("calibration_horizons_days") or [1, 3, 7, 14, 30],
        "holding_horizons_days": vcfg.get("holding_horizons_days") or [90, 180],
        "interpretation": "1-30d horizons calibrate fair-value/confidence models; 90/180d horizons are holding-performance diagnostics and must not automatically reweight short-horizon PCS.",
    }


def run_model_validation(
    conn,
    cfg: dict,
    market_routes_path: Path,
    tcgplayer_reference_path: Path,
    ebay_sold_path: Path,
    generic_realised_sales_path: Path,
    output_dir: Path,
    *,
    today: date | None = None,
) -> dict:
    today = today or date.today()
    vcfg = cfg.get("model_validation", {})
    if not bool(vcfg.get("enabled", True)):
        return {"enabled": False, "reason": "disabled in config"}

    ensure_model_validation_schema(conn)
    imported = import_realised_sales(conn, cfg, [ebay_sold_path, generic_realised_sales_path])
    predictions_added = freeze_predictions(conn, cfg, market_routes_path, today)
    observations_added = capture_market_observations(conn, cfg, tcgplayer_reference_path, today)
    outcomes_added = mature_outcomes(conn, cfg, today)

    predictions = _prediction_exports(conn)
    outcomes = _outcome_exports(conn)
    calibration = build_calibration_rows(outcomes)
    summary = _summary(cfg, predictions, outcomes, calibration, today)

    _write_csv(output_dir / "model_predictions.csv", predictions, PREDICTION_FIELDS)
    _write_csv(output_dir / "model_outcomes.csv", outcomes, OUTCOME_FIELDS)
    _write_csv(output_dir / "model_calibration.csv", calibration, CALIBRATION_FIELDS)
    (output_dir / "model_validation_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    return {
        "enabled": True,
        "predictions_added": predictions_added,
        "market_observations_added": observations_added,
        "realised_sales_added": imported,
        "outcomes_added": outcomes_added,
        "prediction_rows_total": len(predictions),
        "outcome_rows_total": len(outcomes),
        "recalibration_eligible": summary["recalibration_eligible"],
        "policy": summary["interpretation"],
    }
