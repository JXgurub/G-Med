#!/usr/bin/env bash
set -Eeuo pipefail

# Usage:
#   bash scripts/hetzner-bootstrap.sh
# Run as a sudo-capable user on Ubuntu 24.04.

if [[ "$(id -u)" -eq 0 ]]; then
  echo "Please run this script as a regular sudo user, not root." >&2
  exit 1
fi

echo "[1/6] Installing base packages..."
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg lsb-release git ufw fail2ban

echo "[2/6] Installing Docker Engine + Compose plugin..."
if ! command -v docker >/dev/null 2>&1; then
  sudo install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  sudo chmod a+r /etc/apt/keyrings/docker.gpg

  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
    $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
    sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

  sudo apt-get update
  sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi

sudo systemctl enable --now docker
sudo usermod -aG docker "$USER" || true

echo "[3/6] Creating 2GB swap (if absent)..."
if ! sudo swapon --show | grep -q .; then
  sudo fallocate -l 2G /swapfile
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
fi

echo "[4/6] Enabling firewall..."
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable

echo "[5/6] Enabling fail2ban..."
sudo systemctl enable --now fail2ban

echo "[6/6] Bootstrap complete."
echo "IMPORTANT: Log out and log back in once to apply docker group membership."
