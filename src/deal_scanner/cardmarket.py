from __future__ import annotations

import json
import shutil
import tempfile
import time
from datetime import date
from pathlib import Path
from typing import Iterable

import requests


def _extract_rows(payload, preferred_keys: Iterable[str]) -> list[dict]:
    """Accept known Cardmarket root shapes and gracefully handle future wrappers."""
    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]
    if not isinstance(payload, dict):
        raise ValueError("JSON root must be an object or array")
    for key in preferred_keys:
        value = payload.get(key)
        if isinstance(value, list):
            return [r for r in value if isinstance(r, dict)]
    candidates = []
    for key, value in payload.items():
        if isinstance(value, list) and (not value or isinstance(value[0], dict)):
            candidates.append((len(value), key, value))
    if candidates:
        return max(candidates, key=lambda x: x[0])[2]
    raise ValueError(f"Could not locate row array. Root keys: {list(payload)[:20]}")


def read_catalog(path: str | Path) -> list[dict]:
    with Path(path).open("r", encoding="utf-8") as f:
        payload = json.load(f)
    return _extract_rows(payload, ("products", "product", "items", "data"))


def read_price_guide(path: str | Path) -> tuple[list[dict], str | None]:
    with Path(path).open("r", encoding="utf-8") as f:
        payload = json.load(f)
    created_at = payload.get("createdAt") if isinstance(payload, dict) else None
    rows = _extract_rows(payload, ("priceGuides", "priceGuide", "prices", "products", "items", "data"))
    return rows, created_at


def filter_price_rows_to_catalog(rows: Iterable[dict], valid_product_ids: Iterable[int]) -> tuple[list[dict], int]:
    """Drop stale/retired price-guide IDs that are absent from the current catalogue.

    Cardmarket's public price guide can temporarily retain products that no longer
    exist in the current singles catalogue.  Those rows are useful neither for
    the current scan nor for a foreign-keyed snapshot table, so filtering them is
    the stable core behavior rather than a CI-only monkeypatch.
    """
    valid = {int(x) for x in valid_product_ids}
    kept: list[dict] = []
    skipped = 0
    for row in rows:
        pid = row.get("idProduct", row.get("id_product", row.get("id")))
        try:
            pid_i = int(pid)
        except (TypeError, ValueError):
            skipped += 1
            continue
        if pid_i in valid:
            kept.append(row)
        else:
            skipped += 1
    return kept, skipped


def _next_archive_path(directory: Path, stem: str, snapshot_date: date) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    base = directory / f"{stem}_{snapshot_date.isoformat()}.json"
    if not base.exists():
        return base
    i = 1
    while True:
        candidate = directory / f"{stem}_{snapshot_date.isoformat()}_rerun-{i:02d}.json"
        if not candidate.exists():
            return candidate
        i += 1


def download(url: str, *, archive_dir: Path | None, stem: str, snapshot_date: date,
             retries: int = 3, timeout: int = 90) -> Path:
    """Download to immutable archive or a temporary file when archive_dir=None."""
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            with requests.get(
                url,
                stream=True,
                timeout=timeout,
                headers={"User-Agent": "pokemon-deal-scanner/0.4 (+personal research)"},
            ) as r:
                r.raise_for_status()
                if archive_dir is not None:
                    target = _next_archive_path(archive_dir, stem, snapshot_date)
                    temp_target = target.with_suffix(target.suffix + ".part")
                else:
                    fd, tmp = tempfile.mkstemp(prefix=f"{stem}_", suffix=".json")
                    Path(tmp).unlink(missing_ok=True)
                    target = Path(tmp)
                    temp_target = target
                with temp_target.open("wb") as f:
                    for chunk in r.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            f.write(chunk)
                if archive_dir is not None:
                    temp_target.replace(target)
                return target
        except Exception as exc:
            last_exc = exc
            if attempt < retries:
                time.sleep(2 ** (attempt - 1))
    raise RuntimeError(f"Failed downloading {url} after {retries} attempts: {last_exc}")


def latest_archive(directory: Path, stem: str) -> Path | None:
    if not directory.exists():
        return None
    files = sorted(directory.glob(f"{stem}_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def copy_fixture(source: Path, *, archive_dir: Path | None, stem: str, snapshot_date: date) -> Path:
    """Used by tests/demo to exercise the exact pipeline without internet."""
    if archive_dir is None:
        fd, tmp = tempfile.mkstemp(prefix=f"{stem}_", suffix=".json")
        Path(tmp).unlink(missing_ok=True)
        target = Path(tmp)
    else:
        target = _next_archive_path(archive_dir, stem, snapshot_date)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return target
