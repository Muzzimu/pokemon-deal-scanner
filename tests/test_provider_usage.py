from pathlib import Path

from deal_scanner.provider_usage import append_provider_usage


def test_provider_usage_deduplicates_same_run(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("GITHUB_RUN_ID", "42")
    path = tmp_path / "usage.csv"
    append_provider_usage(path, provider="X", operation="one", requests=2, documented_credits=4, rows=1)
    append_provider_usage(path, provider="X", operation="one", requests=3, documented_credits=6, rows=2)
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert ",3,6," in lines[1]
