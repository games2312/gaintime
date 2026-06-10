#!/bin/bash
set -e

echo "--- Application des migrations ---"
python manage.py migrate --no-input

echo "--- Collecte des fichiers statiques ---"
python manage.py collectstatic --no-input --clear 2>/dev/null || true

echo "--- Compilation des traductions ---"
python manage.py compilemessages --ignore=reward 2>/dev/null || true

exec "$@"
