#!/usr/bin/env bash
set -euo pipefail

REGISTRY_ID="crpjr8em43c2vgubc740"
FOLDER_ID="b1gfcf72vsjpn579igo1"
COMPOSE_FILE="docker-compose.server.yml"

echo "=== 1. Установка yc CLI ==="
if ! command -v yc &>/dev/null; then
  if command -v brew &>/dev/null; then
    brew install yandex-cloud-cli
  else
    curl -sSL https://storage.yandexcloud.net/yandexcloud-yc/install.sh | bash
    export PATH="$HOME/yandex-cloud/bin:$PATH"
  fi
else
  echo "yc уже установлен: $(yc --version)"
fi

echo ""
echo "=== 2. Авторизация в Yandex Cloud ==="
echo "Выполните авторизацию. Если используете OAuth-токен:"
echo "  yc config set token <OAuth-токен>"
echo "Если используете сервисный аккаунт:"
echo "  yc config set service-account-key sa-key.json"
echo ""
echo "Рекомендуется сервисный аккаунт с ролью container-registry.images.puller"
echo "на реестре $REGISTRY_ID"
echo ""
if ! yc config list &>/dev/null || ! yc iam whoami &>/dev/null; then
  echo "!!! Авторизация не настроена. Выполните yc init или настройте профиль вручную."
  echo "    После этого запустите скрипт заново."
  exit 1
fi
yc config set folder-id "$FOLDER_ID"
echo "Авторизация успешна: $(yc iam whoami)"

echo ""
echo "=== 3. Настройка Docker для реестра ==="
yc container registry configure-docker

echo ""
echo "=== 4. Проверка доступа к реестру ==="
if ! docker pull "cr.yandex/$REGISTRY_ID/main-module:latest" &>/dev/null; then
  echo "!!! Не удалось получить образ. Проверьте права сервисного аккаунта"
  echo "    (нужна роль container-registry.images.puller на реестр)."
  exit 1
fi
echo "Доступ к реестру подтверждён."

echo ""
echo "=== 5. Запуск контейнеров ==="
if [ ! -f "$COMPOSE_FILE" ]; then
  echo "!!! Файл $COMPOSE_FILE не найден. Скопируйте его на сервер."
  exit 1
fi
if [ ! -f "llm_service.env" ]; then
  echo "!!! Файл llm_service.env не найден. Скопируйте его на сервер."
  exit 1
fi

docker compose -f "$COMPOSE_FILE" up -d

echo ""
echo "=== Готово ==="
echo "Сервисы запущены:"
docker compose -f "$COMPOSE_FILE" ps