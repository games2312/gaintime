#!/usr/bin/env bash
# =============================================================================
# GAINTIME — Configuration du firewall (UFW)
# =============================================================================
# Usage : sudo ./scripts/setup-firewall.sh
# =============================================================================
set -o errexit

echo "--- Configuration du firewall ---"

# S'assurer qu'UFW est installé
if ! command -v ufw &>/dev/null; then
    echo "Installation de ufw..."
    apt-get update -qq && apt-get install -y -qq ufw
fi

# Réinitialiser
ufw --force reset

# Politique par défaut : tout bloquer
ufw default deny incoming
ufw default allow outgoing

# SSH (conserver ta connexion)
ufw allow ssh

# HTTP / HTTPS
ufw allow 80/tcp comment "HTTP"
ufw allow 443/tcp comment "HTTPS"

# Optionnel : Daphne en dev (port 8000) — désactivé en prod
# ufw allow 8000/tcp comment "Daphne dev"

# Activer
ufw --force enable

echo "--- Statut du firewall ---"
ufw status verbose

echo ""
echo "Firewall configuré avec succès."
echo "Ports ouverts : 22 (SSH), 80 (HTTP), 443 (HTTPS)"
