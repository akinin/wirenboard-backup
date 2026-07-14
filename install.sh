#!/bin/sh
set -eu

REPOSITORY="akinin/wirenboard-backup"
BRANCH="${WB_BACKUP_BRANCH:-main}"
URL="https://github.com/${REPOSITORY}/archive/refs/heads/${BRANCH}.tar.gz"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT INT TERM

echo "Downloading Wiren Board Backup..."
curl -fsSL "$URL" | tar -xz -C "$TMP"
"$TMP/wirenboard-backup-${BRANCH}/installer/install-local.sh"
