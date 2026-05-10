# ReSpeaker mic status — working

Date: 2026-05-10

Working overlay:
- `tmp-seeedsound-micbias-fix.dts`
- Installed as `/boot/firmware/overlays/seeed-2mic-voicecard.dtbo`

Important properties:
- ALSA card: `seeed2micvoicec`
- Capture device for Rako scripts: `plughw:seeed2micvoicec,0`
- Overlay includes both:
  - WM8960 `mclk` route
  - `"Mic Jack", "MICB"` route

Verified after reboot:
- `MICB: On` during capture
- Direct capture RMS ~5536, peak ~32250
- Script capture RMS ~7103, peak ~32757

Backups:
- `/boot/firmware/overlays/seeed-2mic-voicecard.dtbo.before-seeed-micbias-20260510-005959`

Notes:
- STT may still fail if audio clips or nobody speaks clearly in the capture window.
- `scripts/button_conversation.py` normalizes PCM16 peak before sending to STT.
