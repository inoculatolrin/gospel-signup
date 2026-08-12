#!/usr/bin/env python3
"""境外基金公開資料抓取工具。

用法：
    python3 fetch_fund_data.py check                     # 檢查三個來源網域是否連得到
    python3 fetch_fund_data.py aum                       # 抓 Amundi 月報的基金規模
    python3 fetch_fund_data.py discover                  # 探測 FundClear／SITCA 表單欄位
    python3 fetch_fund_data.py nav --param k=v --param … # 抓每日淨值
    python3 fetch_fund_data.py funds                     # 列出已設定的基金

輸出寫入 data/ 目錄的 CSV，同一個 (isin, 日期) 只保留一筆。
"""

from __future__ import annotations

import argparse
import csv
import sys
import unicodedata
from dataclasses import asdict, fields as dc_fields
from pathlib import Path

import fund_sources as fs

DATA_DIR = Path(__file__).parent / "data"


def _write_csv(path: Path, rows: list, key: tuple[str, ...]) -> int:
    """合併寫入，依 key 去重。回傳新增筆數。"""
    if not rows:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = [f.name for f in dc_fields(rows[0])]

    existing: dict[tuple, dict] = {}
    if path.exists():
        with path.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                existing[tuple(row[k] for k in key)] = row

    added = 0
    for item in rows:
        row = {k: str(v) for k, v in asdict(item).items()}
        ident = tuple(row[k] for k in key)
        if ident not in existing:
            added += 1
        existing[ident] = row

    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns)
        writer.writeheader()
        for _, row in sorted(existing.items()):
            writer.writerow(row)
    return added


def _resolve(key: str | None) -> fs.Fund:
    if key is None:
        return next(iter(fs.FUNDS.values()))
    if key not in fs.FUNDS:
        sys.exit(f"未知的基金代號：{key}（可用：{', '.join(fs.FUNDS)}）")
    return fs.FUNDS[key]


def cmd_funds(_: argparse.Namespace) -> int:
    for fund in fs.FUNDS.values():
        print(f"{fund.key}\n  名稱：{fund.name}\n  ISIN：{fund.isin}"
              f"\n  淨值幣別：{fund.nav_currency}\n  月報：{fs.factsheet_url(fund)}")
    return 0


def _pad(text: str, width: int) -> str:
    """中文字佔兩格，用顯示寬度補齊才會對齊。"""
    used = sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in text)
    return text + " " * max(width - used, 1)


def cmd_check(_: argparse.Namespace) -> int:
    blocked = 0
    for label, status in fs.check_hosts().items():
        print(f"{_pad(label, 28)}{status}")
        if status.startswith("BLOCKED"):
            blocked += 1
    if blocked:
        print(
            f"\n{blocked} 個來源不可用。若在受管制的執行環境，"
            "請將下列網域加入 egress 允許清單：\n"
            "  www.amundi.com / announce.fundclear.com.tw / www.sitca.org.tw"
        )
    return 1 if blocked else 0


def cmd_aum(args: argparse.Namespace) -> int:
    fund = _resolve(args.fund)
    try:
        point = fs.fetch_aum(fund)
    except (fs.SourceBlocked, fs.SourceUnavailable) as exc:
        print(f"取得規模失敗：{exc}", file=sys.stderr)
        return 1
    added = _write_csv(DATA_DIR / "aum.csv", [point], ("isin", "as_of"))
    print(f"{fund.name}\n  規模 {point.aum:,.2f} 百萬 {point.currency}"
          f"（{point.as_of or '日期未知'}，{point.scope}）\n  新增 {added} 筆")
    return 0


def cmd_nav(args: argparse.Namespace) -> int:
    fund = _resolve(args.fund)
    params = dict(p.split("=", 1) for p in args.param)
    try:
        points = fs.fetch_nav(fund, params)
    except (fs.SourceBlocked, fs.SourceUnavailable) as exc:
        print(f"取得淨值失敗：{exc}", file=sys.stderr)
        return 1
    added = _write_csv(DATA_DIR / "nav.csv", points, ("isin", "date"))
    print(f"{fund.name}\n  取得 {len(points)} 筆淨值"
          f"（{points[0].date} ~ {points[-1].date}），新增 {added} 筆")
    return 0


def cmd_discover(_: argparse.Namespace) -> int:
    for label, fetch in (
        ("FundClear", fs.discover_fundclear),
        ("SITCA", fs.discover_sitca),
    ):
        print(f"\n=== {label} ===")
        try:
            forms = fetch()
        except (fs.SourceBlocked, fs.SourceUnavailable) as exc:
            print(f"  無法探測：{exc}")
            continue
        if not forms:
            print("  頁面上沒有 form，可能改為前端 API，請開 DevTools 觀察 XHR")
        for i, form in enumerate(forms):
            print(f"  form[{i}] {form.method.upper()} action={form.action or '(self)'}")
            for fld in form.fields:
                opts = f"  options={fld.options[:8]}" if fld.options else ""
                print(f"    - {fld.name} ({fld.kind}) value={fld.value!r}{opts}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--fund", help="基金代號，預設取清單第一檔")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("funds", help="列出已設定的基金").set_defaults(func=cmd_funds)
    sub.add_parser("check", help="檢查來源網域連線").set_defaults(func=cmd_check)
    sub.add_parser("aum", help="抓 Amundi 月報基金規模").set_defaults(func=cmd_aum)
    sub.add_parser("discover", help="探測 FundClear／SITCA 表單欄位").set_defaults(
        func=cmd_discover)

    nav = sub.add_parser("nav", help="抓每日淨值")
    nav.add_argument("--param", action="append", default=[],
                     metavar="KEY=VALUE", help="查詢參數，可重複；先跑 discover 取得")
    nav.set_defaults(func=cmd_nav)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
