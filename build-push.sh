#!/usr/bin/env bash
set -euo pipefail

REGISTRY_ID="crpjr8em43c2vgubc740"
REGISTRY="cr.yandex/${REGISTRY_ID}"
TAG="${1:-latest}"

SERVICE_NAMES=(
  "main-module"
  "regex-module"
  "llm-service"
  "gliner-famous"
  "ml-for-all-types"
  "load-balancer"
)
SERVICE_DIRS=(
  "./main-module"
  "./regex-module"
  "./llm_service"
  "./gliner_famous"
  "./ml_for_all_types"
  "./load_balanser"
)

echo ">>> Authenticating Docker to ${REGISTRY}"
yc container registry configure-docker

# Собираем multi-arch образы (linux/amd64 + linux/arm64) и пушим сразу.
# Сервер работает на amd64, локальная разработка — на arm64 (Apple Silicon).
PLATFORMS="${PLATFORMS:-linux/amd64,linux/arm64}"

for i in "${!SERVICE_NAMES[@]}"; do
  name="${SERVICE_NAMES[$i]}"
  dir="${SERVICE_DIRS[$i]}"
  image="${REGISTRY}/${name}:${TAG}"
  echo ">>> Building ${image} from ${dir} (${PLATFORMS})"
  docker buildx build --platform "${PLATFORMS}" --push -t "${image}" "${dir}"
done

echo ">>> All images pushed successfully"