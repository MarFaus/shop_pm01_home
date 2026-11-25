// «Распродажа»: всплеск заказов. Показывает, что очередь принимает заказы быстро,
// а consumer разбирает их в своём темпе.
// Запуск: docker compose run --rm k6 run /scripts/orders.js
// Во время теста откройте http://localhost:15672 (shop / shop) → Queues → orders.
import http from 'k6/http';
import { check } from 'k6';

const BASE = __ENV.BASE_URL || 'http://localhost:8080';

http.setResponseCallback(http.expectedStatuses({ min: 200, max: 299 }, 409));

export const options = {
  scenarios: {
    sale: {
      executor: 'constant-arrival-rate',
      rate: parseInt(__ENV.RATE || '150'),   // заказов в секунду (перегрузка: -e RATE=300)
      timeUnit: '1s',
      duration: '30s',
      preAllocatedVUs: 50,
      maxVUs: 200,
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<200'],   // заказ принимается быстрее «шлюза» (200 мс)
  },
};

export default function () {
  const res = http.post(
    `${BASE}/orders`,
    JSON.stringify({ product_id: Math.floor(Math.random() * 200000) + 1, quantity: 1 }),
    { headers: { 'Content-Type': 'application/json' } },
  );
  check(res, { 'заказ принят (202)': (r) => r.status === 202 || r.status === 409 });
}
