# Мини-магазин — высоконагруженное приложение (ПМ01)

Готовый рабочий проект по практикуму. Сделаны лабораторные 0–2: FastAPI + PostgreSQL в Docker,
нагрузочный тест k6, балансировщик Nginx перед тремя воркерами.

| Тег | Что добавлено |
|-----|---------------|
| `lab-0` | структура проекта, `.gitignore`, `.gitattributes` |
| `lab-1` | API магазина (`app/main.py`, включая `GET /orders/{id}`), база на 200 000 товаров и 500 000 заказов, Dockerfile, compose, `k6/load.js` |
| `lab-2` | `nginx/default.conf`, воркеры `app1–app3` через YAML-якорь, балансировщик `lb` |

Посмотреть изменения лабы: `git diff lab-1 lab-2`.

## Запуск

Нужен запущенный Docker Desktop. Из папки проекта в PowerShell:

```powershell
docker compose up -d --build
docker compose ps            # postgres — healthy, app1..app3 и lb — Up (первый раз ~1 мин)
```

- API: http://localhost:8080/ — поле `instance` показывает воркер
- Swagger: http://localhost:8080/docs
- Заказ по номеру: http://localhost:8080/orders/1, несуществующий http://localhost:8080/orders/999999999 → 404

Нагрузочный тест (70 с), во втором терминале в это время `docker stats`:

```powershell
docker compose run --rm k6 run /scripts/load.js
```

Остановить: `docker compose down` (данные сохранятся), `docker compose down -v` (с удалением базы).

## Результаты

- Журнал замеров — [ЖУРНАЛ.md](ЖУРНАЛ.md), полные отчёты k6 — папка `results/`
- Ответы на контрольные вопросы — [ОТВЕТЫ.md](ОТВЕТЫ.md)
