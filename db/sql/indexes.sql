-- Индексы под запросы приложения. Можно выполнять повторно (IF NOT EXISTS).
-- Применяется автоматически сервисом db-migrate при docker compose up,
-- вручную: docker compose exec -T postgres psql -U shop -d shop -f /sql/indexes.sql
-- На реплики индексы попадают сами — через репликацию.

-- GET /products?category_id=..: фильтр по категории + сортировка по цене.
-- Индекс уже упорядочен как нужно — PostgreSQL читает первые 20 строк и останавливается.
CREATE INDEX IF NOT EXISTS products_category_price_idx
    ON products (category_id, price DESC);

-- GET /products/search: ILIKE '%abc%' обычный B-tree не ускорит (шаблон начинается с %).
-- GIN по триграммам (pg_trgm) находит строки, содержащие все тройки букв шаблона.
CREATE INDEX IF NOT EXISTS products_name_trgm_idx
    ON products USING gin (name gin_trgm_ops);

-- GET /stats/top-products: заказы за последние 7 дней.
-- INCLUDE кладёт product_id и quantity прямо в индекс — таблицу читать не нужно
-- (Index Only Scan).
CREATE INDEX IF NOT EXISTS orders_created_at_idx
    ON orders (created_at) INCLUDE (product_id, quantity);

-- Внешний ключ orders.product_id: без индекса удаление товара перебирает все заказы
CREATE INDEX IF NOT EXISTS orders_product_id_idx
    ON orders (product_id);

-- consumer ищет «застрявшие» pending-заказы. Частичный индекс: только pending,
-- поэтому он крошечный, хотя заказов полмиллиона
CREATE INDEX IF NOT EXISTS orders_pending_idx
    ON orders (created_at) WHERE status = 'pending';

ANALYZE products;
ANALYZE orders;
