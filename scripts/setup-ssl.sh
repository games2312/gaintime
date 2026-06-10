#!/usr/bin/env bash
# =============================================================================
# GAINTIME — Configuration SSL (Let's Encrypt)
# =============================================================================
# Usage : sudo ./scripts/setup-ssl.sh gaintime.jo3.org admin@gaintime.com
#
# Prérequis :
#   - Le serveur doit être accessible sur les ports 80 et 443
#   - Le domaine doit pointer vers l'IP du serveur
#   - Docker installé
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

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SSL_DIR="$PROJECT_DIR/nginx/ssl"
CERTBOT_DIR="$SSL_DIR/certbot"

mkdir -p "$CERTBOT_DIR/www" "$CERTBOT_DIR/conf" "$SSL_DIR/logs"

echo "--- Obtention du certificat SSL pour $DOMAIN ---"

# On utilise certbot directement via Docker (pas besoin du compose stack)
docker run --rm \
    -v "$CERTBOT_DIR/www:/var/www/certbot:rw" \
    -v "$CERTBOT_DIR/conf:/etc/letsencrypt:rw" \
    -p 80:80 \
    certbot/certbot:v3.3.1 certonly \
    --standalone \
    --non-interactive \
    --agree-tos \
    --email "$EMAIL" \
    -d "$DOMAIN" -d "www.$DOMAIN"

echo "--- Certificat obtenu avec succès ---"
echo "Les certificats sont stockés dans : $CERTBOT_DIR/conf"
echo ""
echo "Déploiement : ./scripts/deploy.sh"
