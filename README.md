# ALFA Hack

Проект для хакатона Альфа.

## Структура

- `gliner_famous/` — сервис на базе GLiNER для распознавания сущностей (FastAPI + WebSocket).
- `llm_service/` — сервис распознавания сущностей на базе LLM (провайдер ALFA), тот же контракт, что и `gliner_famous`.
- `load_balanser/` — балансировщик нагрузки на базе Nginx.

## Архитектура

Компонентная и sequence-диаграммы (PlantUML) лежат в `docs/`:

- `docs/component.puml` — компонентная диаграмма системы;
- `docs/sequence.puml` — sequence-диаграмма маскирования текста через `main-module`.

```plantuml
@startuml component
!theme plain
title Компонентная диаграмма ALFA Hack

skinparam componentStyle rectangle
skinparam shadowing false
skinparam defaultFontName "Helvetica"
skinparam defaultFontSize 12
skinparam component {
    BackgroundColor #FFFFFF
    BorderColor #333333
    FontColor #1A1A1A
    ArrowColor #555555
}
skinparam actor {
    BackgroundColor #FFD54F
    BorderColor #B8860B
    FontColor #4A3B00
}
skinparam package {
    BackgroundColor #F5F7FA
    BorderColor #9AA5B1
    FontColor #2C3E50
}
skinparam arrow {
    Color #555555
    FontColor #555555
}

' ===== Внешние акторы =====
actor "Клиент" as Client

' ===== main-module =====
package "main-module" #E8F0FE {
    component "FastAPI app" as MainApp #D2E3FC
    component "MaskingOrchestrator" as Orchestrator #D2E3FC
    component "RestMaskingProvider" as RestProvider #E3EEFF
    component "WebSocketMaskingProvider" as WsProvider #E3EEFF
    component "CorrelationStore" as Store #E3EEFF
    component "Redis" as Redis #FDE9D9
}

' ===== load_balanser =====
component "Nginx Load Balancer" as LB #FCE8E6

' ===== gliner_famous =====
package "gliner_famous" #E6F4EA {
    component "FastAPI (POST /process, WS /ws)" as GlinerApi #C8E6C9
    component "GLiNER NER model" as GlinerModel #DCEDC8
    component "PII type mapper" as PiiMapper #DCEDC8
    component "Famous person check" as FamousCheck #DCEDC8
}

' ===== llm_service =====
package "llm_service" #F3E8FD {
    component "FastAPI (POST /process, WS /ws)" as LlmApi #E1BEE7
    component "ALFA LLM client (SSE)" as LlmClient #EDE7F6
}

' ===== regex-module =====
package "regex-module" #FFF8E1 {
    component "FastAPI (WS /scan)" as RegexApi #FFECB3
    component "Regex scanner" as RegexScan #FFF3CD
}

' ===== training_data =====
package "training_data" #ECEFF1 {
    component "Dataset & training scripts" as Training #CFD8DC
}

' ===== Связи =====
Client --> MainApp : POST /process (payload, payload_id)
Client --> LB : WS /gliner-famous/ws, /llm-service/ws

MainApp --> Orchestrator : mask(text)
Orchestrator --> RestProvider : parallel, timeout
Orchestrator --> WsProvider : parallel, timeout
RestProvider --> LB : POST /gliner-famous/process, /llm-service/process
WsProvider --> LB : WS /gliner-famous/ws, /llm-service/ws
MainApp --> Store : put/get payload_id
Store --> Redis : pd:{payload_id}

LB --> GlinerApi : round-robin
LB --> LlmApi : round-robin

GlinerApi --> GlinerModel : extract_entities_long()
GlinerApi --> PiiMapper : map_to_pii_types()
GlinerApi --> FamousCheck : is_famous()
LlmApi --> LlmClient : /chat/completions (SSE)

RegexApi --> RegexScan : scan(text)

Training ..> GlinerModel : обученная модель
Training ..> FamousCheck : база известных персон

@enduml
```

```plantuml
@startuml sequence
!theme plain
title Sequence: маскирование текста через main-module

skinparam shadowing false
skinparam defaultFontName "Helvetica"
skinparam defaultFontSize 12
skinparam sequence {
    ArrowColor #555555
    MessageAlign center
    LifeLineBorderColor #333333
}
skinparam actor {
    BackgroundColor #FFD54F
    BorderColor #B8860B
    FontColor #4A3B00
}
skinparam participant {
    BackgroundColor #FFFFFF
    BorderColor #333333
    FontColor #1A1A1A
}
skinparam database {
    BackgroundColor #FDE9D9
    BorderColor #B8860B
    FontColor #4A3B00
}

actor "Клиент" as Client
participant "main-module\n(FastAPI)" as Main #D2E3FC
participant "MaskingOrchestrator" as Orch #D2E3FC
participant "RestMaskingProvider" as Rest #E3EEFF
participant "WebSocketMaskingProvider" as Ws #E3EEFF
participant "Nginx LB" as LB #FCE8E6
participant "gliner_famous\nреплика" as Gliner #C8E6C9
participant "llm_service\nреплика" as Llm #E1BEE7
database "Redis" as Redis #FDE9D9

Client -> Main : POST /process\n{payload, payload_id}
activate Main

Main -> Redis : GET pd:{payload_id}
Redis --> Main : null (нет записи)

Main -> Orch : mask(payload)
activate Orch

par Параллельно с таймаутом
    Orch -> Rest : mask(payload)
    activate Rest
    Rest -> LB : POST /gliner-famous/process
    LB -> Gliner : round-robin
    activate Gliner
    Gliner --> Gliner : GLiNER NER + PII map + famous check
    Gliner --> LB : {entities}
    LB --> Rest : {entities}
    Rest --> Orch : result
    deactivate Rest
    deactivate Gliner

    Orch -> Ws : mask(payload)
    activate Ws
    Ws -> LB : WS /llm-service/ws
    LB -> Llm : round-robin
    activate Llm
    Llm -> Llm : LLM (ALFA, SSE) NER
    Llm --> LB : {entities}
    LB --> Ws : result
    Ws --> Orch : result
    deactivate Ws
    deactivate Llm
end

Orch --> Main : результат последнего успешного провайдера
deactivate Orch

Main -> Redis : PUT pd:{payload_id}\n{original, masked}
Main --> Client : {result: masked}
deactivate Main

@enduml
```

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

### 2. Сборка и запуск `llm_service`

Сервис делает то же, что и `gliner_famous` (тот же контракт: `POST /process` и `WS /ws`),
но вместо локальной модели GLiNER использует запрос к LLM провайдера ALFA.
Ориентирован на скорость: один запрос к LLM возвращает все сущности сразу.

Креды провайдера ALFA задаются в `.env` (см. `.env.example`):

```bash
LLM_BASE_URL=https://alfagen.alfabank.ru/continue-dev/
LLM_API_KEY=<ваш ключ>
LLM_MODEL=deepseek-ai/DeepSeek-V4-Flash-0731
```

Соберите образ:

```bash
docker build -t llm_service ./llm_service
```

Запустите реплики на разных портах:

```bash
docker run -d --name llm1 -p 8003:8000 llm_service
docker run -d --name llm2 -p 8004:8000 llm_service
```

Сервис слушает порт `8000` внутри контейнера и отдаёт те же эндпоинты, что и `gliner_famous`:
- `POST /process` — обработка текста (JSON `{"text": "..."}`);
- `WS /ws` — WebSocket-обработка текста.

Проверка:

```bash
curl -X POST http://localhost:8003/process \
  -H "Content-Type: application/json" \
  -d '{"text": "Иван Петров работает в Альфа-Банке"}'
```

> Примечание: `.env` не коммитится в git (добавлен в `.gitignore`). Для локального
> запуска без Docker скопируйте `.env.example` в `.env` и заполните ключ.

### 3. Сборка и запуск `load_balanser`

Соберите образ балансировщика:

```bash
docker build -t load_balanser ./load_balanser
```

Запустите его, передав списки бэкендов через переменные окружения `GLINER_BACKENDS` и `LLM_BACKENDS` (имена хостов через пробел):

```bash
docker run -d --name lb -p 8080:80 \
  -e GLINER_BACKENDS="gliner1:8000 gliner2:8000" \
  -e LLM_BACKENDS="llm1:8000 llm2:8000" \
  --link gliner1 --link gliner2 --link llm1 --link llm2 \
  load_balanser
```

Если `GLINER_BACKENDS` не задан, по умолчанию используется один бэкенд `gliner1:8000`.
Если `LLM_BACKENDS` не задан, по умолчанию используется один бэкенд `llm1:8000`.

Балансировщик слушает порт `80` внутри контейнера и проксирует запросы на реплики:
- `WS /gliner-famous/ws` → `/ws` (WebSocket, round-robin);
- `POST /gliner-famous/process` → `/process`;
- `WS /llm-service/ws` → `/ws` (WebSocket, round-robin);
- `POST /llm-service/process` → `/process`.

### 4. Проверка

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

HTTP-запрос к `llm_service` через балансировщик:

```bash
curl -X POST http://localhost:8080/llm-service/process \
  -H "Content-Type: application/json" \
  -d '{"text": "Иван Петров работает в Альфа-Банке"}'
```

WebSocket-подключение к `llm_service` через балансировщик:

```bash
wscat -c ws://localhost:8080/llm-service/ws
```

> Примечание: для связи контейнеров по именам (`gliner1`, `gliner2`) используйте общую Docker-сеть вместо `--link` (устаревший флаг), например `docker network create alfa-net` и подключите все контейнеры к ней.