-- Планы «тяжёлых» запросов приложения. Сравнить до и после indexes.sql:
--   docker compose exec -T postgres psql -U shop -d shop -f /sql/explain.sql
-- Смотрим на: Seq Scan (полный перебор таблицы) vs Index Scan, и на Execution Time.

\echo '=== 1. Список категории (GET /products?category_id=7) ==='
EXPLAIN (ANALYZE, BUFFERS, COSTS OFF)
SELECT id, name, price, stock FROM products
WHERE category_id = 7 ORDER BY price DESC LIMIT 20 OFFSET 0;

\echo '=== 2. Поиск (GET /products/search?q=abc) ==='
EXPLAIN (ANALYZE, BUFFERS, COSTS OFF)
SELECT id, name, price FROM products WHERE name ILIKE '%abc%' LIMIT 20;

\echo '=== 3. Поиск, которого нет (худший случай: перебрать всё) ==='
EXPLAIN (ANALYZE, BUFFERS, COSTS OFF)
SELECT id, name, price FROM products WHERE name ILIKE '%zzz%' LIMIT 20;

\echo '=== 4. Топ продаж за неделю (GET /stats/top-products) ==='
EXPLAIN (ANALYZE, BUFFERS, COSTS OFF)
SELECT p.id, p.name, t.sold
FROM (SELECT product_id, sum(quantity) AS sold
      FROM orders
      WHERE created_at > now() - interval '7 days'
      GROUP BY product_id
      ORDER BY sold DESC
      LIMIT 10) t
JOIN products p ON p.id = t.product_id
ORDER BY t.sold DESC;
