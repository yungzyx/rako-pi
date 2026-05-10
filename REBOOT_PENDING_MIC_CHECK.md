# Pending after reboot

Reason: Installed Seeed-named overlay with both known WM8960 MCLK fix and `"Mic Jack", "MICB"` route.

Backup before change:
`/boot/firmware/overlays/seeed-2mic-voicecard.dtbo.before-seeed-micbias-20260510-005959`

Expected:
- ALSA card: `seeed2micvoicec`
- During capture, DAPM `MICB` should be On
- Capture should show nonzero RMS
