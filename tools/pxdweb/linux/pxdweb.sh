#!/bin/sh
# PXD Web for Linux: .pxd names work in every browser and app on this machine, like .com.
#   pxdweb.sh on | off | status | install
# Only .pxd and .pxd2 go to the PXD root (a systemd-resolved routing domain); every other name keeps your normal DNS.
set -e
HOME_DIR=/opt/pxd-web
UNIT=/etc/systemd/system/pxd-web.service
DROP=/etc/systemd/resolved.conf.d/pxd-web.conf
PORT=5300
HERE=$(cd "$(dirname "$0")" && pwd)
MODE=${1:-status}

need_root() {
  if [ "$(id -u)" != 0 ]; then
    if command -v pkexec >/dev/null 2>&1 && [ -n "$DISPLAY$WAYLAND_DISPLAY" ]; then exec pkexec "$HERE/pxdweb.sh" "$MODE" "$(id -un)"; fi
    exec sudo "$HERE/pxdweb.sh" "$MODE" "$(id -un)"
  fi
}

src_root() {
  if [ -f "$HERE/../names.json" ]; then cd "$HERE/.." && pwd; return; fi
  if [ -f "$HERE/../../../names.json" ]; then cd "$HERE/../../.." && pwd; return; fi
}

test_name() { python3 - "$PORT" <<'PY'
import socket, struct, sys, random
q = random.randint(0, 65535)
pkt = struct.pack(">HHHHHH", q, 0x0100, 1, 0, 0, 0) + b"\x04pxd2\x03pxd\x00" + struct.pack(">HH", 1, 1)
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.settimeout(2)
try:
    s.sendto(pkt, ("127.0.0.1", int(sys.argv[1]))); r = s.recv(512)
    sys.exit(0 if r[:2] == pkt[:2] and r[3] & 15 == 0 and struct.unpack(">H", r[6:8])[0] > 0 else 1)
except Exception:
    sys.exit(1)
PY
}

install_files() {
  SRC=$(src_root)
  [ -n "$SRC" ] || { echo "PXD Web files not found next to this script."; exit 1; }
  [ "$SRC" = "$HOME_DIR" ] && return 0
  mkdir -p "$HOME_DIR/tools/pxd2root" "$HOME_DIR/tools/pxdz" "$HOME_DIR/pxd" "$HOME_DIR/linux"
  cp "$SRC/tools/pxd2root/pxd2root.py" "$HOME_DIR/tools/pxd2root/"
  cp "$SRC/tools/pxdz/pxdsign.py" "$HOME_DIR/tools/pxdz/"
  cp "$SRC/names.json" "$HOME_DIR/"
  [ -f "$SRC/names.json.sig" ] && cp "$SRC/names.json.sig" "$HOME_DIR/" || true
  [ -f "$SRC/pxd/authority.json" ] && cp "$SRC/pxd/authority.json" "$HOME_DIR/pxd/" || true
  cp "$HERE"/* "$HOME_DIR/linux/"
  chmod +x "$HOME_DIR/linux/pxdweb.sh"
}

desktop_icons() {
  U=${2:-${SUDO_USER:-${PKEXEC_UID:+$(getent passwd "$PKEXEC_UID" | cut -d: -f1)}}}
  [ -n "$U" ] || return 0
  UH=$(getent passwd "$U" | cut -d: -f6)
  DESK=$(sudo -u "$U" xdg-user-dir DESKTOP 2>/dev/null || echo "$UH/Desktop")
  mkdir -p "$DESK" "$UH/.local/share/applications"
  for m in on off status; do
    M=$(echo "$m" | tr a-z A-Z)
    for d in "$DESK" "$UH/.local/share/applications"; do
      cat > "$d/pxd-web-$m.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=PXD Web $M
Comment=.pxd names on this computer: $m
Exec=sh -c '"$HOME_DIR/linux/pxdweb.sh" $m; echo; echo Press Enter to close; read x'
Terminal=true
Icon=network-workgroup
Categories=Network;
EOF
      chown "$U" "$d/pxd-web-$m.desktop"; chmod +x "$d/pxd-web-$m.desktop"
      sudo -u "$U" gio set "$d/pxd-web-$m.desktop" metadata::trusted true 2>/dev/null || true
    done
  done
}

case "$MODE" in
  install|on)
    need_root
    command -v python3 >/dev/null || { (apt-get install -y python3 || dnf install -y python3 || pacman -S --noconfirm python) >/dev/null 2>&1; }
    python3 -c "import cryptography" 2>/dev/null || (apt-get install -y python3-cryptography || dnf install -y python3-cryptography || pacman -S --noconfirm python-cryptography || python3 -m pip install --break-system-packages cryptography) >/dev/null 2>&1 || true
    install_files
    [ "$MODE" = install ] && desktop_icons "$@"
    AUTH=""; [ -f "$HOME_DIR/pxd/authority.json" ] && AUTH="--authority $HOME_DIR/pxd/authority.json"
    cat > "$UNIT" <<EOF
[Unit]
Description=PXD Web: the .pxd root on this machine
After=network-online.target
Wants=network-online.target

[Service]
WorkingDirectory=$HOME_DIR
ExecStart=/usr/bin/env python3 $HOME_DIR/tools/pxd2root/pxd2root.py --host 127.0.0.1 --dns-port $PORT --web-port 80 --edge-ip 127.0.0.1 --ns-ip 127.0.0.1 $AUTH
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
    systemctl daemon-reload
    systemctl enable --now pxd-web.service >/dev/null
    systemctl restart pxd-web.service
    mkdir -p "$(dirname "$DROP")"
    printf '[Resolve]\nDNS=127.0.0.1:%s\nDomains=~pxd ~pxd2\n' "$PORT" > "$DROP"
    systemctl restart systemd-resolved 2>/dev/null || echo "systemd-resolved not found: point .pxd at 127.0.0.1:$PORT in your resolver."
    i=0; until test_name || [ $i -ge 20 ]; do sleep 0.5; i=$((i+1)); done
    if test_name; then
      echo "PXD Web is ON. .pxd names now work in every browser on this machine."
      echo "Type the name with a slash the first time, like  bearwallow.pxd/"
    else
      echo "PXD Web started but pxd2.pxd did not answer yet. Run PXD Web STATUS in a minute."
    fi
    ;;
  off)
    need_root
    rm -f "$DROP"
    systemctl disable --now pxd-web.service >/dev/null 2>&1 || true
    rm -f "$UNIT"; systemctl daemon-reload
    systemctl restart systemd-resolved 2>/dev/null || true
    echo "PXD Web is OFF. This machine is back to plain DNS for everything."
    ;;
  status)
    echo "Service:   $(systemctl is-active pxd-web.service 2>/dev/null || echo 'not installed')"
    [ -f "$DROP" ] && echo "Rules:     .pxd .pxd2 -> 127.0.0.1:$PORT" || echo "Rules:     none"
    if test_name; then echo "Test:      pxd2.pxd answers. PXD Web is working."; else echo "Test:      pxd2.pxd does not answer."; fi
    ;;
  *) echo "pxdweb.sh on | off | status | install"; exit 2 ;;
esac
