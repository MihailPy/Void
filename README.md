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

Swagger UI:

```text
http://127.0.0.1:8000/docs
```
