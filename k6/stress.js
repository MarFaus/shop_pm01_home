// Стресс-тест: тот же сценарий, что load.js, но до 300 пользователей.
// Показывает, что PgBouncer держит к базе ограниченное число соединений,
// сколько бы клиентов ни пришло.
// Запуск: docker compose run --rm k6 run /scripts/stress.js
// Во время теста: docker compose exec -T postgres psql -U shop -d shop -c
//   "SELECT count(*) FROM pg_stat_activity WHERE backend_type = 'client backend'"
export { default } from './load.js';

const VUS = parseInt(__ENV.VUS || '300');

export const options = {
  stages: [
    { duration: '20s', target: VUS },
    { duration: '40s', target: VUS },
    { duration: '10s', target: 0 },
  ],
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<1000'],
  },
};
