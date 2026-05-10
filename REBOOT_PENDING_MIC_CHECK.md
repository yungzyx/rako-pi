# Pending after reboot

Reason: ReSpeaker/WM8960 capture stream was active but `MICB` stayed Off in ASoC DAPM, so onboard electret mics likely had no mic bias/power. Installed custom overlay adding `"Mic Jack", "MICB"` routing plus all L/R input routes.

Backups:
- `/boot/firmware/overlays/seeed-2mic-voicecard.dtbo.pre-wm8960-official-20260510-000402`
- `/boot/firmware/overlays/seeed-2mic-voicecard.dtbo.pre-micbias-20260510-001744`

After reboot:

```bash
cd ~/rako-pi
dtoverlay -l
arecord -l
arecord -D hw:wm8960soundcard,0 -f S16_LE -c 2 -r 48000 -d 3 /tmp/rako-after-micbias.wav
python3 - <<'PY'
import wave, struct, math
p='/tmp/rako-after-micbias.wav'
with wave.open(p,'rb') as w:
    b=w.readframes(w.getnframes())
    s=struct.unpack('<'+'h'*(len(b)//2), b) if b else []
    rms=math.sqrt(sum(x*x for x in s)/len(s)) if s else 0
    peak=max((abs(x) for x in s), default=0)
    print('rms', round(rms,2), 'peak', peak, 'nonzero', sum(1 for x in s if x))
PY
```
