# ReSpeaker mic check — completed

Date: 2026-05-09

Issue:
- ReSpeaker 2-Mics Pi HAT was detected as `seeed-2mic-voicecard`, but capture failed with `wm8960: No MCLK configured`.

Fix applied:
- Installed corrected `seeed-2mic-voicecard.dtbo` overlay that provides `mclk` to the `wm8960` node.
- Backup created at:
  `/boot/firmware/overlays/seeed-2mic-voicecard.dtbo.bak-20260509-195625`
- Rebooted Raspberry Pi.

Post-reboot result:
- `arecord` captures successfully from `hw:seeed2micvoicec,0`.
- Test file: `/tmp/rako-after-reboot.wav`
- Capture stats: 2 channels, 48000 Hz, 3 seconds, RMS ~7499.76, nonzero samples 287994/288000.
- `sounddevice` sees the device:
  `seeed-2mic-voicecard: ... (hw:3,0), ALSA (2 in, 2 out)`.

Rako audio tests:
- `pytest tests/test_hardware_audio.py tests/test_voice_audio_io.py -q`
- Result: 6 passed.

Notes:
- The mic is working after reboot.
- The current default ALSA device is `default`/`capture`, but direct hardware is available as `hw:seeed2micvoicec,0` and sounddevice device index 1 at the time of testing.
