"""Bulk-embedding worker: runs in its own process so torch can use more
than one torch thread.

The server process keeps OMP/MKL pinned to a single thread because torch,
faiss, and sklearn each bundle an OpenMP runtime, and raising torch's
thread count while they share a process segfaults on Intel Mac. This
worker imports only torch, numpy, and sentence-transformers, where the
extra threads are safe.

Protocol: embed_worker.py <texts_json> <out_npy> <model_name> <threads>
Reads a JSON list of strings, writes float32 L2-normalized embeddings.
"""
import json
import sys


def main() -> None:
    texts_path, out_path, model_name, threads = sys.argv[1:5]

    import torch

    torch.set_num_threads(int(threads))

    import numpy as np
    from sentence_transformers import SentenceTransformer

    with open(texts_path) as f:
        texts = json.load(f)

    model = SentenceTransformer(model_name)
    embeddings = model.encode(
        texts,
        batch_size=32,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=True,
    )
    np.save(out_path, embeddings.astype(np.float32))


if __name__ == "__main__":
    main()
