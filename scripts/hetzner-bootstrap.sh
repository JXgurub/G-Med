#!/usr/bin/env bash
set -Eeuo pipefail

# Usage:
#   bash scripts/hetzner-bootstrap.sh
# Run as root or a sudo-capable user on Ubuntu 24.04.

if [[ "$(id -u)" -eq 0 ]]; then
  SUDO=""
  TARGET_USER="${SUDO_USER:-}"
  echo "Running as root."
else
  SUDO="sudo"
  TARGET_USER="$USER"
fi

run_cmd() {
  if [[ -n "$SUDO" ]]; then
    $SUDO "$@"
  else
    "$@"
  fi
}

echo "[1/6] Installing base packages..."
run_cmd apt-get update
run_cmd apt-get install -y ca-certificates curl gnupg lsb-release git ufw fail2ban

echo "[2/6] Installing Docker Engine + Compose plugin..."
if ! command -v docker >/dev/null 2>&1; then
  run_cmd install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | run_cmd gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  run_cmd chmod a+r /etc/apt/keyrings/docker.gpg

  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
    $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
    run_cmd tee /etc/apt/sources.list.d/docker.list > /dev/null

  run_cmd apt-get update
  run_cmd apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi

run_cmd systemctl enable --now docker
if [[ -n "$TARGET_USER" && "$TARGET_USER" != "root" ]]; then
  run_cmd usermod -aG docker "$TARGET_USER" || true
fi

echo "[3/6] Creating 2GB swap (if absent)..."
if ! run_cmd swapon --show | grep -q .; then
  run_cmd fallocate -l 2G /swapfile
  run_cmd chmod 600 /swapfile
  run_cmd mkswap /swapfile
  run_cmd swapon /swapfile
  echo '/swapfile none swap sw 0 0' | run_cmd tee -a /etc/fstab >/dev/null
fi

echo "[4/6] Enabling firewall..."
run_cmd ufw allow OpenSSH
run_cmd ufw allow 80/tcp
run_cmd ufw allow 443/tcp
run_cmd ufw --force enable

echo "[5/6] Enabling fail2ban..."
run_cmd systemctl enable --now fail2ban

echo "[6/6] Bootstrap complete."
if [[ -n "$TARGET_USER" && "$TARGET_USER" != "root" ]]; then
  echo "IMPORTANT: Log out and log back in once to apply docker group membership for ${TARGET_USER}."
fi
