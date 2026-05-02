"""Funciones de embedding para el RAG.

`DefaultEmbeddingFunction` usa el modelo ONNX que viene con ChromaDB
(`all-MiniLM-L6-v2`). Funciona offline, sin torch, suficiente para
queries en español aunque sin la calidad de un modelo multilingual
dedicado.

Para producción en la Pi, usar
`paraphrase-multilingual-MiniLM-L12-v2` vía `sentence-transformers`
(ver `_MultilingualEmbeddingFunction` cuando se aprovisione la Pi).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from chromadb.utils.embedding_functions import DefaultEmbeddingFunction as _ChromaDefault


@runtime_checkable
class EmbeddingFunction(Protocol):
    def __call__(self, texts: Sequence[str]) -> list[list[float]]: ...


class DefaultEmbeddingFunction:
    """Wrapper estable sobre la default de ChromaDB.

    ChromaDB carga el modelo ONNX la primera vez que se usa. Subsiguientes
    invocaciones reutilizan la instancia cacheada.
    """

    def __init__(self) -> None:
        self._fn = _ChromaDefault()

    def __call__(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            raise ValueError("cannot embed an empty list")
        # ChromaDB devuelve numpy arrays; los normalizamos a listas de floats.
        result = self._fn(list(texts))
        return [[float(x) for x in vec] for vec in result]
