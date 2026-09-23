#!/bin/sh
set -e

# Список бэкендов через пробел, например:
#   GLINER_BACKENDS="gliner1:8000 gliner2:8000"
# Если не задан — используем один локальный бэкенд.
GLINER_BACKENDS="${GLINER_BACKENDS:-gliner1:8000}"
LLM_BACKENDS="${LLM_BACKENDS:-llm1:8000}"
REGEX_BACKENDS="${REGEX_BACKENDS:-regex1:8000}"
MAIN_BACKENDS="${MAIN_BACKENDS:-main1:8000}"
ML_BACKENDS="${ML_BACKENDS:-ml1:8000}"

# Генерируем upstream-блоки для каждого набора бэкендов. Имена резолвятся через
# resolver в момент запроса, поэтому nginx не падает, если бэкенд недоступен.
# Round-robin распределяет запросы между всеми перечисленными бэкендами.
gen_upstream() {
    name="$1"
    backends="$2"
    echo "    upstream ${name} {"
    for b in $backends; do
        echo "        server ${b};"
    done
    echo "    }"
}

UPSTREAM_DIRECTIVES=""
UPSTREAM_DIRECTIVES="${UPSTREAM_DIRECTIVES}$(gen_upstream gliner_upstream "$GLINER_BACKENDS")
"
UPSTREAM_DIRECTIVES="${UPSTREAM_DIRECTIVES}$(gen_upstream llm_upstream "$LLM_BACKENDS")
"
UPSTREAM_DIRECTIVES="${UPSTREAM_DIRECTIVES}$(gen_upstream regex_upstream "$REGEX_BACKENDS")
"
UPSTREAM_DIRECTIVES="${UPSTREAM_DIRECTIVES}$(gen_upstream main_upstream "$MAIN_BACKENDS")
"
UPSTREAM_DIRECTIVES="${UPSTREAM_DIRECTIVES}$(gen_upstream ml_upstream "$ML_BACKENDS")
"

# Подставляем upstream-блоки в шаблон и кладём в рабочий конфиг.
export UPSTREAM_DIRECTIVES
envsubst '${UPSTREAM_DIRECTIVES}' < /etc/nginx/nginx.conf.template > /etc/nginx/nginx.conf

exec nginx -g "daemon off;"