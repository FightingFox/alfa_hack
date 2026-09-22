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

# Подставляем upstream-блок в шаблон и кладём в рабочий конфиг.
export GLINER_UPSTREAM="$UPSTREAM"
envsubst '${GLINER_UPSTREAM}' < /etc/nginx/nginx.conf.template > /etc/nginx/nginx.conf

exec nginx -g "daemon off;"