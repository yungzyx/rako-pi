# Pending after reboot

Reason: Restored the first custom Seeed/WM8960 overlay (`tmp-seeedsound-fix.dts`) that previously produced real signal after reboot. Need clean boot for device-tree overlay to apply.

Installed overlay backup before change:
`/boot/firmware/overlays/seeed-2mic-voicecard.dtbo.before-known-good-20260510-005041`

After reboot:
- detect ALSA card name
- test capture RMS/peak
- set mixer route and persist ALSA state if working
