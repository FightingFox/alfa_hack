#!/bin/sh
set -e

# Список бэкендов gliner_famous через пробел, например:
#   GLINER_BACKENDS="gliner1:8000 gliner2:8000"
# Если не задан — используем один локальный бэкенд.
BACKENDS="${GLINER_BACKENDS:-gliner1:8000}"

GLINER_BACKEND=""
for b in $BACKENDS; do
    GLINER_BACKEND="$b"
    break
done

# Список бэкендов llm_service через пробел, например:
#   LLM_BACKENDS="llm1:8000 llm2:8000"
# Если не задан — используем один локальный бэкенд.
LLM_BACKENDS="${LLM_BACKENDS:-llm1:8000}"

LLM_BACKEND=""
for b in $LLM_BACKENDS; do
    LLM_BACKEND="$b"
    break
done

# Список бэкендов regex_module через пробел, например:
#   REGEX_BACKENDS="regex1:8000 regex2:8000"
# Если не задан — используем один локальный бэкенд.
REGEX_BACKENDS="${REGEX_BACKENDS:-regex1:8000}"

# Список бэкендов main_module через пробел, например:
#   MAIN_BACKENDS="main1:8000 main2:8000"
# Если не задан — используем один локальный бэкенд.
MAIN_BACKENDS="${MAIN_BACKENDS:-main1:8000}"

# Список бэкендов ml_for_all_types через пробел, например:
#   ML_BACKENDS="ml1:8000 ml2:8000"
# Если не задан — используем один локальный бэкенд.
ML_BACKENDS="${ML_BACKENDS:-ml1:8000}"

# Собираем upstream-блок для regex-бэкендов (round-robin, динамический DNS).
# Каждый бэкенд добавляется как "server host:port resolve;".
UPSTREAM_DIRECTIVES="    upstream regex_upstream {
"
for b in $REGEX_BACKENDS; do
    UPSTREAM_DIRECTIVES="${UPSTREAM_DIRECTIVES}        server ${b} resolve;
"
done
UPSTREAM_DIRECTIVES="${UPSTREAM_DIRECTIVES}    }
"

# Генерируем set-директивы для каждого бэкенда. Имена резолвятся через
# resolver в момент запроса, поэтому nginx не падает, если бэкенд недоступен.
SET_DIRECTIVES=""
SET_DIRECTIVES="${SET_DIRECTIVES}        set \$gliner_backend ${GLINER_BACKEND};
"
SET_DIRECTIVES="${SET_DIRECTIVES}        set \$llm_backend ${LLM_BACKEND};
"
SET_DIRECTIVES="${SET_DIRECTIVES}        set \$main_backend ${MAIN_BACKEND};
"
SET_DIRECTIVES="${SET_DIRECTIVES}        set \$ml_backend ${ML_BACKEND};
"

# Подставляем set-директивы в шаблон и кладём в рабочий конфиг.
export SET_DIRECTIVES UPSTREAM_DIRECTIVES
envsubst '${SET_DIRECTIVES} ${UPSTREAM_DIRECTIVES}' < /etc/nginx/nginx.conf.template > /etc/nginx/nginx.conf

exec nginx -g "daemon off;"