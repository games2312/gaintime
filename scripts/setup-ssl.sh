#!/usr/bin/env bash
# =============================================================================
# GAINTIME — Configuration SSL (Let's Encrypt)
# =============================================================================
# Usage : sudo ./scripts/setup-ssl.sh gaintime.jo3.org admin@gaintime.com
#
# Prérequis :
#   - Le serveur doit être accessible sur les ports 80 et 443
#   - Le domaine doit pointer vers l'IP du serveur
#   - Docker et docker-compose doivent être installés
# =============================================================================
set -o errexit
set -o nounset
set -o pipefail

DOMAIN="${1:-}"
EMAIL="${2:-}"

if [ -z "$DOMAIN" ] || [ -z "$EMAIL" ]; then
    echo "Usage: $0 <domain> <email>"
    echo "Exemple: $0 gaintime.jo3.org admin@gaintime.com"
    exit 1
fi

SSL_DIR="$(dirname "$0")/../nginx/ssl"
CERTBOT_DIR="$SSL_DIR/certbot"

mkdir -p "$CERTBOT_DIR/www" "$CERTBOT_DIR/conf" "$SSL_DIR/logs"

echo "--- Obtention du certificat SSL pour $DOMAIN ---"

docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm \
    --entrypoint "certbot certonly --webroot -w /var/www/certbot \
    -d $DOMAIN -d www.$DOMAIN \
    --email $EMAIL --agree-tos --non-interactive" \
    nginx

echo "--- Certificat obtenu avec succès ---"
echo "Les certificats sont stockés dans : $CERTBOT_DIR/conf"
echo ""
echo "Déploiement : docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d"
