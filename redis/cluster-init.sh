#!/bin/sh
# Собирает кластер из 6 узлов: 3 мастера + 3 реплики (по одной на мастер).
# Запускается одноразовым контейнером redis-init после старта узлов.
set -e

if redis-cli -h redis1 cluster info | grep -q 'cluster_state:ok'; then
  echo "Кластер уже собран"
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
for i in $(seq 1 30); do
  if redis-cli -h redis1 cluster info | grep -q 'cluster_state:ok'; then
    echo "Кластер готов"
    redis-cli -h redis1 cluster nodes
    exit 0
  fi
  sleep 1
done
echo "Кластер не собрался" >&2
exit 1
