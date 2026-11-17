
import os
os.environ["TF_USE_LEGACY_KERAS"] = "1"
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"

import argparse
from pathlib import Path

import numpy as np
import faiss
import tf_keras


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--staging-dir",
        required=True
    )

    parser.add_argument(
        "--output-dir",
        required=True
    )

    args = parser.parse_args()

    staging_dir = Path(args.staging_dir).resolve()
    output_dir = Path(args.output_dir).resolve()

    movie_model_path = staging_dir / "movie_tower.keras"
    movie_ids_path = staging_dir / "movie_ids.npy"

    if not movie_model_path.is_file():
        raise FileNotFoundError(movie_model_path)

    if not movie_ids_path.is_file():
        raise FileNotFoundError(movie_ids_path)

    # Never overwrite an existing output folder
    if output_dir.exists():
        raise FileExistsError(
            f"Output already exists: {output_dir}"
        )

    movie_ids = np.load(movie_ids_path, allow_pickle=False)

    if len(movie_ids) == 0:
        raise ValueError("Empty movie vocabulary")

    if len(np.unique(movie_ids)) != len(movie_ids):
        raise ValueError("Duplicate movie IDs")

    movie_tower = tf_keras.models.load_model(
        str(movie_model_path),
        compile=False
    )

    movie_indices = np.arange(
        1,
        len(movie_ids) + 1,
        dtype=np.int32
    )

    embeddings = movie_tower.predict(
        movie_indices,
        batch_size=256,
        verbose=0
    ).astype(np.float32)

    if embeddings.ndim != 2:
        raise ValueError("Expected 2D embeddings")

    if embeddings.shape[0] != len(movie_ids):
        raise ValueError("Embedding count mismatch")

    if not np.isfinite(embeddings).all():
        raise ValueError("Non-finite movie embeddings")

    index = faiss.IndexFlatIP(embeddings.shape[1])

    index.add(
        np.ascontiguousarray(embeddings)
    )

    if index.ntotal != len(movie_ids):
        raise ValueError("FAISS indexing failed")

    # Create only a new, previously unused directory
    output_dir.mkdir(parents=True, exist_ok=False)

    faiss.write_index(
        index,
        str(output_dir / "movie_embeddings.index")
    )

    np.save(
        output_dir / "indexed_movie_ids.npy",
        movie_ids
    )

    # Read index back to verify persisted files
    reloaded = faiss.read_index(
        str(output_dir / "movie_embeddings.index")
    )

    assert reloaded.ntotal == len(movie_ids)
    assert reloaded.d == embeddings.shape[1]

    print("FAISS rebuilding PASSED!")
    print("Indexed movies:", reloaded.ntotal)
    print("Embedding dimension:", reloaded.d)
    print("Output directory:", output_dir)


if __name__ == "__main__":
    main()
