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
