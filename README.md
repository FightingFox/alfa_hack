# ALFA Hack

Проект для хакатона Альфа.

## Структура

- `gliner_famous/` — сервис на базе GLiNER для распознавания сущностей (FastAPI + WebSocket).
- `load_balanser/` — балансировщик нагрузки на базе Nginx.

## Запуск реплик контейнеров

### 1. Сборка и запуск реплик `gliner_famous`

Соберите образ сервиса:

```bash
docker build -t gliner_famous ./gliner_famous
```

Запустите несколько реплик (например, две) на разных портах:

```bash
docker run -d --name gliner1 -p 8001:8000 gliner_famous
docker run -d --name gliner2 -p 8002:8000 gliner_famous
```

Сервис слушает порт `8000` внутри контейнера и отдаёт два эндпоинта:
- `POST /process` — обработка текста (JSON `{"text": "..."}`);
- `WS /ws` — WebSocket-обработка текста.

### 2. Сборка и запуск `load_balanser`

Соберите образ балансировщика:

```bash
docker build -t load_balanser ./load_balanser
```

Запустите его, передав список бэкендов `gliner_famous` через переменную окружения `GLINER_BACKENDS` (имена хостов через пробел):

```bash
docker run -d --name lb -p 8080:80 \
  -e GLINER_BACKENDS="gliner1:8000 gliner2:8000" \
  --link gliner1 --link gliner2 \
  load_balanser
```

Если `GLINER_BACKENDS` не задан, по умолчанию используется один бэкенд `gliner1:8000`.

Балансировщик слушает порт `80` внутри контейнера и проксирует запросы на реплики:
- `WS /gliner-famous/ws` → `/ws` (WebSocket, round-robin);
- `POST /gliner-famous/process` → `/process`.

### 3. Проверка

HTTP-запрос через балансировщик:

```bash
curl -X POST http://localhost:8080/gliner-famous/process \
  -H "Content-Type: application/json" \
  -d '{"text": "Иван Петров работает в Альфа-Банке"}'
```

WebSocket-подключение через балансировщик:

```bash
wscat -c ws://localhost:8080/gliner-famous/ws
```

> Примечание: для связи контейнеров по именам (`gliner1`, `gliner2`) используйте общую Docker-сеть вместо `--link` (устаревший флаг), например `docker network create alfa-net` и подключите все контейнеры к ней.