#!/usr/bin/env python3
"""Загрузка data/review.csv в review_raw + отчёт по аномалиям.

Принцип: сырые значения храним как text, отдельно пишем очищенные значения и список
issues[]. Строку не выбрасываем никогда — иначе аномалию невозможно доказать.

Запуск: python3 scripts/load_reviews.py
"""
from __future__ import annotations

import csv
import os
import re
import sys
from collections import Counter
from pathlib import Path

import psycopg

CSV_PATH = Path(__file__).resolve().parents[1] / "data" / "review.csv"
PHONE_RE = re.compile(r"^\+7 \(\d{3}\) \d{3}-\d{2}-\d{2}$")
INT_RE = re.compile(r"^-?\d+$")

# UTF-8 байты кириллицы, прочитанные как cp1251 ("РњРѕСЃРєРІР°" == "Москва").
def fix_mojibake(value: str) -> str | None:
    for src, dst in (("cp1251", "utf-8"), ("cp1252", "utf-8")):
        try:
            repaired = value.encode(src).decode(dst)
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
        if repaired != value and re.search(r"[А-Яа-я]", repaired):
            return repaired
    return None


CITY_CANON = {
    "москва": "Москва",
    "moscow": "Москва",
    "санкат-петербург": "Санкт-Петербург",
    "санкт-петербург": "Санкт-Петербург",
}


def clean_city(raw: str | None) -> tuple[str | None, list[str]]:
    issues: list[str] = []
    if raw is None or raw.strip() == "":
        return None, ["city_empty"]
    value = raw.strip()
    fixed = fix_mojibake(value)
    if fixed:
        issues.append("city_mojibake")
        value = fixed.strip()
    if re.search(r"\bд\.\s*\d|ул\.|офис", value, re.I):
        issues.append("city_looks_like_address")
        return None, issues
    key = value.lower()
    if key in CITY_CANON and CITY_CANON[key] != value:
        issues.append("city_normalized")
        value = CITY_CANON[key]
    if value != raw:
        issues.append("city_trimmed") if raw.strip() != raw else None
    return value, [i for i in issues if i]


def clean_rating(raw: str | None) -> tuple[float | None, list[str]]:
    if raw is None or raw.strip() == "":
        return None, ["rating_empty"]
    value = raw.strip()
    issues: list[str] = []
    if value.upper() in {"N/A", "NA", "-", "НЕТ"}:
        return None, ["rating_not_a_number"]
    if "," in value:
        issues.append("rating_comma_decimal")
        value = value.replace(",", ".")
    try:
        num = float(value)
    except ValueError:
        return None, issues + ["rating_not_a_number"]
    if not 0 <= num <= 5:
        return None, issues + ["rating_out_of_range"]
    return num, issues


def clean_reviews(raw: str | None) -> tuple[int | None, list[str]]:
    if raw is None or raw.strip() == "":
        return None, ["reviews_empty"]
    value = raw.strip()
    if not INT_RE.match(value):
        return None, ["reviews_not_an_integer"]
    num = int(value)
    if num < 0:
        return None, ["reviews_negative"]
    return num, []


def clean_site(raw: str | None) -> tuple[str | None, list[str]]:
    if raw is None or raw.strip() == "":
        return None, ["site_empty"]
    value = raw.strip()
    if not re.match(r"^https?://", value):
        if re.match(r"^htt?ps?:?/{0,2}", value):
            return None, ["site_malformed_scheme"]
        return None, ["site_not_a_url"]
    return value, []


def clean_phone(raw: str | None) -> tuple[str | None, list[str]]:
    if raw is None or raw.strip() == "":
        return None, ["phone_empty"]
    value = raw.strip()
    if PHONE_RE.match(value):
        return value, []
    digits = re.sub(r"\D", "", value)
    if len(digits) == 11 and digits[0] in "78":
        canon = f"+7 ({digits[1:4]}) {digits[4:7]}-{digits[7:9]}-{digits[9:11]}"
        return canon, ["phone_reformatted"]
    return None, ["phone_invalid"]


def dsn() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("DATABASE_URL is not set (see .env.example)")
    return url


def main() -> None:
    with open(CSV_PATH, encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    print(f"read {len(rows)} rows from {CSV_PATH.name}")

    seen_ids: Counter[str] = Counter()
    prepared = []
    stats: Counter[str] = Counter()

    for number, row in enumerate(rows, start=2):  # 1 — заголовок
        issues: list[str] = []
        ext_id = (row.get("id") or "").strip() or None
        if ext_id is None:
            issues.append("id_empty")
        else:
            seen_ids[ext_id] += 1
            if seen_ids[ext_id] > 1:
                issues.append("id_duplicate")
            if not re.fullmatch(r"c_0\d{5}", ext_id):
                # выгрузка компаний — c_000001..c_001000; всё вне диапазона нечего
                # связывать с базой, это чужой источник
                issues.append("id_out_of_source_range")
        if not (row.get("name") or "").strip():
            issues.append("name_empty")
        if not (row.get("category") or "").strip():
            issues.append("category_empty")
        if not (row.get("address") or "").strip():
            issues.append("address_empty")

        city, city_issues = clean_city(row.get("city"))
        rating, rating_issues = clean_rating(row.get("rating"))
        reviews, reviews_issues = clean_reviews(row.get("reviews_count"))
        site, site_issues = clean_site(row.get("site"))
        phone, phone_issues = clean_phone(row.get("phone"))
        issues += city_issues + rating_issues + reviews_issues + site_issues + phone_issues
        stats.update(issues)

        prepared.append(
            (
                number,
                ext_id,
                row.get("name"),
                row.get("category"),
                row.get("city"),
                row.get("address"),
                row.get("rating"),
                row.get("reviews_count"),
                row.get("site"),
                row.get("phone"),
                rating,
                reviews,
                city,
                site,
                phone,
                issues,
            )
        )

    with psycopg.connect(dsn(), autocommit=False) as conn, conn.cursor() as cur:
        cur.execute("TRUNCATE review_raw RESTART IDENTITY")
        cur.executemany(
            "INSERT INTO review_raw (row_number, ext_id, name, category, city, address,"
            " rating_raw, reviews_count_raw, site_raw, phone_raw,"
            " rating_clean, reviews_count_clean, city_clean, site_clean, phone_clean, issues)"
            " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            prepared,
        )
        conn.commit()
        cur.execute("SELECT count(*) FROM review_raw")
        total = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM review_raw WHERE issues <> '{}'")
        dirty = cur.fetchone()[0]
        cur.execute(
            "SELECT count(*) FROM review_raw r JOIN company c ON c.id = r.ext_id"
        )
        matched = cur.fetchone()[0]

    print(f"review_raw rows: {total}, with issues: {dirty}, clean: {total - dirty}")
    print(f"ext_id matching company table: {matched} ({total - matched} rows are NOT in the company base)")
    print("issues breakdown:")
    for issue, count in stats.most_common():
        print(f"  {issue}: {count}")


if __name__ == "__main__":
    main()
