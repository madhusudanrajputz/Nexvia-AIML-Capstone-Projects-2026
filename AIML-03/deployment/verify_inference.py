
import os
os.environ["TF_USE_LEGACY_KERAS"] = "1"
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"

import sys
import numpy as np
from pathlib import Path

project = Path(sys.argv[1])
sys.path.insert(0, str(project / "deployment"))

from recommendation_engine import RecommendationEngine

engine = RecommendationEngine(project)

# Known user
known = engine.recommend(
    user_id=100,
    top_k=10,
    candidates=200
)

assert len(known) == 10
assert known["movieId"].is_unique
assert known["ranking_score"].notna().all()
assert np.isfinite(known["ranking_score"]).all()
assert known["recommendation_type"].eq("personalized").all()

seen = engine.seen_by_user.get(100, set())
assert not set(known["movieId"]).intersection(seen)

print("KNOWN USER INFERENCE: PASSED")

# New user: popularity-based cold start
new_user = engine.recommend(
    user_id=None,
    top_k=10
)

assert len(new_user) == 10
assert new_user["movieId"].is_unique
assert new_user["recommendation_type"].eq("cold_start").all()

print("COLD START INFERENCE: PASSED")

# Verify exact retrieval/index alignment
assert engine.index.ntotal == len(engine.indexed_movie_ids)

print("FAISS ALIGNMENT: PASSED")
print("CLEAN-LOAD INFERENCE TEST: PASSED")
