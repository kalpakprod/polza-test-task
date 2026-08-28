-- Polza Agency test task — три обязательных запроса.
-- Запуск: psql "$DATABASE_URL" -f sql/queries.sql

\echo '== 1. Топ-5 категорий по числу компаний =='
SELECT category,
       count(*) AS companies
FROM company
GROUP BY category
ORDER BY companies DESC, category
LIMIT 5;

\echo '== 2. Средний рейтинг по городам среди компаний с 10+ отзывами =='
-- rating может быть NULL (79 записей) — avg их игнорирует, поэтому отдельно показываю,
-- на скольких компаниях посчитано среднее.
SELECT city,
       round(avg(rating), 2)            AS avg_rating,
       count(rating)                    AS rated_companies,
       count(*)                         AS companies_10plus_reviews
FROM company
WHERE reviews_count >= 10
GROUP BY city
HAVING count(rating) > 0
ORDER BY avg_rating DESC, city;

\echo '== 3. Доля компаний с сайтом по категориям =='
SELECT category,
       count(*)                                                        AS companies,
       count(site)                                                     AS with_site,
       round(100.0 * count(site) / count(*), 1)                        AS with_site_pct
FROM company
GROUP BY category
ORDER BY with_site_pct DESC, companies DESC;
