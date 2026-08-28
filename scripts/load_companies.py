#!/usr/bin/env python3
"""Загрузка выгрузки page_*.json в PostgreSQL.

Что делает:
  1. читает все data/page_*.json (структура: {page, per_page, total, items:[...]});
  2. пишет каждую физическую строку в company_source (payload jsonb) — чтобы дедупликация
     была видимой, а не «молча выкинули»;
  3. схлопывает записи в company: первичный ключ — id из API, вторая линия — name+address;
  4. печатает отчёт: сколько прочитано, сколько дублей, сколько пропусков по полям.

Запуск: python3 scripts/load_companies.py
Соединение берётся из DATABASE_URL (см. .env.example).
"""
from __future__ import annotations

import glob
import json
import os
import sys
from collections import Counter
from pathlib import Path

import psycopg
from psycopg.types.json import Jsonb

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
FIELDS = ("id", "name", "category", "city", "address", "rating", "reviews_count", "site", "phone")


def dsn() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("DATABASE_URL is not set (see .env.example)")
    return url


def read_pages() -> list[tuple[str, int, int, dict]]:
    """[(source_file, page, row_index, item)] в порядке файлов и строк."""
    rows: list[tuple[str, int, int, dict]] = []
    files = sorted(glob.glob(str(DATA_DIR / "page_*.json")))
    if not files:
        sys.exit(f"no page_*.json in {DATA_DIR}")
    for path in files:
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
        page = doc.get("page")
        for idx, item in enumerate(doc.get("items") or []):
            rows.append((Path(path).name, page, idx, item))
    return rows


def norm_key(item: dict) -> str:
    name = " ".join((item.get("name") or "").split()).lower()
    addr = " ".join((item.get("address") or "").split()).lower()
    return f"{name}|{addr}"


def main() -> None:
    rows = read_pages()
    print(f"read {len(rows)} rows from {len(set(r[0] for r in rows))} files")

    canonical: dict[str, dict] = {}
    by_norm: dict[str, str] = {}
    dup_by_id = 0
    dup_by_norm = 0
    conflicts: list[str] = []
    flags: list[bool] = []

    for _f, _p, _i, item in rows:
        cid = item.get("id")
        if cid in canonical:
            dup_by_id += 1
            flags.append(True)
            if canonical[cid] != item:
                conflicts.append(cid)
            continue
        nk = norm_key(item)
        if nk in by_norm and nk != "|":
            dup_by_norm += 1
            flags.append(True)
            continue
        canonical[cid] = item
        by_norm[nk] = cid
        flags.append(False)

    missing = Counter()
    for item in canonical.values():
        for field in ("rating", "site", "phone", "address"):
            if item.get(field) in (None, ""):
                missing[field] += 1

    with psycopg.connect(dsn(), autocommit=False) as conn, conn.cursor() as cur:
        cur.execute("TRUNCATE company_source, company RESTART IDENTITY")
        cur.executemany(
            "INSERT INTO company_source (company_id, source_file, page, row_index, payload, is_duplicate)"
            " VALUES (%s, %s, %s, %s, %s, %s)",
            [
                (item.get("id"), f, p, i, Jsonb(item), dup)
                for (f, p, i, item), dup in zip(rows, flags)
            ],
        )
        cur.executemany(
            "INSERT INTO company (id, name, category, city, address, rating, reviews_count, site, phone)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"
            " ON CONFLICT (id) DO NOTHING",
            [tuple(item.get(k) for k in FIELDS) for item in canonical.values()],
        )
        conn.commit()
        cur.execute("SELECT count(*) FROM company")
        loaded = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM company_source WHERE is_duplicate")
        dupes = cur.fetchone()[0]

    print(f"companies loaded: {loaded}")
    print(f"duplicates skipped: {dup_by_id} by id, {dup_by_norm} by name+address (source rows flagged: {dupes})")
    print(f"id duplicates with differing payload: {len(conflicts)} {conflicts[:5]}")
    print("empty fields among canonical rows:", dict(missing))


if __name__ == "__main__":
    main()
