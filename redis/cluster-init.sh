#!/bin/sh
# Собирает кластер из 6 узлов: 3 мастера + 3 реплики (по одной на мастер).
# Запускается одноразовым контейнером redis-init после старта узлов.
# Если кластер уже был собран — завершается с кодом 0 в любом случае:
# кэш необязателен, его временная неисправность не должна мешать запуску приложения.
set -e

wait_ok() {
  for i in $(seq 1 "$1"); do
    if redis-cli -h redis1 cluster info | grep -q 'cluster_state:ok'; then
      echo "Кластер готов"
      redis-cli -h redis1 cluster nodes
      return 0
    fi
    sleep 1
  done
  return 1
}

# Слоты уже розданы — кластер собирали раньше (например, до перезапуска Docker).
# Создавать заново нельзя (узлы не пустые) — ждём, пока узлы договорятся сами.
assigned=$(redis-cli -h redis1 cluster info | grep cluster_slots_assigned | cut -d: -f2 | tr -d '\r')
if [ "${assigned:-0}" -gt 0 ]; then
  echo "Кластер уже собран (слотов: $assigned), жду состояния ok"
  wait_ok 30 || echo "Кластер пока не в ok — приложение поработает без кэша, пока он не восстановится"
  exit 0
fi

# redis-cli --cluster create принимает только IP-адреса — узнаём их по именам
ADDRS=""
for n in 1 2 3 4 5 6; do
  ip=$(getent hosts "redis$n" | awk '{print $1}')
  ADDRS="$ADDRS $ip:6379"
done
echo "Узлы:$ADDRS"

# --cluster-replicas 1: на каждый мастер по одной реплике
# --cluster-yes: не спрашивать подтверждение
redis-cli --cluster create $ADDRS --cluster-replicas 1 --cluster-yes

# Ждём, пока все узлы договорятся о раскладке слотов
if wait_ok 30; then
  exit 0
fi
echo "Кластер не собрался" >&2
exit 1
