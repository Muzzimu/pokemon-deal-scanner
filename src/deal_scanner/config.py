from __future__ import annotations

from pathlib import Path
import yaml


def load_config(path: str | Path) -> dict:
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if not isinstance(cfg, dict):
        raise ValueError(f"Invalid config: {path}")
    cfg["_root"] = str(path.resolve().parent)
    return cfg


def resolve_path(cfg: dict, value: str) -> Path:
    p = Path(value)
    if p.is_absolute():
        return p
    return Path(cfg["_root"]) / p
