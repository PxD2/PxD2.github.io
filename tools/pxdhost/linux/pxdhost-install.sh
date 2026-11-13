#!/bin/sh
# PXD Host installer for a Raspberry Pi 5 (Raspberry Pi OS 64-bit) or any Debian/Ubuntu box.
#   sh pxdhost-install.sh [host-id]        (the .pxd2 file runs this for you)
# Installs to /opt/pxd-host: a copy of the PXD2 site, the PXD root, and Cloudflare's tunnel client.
# Starts at boot as the pxd-host service. Updating the site copy only happens when you press Update.
set -e
ID=${1:-pi1}
HERE=$(cd "$(dirname "$0")" && pwd)
if [ "$(id -u)" != 0 ]; then
  if command -v pkexec >/dev/null 2>&1 && [ -n "$DISPLAY$WAYLAND_DISPLAY" ]; then exec pkexec sh "$HERE/pxdhost-install.sh" "$ID" "$(id -un)"; fi
  exec sudo sh "$HERE/pxdhost-install.sh" "$ID" "$(id -un)"
fi
USER_NAME=${2:-${SUDO_USER:-}}
echo "== PXD Host '$ID'"
apt-get update -qq && apt-get install -y -qq python3 python3-cryptography git curl >/dev/null
case "$(uname -m)" in aarch64|arm64) A=arm64;; x86_64) A=amd64;; armv7l|armhf) A=arm;; *) echo "unsupported CPU $(uname -m)"; exit 1;; esac
if ! command -v cloudflared >/dev/null 2>&1; then
  echo "== Cloudflare tunnel client ($A)"
  curl -fsSL -o /usr/local/bin/cloudflared "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-$A"
  chmod +x /usr/local/bin/cloudflared
fi
mkdir -p /opt/pxd-host
if [ ! -d /opt/pxd-host/site/.git ]; then
  echo "== site copy"
  git clone -q --depth 1 https://github.com/PxD2/PxD2.github.io /opt/pxd-host/site
fi
cp "$HERE/pxdhost.py" /opt/pxd-host/pxdhost.py
cp "$HERE/pxdhost-install.sh" /opt/pxd-host/
[ -f /etc/pxd-host.json ] || printf '{\n  "id": "%s",\n  "name": "PXD Host %s",\n  "site": "/opt/pxd-host/site",\n  "repo": "PxD2/PxD2.github.io",\n  "port": 8080\n}\n' "$ID" "$ID" > /etc/pxd-host.json
cat > /etc/systemd/system/pxd-host.service <<EOF
[Unit]
Description=PXD Host: .pxd sites and 3D assets from this machine
After=network-online.target
Wants=network-online.target

[Service]
ExecStart=/usr/bin/python3 /opt/pxd-host/pxdhost.py run
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now pxd-host >/dev/null
if [ -n "$USER_NAME" ]; then
  UH=$(getent passwd "$USER_NAME" | cut -d: -f6)
  DESK=$(sudo -u "$USER_NAME" xdg-user-dir DESKTOP 2>/dev/null || echo "$UH/Desktop"); mkdir -p "$DESK"
  for m in status update restart; do
    case $m in status) C="python3 /opt/pxd-host/pxdhost.py status";; update) C="sudo python3 /opt/pxd-host/pxdhost.py update && sudo systemctl restart pxd-host";; restart) C="sudo systemctl restart pxd-host && sleep 8 && python3 /opt/pxd-host/pxdhost.py status";; esac
    M=$(echo $m | tr a-z A-Z)
    printf '[Desktop Entry]\nType=Application\nName=PXD Host %s\nExec=sh -c "%s; echo; echo Press Enter to close; read x"\nTerminal=true\nIcon=network-server\n' "$M" "$C" > "$DESK/pxd-host-$m.desktop"
    chown "$USER_NAME" "$DESK/pxd-host-$m.desktop"; chmod +x "$DESK/pxd-host-$m.desktop"
    sudo -u "$USER_NAME" gio set "$DESK/pxd-host-$m.desktop" metadata::trusted true 2>/dev/null || true
  done
fi
sleep 12
python3 /opt/pxd-host/pxdhost.py status
if [ ! -f /etc/pxd-host.token ]; then
  echo
  echo "To let browsers find this host, give it a GitHub token that can only edit the site repo:"
  echo "  github.com > Settings > Developer settings > Fine-grained tokens > repository PxD2/PxD2.github.io > Contents: Read and write"
  printf "Paste the token now (or press Enter to skip): "
  read T || true
  if [ -n "$T" ]; then umask 077; printf '%s' "$T" > /etc/pxd-host.token; systemctl restart pxd-host; echo "saved; restarting"; fi
fi
echo "== PXD Host '$ID' installed. Desktop: PXD Host STATUS / UPDATE / RESTART"
