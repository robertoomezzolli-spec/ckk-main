#!/usr/bin/env bash
set -euo pipefail

swap_file=/var/lib/sovereign-experiment.swap
swap_size=4G
fstab_entry="$swap_file none swap sw 0 0"

if swapon --show=NAME --noheadings --raw | grep -Fxq "$swap_file"; then
  exit 0
fi

if [[ -e "$swap_file" ]]; then
  echo "Refusing to overwrite inactive existing swap file: $swap_file" >&2
  exit 1
fi

fallocate -l "$swap_size" "$swap_file"
chmod 0600 "$swap_file"
mkswap "$swap_file" >/dev/null
swapon "$swap_file"

if ! grep -Fqx "$fstab_entry" /etc/fstab; then
  printf '%s\n' "$fstab_entry" >>/etc/fstab
fi
