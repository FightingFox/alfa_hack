#!/usr/bin/env bash
set -euo pipefail

REGISTRY_ID="crpjr8em43c2vgubc740"
REGISTRY="cr.yandex/${REGISTRY_ID}"
TAG="${1:-latest}"

declare -A SERVICES=(
  [main-module]="./main-module"
  [regex-module]="./regex-module"
  [llm-service]="./llm_service"
  [gliner-famous]="./gliner_famous"
  [ml-for-all-types]="./ml_for_all_types"
  [load-balancer]="./load_balanser"
)

echo ">>> Authenticating Docker to ${REGISTRY}"
yc container registry configure-docker

for name in "${!SERVICES[@]}"; do
  dir="${SERVICES[$name]}"
  image="${REGISTRY}/${name}:${TAG}"
  echo ">>> Building ${image} from ${dir}"
  docker build -t "${image}" "${dir}"
  echo ">>> Pushing ${image}"
  docker push "${image}"
done

echo ">>> All images pushed successfully"