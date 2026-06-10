#!/usr/bin/env bash
# =============================================================================
# Génère des secrets sécurisés pour le déploiement
# =============================================================================
set -o errexit

echo "DJANGO_SECRET_KEY=$(python3 -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())')"
echo ""
echo "Ajoute cette ligne à ton fichier .env ou aux variables d'environnement du serveur."
echo "Ne JAMAIS commiter cette clé dans git."
