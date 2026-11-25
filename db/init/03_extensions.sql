-- Расширения. Выполняется ОДИН раз — при первом запуске пустой базы.

-- Триграммы: индекс GIN по ним ускоряет ILIKE '%...%' (поиск товаров)
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Статистика выполнения всех запросов (нужен shared_preload_libraries в postgresql.conf)
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
