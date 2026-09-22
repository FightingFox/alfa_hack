#!/bin/sh
set -e

# Список бэкендов gliner_famous через пробел, например:
#   GLINER_BACKENDS="gliner1:8000 gliner2:8000"
# Если не задан — используем один локальный бэкенд.
BACKENDS="${GLINER_BACKENDS:-gliner1:8000}"

UPSTREAM=""
for b in $BACKENDS; do
    UPSTREAM="${UPSTREAM}    server ${b};
"
done

# Список бэкендов llm_service через пробел, например:
#   LLM_BACKENDS="llm1:8000 llm2:8000"
# Если не задан — используем один локальный бэкенд.
LLM_BACKENDS="${LLM_BACKENDS:-llm1:8000}"

LLM_UPSTREAM=""
for b in $LLM_BACKENDS; do
    LLM_UPSTREAM="${LLM_UPSTREAM}    server ${b};
"
done

# Подставляем upstream-блоки в шаблон и кладём в рабочий конфиг.
export GLINER_UPSTREAM="$UPSTREAM"
export LLM_UPSTREAM="$LLM_UPSTREAM"
envsubst '${GLINER_UPSTREAM} ${LLM_UPSTREAM}' < /etc/nginx/nginx.conf.template > /etc/nginx/nginx.conf

exec nginx -g "daemon off;"