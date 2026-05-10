#!/usr/bin/env bash
set -euo pipefail

CARD="${1:-seeed2micvoicec}"

amixer -c "$CARD" sset 'Capture' 45 unmute >/dev/null
amixer -c "$CARD" sset 'ADC PCM' 185 >/dev/null
amixer -c "$CARD" sset 'Left Boost Mixer LINPUT1' on >/dev/null
amixer -c "$CARD" sset 'Right Boost Mixer RINPUT1' on >/dev/null
amixer -c "$CARD" sset 'Left Input Boost Mixer LINPUT1' 2 >/dev/null
amixer -c "$CARD" sset 'Right Input Boost Mixer RINPUT1' 2 >/dev/null
amixer -c "$CARD" sset 'Left Input Mixer Boost' on >/dev/null
amixer -c "$CARD" sset 'Right Input Mixer Boost' on >/dev/null
amixer -c "$CARD" sset 'ALC Function' Stereo >/dev/null
amixer -c "$CARD" sset 'ALC Max Gain' 5 >/dev/null
amixer -c "$CARD" sset 'ALC Target' 5 >/dev/null

echo "Configured ReSpeaker WM8960 capture profile for card: $CARD"
echo "Target: strong voice capture without clipping. Device: plughw:${CARD},0"
