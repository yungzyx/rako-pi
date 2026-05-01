"""Entrada/salida de audio en la Pi.

Abstrae el micrófono USB y el parlante detrás de interfaces que se pueden
mockear en tests. Sobre la Pi usa `sounddevice`/`pyaudio`. En desarrollo,
fakes en memoria.
"""
