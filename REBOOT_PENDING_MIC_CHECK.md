# Pending after reboot

Reason: Installed minimal ReSpeaker/WM8960 overlay based on the official working overlay, adding only mic-bias route:

`"Mic Jack", "MICB"`

Backups:
- `/boot/firmware/overlays/seeed-2mic-voicecard.dtbo.pre-wm8960-official-20260510-000402`
- `/boot/firmware/overlays/seeed-2mic-voicecard.dtbo.pre-micbias-20260510-001744`
- `/boot/firmware/overlays/seeed-2mic-voicecard.dtbo.pre-minimal-micbias-20260510-003501`

After reboot, verify:

```bash
cd ~/rako-pi
arecord -l
dmesg | grep -Ei 'wm8960|seeed|asoc|parse error' | tail -80
cat /sys/kernel/debug/asoc/wm8960-soundcard/wm8960.1-001a/dapm/MICB
arecord -D hw:wm8960soundcard,0 -f S16_LE -c 2 -r 48000 -d 3 /tmp/rako-after-minimal-micbias.wav
```
