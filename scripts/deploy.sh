#!/usr/bin/env bash
# =============================================================================
# GAINTIME — Script de déploiement
# =============================================================================
# Usage :
#   ./scripts/deploy.sh              # déploiement normal
#   ./scripts/deploy.sh --no-cache   # rebuild sans cache
# =============================================================================
set -o errexit
set -o nounset
set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

echo "=================================================="
echo "  GAINTIME — Déploiement"
echo "=================================================="

# 1. Vérifier la présence du fichier .env.prod
if [ ! -f ".env.prod" ]; then
    echo "ERREUR : .env.prod introuvable."
    echo "Crée-le à partir de .env.example :"
    echo "  cp .env.example .env.prod"
    echo "Puis édite-le avec tes vraies valeurs."
    exit 1
fi

# 2. Vérifier que les certificats SSL existent
if [ ! -d "nginx/ssl/certbot/conf/live" ]; then
    echo "ATTENTION : Certificats SSL introuvables."
    echo "Exécute d'abord : sudo ./scripts/setup-ssl.sh <domaine> <email>"
    echo ""
    read -rp "Continuer sans SSL (HTTP uniquement) ? (o/N) " reply
    if [ "$reply" != "o" ] && [ "$reply" != "O" ]; then
        exit 1
    fi
fi

# 3. Pull les dernières images
echo "--- Pull des images ---"
docker compose -f docker-compose.yml -f docker-compose.prod.yml pull

# 4. Build des images
echo "--- Build des images ---"
BUILD_ARGS=""
if [ "${1:-}" = "--no-cache" ]; then
    BUILD_ARGS="--no-cache"
    echo "(sans cache)"
fi
docker compose -f docker-compose.yml -f docker-compose.prod.yml build $BUILD_ARGS

# 5. Appliquer les migrations
echo "--- Migrations ---"
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm web python manage.py migrate --no-input

# 6. Collecter les fichiers statiques
echo "--- Collecte des fichiers statiques ---"
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm web python manage.py collectstatic --no-input --clear

# 7. Redémarrer les services
echo "--- Redémarrage des services ---"
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --remove-orphans

# 8. Nettoyer les anciennes images
echo "--- Nettoyage ---"
docker system prune -f --filter "until=24h"

echo ""
echo "=================================================="
echo "  Déploiement terminé avec succès !"
echo "=================================================="
echo ""
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
