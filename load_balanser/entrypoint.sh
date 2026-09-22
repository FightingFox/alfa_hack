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

# Список бэкендов ml_for_all_types через пробел, например:
#   ML_BACKENDS="ml1:8000 ml2:8000"
# Если не задан — используем один локальный бэкенд.
ML_BACKENDS="${ML_BACKENDS:-ml1:8000}"

ML_UPSTREAM=""
for b in $ML_BACKENDS; do
    ML_UPSTREAM="${ML_UPSTREAM}    server ${b};
"
done

# Подставляем upstream-блоки в шаблон и кладём в рабочий конфиг.
export GLINER_UPSTREAM="$UPSTREAM"
export LLM_UPSTREAM="$LLM_UPSTREAM"
export ML_UPSTREAM="$ML_UPSTREAM"
envsubst '${GLINER_UPSTREAM} ${LLM_UPSTREAM} ${ML_UPSTREAM}' < /etc/nginx/nginx.conf.template > /etc/nginx/nginx.conf

exec nginx -g "daemon off;"