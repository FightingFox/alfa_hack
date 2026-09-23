# ALFA Hack

Проект для хакатона Альфа: маскирование персональных данных (ПДн) в тексте.

## Структура

- `main-module/` — точка входа: FastAPI-приложение, которое параллельно опрашивает
  все сервисы-детекторы, объединяет результаты, маскирует явные ПДн и хранит
  корреляцию `payload_id` в Redis (поддерживает демаскирование).
- `regex-module/` — детектор ПДн на регулярных выражениях + справочник адресов
  (КЛАДР), WebSocket-эндпоинт `/scan`.
- `gliner_famous/` — сервис на базе GLiNER для распознавания сущностей
  (FastAPI + WebSocket), с проверкой «известных персон».
- `llm_service/` — сервис распознавания сущностей на базе LLM (провайдер ALFA),
  тот же контракт, что и `gliner_famous`.
- `ml_for_all_types/` — ансамбль лёгковесных ML-детекторов ПД (numpy, без тяжёлых
  зависимостей), тот же контракт.
- `load_balanser/` — балансировщик нагрузки на базе Nginx.
- `monitoring/` — Prometheus + Grafana (+ cAdvisor) для мониторинга всех сервисов.
- `e2e_tests/` — end-to-end тесты всей цепочки маскирования по датасету.
- `test-data/` — датасеты и вспомогательные данные для тестов.
- `training_data/` — данные и скрипты обучения моделей.
- `docker-compose.yml` — полный стек (все сервисы + мониторинг);
  `docker-compose.services.yml` — только сервисы;
  `docker-compose.server.yml` — конфигурация для деплоя на Yandex Cloud.
- `setup-server.sh`, `build-push.sh` — скрипты сборки/публикации образов и
  развёртывания на сервере Yandex Cloud.

## Архитектура

Клиент обращается к `main-module` (`POST /process` с `{payload, payload_id}`).
`main-module` параллельно (с таймаутом) опрашивает четыре детектора через
балансировщик:

- `regex-module` (WebSocket `/scan`);
- `llm-service` (REST `/process`);
- `gliner_famous` (REST `/process`);
- `ml_for_all_types` (REST `/process`).

Полученные сущности объединяются, фильтруются (ФИО сверяются со справочником
имён), а явные ПДн заменяются на маски вида `{{ TYPE1,TYPE2 N }}`. Результат и
исходный текст сохраняются в Redis по `payload_id`, что позволяет демаскировать
строку повторным запросом с тем же `payload_id`.

Компонентная и sequence-диаграммы (PlantUML) лежат в `docs/`:

- `docs/component.puml` — компонентная диаграмма системы;
- `docs/sequence.puml` — sequence-диаграмма маскирования текста через `main-module`.

### Компонентная диаграмма

![Компонентная диаграмма](docs/component.png)

### Sequence-диаграмма

![Sequence-диаграмма](docs/sequence.png)

## Быстрый старт (docker compose)

Поднимите весь стек (все сервисы + Redis + балансировщик + мониторинг):

```bash
docker compose up -d --build
```

Проверьте, что `main-module` поднялся:

```bash
curl http://localhost:8000/health
```

### API `main-module`

`main-module` — точка входа для маскирования/демаскирования:

- `POST /process` — тело `{"payload": "<текст>", "payload_id": "<id>"}`.
  Возвращает `results` (сущности по каждому сервису), `masked_text`
  (замаскированный текст) и `replacements` (список замен).
- `POST /process` с тем же `payload_id` и `payload`, равным ранее возвращённому
  `masked_text`, — демаскирование (возвращает исходную строку в `results`).
- `GET /health` — проверка живости.
- `GET /metrics` — метрики Prometheus.

Пример маскирования:

```bash
curl -X POST http://localhost:8000/process \
  -H "Content-Type: application/json" \
  -d '{"payload": "Иван Петров, тел. +7 900 123-45-67", "payload_id": "demo-1"}'
```

Пример демаскирования (тем же `payload_id` и замаскированной строкой):

```bash
curl -X POST http://localhost:8000/process \
  -H "Content-Type: application/json" \
  -d '{"payload": "{{ FIO 1 }}, тел. {{ PHONE 2 }}", "payload_id": "demo-1"}'
```

### Конфигурация `main-module`

Список детекторов задаётся переменной окружения `MASKING_SERVICES` (JSON-массив).
Каждый элемент: `name`, `protocol` (`rest` | `websocket`), `url`, `timeout`,
опционально `pool` (для WebSocket-пула). По умолчанию в `docker-compose.yml`
подключены `regex` (WS), `llm` (REST), `gliner` (REST), `ml` (REST).

Корреляция `payload_id` хранится в Redis (`REDIS_URL`).

## Сервисы-детекторы

Все детекторы отдают сущности в едином контракте `Entity`:
`{text, type[], score, slice, will_be_used}`.

### `regex-module`

Детектор на регулярных выражениях + справочник адресов (КЛАДР). При старте
загружает адресную книгу из `BASE/`. Эндпоинт:

- `WS /scan` — принимает текст, возвращает найденные ПДн.

### `gliner_famous`

Детектор на базе GLiNER (FastAPI + WebSocket) с проверкой «известных персон».
Эндпоинты:

- `POST /process` — обработка текста (JSON `{"text": "..."}`);
- `WS /ws` — WebSocket-обработка текста.

### `llm_service`

Детектор на базе LLM провайдера ALFA (тот же контракт, что и `gliner_famous`).
Ориентирован на скорость: один запрос к LLM возвращает все сущности сразу.

Креды провайдера ALFA задаются в `llm_service/.env` (см. `.env.example`):

```bash
LLM_BASE_URL=https://alfagen.alfabank.ru/continue-dev/
LLM_API_KEY=<ваш ключ>
LLM_MODEL=deepseek-ai/DeepSeek-V4-Flash-0731
```

> Примечание: `.env` не коммитится в git (добавлен в `.gitignore`). Для локального
> запуска скопируйте `.env.example` в `.env` и заполните ключ.

### `ml_for_all_types`

Ансамбль лёгковесных numpy-классификаторов (по одному на каждый тип ПД), тот же
контракт, что и `gliner_famous`. Не требует GPU и тяжёлых зависимостей.

## Балансировщик (`load_balanser`)

Nginx-балансировщик слушает порт `80` и проксирует запросы на бэкенды
(имена задаются переменными окружения `*_BACKENDS`, по умолчанию — один бэкенд):

- `WS /gliner-famous/ws` → `/ws`;
- `POST /gliner-famous/process` → `/process`;
- `WS /llm-service/ws` → `/ws`;
- `POST /llm-service/process` → `/process`;
- `WS /regex-module/scan` → `/scan`;
- `POST /main-module/process` → `/process`;
- `GET /main-module/health` → `/health`;
- `WS /ml-for-all-types/ws` → `/ws`;
- `POST /ml-for-all-types/process` → `/process`;
- `GET /nginx_status` — метрики nginx для Prometheus.

Пример запроса к детектору через балансировщик:

```bash
curl -X POST http://localhost:8080/gliner-famous/process \
  -H "Content-Type: application/json" \
  -d '{"text": "Иван Петров работает в Альфа-Банке"}'
```

## End-to-end тесты

Тесты в `e2e_tests/` прогоняют датасет через `POST /process` `main-module` и
сверяют найденные сущности с ожидаемыми `personal_data`.

```bash
cd e2e_tests
pip install -e .
MAIN_MODULE_URL=http://localhost:8000 pytest test_e2e_dataset.py
```

Переменные окружения: `MAIN_MODULE_URL` (по умолчанию `http://localhost:8000`) и
`DATASET_PATH` (по умолчанию `test-data/deepseek_json_20260922_merged.json`).

## Мониторинг (Prometheus + Grafana)

Все FastAPI-сервисы отдают метрики Prometheus на эндпоинте `/metrics` (через
`prometheus-fastapi-instrumentator`), балансировщик — через sidecar-контейнер
`nginx-prometheus-exporter` (эндпоинт `/nginx_status`), а cAdvisor собирает
метрики CPU/RAM контейнеров.

### Запуск

Prometheus, Grafana и cAdvisor поднимаются вместе со стеком через
`docker-compose.yml`:

```bash
docker compose up -d
```

### Доступ

| Сервис      | URL                          | Логин/пароль |
|-------------|------------------------------|--------------|
| Prometheus  | http://localhost:9090        | —            |
| Grafana     | http://localhost:3000        | admin/admin  |
| cAdvisor    | http://localhost:8081        | —            |

### Преднастройки

- **Prometheus** (`monitoring/prometheus/prometheus.yml`) — скрейпит все сервисы
  (`main-module`, `regex-module`, `llm-service`, `gliner-famous`, `ml-for-all-types`),
  балансировщик через exporter и cAdvisor.
- **Grafana** (`monitoring/grafana/`) — авто-провижининг datasource Prometheus и
  готовый дашборд **«ALFA Hack — Мониторинг сервисов»**:
  - статус сервисов (`up`);
  - RPS по сервисам;
  - задержка ответа (p95/p99);
  - ошибки 4xx/5xx;
  - запросы по эндпоинтам;
  - метрики nginx (RPS, соединения);
  - метрики CPU/RAM контейнеров (cAdvisor).

Дашборд доступен сразу после старта Grafana (обновляется каждые 10 секунд).

### Проверка метрик

```bash
# Метрики конкретного сервиса
curl http://localhost:8000/metrics

# Метрики балансировщика (через exporter)
curl http://localhost:9113/metrics
```

### Сборка образов мониторинга отдельно

```bash
docker build -t alfa-prometheus ./monitoring/prometheus
docker build -t alfa-grafana ./monitoring/grafana
```

## Деплой на Yandex Cloud

Образы публикуются в Yandex Container Registry, а сервер разворачивается через
`docker-compose.server.yml`.

### 1. Сборка и публикация образов

```bash
./build-push.sh            # тег latest
./build-push.sh v1.0.0     # конкретный тег
```

Скрипт собирает и пушит образы `main-module`, `regex-module`, `llm-service`,
`gliner-famous`, `ml-for-all-types`, `load-balancer` в реестр
`cr.yandex/crpjr8em43c2vgubc740`.

### 2. Настройка сервера

Скопируйте на сервер `docker-compose.server.yml`, `llm_service.env` и
`monitoring/`, затем выполните:

```bash
./setup-server.sh
```

Скрипт установит `yc` CLI, настроит авторизацию (OAuth-токен или сервисный
аккаунт с ролью `container-registry.images.puller`), настроит Docker для реестра
и запустит контейнеры через `docker compose -f docker-compose.server.yml up -d`.

> Примечание: `docker-compose.server.yml` использует готовые образы из реестра
> (без `build:`), а `docker-compose.yml` собирает образы локально.