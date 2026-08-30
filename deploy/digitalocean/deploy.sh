#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."

for file in .env.sovereign .env.digitalocean .env.observatory .env.observatory-ingest; do
  if [[ ! -f "$file" ]]; then
    echo "Missing $file" >&2
    exit 1
  fi
  if grep -Eq '(^|=)(replace_me|choose_a_long_random_value)$' "$file"; then
    echo "Unresolved placeholder in $file" >&2
    exit 1
  fi
done

docker compose -f docker-compose.digitalocean.yml config --quiet
docker compose -f docker-compose.digitalocean.yml up -d --build
docker compose -f docker-compose.digitalocean.yml up -d --force-recreate caddy
docker compose -f docker-compose.digitalocean.yml ps
