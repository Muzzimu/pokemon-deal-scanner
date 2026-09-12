from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# --- Feature 1: provider usage telemetry + dashboard operations panel ---

provider_usage = '''from __future__ import annotations

import csv
import os
from datetime import datetime, timezone
from pathlib import Path

USAGE_FIELDS = [
    "observed_at_utc",
    "snapshot_date",
    "provider",
    "operation",
    "requests",
    "documented_credits",
    "status",
    "rows",
    "run_id",
    "notes",
]


def _clean(value) -> str:
    return "" if value is None else str(value)


def append_provider_usage(
    path: Path,
    *,
    provider: str,
    operation: str,
    requests: int = 0,
    documented_credits: int | float | None = None,
    status: str = "OK",
    rows: int | None = None,
    notes: str = "",
    observed_at_utc: str | None = None,
) -> dict:
    """Append one provider-usage observation without creating duplicate run rows.

    `documented_credits` is only populated when the provider documents the unit cost
    or account UI confirms it. Unknown credit conversion remains blank.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    now = observed_at_utc or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    snapshot_date = now[:10]
    run_id = os.environ.get("GITHUB_RUN_ID", "local")
    record = {
        "observed_at_utc": now,
        "snapshot_date": snapshot_date,
        "provider": provider,
        "operation": operation,
        "requests": int(requests or 0),
        "documented_credits": "" if documented_credits is None else documented_credits,
        "status": status,
        "rows": "" if rows is None else int(rows),
        "run_id": run_id,
        "notes": notes,
    }

    existing: list[dict] = []
    if path.exists():
        with path.open(newline="", encoding="utf-8") as fh:
            existing = [dict(row) for row in csv.DictReader(fh)]
    key = (run_id, provider, operation)
    existing = [
        row for row in existing
        if (str(row.get("run_id")), str(row.get("provider")), str(row.get("operation"))) != key
    ]
    existing.append({field: _clean(record.get(field)) for field in USAGE_FIELDS})
    existing.sort(key=lambda r: (r.get("observed_at_utc", ""), r.get("provider", ""), r.get("operation", "")))

    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=USAGE_FIELDS)
        writer.writeheader()
        writer.writerows(existing)
    return record
'''
(ROOT / "src/deal_scanner/provider_usage.py").write_text(provider_usage, encoding="utf-8")

usage_path = ROOT / "dashboard/data/provider_usage.csv"
if not usage_path.exists():
    usage_path.parent.mkdir(parents=True, exist_ok=True)
    usage_path.write_text(
        "observed_at_utc,snapshot_date,provider,operation,requests,documented_credits,status,rows,run_id,notes\n",
        encoding="utf-8",
    )

limits_path = ROOT / "data/reference/provider_limits.csv"
if not limits_path.exists():
    limits_path.write_text(
        "provider,monthly_credit_limit,unit,as_of,notes\n"
        "PARSE_CARDMARKET,300,credits,2026-09-12,Free plan account panel; simple live calls are approximately one credit\n"
        "FIRECRAWL,1000,credits,2026-09-12,Free-cycle allowance shown in account email; scanner automation does not currently consume this provider\n"
        "SCRAPEBADGER,,credits,2026-09-12,Track documented per-request credits; no monthly cap encoded without an account limit\n",
        encoding="utf-8",
    )

# Vinted collector
path = ROOT / "scripts/run_scrapebadger_vinted.py"
text = path.read_text(encoding="utf-8")
anchor = "from deal_scanner.db import connect\n"
if "provider_usage import append_provider_usage" not in text:
    text = text.replace(anchor, anchor + "from deal_scanner.provider_usage import append_provider_usage\n", 1)
if "USAGE_PATH = ROOT / \"dashboard\" / \"data\" / \"provider_usage.csv\"" not in text:
    text = text.replace('STATUS = ROOT / "output" / "scrapebadger_vinted_status.json"\n', 'STATUS = ROOT / "output" / "scrapebadger_vinted_status.json"\nUSAGE_PATH = ROOT / "dashboard" / "data" / "provider_usage.csv"\n', 1)
old = '''        print("ScrapeBadger Vinted pilot skipped: missing SCRAPEBADGER_API_KEY")\n        return 0\n'''
new = '''        append_provider_usage(\n            USAGE_PATH, provider="SCRAPEBADGER", operation="vinted_research", requests=0,\n            documented_credits=0, status="UNAVAILABLE", rows=0, notes="missing SCRAPEBADGER_API_KEY",\n        )\n        print("ScrapeBadger Vinted pilot skipped: missing SCRAPEBADGER_API_KEY")\n        return 0\n'''
if old in text and "operation=\"vinted_research\"" not in text:
    text = text.replace(old, new, 1)
old = '''    print(\n        f"ScrapeBadger Vinted pilot: status={status} search={search_requests} detail={detail_requests} "\n        f"rows={len(all_rows)} states={counts}"\n    )\n'''
new = '''    append_provider_usage(\n        USAGE_PATH,\n        provider="SCRAPEBADGER",\n        operation="vinted_research",\n        requests=search_requests + detail_requests,\n        documented_credits=estimated_credits,\n        status=status,\n        rows=len(all_rows),\n        notes=f"search={search_requests}; detail={detail_requests}",\n    )\n    print(\n        f"ScrapeBadger Vinted pilot: status={status} search={search_requests} detail={detail_requests} "\n        f"rows={len(all_rows)} states={counts}"\n    )\n'''
if old in text and "notes=f\"search={search_requests}; detail={detail_requests}\"" not in text:
    text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8")

# eBay completed collector
path = ROOT / "scripts/run_scrapebadger_ebay_completed.py"
text = path.read_text(encoding="utf-8")
anchor = "from deal_scanner.db import connect\n"
if "provider_usage import append_provider_usage" not in text:
    text = text.replace(anchor, anchor + "from deal_scanner.provider_usage import append_provider_usage\n", 1)
if "USAGE_PATH = ROOT / \"dashboard\" / \"data\" / \"provider_usage.csv\"" not in text:
    text = text.replace('STATUS = ROOT / "output" / "scrapebadger_ebay_status.json"\n', 'STATUS = ROOT / "output" / "scrapebadger_ebay_status.json"\nUSAGE_PATH = ROOT / "dashboard" / "data" / "provider_usage.csv"\n', 1)
old = '''        print("ScrapeBadger eBay completed pilot skipped: missing SCRAPEBADGER_API_KEY")\n        return 0\n'''
new = '''        append_provider_usage(\n            USAGE_PATH, provider="SCRAPEBADGER", operation="ebay_completed_research", requests=0,\n            documented_credits=0, status="UNAVAILABLE", rows=0, notes="missing SCRAPEBADGER_API_KEY",\n        )\n        print("ScrapeBadger eBay completed pilot skipped: missing SCRAPEBADGER_API_KEY")\n        return 0\n'''
if old in text and "operation=\"ebay_completed_research\"" not in text:
    text = text.replace(old, new, 1)
old = '''    print(\n        f"ScrapeBadger eBay completed pilot: status={status} requests={requests_made} "\n        f"rows={len(rows)} exact={sum(r['identity_status'] == 'EXACT_TITLE_MATCH' for r in rows)}"\n    )\n'''
new = '''    append_provider_usage(\n        USAGE_PATH,\n        provider="SCRAPEBADGER",\n        operation="ebay_completed_research",\n        requests=requests_made,\n        documented_credits=requests_made * 5,\n        status=status,\n        rows=len(rows),\n        notes=f"domains={','.join(DOMAINS)}; watch_cards={len(watches)}",\n    )\n    print(\n        f"ScrapeBadger eBay completed pilot: status={status} requests={requests_made} "\n        f"rows={len(rows)} exact={sum(r['identity_status'] == 'EXACT_TITLE_MATCH' for r in rows)}"\n    )\n'''
if old in text and "notes=f\"domains={','.join(DOMAINS)}" not in text:
    text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8")

# Owned-card Parse usage
path = ROOT / "scripts/refresh_owned_market.py"
text = path.read_text(encoding="utf-8")
anchor = "from deal_scanner.db import blueprint_product_map_for_expansion, expansion_ids_for_products\n"
if "provider_usage import append_provider_usage" not in text:
    text = text.replace(anchor, anchor + "from deal_scanner.provider_usage import append_provider_usage\n", 1)
if "USAGE_PATH = ROOT / \"dashboard\" / \"data\" / \"provider_usage.csv\"" not in text:
    text = text.replace('OUTPUT_PATH = ROOT / "dashboard" / "data" / "owned_market.json"\n', 'OUTPUT_PATH = ROOT / "dashboard" / "data" / "owned_market.json"\nUSAGE_PATH = ROOT / "dashboard" / "data" / "provider_usage.csv"\n', 1)
old = '''    cm = cm_market(cfg, owned)\n\n    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()\n'''
new = '''    cm = cm_market(cfg, owned)\n    live_cfg = cfg.get("cardmarket_live", {})\n    parse_key = os.environ.get(str(live_cfg.get("api_key_env") or "PARSE_API_KEY"))\n    parse_requests = len(owned) if parse_key else 0\n\n    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()\n'''
if old in text and "parse_requests = len(owned)" not in text:
    text = text.replace(old, new, 1)
old = '''    print(f"Wrote {OUTPUT_PATH.relative_to(ROOT)} with {len(cards)} owned cards")\n    return 0\n'''
new = '''    append_provider_usage(\n        USAGE_PATH,\n        provider="PARSE_CARDMARKET",\n        operation="owned_card_live_asks",\n        requests=parse_requests,\n        documented_credits=parse_requests if parse_key else 0,\n        status="OK" if parse_key else "UNAVAILABLE",\n        rows=sum(1 for value in cm.values() if str(value.get("status") or "").upper() == "OK"),\n        notes="Account UI indicates approximately one credit per simple live call; one exact-product request per owned card.",\n        observed_at_utc=now,\n    )\n    print(f"Wrote {OUTPUT_PATH.relative_to(ROOT)} with {len(cards)} owned cards")\n    return 0\n'''
if old in text and "provider=\"PARSE_CARDMARKET\"" not in text:
    text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8")

# ScrapeBadger workflow: publish usage telemetry.
path = ROOT / ".github/workflows/scrapebadger_research.yml"
text = path.read_text(encoding="utf-8")
text = text.replace("permissions:\n  contents: read\n", "permissions:\n  contents: write\n", 1)
anchor = '''      - name: Verify research database\n'''
publish = '''      - name: Publish provider usage telemetry\n        shell: bash\n        run: |\n          set -euo pipefail\n          if [ -z "$(git status --porcelain -- dashboard/data/provider_usage.csv)" ]; then\n            echo "Provider usage telemetry unchanged"\n          else\n            git config user.name "pokemon-deal-scanner-dashboard"\n            git config user.email "actions@users.noreply.github.com"\n            git add dashboard/data/provider_usage.csv\n            git commit -m "Update provider usage telemetry [skip ci]"\n            git pull --rebase --autostash origin main\n            git push origin HEAD:main\n          fi\n\n'''
if publish not in text:
    text = text.replace(anchor, publish + anchor, 1)
path.write_text(text, encoding="utf-8")

# Owned market workflow: include provider usage in same commit.
path = ROOT / ".github/workflows/owned_market_refresh.yml"
text = path.read_text(encoding="utf-8")
text = text.replace(
    'if [ -z "$(git status --porcelain -- dashboard/data/owned_market.json)" ]; then',
    'if [ -z "$(git status --porcelain -- dashboard/data/owned_market.json dashboard/data/provider_usage.csv)" ]; then',
    1,
)
text = text.replace(
    'git add dashboard/data/owned_market.json\n',
    'git add dashboard/data/owned_market.json dashboard/data/provider_usage.csv\n',
    1,
)
path.write_text(text, encoding="utf-8")

# Dashboard provider-usage operations panel.
path = ROOT / "dashboard/app.py"
text = path.read_text(encoding="utf-8")
const_anchor = 'CARD_IMAGE_PATH = ROOT / "dashboard" / "data" / "card_images.json"\n'
if 'PROVIDER_USAGE_PATH' not in text:
    text = text.replace(
        const_anchor,
        const_anchor + 'PROVIDER_USAGE_PATH = ROOT / "dashboard" / "data" / "provider_usage.csv"\nPROVIDER_LIMITS_PATH = ROOT / "data" / "reference" / "provider_limits.csv"\n',
        1,
    )
helper_anchor = '''def load_card_images(path: Path) -> dict[str, dict]:\n'''
helpers = '''def provider_usage_summary(rows: list[dict], limits: list[dict]) -> list[dict]:\n    now = datetime.now().astimezone()\n    limit_map = {str(r.get("provider")): r for r in limits}\n    providers = sorted({str(r.get("provider")) for r in rows if r.get("provider")} | set(limit_map))\n    result = []\n    for provider in providers:\n        provider_rows = [r for r in rows if str(r.get("provider")) == provider]\n        def within_days(days: int) -> list[dict]:\n            cutoff = now.timestamp() - days * 86400\n            selected = []\n            for row in provider_rows:\n                stamp = clean_text(row.get("observed_at_utc"))\n                if not stamp:\n                    continue\n                try:\n                    parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))\n                except ValueError:\n                    continue\n                if parsed.timestamp() >= cutoff:\n                    selected.append(row)\n            return selected\n        month_rows = [r for r in provider_rows if str(r.get("snapshot_date") or "")[:7] == now.strftime("%Y-%m")]\n        today_rows = [r for r in provider_rows if str(r.get("snapshot_date") or "") == now.strftime("%Y-%m-%d")]\n        def total(selected: list[dict], field: str) -> float:\n            return sum(as_float(r.get(field)) or 0 for r in selected)\n        limit = as_float(limit_map.get(provider, {}).get("monthly_credit_limit"))\n        month_credits = total(month_rows, "documented_credits")\n        remaining = None if limit is None else max(0.0, limit - month_credits)\n        result.append({\n            "Provider": provider.replace("_", " ").title(),\n            "Today requests": int(total(today_rows, "requests")),\n            "7d requests": int(total(within_days(7), "requests")),\n            "30d requests": int(total(within_days(30), "requests")),\n            "Month credits": month_credits if provider_rows else None,\n            "Monthly limit": limit,\n            "Remaining": remaining if provider_rows else None,\n            "Latest status": clean_text(provider_rows[-1].get("status")) if provider_rows else "NOT INSTRUMENTED",\n        })\n    return result\n\n\n'''
if 'def provider_usage_summary(' not in text:
    text = text.replace(helper_anchor, helpers + helper_anchor, 1)
load_anchor = 'CARD_IMAGES = load_card_images(CARD_IMAGE_PATH)\n'
if 'provider_usage_rows = read_csv(PROVIDER_USAGE_PATH)' not in text:
    text = text.replace(
        load_anchor,
        load_anchor + 'provider_usage_rows = read_csv(PROVIDER_USAGE_PATH)\nprovider_limits = read_csv(PROVIDER_LIMITS_PATH)\n',
        1,
    )
health_anchor = '''with tab_health:\n    st.subheader("Experience-store maturity")\n'''
health_new = '''with tab_health:\n    st.subheader("Provider usage")\n    usage_summary = provider_usage_summary(provider_usage_rows, provider_limits)\n    if usage_summary:\n        st.dataframe(\n            usage_summary,\n            use_container_width=True,\n            hide_index=True,\n            column_config={\n                "Month credits": st.column_config.NumberColumn(format="%.0f"),\n                "Monthly limit": st.column_config.NumberColumn(format="%.0f"),\n                "Remaining": st.column_config.NumberColumn(format="%.0f"),\n            },\n        )\n        st.caption("Credits are shown only where the provider documents the unit cost or the account UI confirms it. Firecrawl is listed as a known account limit but scanner automation does not currently instrument its usage.")\n    else:\n        st.caption("No provider-usage observations have been recorded yet.")\n\n    st.subheader("Experience-store maturity")\n'''
if health_anchor in text and 'st.subheader("Provider usage")' not in text:
    text = text.replace(health_anchor, health_new, 1)
path.write_text(text, encoding="utf-8")

# Tests
provider_test = '''from pathlib import Path\n\nfrom deal_scanner.provider_usage import append_provider_usage\n\n\ndef test_provider_usage_deduplicates_same_run(monkeypatch, tmp_path: Path):\n    monkeypatch.setenv("GITHUB_RUN_ID", "42")\n    path = tmp_path / "usage.csv"\n    append_provider_usage(path, provider="X", operation="one", requests=2, documented_credits=4, rows=1)\n    append_provider_usage(path, provider="X", operation="one", requests=3, documented_credits=6, rows=2)\n    lines = path.read_text(encoding="utf-8").strip().splitlines()\n    assert len(lines) == 2\n    assert ",3,6," in lines[1]\n'''
(ROOT / "tests/test_provider_usage.py").write_text(provider_test, encoding="utf-8")

# Dashboard contract note.
doc_path = ROOT / "docs/DASHBOARD.md"
doc = doc_path.read_text(encoding="utf-8")
marker = "## "
note = '''\n## Provider usage telemetry\n\nProvider/API consumption is an operational diagnostic, not a market or BUY signal. Persist request counts and documented/provider-confirmed credit units by run, keep providers separate, and show daily/7d/30d/month usage under Model health. Never invent a credit conversion. Optimisation should remove duplicate/low-value calls before weakening identity/language/condition/finish validation.\n\n'''
if "## Provider usage telemetry" not in doc:
    idx = doc.find(marker)
    if idx >= 0:
        doc = doc[:idx] + note + doc[idx:]
    else:
        doc += note
    doc_path.write_text(doc, encoding="utf-8")

(ROOT / ".patch-message").write_text("Add provider usage telemetry and operations panel\n", encoding="utf-8")
