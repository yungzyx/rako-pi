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

import logging
import os
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol, runtime_checkable

from chromadb.utils.embedding_functions import DefaultEmbeddingFunction as _ChromaDefault

_log = logging.getLogger(__name__)

# fastembed cachea el modelo en $TMPDIR/fastembed_cache por defecto; en la Pi
# /tmp es tmpfs, así que un reinicio borraría el modelo y `build_embedder`
# degradaría silenciosamente al default inglés (retrieval basura sin error).
# Cache persistente en el home, con override por env var.
_FASTEMBED_CACHE_ENV = "FASTEMBED_CACHE_PATH"
_FASTEMBED_CACHE_DEFAULT = Path.home() / ".cache" / "fastembed"


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


@runtime_checkable
class Embedder(Protocol):
    """Calcula vectores para una lista de textos.

    A diferencia de `EmbeddingFunction` (interfaz de ChromaDB), el indexer y el
    retriever comparten un `Embedder`: si hay uno, ambos calculan los vectores y
    ChromaDB solo almacena/busca; si es `None`, ambos caen a la embedding
    function default de ChromaDB.
    """

    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class FastEmbedEmbedder:  # pragma: no cover - requires fastembed + model at runtime
    """Embedder multilingüe vía fastembed (ONNX, sin torch).

    Usa `paraphrase-multilingual-MiniLM-L12-v2` por defecto (ver
    `Settings.rag_embedding_model`) para queries en español de calidad, sin
    arrastrar `torch`. El modelo se descarga la primera vez y se cachea.
    """

    def __init__(self, model_name: str) -> None:
        from fastembed import TextEmbedding

        cache_dir = os.environ.get(_FASTEMBED_CACHE_ENV) or str(_FASTEMBED_CACHE_DEFAULT)
        self._model = TextEmbedding(model_name=model_name, cache_dir=cache_dir)

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            raise ValueError("cannot embed an empty list")
        return [[float(x) for x in vec] for vec in self._model.embed(list(texts))]


def build_embedder(model_name: str | None) -> Embedder | None:
    """Construye el embedder multilingüe, o `None` para caer al default.

    Nunca levanta: si `model_name` está vacío, o si fastembed/el modelo no
    están disponibles, degrada silenciosamente a la embedding function default
    de ChromaDB (inglés-céntrica pero funcional y offline).
    """
    if not model_name:
        return None
    try:  # pragma: no cover - depende de fastembed y del modelo en runtime
        return FastEmbedEmbedder(model_name)
    except Exception:  # pragma: no cover - fastembed ausente o fallo de carga
        _log.warning(
            "multilingual embedder unavailable (%s); using ChromaDB default",
            model_name,
        )
        return None
