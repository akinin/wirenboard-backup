#!/bin/sh
set -eu

if [ "$(id -u)" -ne 0 ]; then
  echo "Run as root" >&2
  exit 1
fi

systemctl disable --now wb-backup-config.timer wb-backup-full.timer wb-backup-mqtt.service 2>/dev/null || true
rm -f /etc/systemd/system/wb-backup@.service /etc/systemd/system/wb-backup-config.timer
rm -f /etc/systemd/system/wb-backup-full.timer /etc/systemd/system/wb-backup-mqtt.service
rm -rf /etc/systemd/system/wb-backup-config.timer.d /etc/systemd/system/wb-backup-full.timer.d
rm -f /etc/wb-rules/wb-backup.js /usr/local/sbin/wb-backup-ctl
rm -rf /opt/wirenboard-backup
systemctl daemon-reload
systemctl restart wb-rules 2>/dev/null || true
echo "Removed. Configuration and state were kept in /etc/wb-backup and /var/lib/wb-backup."
