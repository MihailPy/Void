# Void

Void — локальный AI-помощник, который учится
использовать инструменты операционной системы.

Версия v0.1 умеет:

- выбирать действие
- читать файлы
- писать файлы
- смотреть список файлов

## FastAPI Backend

Запуск:

```bash
python -m void.api.server
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

Chat:

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Сделай статистику проекта"}'
```

## Auth

Local dev без токена:

```bash
python -m void.api.server
```

Если `VOID_API_TOKEN` не задан, backend запускается в local dev mode:
auth отключена, `/health` и protected endpoints работают без токена, а при
старте выводится warning.

Protected mode:

```bash
export VOID_API_TOKEN="your-long-random-token"
python -m void.api.server
```

Запрос с токеном:

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Authorization: Bearer your-long-random-token" \
  -H "Content-Type: application/json" \
  -d '{"message":"Сделай статистику проекта"}'
```

Web UI:

* открой `http://localhost:5173`
* вставь API token в Auth panel
* нажми Save

Не публикуй Void API в интернет без VPN/Tailscale/reverse proxy HTTPS.

Swagger UI:

```text
http://127.0.0.1:8000/docs
```

## Task Scheduler

Void хранит запланированные задачи в `memory/scheduled_tasks.json`.
Фонового worker на этом этапе нет: задачи можно создать, посмотреть,
включить, отключить, удалить и запустить вручную.

CLI:

```bash
python -m void.main
```

Команды:

```text
/tasks
/run-task <id>
/enable-task <id>
/disable-task <id>
/delete-task <id>
```

Примеры сообщений:

```text
Напомни через 5 минут проверить проект
Каждый день в 09:00 покажи задачи
Раз в 60 минут проверяй pending approvals
Покажи scheduled tasks
```

API:

```bash
curl http://127.0.0.1:8000/tasks
```

Создание задачи:

```bash
curl -X POST http://127.0.0.1:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{"title":"Проверить проект","prompt":"Проверь состояние проекта и покажи краткий отчёт","schedule_type":"interval","schedule_value":{"minutes":60}}'
```

Ручной запуск:

```bash
curl -X POST http://127.0.0.1:8000/tasks/<id>/run
```

State-changing API actions создают approval. Подтвердить можно через
Approvals tab или:

```bash
curl -X POST http://127.0.0.1:8000/approvals/<approval_id>/approve
```

Web UI:

* открой `http://localhost:5173`
* перейди во вкладку Tasks
* создай задачу
* подтверди действие во вкладке Approvals
* вернись во вкладку Tasks и нажми Refresh

## Web UI

Запуск backend:

```bash
python -m void.api.server
```

Запуск frontend:

```bash
cd web
npm install
npm run dev
```

По умолчанию frontend использует:

```text
http://127.0.0.1:8000
```

Можно переопределить:

```bash
VITE_VOID_API_URL=http://127.0.0.1:8000 npm run dev
```
