# Заметки по проекту

## Что это
Практикум ПМ01 «Мини-магазин» (задание — 51.docx, в нём пока лабы 0–2).
- Этот репозиторий (`shop_pm01_home`) — готовый рабочий проект, делает Claude.
- `shop_pm01_full` — пользователь делает сам по шагам для преподавателя. Туда не пушить.

## Запуск
- `docker compose up -d --build`, затем `docker compose ps`.
- Тест: `docker compose run --rm k6 run /scripts/load.js`.
- Перед работой запустить Docker Desktop: без него `failed to connect to the docker API`.

## Подводные камни
- В Git Bash путь `/scripts/load.js` превращается в `C:/Program Files/Git/scripts/...`:
  ставить `MSYS_NO_PATHCONV=1`. В PowerShell проблемы нет.
- Отдельные запросы `curl` к lb всё время дают app1: у каждого процесса nginx свой счётчик
  балансировки. В одном соединении (браузер, `curl url url url`) воркеры чередуются.
- RPS в Лаб 1 и 2 одинаковый (~240): его ограничивает сам k6/load.js (`sleep(0.1)`, ~30 VU
  в среднем). Рост виден по CPU воркеров в `docker stats`, а не по RPS. k6/load.js не менять.
- Путь проекта с кириллицей (`D:\Проекты`) Docker-у не мешает.

## Не сделано
- Лабы 3–8 (Redis, Redis Cluster, RabbitMQ, реплики, PgBouncer, CDN/мониторинг):
  в 51.docx пока нет их шагов. Делать, когда появится задание.
