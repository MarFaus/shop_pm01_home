-- Самые «дорогие» запросы по суммарному времени (pg_stat_statements).
--   docker compose exec -T postgres psql -U shop -d shop -f /sql/top_queries.sql
-- Сбросить статистику перед замером: SELECT pg_stat_statements_reset();
SELECT calls,
       round(total_exec_time::numeric, 1)          AS total_ms,
       round(mean_exec_time::numeric, 2)           AS mean_ms,
       round((100 * total_exec_time / sum(total_exec_time) OVER ())::numeric, 1) AS percent,
       left(regexp_replace(query, '\s+', ' ', 'g'), 80) AS query
FROM pg_stat_statements
WHERE dbid = (SELECT oid FROM pg_database WHERE datname = current_database())
ORDER BY total_exec_time DESC
LIMIT 10;
