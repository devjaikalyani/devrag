"""Static (model2vec) embedding path: correct shapes, unit norms, and no
subprocess worker involvement regardless of batch size."""
from unittest.mock import patch

import numpy as np
import pytest

from devrag.rag.retrieval.embedder import CodeEmbedder

STATIC_MODEL = "static:minishlab/potion-base-8M"


@pytest.fixture(scope="module")
def embedder():
    return CodeEmbedder(model_name=STATIC_MODEL)


def test_static_model_loads_and_reports_dim(embedder):
    assert embedder.is_static
    assert embedder.dim == 256


def test_encode_returns_normalized_float32(embedder):
    emb = embedder.encode(["def add(a, b): return a + b", "class UserSerializer: pass"])
    assert emb.shape == (2, embedder.dim)
    assert emb.dtype == np.float32
    assert np.allclose(np.linalg.norm(emb, axis=1), 1.0, atol=1e-4)


def test_encode_bulk_never_spawns_worker(embedder):
    texts = [f"def fn_{i}(x): return x" for i in range(CodeEmbedder.BULK_WORKER_MIN_TEXTS + 8)]
    with patch("subprocess.run") as run:
        emb = embedder.encode_bulk(texts)
        run.assert_not_called()
    assert emb.shape == (len(texts), embedder.dim)


def test_similar_code_scores_higher_than_unrelated(embedder):
    emb = embedder.encode([
        "def authenticate_user(username, password): return check_password(password)",
        "def login_handler(request): user = authenticate_user(...)",
        "SELECT AVG(temperature) FROM weather GROUP BY city",
    ])
    sim_related = float(emb[0] @ emb[1])
    sim_unrelated = float(emb[0] @ emb[2])
    assert sim_related > sim_unrelated
