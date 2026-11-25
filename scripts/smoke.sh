#!/bin/bash
# Сквозная проверка стенда по всем лабам (0 FAIL — всё работает).
# Запуск из корня проекта при поднятом стенде: bash scripts/smoke.sh
export MSYS_NO_PATHCONV=1
P=0; F=0
ok()   { echo "PASS  $1"; P=$((P+1)); }
bad()  { echo "FAIL  $1  -> $2"; F=$((F+1)); }
check(){ if [ "$2" = "$3" ]; then ok "$1"; else bad "$1" "ожидали [$3], получили [$2]"; fi; }
psqlc(){ docker compose exec -T "$1" psql -U shop -d shop -tAc "$2" 2>&1 | tr -d '\r'; }

sleep 10
# Лаб 1
check "Лаб1 товаров 200000"        "$(psqlc postgres 'select count(*) from products')" "200000"
check "Лаб1 GET /products/1"       "$(curl -s -o /dev/null -w '%{http_code}' localhost:8080/products/1)" "200"
check "Лаб1 GET /orders/999999999" "$(curl -s -o /dev/null -w '%{http_code}' localhost:8080/orders/999999999)" "404"
check "Лаб1 /docs"                 "$(curl -s -o /dev/null -w '%{http_code}' localhost:8080/docs)" "200"
# Лаб 2
inst=$(python -c "import json,urllib.request as u;print(' '.join(sorted({json.load(u.urlopen('http://localhost:8080/'))['instance'] for _ in range(9)})))" | tr -d '\r')
check "Лаб2 все воркеры отвечают"  "$inst" "app1 app2 app3"
check "Лаб2 /metrics закрыт снаружи" "$(curl -s -o /dev/null -w '%{http_code}' localhost:8081/metrics)" "404"
# Лаб 3
curl -s -o /dev/null "localhost:8081/products/77"
check "Лаб3 Redis HIT"             "$(curl -si localhost:8081/products/77 | grep -i '^x-cache:' | awk '{print $2}' | tr -d '\r')" "HIT"
# Лаб 4
check "Лаб4 кластер ok"            "$(docker compose exec -T redis1 redis-cli cluster info | grep cluster_state | tr -d '\r')" "cluster_state:ok"
check "Лаб4 мастеров 3"            "$(docker compose exec -T redis1 redis-cli cluster nodes | grep -c master)" "3"
# Лаб 5
R=$(curl -s -XPOST localhost:8080/orders -H 'Content-Type: application/json' -d '{"product_id":77,"quantity":1}' -w ' %{http_code}')
check "Лаб5 POST /orders 202"      "${R##* }" "202"
ID=$(echo "${R% *}" | python -c "import sys,json;print(json.load(sys.stdin)['id'])")
sleep 1
check "Лаб5 заказ processed"       "$(curl -s localhost:8080/orders/$ID | python -c "import sys,json;print(json.load(sys.stdin)['status'])")" "processed"
check "Лаб5 инвалидация (MISS после заказа)" "$(curl -si localhost:8081/products/77 | grep -i '^x-cache:' | awk '{print $2}' | tr -d '\r')" "MISS"
# Лаб 6
check "Лаб6 реплик streaming"      "$(psqlc postgres "select count(*) from pg_stat_replication where state='streaming'")" "2"
check "Лаб6 слоты активны"         "$(psqlc postgres "select string_agg(slot_name||':'||active, ',' order by slot_name) from pg_replication_slots")" "replica1:true,replica2:true"
check "Лаб6 реплика read-only"     "$(psqlc postgres-r1 'select pg_is_in_recovery()')" "t"
check "Лаб6 /health реплики"       "$(curl -s localhost:8080/health | python -c "import sys,json;print(json.load(sys.stdin)['replicas'])")" "[True, True]"
# Лаб 7
check "Лаб7 индексов создано"      "$(psqlc postgres "select count(*) from pg_indexes where indexname in ('products_category_price_idx','products_name_trgm_idx','orders_created_at_idx','orders_product_id_idx','orders_pending_idx')")" "5"
check "Лаб7 индексы на реплике"    "$(psqlc postgres-r2 "select count(*) from pg_indexes where indexname like '%trgm%'")" "1"
check "Лаб7 конфиг: jit"           "$(psqlc postgres 'show jit')" "off"
check "Лаб7 pg_stat_statements"    "$(psqlc postgres "select count(*) from pg_extension where extname in ('pg_stat_statements','pg_trgm')")" "2"
check "Лаб7 PgBouncer пулы"        "$(docker compose exec -T -e PGPASSWORD=shop pgbouncer psql -h 127.0.0.1 -p 6432 -U shop pgbouncer -tAc 'show databases' | grep -c '^shop')" "3"
# Лаб 8
curl -s -o /dev/null localhost:8080/products/88
check "Лаб8 edge HIT"              "$(curl -si localhost:8080/products/88 | grep -i '^x-cache-status' | awk '{print $2}' | tr -d '\r')" "HIT"
check "Лаб8 POST не кэшируется"    "$(curl -si -XPOST localhost:8080/orders -H 'Content-Type: application/json' -d '{"product_id":88}' | grep -ic '^x-cache-status')" "0"
sleep 6
up=$(curl -s localhost:9090/api/v1/targets | python -c "import sys,json;t=json.load(sys.stdin)['data']['activeTargets'];print(sum(x['health']=='up' for x in t),'/',len(t))")
check "Лаб8 цели Prometheus up"    "$up" "16 / 16"
check "Лаб8 очередь по метке queue" "$(curl -s 'localhost:9090/api/v1/query?query=rabbitmq_queue_messages_ready%7Bqueue%3D%22orders%22%7D' | python -c "import sys,json;print(len(json.load(sys.stdin)['data']['result']))")" "1"
check "Лаб8 Grafana дашборд"       "$(curl -s localhost:3000/api/dashboards/uid/shop | python -c "import sys,json;print(len(json.load(sys.stdin)['dashboard']['panels']))")" "21"
echo "ИТОГО: PASS=$P FAIL=$F"
