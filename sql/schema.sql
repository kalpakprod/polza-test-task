-- Polza Agency test task — schema
-- Postgres 16. Applied via: psql -f sql/schema.sql

BEGIN;

DROP TABLE IF EXISTS review_raw;
DROP TABLE IF EXISTS company_source;
DROP TABLE IF EXISTS company;

-- Канонические компании из выгрузки page_*.json.
-- id из API считаем натуральным ключом: он стабилен между страницами.
CREATE TABLE company (
    id             text PRIMARY KEY,
    name           text        NOT NULL,
    category       text        NOT NULL,
    city           text        NOT NULL,
    address        text,
    rating         numeric(2,1) CHECK (rating IS NULL OR rating BETWEEN 0 AND 5),
    reviews_count  integer      NOT NULL DEFAULT 0 CHECK (reviews_count >= 0),
    site           text,
    phone          text,
    -- нормализованный ключ для второй линии дедупликации (name+address без регистра/пробелов)
    dedup_key      text GENERATED ALWAYS AS (
                       lower(regexp_replace(coalesce(name,'')  || '|' || coalesce(address,''), '\s+', ' ', 'g'))
                   ) STORED,
    created_at     timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX company_category_idx      ON company (category);
CREATE INDEX company_city_idx          ON company (city);
CREATE INDEX company_rating_idx        ON company (rating);
CREATE INDEX company_reviews_idx       ON company (reviews_count);
CREATE INDEX company_city_category_idx ON company (city, category);
CREATE INDEX company_dedup_idx         ON company (dedup_key);
-- поиск по названию (ILIKE '%...%') — триграммы
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX company_name_trgm_idx ON company USING gin (name gin_trgm_ops);

-- Каждая физическая строка из источника: нужна, чтобы дедупликация была доказуемой,
-- а не «молча выкинули лишнее».
CREATE TABLE company_source (
    id            bigserial PRIMARY KEY,
    company_id    text NOT NULL,
    source_file   text NOT NULL,
    page          integer,
    row_index     integer,
    payload       jsonb NOT NULL,
    is_duplicate  boolean NOT NULL DEFAULT false,
    loaded_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX company_source_company_idx ON company_source (company_id);
CREATE INDEX company_source_dup_idx     ON company_source (is_duplicate);

-- review.csv грузим КАК ЕСТЬ (все колонки text) + флаги валидации.
-- Причина: файл грязный, приведение типов на входе потеряло бы аномалии.
CREATE TABLE review_raw (
    id                 bigserial PRIMARY KEY,
    row_number         integer NOT NULL,
    ext_id             text,
    name               text,
    category           text,
    city               text,
    address            text,
    rating_raw         text,
    reviews_count_raw  text,
    site_raw           text,
    phone_raw          text,
    rating_clean       numeric(2,1),
    reviews_count_clean integer,
    city_clean         text,
    site_clean         text,
    phone_clean        text,
    issues             text[] NOT NULL DEFAULT '{}',
    loaded_at          timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX review_raw_ext_id_idx ON review_raw (ext_id);
CREATE INDEX review_raw_issues_idx ON review_raw USING gin (issues);

COMMIT;
