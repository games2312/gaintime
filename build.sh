#!/usr/bin/env bash
set -o errexit
set -o nounset
set -o pipefail

echo "--- Installation des dépendances ---"
pip install -r requirements.txt

echo "--- Collecte des fichiers statiques ---"
python manage.py collectstatic --no-input --clear

echo "--- Application des migrations ---"
python manage.py migrate --no-input

echo "--- Compilation des traductions ---"
python manage.py compilemessages --ignore=reward 2>/dev/null || echo "Aucune traduction à compiler"

echo "--- Build terminé avec succès ---"
