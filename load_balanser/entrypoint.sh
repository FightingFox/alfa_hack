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

# Список бэкендов regex_module через пробел, например:
#   REGEX_BACKENDS="regex1:8000 regex2:8000"
# Если не задан — используем один локальный бэкенд.
REGEX_BACKENDS="${REGEX_BACKENDS:-regex1:8000}"

REGEX_UPSTREAM=""
for b in $REGEX_BACKENDS; do
    REGEX_UPSTREAM="${REGEX_UPSTREAM}    server ${b};
"
done

# Список бэкендов main_module через пробел, например:
#   MAIN_BACKENDS="main1:8000 main2:8000"
# Если не задан — используем один локальный бэкенд.
MAIN_BACKENDS="${MAIN_BACKENDS:-main1:8000}"

MAIN_UPSTREAM=""
for b in $MAIN_BACKENDS; do
    MAIN_UPSTREAM="${MAIN_UPSTREAM}    server ${b};
"
done

# Подставляем upstream-блоки в шаблон и кладём в рабочий конфиг.
export GLINER_UPSTREAM="$UPSTREAM"
export LLM_UPSTREAM="$LLM_UPSTREAM"
export REGEX_UPSTREAM="$REGEX_UPSTREAM"
export MAIN_UPSTREAM="$MAIN_UPSTREAM"
envsubst '${GLINER_UPSTREAM} ${LLM_UPSTREAM} ${REGEX_UPSTREAM} ${MAIN_UPSTREAM}' < /etc/nginx/nginx.conf.template > /etc/nginx/nginx.conf

exec nginx -g "daemon off;"