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

# --- Playback path: DAC -> Output Mixer -> jack 3.5mm (HP) / conector JST (SPK) ---
# El WM8960 arranca con el output mixer cerrado y el Headphone en 0%: el TTS
# reproduce pero NO sale sonido. Sin estas 4 líneas el parlante queda mudo.
amixer -c "$CARD" sset 'Left Output Mixer PCM' on >/dev/null
amixer -c "$CARD" sset 'Right Output Mixer PCM' on >/dev/null
# Volumen al máximo: 'Playback' es el volumen digital del DAC (255 = 0dB;
# menos que eso atenúa TODO aunque los análogos estén arriba).
amixer -c "$CARD" sset 'Playback' 255 >/dev/null
amixer -c "$CARD" sset 'PCM Playback -6dB' off >/dev/null
amixer -c "$CARD" sset 'Headphone' 127 unmute >/dev/null
amixer -c "$CARD" sset 'Speaker' 127 unmute >/dev/null

echo "Configured ReSpeaker WM8960 capture + playback profile for card: $CARD"
echo "Capture device: plughw:${CARD},0 | Playback: mismo device (jack 3.5mm o JST)."
