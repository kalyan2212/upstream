#!/bin/bash
# =============================================================================
# cloud_init.sh
# Runs ONCE on first VM boot via cloud-init.
# Sets up: Python 3.11, pip, nginx reverse proxy, systemd service.
# =============================================================================
set -euo pipefail
exec > /var/log/cloud_init_upstream.log 2>&1

echo "[cloud-init] Starting bootstrap at $(date)"

# ── System packages ──────────────────────────────────────────────────────────
apt-get update -y
apt-get install -y python3.11 python3.11-venv python3-pip nginx curl

# ── App directory ─────────────────────────────────────────────────────────────
APP_DIR=/opt/upstream/app
VENV_DIR=/opt/upstream/venv

mkdir -p "$APP_DIR"

# ── Python virtual environment ────────────────────────────────────────────────
python3.11 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --upgrade pip

# Pre-install common packages so first deploy is fast
"$VENV_DIR/bin/pip" install streamlit requests

# ── systemd service ───────────────────────────────────────────────────────────
cat > /etc/systemd/system/upstream.service << 'EOF'
[Unit]
Description=Upstream Data Uploader (Streamlit)
After=network.target

[Service]
Type=simple
User=azureuser
WorkingDirectory=/opt/upstream/app
ExecStart=/opt/upstream/venv/bin/streamlit run upstream_streamlit.py \
    --server.port 8501 \
    --server.address 0.0.0.0 \
    --server.headless true \
    --server.enableCORS false \
    --server.enableXsrfProtection false
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable upstream

# ── nginx reverse proxy ───────────────────────────────────────────────────────
rm -f /etc/nginx/sites-enabled/default

cat > /etc/nginx/sites-available/upstream << 'EOF'
server {
    listen 80;
    server_name _;

    # Streamlit requires websocket upgrade
    location / {
        proxy_pass         http://127.0.0.1:8501;
        proxy_http_version 1.1;
        proxy_set_header   Upgrade $http_upgrade;
        proxy_set_header   Connection "upgrade";
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 86400;
    }
}
EOF

ln -sf /etc/nginx/sites-available/upstream /etc/nginx/sites-enabled/upstream
nginx -t
systemctl enable nginx
systemctl restart nginx

# ── Permissions ───────────────────────────────────────────────────────────────
chown -R azureuser:azureuser /opt/upstream

echo "[cloud-init] Bootstrap complete at $(date)"
