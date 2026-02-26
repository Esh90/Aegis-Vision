"""Load watchlist from face_database directory."""

import json
import numpy as np

from config import Config
from state import surveillance_state


def load_watchlist_from_disk() -> None:
    """Load all saved watchlist entries from face_database folder."""
    if not Config.FACE_DATABASE_DIR.exists():
        print("[Watchlist] No face database found - starting fresh")
        return
    loaded_count = 0
    with surveillance_state.lock:
        for person_dir in Config.FACE_DATABASE_DIR.iterdir():
            if not person_dir.is_dir():
                continue
            person_id = person_dir.name
            embedding_path = person_dir / "embedding.npy"
            metadata_path = person_dir / "metadata.json"
            if not embedding_path.exists() or not metadata_path.exists():
                continue
            try:
                embedding = np.load(str(embedding_path))
                with open(metadata_path, "r") as f:
                    metadata = json.load(f)
                surveillance_state.face_embeddings_db[person_id] = {
                    "embedding": embedding,
                    "metadata": metadata,
                }
                loaded_count += 1
                print(f"[Watchlist] Loaded: {metadata.get('name', 'Unknown')} ({person_id})")
            except Exception as e:
                print(f"[Watchlist] Error loading {person_id}: {e}")
    if loaded_count > 0:
        print(f"[Watchlist] Loaded {loaded_count} person(s) from database")
    else:
        print("[Watchlist] Database empty - add people via /api/watchlist/add")
