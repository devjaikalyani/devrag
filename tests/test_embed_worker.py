"""encode_bulk: worker offload for large batches, in-process for small ones,
and graceful fallback when the worker fails."""
import subprocess
from unittest.mock import patch

import numpy as np
import pytest

from devrag.rag.retrieval.embedder import CodeEmbedder


@pytest.fixture(scope="module")
def embedder():
    return CodeEmbedder()


def test_small_batch_stays_in_process(embedder):
    texts = ["def add(a, b): return a + b"] * 4
    with patch("subprocess.run") as run:
        emb = embedder.encode_bulk(texts)
        run.assert_not_called()
    assert emb.shape == (4, embedder.dim)


def test_worker_path_produces_normalized_embeddings(embedder):
    texts = [f"def fn_{i}(x): return x * {i}" for i in range(CodeEmbedder.BULK_WORKER_MIN_TEXTS)]
    emb = embedder.encode_bulk(texts)
    assert emb.shape == (len(texts), embedder.dim)
    assert emb.dtype == np.float32
    norms = np.linalg.norm(emb, axis=1)
    assert np.allclose(norms, 1.0, atol=1e-3)


def test_worker_failure_falls_back_in_process(embedder):
    texts = [f"def fn_{i}(x): return x" for i in range(CodeEmbedder.BULK_WORKER_MIN_TEXTS)]
    fake = subprocess.CompletedProcess(args=[], returncode=1)
    with patch("subprocess.run", return_value=fake):
        emb = embedder.encode_bulk(texts)
    assert emb.shape == (len(texts), embedder.dim)


def test_worker_and_in_process_agree(embedder):
    texts = [f"def fn_{i}(x): return x + {i}" for i in range(CodeEmbedder.BULK_WORKER_MIN_TEXTS)]
    bulk = embedder.encode_bulk(texts)
    direct = embedder.encode(texts, show_progress=False)
    assert np.allclose(bulk, direct, atol=1e-4)
