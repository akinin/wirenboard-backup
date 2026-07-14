#!/bin/sh
set -eu

if [ "$(id -u)" -ne 0 ]; then
  echo "Run as root" >&2
  exit 1
fi

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
TARGET=/opt/wirenboard-backup

if ! command -v mount.nfs >/dev/null 2>&1; then
  export DEBIAN_FRONTEND=noninteractive
  apt-get update
  apt-get install -y --no-install-recommends nfs-common
fi
for tool in python3 mosquitto_pub mosquitto_sub mount systemctl curl; do
  command -v "$tool" >/dev/null 2>&1 || { echo "Required command not found: $tool" >&2; exit 1; }
done
test -x /usr/lib/cgi-bin/download_configs.sh || { echo "Native configuration backup script not found" >&2; exit 1; }
test -x /usr/lib/cgi-bin/download_everything.sh || { echo "Native full backup script not found" >&2; exit 1; }

systemctl disable --now wb-backup.timer 2>/dev/null || true
systemctl stop wb-backup-mqtt.service 2>/dev/null || true

install -d -m 755 "$TARGET/bin" "$TARGET/lib" /etc/wb-backup /var/lib/wb-backup /etc/wb-rules
install -m 755 "$ROOT/src/wb_backup.py" "$TARGET/bin/wb-backup"
install -m 755 "$ROOT/src/wb_backup_mqtt.py" "$TARGET/bin/wb-backup-mqtt"
install -m 755 "$ROOT/src/wb-backup-ctl" "$TARGET/bin/wb-backup-ctl"
install -m 755 "$ROOT/src/write_timers.py" "$TARGET/lib/write-timers.py"
install -m 644 "$ROOT/wb-rules/wb-backup.js" /etc/wb-rules/wb-backup.js

if [ ! -f /etc/wb-backup/config.json ] || ! grep -q 'config_backup' /etc/wb-backup/config.json; then
  install -m 600 "$ROOT/config/default.json" /etc/wb-backup/config.json
fi
python3 -c 'import json; p="/etc/wb-backup/config.json"; c=json.load(open(p)); c.setdefault("config_backup",{}).setdefault("enabled",True); c.setdefault("full_backup",{}).setdefault("enabled",True); c.pop("enabled",None); open(p,"w").write(json.dumps(c,ensure_ascii=False,indent=2)+"\n")'

install -m 644 "$ROOT/systemd/wb-backup@.service" /etc/systemd/system/wb-backup@.service
install -m 644 "$ROOT/systemd/wb-backup-config.timer" /etc/systemd/system/wb-backup-config.timer
install -m 644 "$ROOT/systemd/wb-backup-full.timer" /etc/systemd/system/wb-backup-full.timer
install -m 644 "$ROOT/systemd/wb-backup-mqtt.service" /etc/systemd/system/wb-backup-mqtt.service

rm -f /etc/systemd/system/wb-backup.service /etc/systemd/system/wb-backup.timer
rm -rf /etc/systemd/system/wb-backup.timer.d
rm -f /usr/local/bin/wb-backup /usr/local/bin/wb-backup-mqtt /usr/local/sbin/wb-backup-ctl

ln -sf "$TARGET/bin/wb-backup-ctl" /usr/local/sbin/wb-backup-ctl
systemctl daemon-reload
"$TARGET/bin/wb-backup-ctl" apply
systemctl enable --now wb-backup-mqtt.service
systemctl restart wb-rules 2>/dev/null || true

echo "Installed in $TARGET"
"$TARGET/bin/wb-backup-ctl" status
