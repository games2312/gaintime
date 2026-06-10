#!/bin/sh
set -e

# Créer les répertoires nécessaires s'ils n'existent pas
mkdir -p /var/www/certbot /etc/letsencrypt

# Démarrer nginx
exec "$@"
