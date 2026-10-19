#!/usr/bin/env bash
# Set up the TwitchNet tracker on an Ubuntu server (tested target: Ubuntu 24.04).
# Run from the repository root after creating .env:   bash deploy/setup_vm.sh
#
# Installs Python dependencies into .venv, seeds the tracked channels, and installs:
#   twitchnet-tracker.service   runs tracker.py, restarts it if it stops (also after reboots)
#   twitchnet-reseed.timer      daily at 20:00 UTC: add top 300 live channels, back up the DB
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
USER_NAME="$(whoami)"
cd "$REPO"

if [ ! -f .env ]; then
    echo "Missing $REPO/.env - create it with TWITCH_CLIENT_ID and TWITCH_CLIENT_SECRET first." >&2
    exit 1
fi
chmod 600 .env

echo "==> Installing system packages"
sudo apt-get update -y
sudo apt-get install -y python3-venv python3-pip git sqlite3

echo "==> Creating virtual environment and installing requirements"
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

echo "==> Checking the code"
.venv/bin/python -m pytest -q

echo "==> Seeding tracked channels (top 300 live right now)"
.venv/bin/python tracker.py --seed --live --limit 300

echo "==> Installing systemd units"
for unit in twitchnet-tracker.service twitchnet-reseed.service twitchnet-reseed.timer; do
    sed -e "s|__USER__|$USER_NAME|g" -e "s|__REPO__|$REPO|g" "deploy/$unit" \
        | sudo tee "/etc/systemd/system/$unit" > /dev/null
done
sudo systemctl daemon-reload
sudo systemctl enable --now twitchnet-tracker.service twitchnet-reseed.timer

echo
echo "==> Done. Status:"
systemctl --no-pager --lines=5 status twitchnet-tracker.service || true
systemctl --no-pager list-timers twitchnet-reseed.timer || true
echo
echo "Follow the log with:  journalctl -u twitchnet-tracker -f"
