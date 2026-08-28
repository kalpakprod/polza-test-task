# Polza Agency — тестовое задание, «Технический специалист»

Репозиторий: https://github.com/kalpakprod/polza-test-task

Максим Рыжов · Алматы (UTC+5) · [@maksimryzhov614](https://t.me/maksimryzhov614) · maksryzhov16@gmail.com
GitHub: https://github.com/maksimryzhov614

Стек как в задании: **Python** (загрузчики) + **PostgreSQL** (схема, индексы, запросы) +
**Next.js 15 App Router / TypeScript strict** (страница `/companies`). Разработка через
Claude Code / Codex, всё проверено запуском.

---

## Что сделано

| Задача | Артефакт | Статус |
|---|---|---|
| 1. Выгрузка → Postgres | `scripts/load_companies.py`, `sql/schema.sql`, `sql/queries.sql` | 994 компании из 1000 строк, дедупликация + индексы |
| 2. Мини-фича | `web/` — `/companies`, `/api/companies` | Server Component + Route Handler, скриншоты в `docs/` |
| 3. Данные с сюрпризом | `scripts/load_reviews.py`, `ANOMALIES.md` | 207 строк, 100 с проблемами, 21 тип аномалий |
| 4. Вайбкод/LLM-стек | `ANSWERS-task4.md` | написано руками, без ИИ |

---

## Быстрый старт

### 1. Postgres

Вариант A — Docker:

```bash
docker run -d --name polza-pg -p 5432:5432 \
  -e POSTGRES_USER=polza -e POSTGRES_PASSWORD=polza -e POSTGRES_DB=polza \
  postgres:16
export DATABASE_URL='postgresql://polza:polza@localhost:5432/polza'
```

Вариант B — Supabase: возьмите connection string из Project Settings → Database.

Локально я проверял на Postgres 16 (Homebrew) в изолированном кластере на порту 55432,
чтобы не трогать системный:

```bash
initdb -D .pgdata -U polza --auth=trust -E UTF8
pg_ctl -D .pgdata -o "-p 55432 -k $PWD/.pgdata" start
export DATABASE_URL="postgresql://polza@localhost:55432/polza?host=$PWD/.pgdata"
```

### 2. Схема и данные

```bash
python3 -m venv .venv && ./.venv/bin/pip install 'psycopg[binary]'

psql "$DATABASE_URL" -f sql/schema.sql
./.venv/bin/python scripts/load_companies.py
./.venv/bin/python scripts/load_reviews.py
psql "$DATABASE_URL" -f sql/queries.sql
```

### 3. Веб-часть

```bash
cd web
cp env.example .env.local        # подставить свой DATABASE_URL
npm install
npm run typecheck && npm run build
npm start                        # http://localhost:3100/companies
```

---

## Фактические результаты прогона

`scripts/load_companies.py`:

```
read 1000 rows from 20 files
companies loaded: 994
duplicates skipped: 6 by id, 0 by name+address (source rows flagged: 6)
id duplicates with differing payload: 0 []
empty fields among canonical rows: {'site': 238, 'rating': 79, 'phone': 110}
```

`scripts/load_reviews.py`:

```
read 207 rows from review.csv
review_raw rows: 207, with issues: 100, clean: 107
ext_id matching company table: 6 (201 rows are NOT in the company base)
```

`sql/queries.sql` — топ-5 категорий:

| category | companies |
|---|---|
| IT-интегратор | 94 |
| Оптовая торговля | 79 |
| Рекламное агентство | 76 |
| Строительная компания | 71 |
| Юридические услуги | 63 |

Средний рейтинг по городам (10+ отзывов), первые строки: Сочи 4.46 (13 компаний),
Пермь 4.43 (30), Омск 4.41 (23), Тюмень 4.35 (23). Полный вывод даёт `sql/queries.sql`.

---

## Решения по схеме и почему так

- **`company`** — канонические записи, PK = `id` из API. Индексы: `category`, `city`,
  `rating`, `reviews_count`, составной `(city, category)` под фильтры страницы и GIN
  `pg_trgm` на `name` — поиск идёт через `ILIKE '%...%'`, обычный btree там бесполезен.
- **`company_source`** — каждая физическая строка источника с `payload jsonb` и флагом
  `is_duplicate`. Дедупликация должна быть доказуемой: видно, какая именно строка
  выброшена и из какого файла, а не «стало 994 вместо 1000, поверьте».
- **Дедупликация в два слоя**: сначала `id`, потом нормализованный `name + address`
  (`dedup_key`, generated column: lower + сжатие пробелов). По id нашлось 6 дублей,
  по второму слою — ни одного, то есть повторы пришли из пагинации.
- **`review_raw`** — все колонки `text` плюс `*_clean` и `issues text[]`. CSV грязный;
  приведение типов на входе потеряло бы аномалии, а строку выбрасывать нельзя, иначе её
  нечем подтвердить. GIN-индекс по `issues` — чтобы фильтровать по типу проблемы.
- **`CHECK (rating BETWEEN 0 AND 5)`** и `reviews_count >= 0` — в CSV есть `-3`, `7.5`,
  `-10`; такие значения не должны попадать в чистый слой даже случайно.

## Что нашёл в данных

Подробно — в **[ANOMALIES.md](ANOMALIES.md)**. Главное:

1. `review.csv` — **не та же база**: пересечение с выгрузкой всего 6 id из 207. Диапазон
   компаний `c_000001…c_001000`, в CSV в основном `c_001004…c_001190` плюс 6 id вида
   `c_9000xx`. У шести совпавших id все поля идентичны JSON — значит это не обновление.
2. Название файла врёт: внутри не отзывы, а те же 9 колонок справочника компаний.
3. 21 тип дефектов: мохибейк `РњРѕСЃРєРІР°` (= `Москва`), сдвиг колонок (адрес в поле
   города), `4,5` вместо `4.5`, `N/A`, рейтинг `-3` и `7.5`, `reviews_count = 45.5` и
   `много`, `-10`, `htp://`, `нет сайта`, телефон `8 (925) abc-12-34`, 3 дубля id в
   хвосте файла, 2 пустые строки.

## Как проверял веб-часть (задача 2)

`npm run typecheck` — 0 ошибок, `npm run build` — успешно, `/companies` и
`/api/companies` собраны как dynamic (`ƒ`). Дальше руками и через HTTP:

1. `/companies` без параметров → «Найдено 994, показаны первые 50», таблица рисуется.
2. Поиск + фильтр вместе: `?q=Прайм&city=Челябинск` → 3 результата, все из Челябинска,
   первый «ООО «Прайм Медиа»». Проверил, что фильтры складываются, а не заменяют друг друга.
3. Пустой результат: `?q=zzzz-nope` → не пустая таблица, а сообщение «Ничего не найдено» —
   первая версия рисовала пустой `<tbody>`, поправил.
4. Защита от инъекции: `?q=' OR 1=1 --` → `total: 0`, 200 OK. Значения идут параметрами
   `$1/$2/$3`, в SQL не склеиваются.
5. `limit=99999` → отдаётся 200 записей: в `listCompanies` лимит зажат `MAX_LIMIT = 200`,
   иначе один запрос вытянет всю таблицу.
6. Мобильная ширина 390px — таблица уходит в горизонтальный скролл внутри `.table-wrap`,
   страница целиком не разъезжается (`docs/05-mobile-390.png`).

Что ломалось в процессе: (а) `rating numeric` приходил из `pg` строкой и в React
рендерился как `"4.30"` — добавил `rating::float8` в SELECT; (б) в dev-режиме на каждом
HMR создавался новый `Pool` — вынес пул в `globalThis`.

Скриншоты: `docs/01-companies-list.png`, `docs/02-search-and-city-filter.png`,
`docs/03-empty-state.png`, `docs/04-route-handler-json.png`, `docs/05-mobile-390.png`.

## Секреты

В репозитории нет `.env` — только `web/env.example`. `DATABASE_URL` читается из окружения,
скрипты падают с внятной ошибкой, если переменная не задана.

## Структура

```
.
├── ANOMALIES.md              # задача 3 — отчёт по review.csv
├── ANSWERS-task4.md          # задача 4 — руками, без ИИ
├── README.md
├── data/                     # page_001..020.json + review.csv из data_pack.zip
├── docs/                     # скриншоты страницы и API
├── scripts/
│   ├── load_companies.py     # page_*.json → company + company_source
│   └── load_reviews.py       # review.csv → review_raw + issues[]
├── sql/
│   ├── schema.sql
│   └── queries.sql           # 3 обязательных запроса
└── web/                      # Next.js 15 App Router, /companies
```

## Где застрял / что не доделал

- Не поднимал Docker (нет на машине) — использовал локальный кластер Postgres 16.
  На Docker/Supabase меняется только `DATABASE_URL`.
- `review.csv` осознанно **не** сливал в `company`: пока не подтверждено, что это та же
  база, мердж по `id` подмешал бы чужие записи. Готов домержить, если это ожидаемое
  поведение — логика приведения типов уже написана в `load_reviews.py`.
- Тестов на pytest нет: за отведённый час приоритет был на данных и проверяемом
  результате. Что бы написал первым — в `ANSWERS-task4.md`.
