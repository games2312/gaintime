#!/usr/bin/env bash
# =============================================================================
# GAINTIME — Service systemd pour auto-démarrage des conteneurs
# =============================================================================
# Usage : sudo ./scripts/setup-systemd.sh
#
# Installe un service systemd qui :
#   - Démarre les conteneurs Docker au boot
#   - Les redémarre automatiquement si le service crash
# =============================================================================
set -o errexit

SERVICE_NAME="gaintime"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE_FILES="-f docker-compose.yml -f docker-compose.prod.yml"

echo "--- Installation du service systemd pour $SERVICE_NAME ---"

cat > "$SERVICE_FILE" << EOF
[Unit]
Description=GainTime — Plateforme de micro-revenus
Requires=docker.service
After=docker.service network-online.target
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$PROJECT_DIR
ExecStart=/usr/bin/docker compose $COMPOSE_FILES up -d --remove-orphans
ExecStop=/usr/bin/docker compose $COMPOSE_FILES down
ExecReload=/usr/bin/docker compose $COMPOSE_FILES restart
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl start "$SERVICE_NAME"

echo ""
echo "Service systemd '$SERVICE_NAME' installé et démarré."
echo ""
echo "Commandes utiles :"
echo "  sudo systemctl status $SERVICE_NAME"
echo "  sudo systemctl restart $SERVICE_NAME"
echo "  sudo journalctl -u $SERVICE_NAME -f"
