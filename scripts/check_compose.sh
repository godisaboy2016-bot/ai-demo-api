#!/usr/bin/env bash
# Validate docker-compose.yml syntax and variable interpolation.
set -euo pipefail

cd "$(dirname "$0")/.."

# api 服务的 JWT_SECRET_KEY 为 compose 必填项（:?）。
# 校验语法时若环境未配置，则使用占位值；运行时请通过 .env 或环境变量提供真实值。
export JWT_SECRET_KEY="${JWT_SECRET_KEY:-validation-only-placeholder-32bytes}"

docker compose config --quiet
echo "docker-compose.yml is valid"
