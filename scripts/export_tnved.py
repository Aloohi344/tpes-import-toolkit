#!/usr/bin/env python3
"""Export all 10-digit leaf TNVED codes as compact JSON, with effective rates (footnotes applied) as of the database as_of date."""
from __future__ import annotations

import json
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOT = Path("/workspace/course-bot")
sys.path.insert(0, str(BOT))

from bot.tnved import (  # noqa: E402
    connect,
    default_db_path,
    effective_for,
    format_code,
    get_meta,
    _load_footnote,
    _row_to_printed,
)

CUR = {"EUR": "евро", "USD": "долларов США", "RUB": "руб."}
UNIT = {
    "kg": "1 кг",
    "1000kg": "1000 кг",
    "l": "1 л",
    "1000l": "1000 л",
    "cm3": "1 см³ объёма двигателя",
    "m2": "1 м²",
    "m3": "1 м³",
    "g": "1 г",
    "t": "1 т",
    "piece": "1 шт",
    "pair": "1 пару",
    "carat": "1 карат",
}


def dec(v) -> float | int:
    if v is None:
        return None
    f = float(v)
    if f == int(f) and abs(f) < 10**12:
        return int(f)
    return float(v)


def fmt_num(v: Decimal | None) -> str:
    if v is None:
        return ""
    s = format(v, "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s.replace(".", ",")


def format_rate(rate) -> str:
    av = fmt_num(rate.ad_valorem_pct)
    spec = ""
    if rate.specific_amount is not None:
        cur = CUR.get(rate.specific_currency or "", (rate.specific_currency or "").lower())
        unit = UNIT.get(rate.specific_unit or "", rate.specific_unit or "")
        if rate.alcohol_100pct:
            unit = "1 л 100% спирта"
        spec = f"{fmt_num(rate.specific_amount)} {cur} за {unit}".strip()
    kind = rate.kind
    if kind == "ad_valorem" and av:
        return f"{av}%"
    if kind == "combined_min" and av and spec:
        return f"{av}%, но не менее {spec}"
    if kind == "combined_plus" and av and spec:
        return f"{av}% плюс {spec}"
    if kind == "specific" and spec:
        return spec
    text = (rate.rate_text or "").replace("800С)", "").replace("С)", "").strip(" ,")
    text = " ".join(text.split())
    return text or "ставку уточните вручную"


def iso_to_ru(s: str | None) -> str | None:
    if not s:
        return None
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return f"{s[8:10]}.{s[5:7]}.{s[0:4]}"
    return s


def main() -> None:
    db = default_db_path()
    meta = get_meta(db)
    as_of = date.fromisoformat(meta.get("as_of") or date.today().isoformat())
    conn = connect(db, readonly=True)
    try:
        rows = conn.execute(
            "SELECT * FROM codes WHERE is_leaf = 1 AND digits = 10 ORDER BY code"
        ).fetchall()
        codes = []
        for row in rows:
            printed = _row_to_printed(row)
            fns = []
            for fid in printed.footnotes:
                fn = _load_footnote(conn, fid)
                if fn:
                    fns.append(fn)
            effective, applied, _warns = effective_for(printed, fns, as_of)
            need = effective.needed_inputs()
            manual = ("manual" in need) or effective.needs_manual
            full = (row["description_full"] or row["description"] or "").strip()
            if len(full) > 240:
                cut = full[:240]
                sp = max(cut.rfind(" / "), cut.rfind(", "), cut.rfind(" "))
                title = (cut[:sp] if sp > 80 else cut).rstrip(" /-,") + "…"
            else:
                title = full
            item = {
                "code": row["code"],
                "fmt": format_code(row["code"]),
                "title": title,
                "rate": format_rate(effective),
                "kind": effective.kind,
            }
            if effective.ad_valorem_pct is not None:
                item["av"] = dec(effective.ad_valorem_pct)
            if effective.specific_amount is not None:
                item["sp"] = dec(effective.specific_amount)
            if effective.specific_currency:
                item["cur"] = effective.specific_currency
            if effective.specific_unit:
                item["unit"] = effective.specific_unit
            per = effective.specific_per_qty
            if per is not None and per != Decimal("1"):
                item["per"] = dec(per)
            if printed.footnotes:
                item["fn"] = printed.footnotes[0]
            if applied and format_rate(printed) != format_rate(effective):
                item["printed"] = format_rate(printed)
            if applied and applied.valid_to:
                item["fnUntil"] = applied.valid_to
            if applied and applied.rf_only:
                item["fnRf"] = True
            if row["source_date"]:
                item["src"] = row["source_date"]
            if manual:
                item["manual"] = True
            codes.append(item)
    finally:
        conn.close()

    out = {
        "meta": {
            "source_url": meta.get("source_url"),
            "source_title": meta.get("source_title"),
            "source_notes_date": meta.get("source_notes_date"),
            "as_of": meta.get("as_of"),
            "legal_base": meta.get("legal_base"),
            "codes": len(codes),
            "imported_at": meta.get("imported_at"),
        },
        "codes": codes,
    }
    dest = ROOT / "data" / "tnved.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {dest} codes={len(codes)} bytes={dest.stat().st_size}")
    # sanity
    by = {c["code"]: c for c in codes}
    for c in ("8471300000", "6101201000", "6102301000", "2208301100", "8703219093"):
        print(c, by.get(c))


if __name__ == "__main__":
    main()
