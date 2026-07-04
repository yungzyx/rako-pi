#!/usr/bin/env bash
set -euo pipefail

FIXED_DTBO="/tmp/seeed-2mic-voicecard-fixed.dtbo"
TARGET="/boot/firmware/overlays/seeed-2mic-voicecard.dtbo"
if [[ ! -f "$FIXED_DTBO" ]]; then
  echo "Missing $FIXED_DTBO. Build it first from hardware/overlays/seeed-2mic-voicecard-micbias-fix.dts." >&2
  exit 1
fi
if [[ ! -f "$TARGET" ]]; then
  echo "Missing $TARGET" >&2
  exit 1
fi

backup="${TARGET}.bak-$(date +%Y%m%d-%H%M%S)"
echo "Backing up $TARGET -> $backup"
sudo cp "$TARGET" "$backup"

echo "Installing fixed overlay"
sudo cp "$FIXED_DTBO" "$TARGET"
sudo chmod 0644 "$TARGET"

echo "Reloading Seeed overlay/service"
sudo dtoverlay -r seeed-2mic-voicecard || true
sudo systemctl restart seeed-voicecard.service
sleep 2

echo "Loaded overlays:"
dtoverlay -l || true

echo "Capture devices:"
arecord -l || true

echo "Testing 1s capture from ReSpeaker"
timeout 5 arecord -D hw:seeed2micvoicec,0 -f S16_LE -c 2 -r 48000 -d 1 /tmp/rako-mic-fixed.wav
ls -lh /tmp/rako-mic-fixed.wav
file /tmp/rako-mic-fixed.wav

echo "OK. Backup saved at: $backup"
