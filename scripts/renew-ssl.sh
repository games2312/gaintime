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
SSL_DIR="$PROJECT_DIR/nginx/ssl"
CERTBOT_DIR="$SSL_DIR/certbot"

cd "$PROJECT_DIR"

echo "--- Renouvellement des certificats SSL ---"

docker run --rm \
    -v "$CERTBOT_DIR/www:/var/www/certbot:rw" \
    -v "$CERTBOT_DIR/conf:/etc/letsencrypt:rw" \
    certbot/certbot:v3.3.1 renew --quiet

echo "--- Rechargement de nginx ---"
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec nginx nginx -s reload || true

echo "--- Renouvellement terminé ---"
