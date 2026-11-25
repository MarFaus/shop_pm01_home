# Мини-магазин — высоконагруженное приложение (ПМ01)

Готовый рабочий проект по практикуму: все 8 лабораторных. REST API магазина на FastAPI
(200 000 товаров, 500 000 заказов), шаг за шагом превращённый в высоконагруженную систему.

```
клиент ─► edge (CDN-кэш) ─► lb (Nginx) ─► app1 / app2 / app3 ─┬─► Redis Cluster (6 узлов) — кэш
                                                              ├─► PgBouncer ─► PostgreSQL primary (запись)
                                                              │              └► реплики r1, r2 (чтение)
                                                              └─► RabbitMQ ─► consumer (оплата заказов)
Prometheus ◄── метрики всех сервисов ──► Grafana (дашборд)
```

| Тег | Лабораторная | Что добавлено |
|-----|--------------|---------------|
| `lab-0` | Подготовка | структура, `.gitignore`, `.gitattributes` |
| `lab-1` | Приложение и БД | `app/main.py` (+ `GET /orders/{id}`), схема и данные, Dockerfile, compose, `k6/load.js` |
| `lab-2` | Балансировщик | `nginx/default.conf`, воркеры `app1–app3` |
| `lab-3` | Кэш Redis | `app/cache.py` — cache-aside, TTL, инвалидация |
| `lab-4` | Redis Cluster | `redis/` — 6 узлов, сборка кластера, failover |
| `lab-5` | RabbitMQ | `app/mq.py`, `app/consumer.py`, `rabbitmq/limits.conf`, `k6/orders.js` |
| `lab-6` | Реплики PostgreSQL | `db/init/02_replication.sh`, `db/replica-entrypoint.sh`, `app/db.py` |
| `lab-7` | PgBouncer и тюнинг | `pgbouncer/`, `db/conf/postgresql.conf`, `db/init/03_extensions.sql`, `db/sql/`, `k6/stress.js` |
| `lab-8` | CDN и мониторинг | `edge/`, `monitoring/` (Prometheus, Grafana), метрики в приложении |

Что изменилось в лабе: `git diff lab-6 lab-7`. Код на любой лабе: `git checkout lab-3` (вернуться: `git checkout main`).

## Запуск

Нужен запущенный Docker Desktop (не меньше 5 ГБ памяти для Docker). Из папки проекта:

```powershell
docker compose up -d --build
docker compose ps
```

Первый запуск — 1–2 минуты (скачать образы, загрузить 700 000 строк в базу, скопировать её на реплики).
Готово, когда `postgres`, реплики и `rabbitmq` — `healthy`, остальное — `Up`,
а `redis-init` и `db-migrate` — `Exited (0)` (это одноразовые контейнеры, так и должно быть).

| Что | Адрес |
|-----|-------|
| Магазин (через edge-кэш) | http://localhost:8080/ |
| Swagger | http://localhost:8080/docs |
| В обход edge, сразу в балансировщик | http://localhost:8081/ |
| Grafana, дашборд «Мини-магазин» | http://localhost:3000 (смотреть можно без входа; admin / admin) |
| Prometheus | http://localhost:9090 → Status → Targets |
| RabbitMQ | http://localhost:15672 (shop / shop) |

Остановить: `docker compose down` (данные сохранятся) или `docker compose down -v` (с удалением баз и очередей).

## Проверка по лабам

```powershell
# Лаб 1–2: воркеры по очереди (поле instance), заказ и 404
curl.exe http://localhost:8080/
curl.exe http://localhost:8080/orders/999999999

# Лаб 3, 8: X-Cache (Redis в приложении) и X-Cache-Status (edge)
curl.exe -i http://localhost:8080/products/42

# Лаб 4: состав кластера
docker compose exec redis1 redis-cli cluster nodes

# Лаб 5: заказ — сначала pending, через 0,2 с processed
curl.exe -X POST http://localhost:8080/orders -H "Content-Type: application/json" -d '{\"product_id\": 5}'

# Лаб 6: реплики получают поток WAL
docker compose exec postgres psql -U shop -d shop -c "SELECT client_addr, state, replay_lag FROM pg_stat_replication"

# Лаб 7: планы запросов, тяжёлые запросы, пулы PgBouncer
docker compose exec postgres psql -U shop -d shop -f /sql/explain.sql
docker compose exec postgres-r1 psql -U shop -d shop -f /sql/top_queries.sql
docker compose exec -e PGPASSWORD=shop pgbouncer psql -h 127.0.0.1 -p 6432 -U shop pgbouncer -c "SHOW POOLS"
```

## Нагрузочные тесты

```powershell
docker compose run --rm k6 run /scripts/load.js     # основной замер для журнала (70 с)
docker compose run --rm k6 run /scripts/orders.js   # всплеск заказов, смотреть очередь в RabbitMQ
docker compose run --rm k6 run /scripts/stress.js   # 300 пользователей
```

Во время теста во втором терминале — `docker stats`, в браузере — дашборд Grafana.
Опыты с отказами: во время `load.js` выполнить `docker compose stop app2` (или `redis1`, `postgres-r1`),
через 20 с — `docker compose start ...`.

## Результаты

- [ЖУРНАЛ.md](ЖУРНАЛ.md) — журнал замеров по всем лабам, опыты с отказами, EXPLAIN до и после индексов
- [ОТВЕТЫ.md](ОТВЕТЫ.md) — ответы на контрольные вопросы
- `results/` — полные отчёты k6, `docker stats`, планы запросов
