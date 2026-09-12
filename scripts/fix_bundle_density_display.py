from pathlib import Path

app = Path("dashboard/app.py")
text = app.read_text(encoding="utf-8")
text = text.replace(
    '"Foil density": (foils / total) if total and foils is not None else None,',
    '"Foil density": (foils / total * 100.0) if total and foils is not None else None,',
    1,
)
text = text.replace(
    '"Foil density": as_float(row.get("foil_density")),',
    '"Foil density": (as_float(row.get("foil_density")) * 100.0) if as_float(row.get("foil_density")) is not None else None,',
    1,
)
app.write_text(text, encoding="utf-8")

test = Path("tests/test_bundle_market_dashboard.py")
body = test.read_text(encoding="utf-8")
if "test_bundle_density_is_displayed_as_percent_points" not in body:
    body += '''\n\ndef test_bundle_density_is_displayed_as_percent_points():\n    text = Path("dashboard/app.py").read_text(encoding="utf-8")\n    assert "foils / total * 100.0" in text\n    assert 'row.get("foil_density")) * 100.0' in text\n'''
    test.write_text(body, encoding="utf-8")
