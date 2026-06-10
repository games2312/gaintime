#!/usr/bin/env bash
# =============================================================================
# GAINTIME — Renouvellement automatique des certificats SSL
# =============================================================================
# À placer dans une crontab (ex: mensuel) :
#   0 3 1 * * /path/to/scripts/renew-ssl.sh
# =============================================================================
set -o errexit

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

echo "--- Renouvellement des certificats SSL ---"

docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm \
    --entrypoint "certbot renew --webroot -w /var/www/certbot --quiet" \
    nginx

echo "--- Rechargement de nginx ---"
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec nginx nginx -s reload

echo "--- Renouvellement terminé ---"
