#!/usr/bin/env bash
# Sortie en cas d'erreur
set -o errexit 

# Installation des dépendances
pip install -r requirements.txt 

# Rassemblement des fichiers statiques
python manage.py collectstatic --no-input

# Application des migrations
python manage.py migrate
