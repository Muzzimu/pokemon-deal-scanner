from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "dashboard" / "app.py"
OWNED = ROOT / "dashboard" / "pages" / "1_Owned_cards.py"
DOC = ROOT / "docs" / "DASHBOARD.md"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"patch target missing: {label}")
    return text.replace(old, new, 1)


# Main dashboard: exact image map + compact Cardmarket-like identity headers.
text = APP.read_text(encoding="utf-8")
text = replace_once(
    text,
    'OWNED_MARKET_PATH = ROOT / "dashboard" / "data" / "owned_market.json"\n',
    'OWNED_MARKET_PATH = ROOT / "dashboard" / "data" / "owned_market.json"\nCARD_IMAGE_PATH = ROOT / "dashboard" / "data" / "card_images.json"\n',
    "app image path",
)
text = replace_once(
    text,
    '''def as_float(value):\n''',
    '''def load_card_images(path: Path) -> dict[str, dict]:\n    payload = read_snapshot(path)\n    cards = payload.get("cards") if isinstance(payload, dict) else None\n    return {str(k): dict(v) for k, v in (cards or {}).items() if isinstance(v, dict)}\n\n\ndef card_image_url(row: dict, quality: str = "low") -> str | None:\n    pid = str(row.get("id_product") or "").strip()\n    record = CARD_IMAGES.get(pid) or {}\n    base = clean_text(record.get("image_base"))\n    return f"{base}/{quality}.webp" if base else None\n\n\ndef render_card_title(row: dict, heading: str = "####", image_width: int = 92, quality: str = "low") -> None:\n    image_url = card_image_url(row, quality=quality)\n    if image_url:\n        image_col, text_col = st.columns([1, 3.2], vertical_alignment="top")\n        with image_col:\n            st.image(image_url, width=image_width)\n        with text_col:\n            st.markdown(f"{heading} {short_name(row.get('name'))}")\n            st.caption(card_context(row))\n    else:\n        st.markdown(f"{heading} {short_name(row.get('name'))}")\n        st.caption(card_context(row))\n\n\ndef as_float(value):\n''',
    "app image helpers",
)
text = replace_once(
    text,
    '''    with st.container(border=True):\n        st.markdown(f"#### {short_name(row.get('name'))}")\n        st.caption(card_context(row))\n        st.markdown(f"**{signal_label(row.get('route_signal'))}**")\n''',
    '''    with st.container(border=True):\n        render_card_title(row)\n        st.markdown(f"**{signal_label(row.get('route_signal'))}**")\n''',
    "route image header",
)
text = replace_once(
    text,
    '''    with st.container(border=True):\n        st.markdown(f"#### {short_name(row.get('name'))}")\n        st.caption(card_context(row))\n        st.markdown("**🟣 OWNED REVIEW**")\n''',
    '''    with st.container(border=True):\n        render_card_title(row)\n        st.markdown("**🟣 OWNED REVIEW**")\n''',
    "tracked image header",
)
text = replace_once(
    text,
    '''snapshot = read_snapshot(SNAPSHOT_PATH)\nconn: sqlite3.Connection | None = None\n''',
    '''snapshot = read_snapshot(SNAPSHOT_PATH)\nCARD_IMAGES = load_card_images(CARD_IMAGE_PATH)\nconn: sqlite3.Connection | None = None\n''',
    "load image map",
)
text = replace_once(
    text,
    '''        st.subheader(short_name(card.get("name")))\n        st.caption(f"{card_context(card)} · {detail_stage(pid_key)}")\n''',
    '''        render_card_title(card, heading="##", image_width=190, quality="high")\n        st.caption(f"Stage: **{detail_stage(pid_key)}**")\n''',
    "detail image header",
)
APP.write_text(text, encoding="utf-8")


# Owned cards page: larger visual identity block before economics.
text = OWNED.read_text(encoding="utf-8")
text = replace_once(
    text,
    'OWNED_LEDGER_PATH = ROOT / "data" / "reference" / "owned_resale_cards.csv"\n',
    'OWNED_LEDGER_PATH = ROOT / "data" / "reference" / "owned_resale_cards.csv"\nCARD_IMAGE_PATH = ROOT / "dashboard" / "data" / "card_images.json"\n',
    "owned image path",
)
text = replace_once(
    text,
    '''def as_float(value):\n''',
    '''def card_image_map() -> dict[str, dict]:\n    payload = read_json(CARD_IMAGE_PATH)\n    cards = payload.get("cards") if isinstance(payload, dict) else None\n    return {str(k): dict(v) for k, v in (cards or {}).items() if isinstance(v, dict)}\n\n\ndef image_url(pid: str, quality: str = "low") -> str | None:\n    record = CARD_IMAGES.get(str(pid)) or {}\n    base = str(record.get("image_base") or "").strip()\n    return f"{base}/{quality}.webp" if base else None\n\n\ndef as_float(value):\n''',
    "owned image helpers",
)
text = replace_once(
    text,
    '''owned_market = read_json(OWNED_MARKET_PATH)\nowned_rows = list(owned_market.get("cards") or [])\n''',
    '''owned_market = read_json(OWNED_MARKET_PATH)\nCARD_IMAGES = card_image_map()\nowned_rows = list(owned_market.get("cards") or [])\n''',
    "owned load image map",
)
text = replace_once(
    text,
    '''            with st.container(border=True):\n                st.markdown(f"### {card.get('name') or 'Unknown card'}")\n                st.caption(\n                    f"{card.get('expansion_name') or 'Unknown set'} · {card.get('number') or 'No number'} · "\n                    f"{card.get('language') or '—'} · {card.get('condition') or '—'} · "\n                    f"Cardmarket ID {pid}"\n                )\n                st.markdown(f"**{signal_label(route.get('route_signal'))}**")\n\n''',
    '''            with st.container(border=True):\n                art = image_url(pid, "low")\n                if art:\n                    art_col, title_col = st.columns([1, 2.6], vertical_alignment="top")\n                    with art_col:\n                        st.image(art, width=125)\n                    with title_col:\n                        st.markdown(f"### {card.get('name') or 'Unknown card'}")\n                        st.caption(\n                            f"{card.get('expansion_name') or 'Unknown set'} · {card.get('number') or 'No number'} · "\n                            f"{card.get('language') or '—'} · {card.get('condition') or '—'} · Cardmarket ID {pid}"\n                        )\n                        st.markdown(f"**{signal_label(route.get('route_signal'))}**")\n                else:\n                    st.markdown(f"### {card.get('name') or 'Unknown card'}")\n                    st.caption(\n                        f"{card.get('expansion_name') or 'Unknown set'} · {card.get('number') or 'No number'} · "\n                        f"{card.get('language') or '—'} · {card.get('condition') or '—'} · Cardmarket ID {pid}"\n                    )\n                    st.markdown(f"**{signal_label(route.get('route_signal'))}**")\n\n''',
    "owned visual header",
)
OWNED.write_text(text, encoding="utf-8")


# Document the image-source contract so visuals never become fuzzy identity data.
text = DOC.read_text(encoding="utf-8")
text = replace_once(
    text,
    '7. **No fabricated precision.** If finish, language, condition, shipping, route or exit evidence is unresolved, display the missing state instead of filling it with a proxy.\n',
    '7. **No fabricated precision.** If finish, language, condition, shipping, route or exit evidence is unresolved, display the missing state instead of filling it with a proxy.\n8. **Artwork follows exact identity.** Small card images may be shown only from an explicit Cardmarket-product → TCGdex mapping. Never fuzzy-match artwork in the UI; if the mapping is missing, show no image.\n',
    "docs UX image rule",
)
text = replace_once(
    text,
    '`dashboard/data/owned_market.json` is refreshed independently from the main scanner so current owned-card ask checks cannot hold the core daily scan hostage. It contains public-safe per-card acquisition economics and comparable-market summaries only; raw seller identities and secrets are not exported.\n',
    '`dashboard/data/owned_market.json` is refreshed independently from the main scanner so current owned-card ask checks cannot hold the core daily scan hostage. It contains public-safe per-card acquisition economics and comparable-market summaries only; raw seller identities and secrets are not exported.\n\n`dashboard/data/card_images.json` stores exact Cardmarket-product → TCGdex artwork references. The repository stores the mapping, not Pokémon artwork binaries. Streamlit requests small WebP assets from TCGdex at display time; missing/unverified mappings degrade to text-only cards.\n',
    "docs image data source",
)
DOC.write_text(text, encoding="utf-8")

print("Dashboard card-image layout patch applied")
