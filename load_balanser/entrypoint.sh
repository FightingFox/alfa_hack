#!/bin/sh
set -e

# Список бэкендов через пробел, например:
#   GLINER_BACKENDS="gliner1:8000 gliner2:8000"
# Если переменная не задана или пуста — сервис не включается в конфиг.
GLINER_BACKENDS="${GLINER_BACKENDS:-}"
LLM_BACKENDS="${LLM_BACKENDS:-}"
REGEX_BACKENDS="${REGEX_BACKENDS:-}"
MAIN_BACKENDS="${MAIN_BACKENDS:-}"
ML_BACKENDS="${ML_BACKENDS:-}"

# Генерируем upstream-блок для набора бэкендов. Имена резолвятся через
# resolver в момент запроса, поэтому nginx не падает, если бэкенд недоступен.
# Round-robin распределяет запросы между всеми перечисленными бэкендами.
gen_upstream() {
    name="$1"
    backends="$2"
    [ -z "$backends" ] && return
    echo "    upstream ${name} {"
    for b in $backends; do
        echo "        server ${b};"
    done
    echo "    }"
}

# Генерируем location-блок для проксирования на upstream.
gen_location() {
    path="$1"
    upstream="$2"
    target="$3"
    ws="$4"
    echo "        location ${path} {"
    echo "            proxy_pass http://${upstream}${target};"
    echo "            proxy_http_version 1.1;"
    if [ "$ws" = "ws" ]; then
        echo "            proxy_set_header Upgrade \$http_upgrade;"
        echo "            proxy_set_header Connection \$connection_upgrade;"
        echo "            proxy_read_timeout 3600s;"
        echo "            proxy_send_timeout 3600s;"
    else
        echo "            proxy_read_timeout 300s;"
    fi
    echo "            proxy_set_header Host \$host;"
    echo "            proxy_set_header X-Real-IP \$remote_addr;"
    echo "            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;"
    echo "        }"
}

UPSTREAM_DIRECTIVES=""
LOCATION_DIRECTIVES=""

if [ -n "$GLINER_BACKENDS" ]; then
    UPSTREAM_DIRECTIVES="${UPSTREAM_DIRECTIVES}$(gen_upstream gliner_upstream "$GLINER_BACKENDS")
"
    LOCATION_DIRECTIVES="${LOCATION_DIRECTIVES}$(gen_location /gliner-famous/ws gliner_upstream /ws ws)
"
    LOCATION_DIRECTIVES="${LOCATION_DIRECTIVES}$(gen_location /gliner-famous/process gliner_upstream /process http)
"
fi

if [ -n "$LLM_BACKENDS" ]; then
    UPSTREAM_DIRECTIVES="${UPSTREAM_DIRECTIVES}$(gen_upstream llm_upstream "$LLM_BACKENDS")
"
    LOCATION_DIRECTIVES="${LOCATION_DIRECTIVES}$(gen_location /llm-service/ws llm_upstream /ws ws)
"
    LOCATION_DIRECTIVES="${LOCATION_DIRECTIVES}$(gen_location /llm-service/process llm_upstream /process http)
"
fi

if [ -n "$REGEX_BACKENDS" ]; then
    UPSTREAM_DIRECTIVES="${UPSTREAM_DIRECTIVES}$(gen_upstream regex_upstream "$REGEX_BACKENDS")
"
    LOCATION_DIRECTIVES="${LOCATION_DIRECTIVES}$(gen_location /regex-module/scan regex_upstream /scan ws)
"
fi

if [ -n "$MAIN_BACKENDS" ]; then
    UPSTREAM_DIRECTIVES="${UPSTREAM_DIRECTIVES}$(gen_upstream main_upstream "$MAIN_BACKENDS")
"
    LOCATION_DIRECTIVES="${LOCATION_DIRECTIVES}$(gen_location /main-module/process main_upstream /process http)
"
    LOCATION_DIRECTIVES="${LOCATION_DIRECTIVES}$(gen_location /main-module/health main_upstream /health http)
"
    LOCATION_DIRECTIVES="${LOCATION_DIRECTIVES}$(gen_location /main-module/docs main_upstream /docs http)
"
    LOCATION_DIRECTIVES="${LOCATION_DIRECTIVES}$(gen_location /main-module/openapi.json main_upstream /openapi.json http)
"
    LOCATION_DIRECTIVES="${LOCATION_DIRECTIVES}$(gen_location /main-module/redoc main_upstream /redoc http)
"
fi

if [ -n "$ML_BACKENDS" ]; then
    UPSTREAM_DIRECTIVES="${UPSTREAM_DIRECTIVES}$(gen_upstream ml_upstream "$ML_BACKENDS")
"
    LOCATION_DIRECTIVES="${LOCATION_DIRECTIVES}$(gen_location /ml-for-all-types/ws ml_upstream /ws ws)
"
    LOCATION_DIRECTIVES="${LOCATION_DIRECTIVES}$(gen_location /ml-for-all-types/process ml_upstream /process http)
"
fi

# Подставляем upstream- и location-блоки в шаблон и кладём в рабочий конфиг.
export UPSTREAM_DIRECTIVES LOCATION_DIRECTIVES
envsubst '${UPSTREAM_DIRECTIVES} ${LOCATION_DIRECTIVES}' < /etc/nginx/nginx.conf.template > /etc/nginx/nginx.conf

exec nginx -g "daemon off;"