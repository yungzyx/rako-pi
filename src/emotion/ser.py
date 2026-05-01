"""Speech Emotion Recognition local.

Carga un modelo Wav2Vec2 cuantizado y devuelve un vector
(valence, arousal, dominance) a partir de un buffer de audio. Diseñado
para latencia sub-segundo en Pi 4.
"""
