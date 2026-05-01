"""Wrapper sobre sentence-transformers.

Carga `paraphrase-multilingual-MiniLM-L12-v2` una sola vez en proceso y
expone `embed(texts) -> np.ndarray`. CPU only en Pi 4.
"""
